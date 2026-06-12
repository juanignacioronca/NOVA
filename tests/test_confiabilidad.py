"""Regresiones de confiabilidad: el caso "hola → alucinación".

Antes: cada turno (incluso "hola") se guardaba como nodo "hecho", el recall sin
umbral devolvía ruido, y ese ruido + un system prompt anti-saludo + temperatura
default hacían que el modelo 3B local inventara cualquier cosa. Estos tests
fijan el comportamiento correcto: charla trivial = respuesta instantánea, sin
modelo, sin recall y sin ensuciar la memoria.
"""

from __future__ import annotations

from nova.core import comprension
from nova.core.comprension import clasificar_rapido, es_smalltalk
from nova.core.conductor import Conductor
from nova.core.empresa import Empresa
from nova.core.message_bus import MessageBus
from nova.core.registry import Registry
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.memory.store import MemoryStore, cosine
from nova.tools import register_default_tools
from nova.tools.executor import ToolExecutor


# --- clasificación determinística (sin modelo) ---
def test_es_smalltalk_detecta_saludos():
    assert es_smalltalk("hola")
    assert es_smalltalk("Hola NOVA!")
    assert es_smalltalk("¿cómo estás?")
    assert es_smalltalk("muchas gracias")
    assert es_smalltalk("buenas noches")
    assert es_smalltalk("dale, joya")


def test_es_smalltalk_no_se_come_pedidos():
    assert not es_smalltalk("hola, organizame un viaje a bariloche")
    assert not es_smalltalk("qué hora es")
    assert not es_smalltalk("receta de ñoquis")
    assert not es_smalltalk("recordame comprar pan")


async def test_clasificar_rapido_saludo_y_tools():
    saludo = clasificar_rapido("hola")
    assert saludo is not None
    assert saludo.intencion == "charla"
    assert saludo.complejidad == "simple"
    assert saludo.fuente == "determinista"

    hora = clasificar_rapido("¿qué hora es?")
    assert hora is not None and hora.intencion == "hora"

    # Lo complejo o ambiguo NO se clasifica por reglas: decide el modelo/heurística.
    assert clasificar_rapido("organizame un viaje a bariloche") is None
    assert clasificar_rapido("organizá el viaje y recordame comprar pasajes") is None


async def test_comprender_saludo_no_llama_al_modelo():
    intent = await comprension.comprender("hola")
    assert intent.fuente == "determinista"  # ni modelo ni stub
    assert intent.intencion == "charla"
    assert not intent.necesita_aclaracion()


# --- el Conductor: "hola" responde al instante y limpio ---
async def test_hola_responde_saludo_sin_alucinar(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    final = await conductor.attend("hola")
    run = conductor.last_run

    assert run["intent"] == "charla"
    assert run["route"] == "local"
    assert run["memoria"] == []                  # sin recall para un saludo
    assert not final.startswith("[stub")         # respuesta real, sin modelo
    assert any(s in final for s in ("Hola", "Buenas", "estoy"))


async def test_que_hora_es_usa_la_tool(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    final = await conductor.attend("¿qué hora es?")
    assert "Son las" in final                    # tool `hora`, no una alucinación
    assert conductor.last_run["intent"] == "hora"
    assert conductor.last_run["route"] == "local"


async def test_saludos_no_ensucian_la_memoria(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    await conductor.attend("hola")
    await conductor.attend("gracias")
    await conductor.attend("chau")
    assert await conductor.memory.all_nodos() == []   # antes: 3 nodos "hecho" basura


# --- recall con umbral de relevancia ---
async def test_recall_sin_solapamiento_devuelve_vacio(tmp_path):
    store = MemoryStore(path=str(tmp_path / "m.db"))
    await store.add_nodo("hecho", "reunión contador", texto="reunión con el contador a las 15")
    assert await store.buscar_semantico("hola", k=5) == []


async def test_min_score_filtra_matches_debiles(tmp_path):
    store = MemoryStore(path=str(tmp_path / "m.db"))
    await store.add_nodo("hecho", "reunión contador", texto="reunión con el contador hoy a las 15")
    # Comparte solo un token débil ("hoy") → con umbral alto no vuelve.
    assert await store.buscar_semantico("hoy hola", k=5, min_score=0.9) == []
    debil = await store.buscar_semantico("hoy hola", k=5, min_score=0.05)
    assert debil  # con el piso del stub sí aparece (el umbral es el que decide)


def test_cosine_no_compara_espacios_distintos():
    # stub (256d) vs nomic (768d): truncar daba similitudes basura; ahora 0.
    assert cosine([1.0] * 256, [1.0] * 768) == 0.0


# --- empresa: el área declarada por el planificador se respeta ---
def _empresa(tmp_path) -> Empresa:
    bus, world, registro = MessageBus(), WorldState(), Registro(tmp_path)
    reg = Registry()
    register_default_tools(reg)
    tools = ToolExecutor(reg, world, registro)
    return Empresa(bus, world, registro, tools, topes={})


def test_resolver_area_respeta_lo_declarado(tmp_path):
    emp = _empresa(tmp_path)
    # El modelo declaró el id exacto → se respeta aunque el objetivo hable de otra cosa.
    assert emp._resolver_area("fitness", "armar rutina", "organizá mi viaje y mi rutina") == "fitness"
    # Sin declaración válida → temas de la descripción (no el objetivo entero).
    assert emp._resolver_area("", "comparar acciones y etf", "plan integral") == "inversiones"
    # Nada matchea → multifacético (fallback), queda para auditoría.
    assert emp._resolver_area("", "algo rarísimo", "tema sin equipo") == "multifacetico"


def test_planificador_parsea_objeto_con_subtareas(tmp_path):
    emp = _empresa(tmp_path)
    salida = (
        '{"subtareas": [{"descripcion": "Rutina de fuerza", "area": "fitness", "deps": [],'
        ' "requiere_finanzas": false, "requiere_estrategia": true},'
        ' {"descripcion": "Presupuesto del gimnasio", "area": "fitness", "deps": [1],'
        ' "requiere_finanzas": true, "requiere_estrategia": false}]}'
    )
    subs = emp._parse_subtareas(salida, "ponete en forma")
    assert [s.area for s in subs] == ["fitness", "fitness"]
    assert subs[1].deps == ["t1"]
    assert subs[1].requiere_finanzas is True
