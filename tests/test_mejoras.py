"""Ajuste fino post-roadmap (offline): lista de compras, avisos proactivos del
calendario con "qué llevar", especialistas por área (sub-agentes), y contexto
por persona al reconocer presencia.
"""

from __future__ import annotations

import datetime

from nova.core.conductor import Conductor
from nova.core.empresa import Empresa
from nova.core.message_bus import MessageBus
from nova.core.proactivo import ProactiveScheduler
from nova.core.registry import Registry
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.memory.store import MemoryStore
from nova.perception.config import ProactiveConfig, load_perception_config
from nova.recognition.faces import FaceRecognizer
from nova.recognition.presencia import contexto_de, detectar_presencia
from nova.tools import calendario, compras, register_default_tools
from nova.tools.executor import ToolExecutor


# --- lista de compras (estilo Alexa): agregar → ver → quitar, por el Conductor ---
async def test_lista_de_compras_ciclo_completo(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))

    r = await conductor.attend("agregá pan a la lista de compras")
    assert "pan" in r.lower()
    assert conductor.last_run["complexity"] == "simple"  # corre local

    r = await conductor.attend("¿qué hay en la lista de compras?")
    assert "pan" in r.lower()

    r = await conductor.attend("sacá el pan de la lista de compras")
    assert "saqué" in r.lower() or "pan" in r.lower()
    r = await conductor.attend("¿qué hay en la lista de compras?")
    assert "vacía" in r.lower()


def test_parsear_pedido_de_compras():
    assert compras.parsear_pedido("agregá leche a la lista de compras") == {"accion": "agregar", "item": "leche"}
    assert compras.parsear_pedido("sacá la leche de la lista del super") == {"accion": "quitar", "item": "leche"}
    assert compras.parsear_pedido("qué tengo que comprar")["accion"] == "ver"
    assert compras.parsear_pedido("contame un chiste") is None


# --- calendario: parseo de `cuando`, sugerencias de qué llevar, ventana próxima ---
def test_parse_cuando_y_sugerencias():
    now = datetime.datetime(2026, 6, 12, 15, 0).timestamp()
    ts = calendario.parse_cuando("2026-06-12 17:00", now=now)
    assert ts is not None and datetime.datetime.fromtimestamp(ts).hour == 17
    ts = calendario.parse_cuando("hoy a las 16:30", now=now)
    assert ts is not None and ts - now == 1.5 * 3600
    ts = calendario.parse_cuando("mañana 9:00", now=now)
    assert ts is not None and ts > now + 12 * 3600
    assert calendario.parse_cuando("cuando pueda", now=now) is None

    assert "protector solar" in calendario.sugerir_llevar("Paseo a la playa")
    assert "raqueta" in calendario.sugerir_llevar("Partido de tenis")
    assert calendario.sugerir_llevar("Reunión de trabajo") == []


async def test_agendar_guarda_llevar_y_proximos_filtra(tmp_path):
    world, registro = WorldState(), Registro(tmp_path)
    reg = Registry()
    register_default_tools(reg)
    tools = ToolExecutor(reg, world, registro)

    class _Agente:
        name, model_key = "conductor", "conductor_simple"

    now = datetime.datetime(2026, 6, 12, 15, 0).timestamp()
    out = await tools.invoke(_Agente(), "agendar_evento",
                             {"titulo": "Tenis con Seba", "cuando": "2026-06-12 16:00"})
    assert "raqueta" in out.content  # sugirió qué llevar por la actividad
    await tools.invoke(_Agente(), "agendar_evento",
                       {"titulo": "Dentista", "cuando": "2026-06-20 10:00"})

    prox = calendario.proximos(horizonte_horas=2.0, now=now)
    assert [e["titulo"] for e in prox] == ["Tenis con Seba"]  # el lejano queda fuera
    assert "raqueta" in prox[0]["llevar"]


async def test_proactivo_avisa_evento_con_llevar(tmp_path):
    world = WorldState()
    reg = Registry()
    register_default_tools(reg)
    tools = ToolExecutor(reg, world, Registro(tmp_path))

    class _Agente:
        name, model_key = "conductor", "conductor_simple"

    now = datetime.datetime(2026, 6, 12, 15, 0).timestamp()
    await tools.invoke(_Agente(), "agendar_evento",
                       {"titulo": "Paseo a la playa", "cuando": "2026-06-12 16:00"})

    salidas = []

    class _Out:
        async def say(self, t, proactivo=False):
            salidas.append(t)

    sched = ProactiveScheduler(world, _Out(), ProactiveConfig(), clock=lambda: now)
    await sched.tick()
    assert any("playa" in s.lower() and "protector solar" in s.lower() for s in salidas)
    n = len(salidas)
    await sched.tick()  # no repite el mismo evento
    assert len(salidas) == n


def test_config_proactiva_carga_horizonte():
    cfg = load_perception_config()
    assert cfg.proactive.event_horizon_hours > 0


# --- empresa: las áreas tienen especialistas y el líder los consulta ---
async def test_lider_consulta_a_sus_especialistas(tmp_path):
    bus, world, registro = MessageBus(), WorldState(), Registro(tmp_path)
    reg = Registry()
    register_default_tools(reg)
    emp = Empresa(bus, world, registro, ToolExecutor(reg, world, registro))

    # El roster declara los especialistas pedidos (research/riesgo/operador, etc.).
    for name in ("inversiones_research", "inversiones_riesgo", "inversiones_operador",
                 "fitness_nutricionista", "fitness_coach",
                 "ecommerce_marketing", "ecommerce_operaciones"):
        assert name in emp.agents, f"falta el especialista {name}"

    # El coordinador hace que el líder consulte primero a su propio equipo.
    res = await emp.ejecutar("analizá si conviene invertir en acciones tech con $500")
    consultados = " ".join(res.data["topes"])
    assert "inversiones_research" in consultados or "inversiones_riesgo" in consultados


# --- presencia: al reconocer a alguien, su contexto queda disponible ---
async def test_presencia_carga_contexto_por_persona(tmp_path):
    store = MemoryStore(path=str(tmp_path / "m.db"))
    world = WorldState()
    faces = FaceRecognizer(store)
    await faces.enrolar("Juan", [b"j1", b"j2"])
    pid = store.node_id("persona", "Juan")
    tarea = await store.add_nodo("tarea", "llamar al banco")
    evento = await store.add_nodo("evento", "tenis el sábado")
    pref = await store.add_nodo("preferencia", "plan nutricional sin harinas")
    for nid in (tarea, evento, pref):
        await store.add_arista(nid, pid, "de")

    ctx = await contexto_de(store, "Juan")
    assert ctx["pendientes"] == ["llamar al banco"]
    assert ctx["eventos"] == ["tenis el sábado"]
    assert ctx["preferencias"] == ["plan nutricional sin harinas"]

    res = await detectar_presencia(store, faces, b"j1", world)
    assert res and res["contexto"]["eventos"]
    presente = await world.get("persona_presente")
    assert presente and presente["nombre"] == "Juan"
    assert "plan nutricional sin harinas" in presente["contexto"]["preferencias"]


async def test_conductor_usa_contexto_del_presente(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    await conductor.world.set("persona_presente", {
        "nombre": "Juan", "conf": 0.9,
        "contexto": {"pendientes": [], "eventos": ["tenis el sábado"],
                     "preferencias": ["plan nutricional sin harinas"]},
    })
    await conductor.attend("contame algo")
    assert "presente: Juan" in conductor.last_run["memoria"]
    assert "tenis el sábado" in conductor.last_run["memoria"]
