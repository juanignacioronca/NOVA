"""Memoria de largo plazo (offline, embeddings stub deterministas): store
semántico + grafo, extractor + Obsidian, recall en el Conductor, y permisos de
la tool de memoria.
"""

from __future__ import annotations

import pathlib

import pytest

from nova.core.conductor import Conductor
from nova.core.registry import Registry
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.memory import Extractor, MemoryStore, ObsidianVault
from nova.tools import register_default_tools
from nova.tools.base import PermisoDenegado
from nova.tools.executor import ToolExecutor


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(path=str(tmp_path / "m.db"))


# --- store: nodos/aristas, semántico, multi-hop ---
async def test_add_y_busqueda_semantica(tmp_path):
    store = _store(tmp_path)
    await store.add_nodo("preferencia", "dificultad media", texto="prefiero dificultad media en trekkings")
    await store.add_nodo("hecho", "comí pizza", texto="hoy comí una pizza enorme")

    hits = await store.buscar_semantico("qué dificultad me conviene para un trekking", k=3)
    assert hits, "no recuperó nada"
    assert hits[0][0].nombre == "dificultad media"   # lo relevante primero


async def test_multi_hop_recorre_relaciones(tmp_path):
    store = _store(tmp_path)
    a = await store.add_nodo("persona", "Papá")
    b = await store.add_nodo("tarea", "lista del Papá")
    c = await store.add_nodo("lugar", "Supermercado")
    await store.add_arista(b, a, "de")
    await store.add_arista(b, c, "en")

    vecinos = await store.vecinos(a)
    assert any(n.nombre == "lista del Papá" for n in vecinos)
    # A 2 saltos desde Papá se llega al Supermercado (Papá→lista→supermercado).
    alcanzables = {n.nombre for n in await store.multi_hop(a, profundidad=2)}
    assert "Supermercado" in alcanzables


# --- extractor + Obsidian ---
async def test_extractor_genera_grafo_y_notas(tmp_path):
    store = _store(tmp_path)
    vault = ObsidianVault(tmp_path / "vault")
    ext = Extractor(store, vault)

    await ext.extraer("la lista del papá: comprar pan y leche")

    papa = store.node_id("persona", "Papá")
    lista = store.node_id("tarea", "lista del Papá")
    assert await store.get_nodo(papa) is not None
    assert any(n.nombre == "Papá" for n in await store.vecinos(lista))  # tarea ligada a Papá

    nota = pathlib.Path(tmp_path / "vault" / "lista-del-papa.md")
    assert nota.exists()
    assert "[[Papá]]" in nota.read_text(encoding="utf-8")  # wikilink espeja el grafo


async def test_preferencia_se_recupera_despues(tmp_path):
    store = _store(tmp_path)
    ext = Extractor(store, None)
    await ext.extraer("prefiero dificultad media para los trekkings")

    hits = await store.buscar_semantico("armá un plan de trekking al cerro", k=3)
    nombres = " ".join(n.nombre for n, _ in hits)
    assert "dificultad" in nombres  # la preferencia aparece en un plan posterior


# --- tool de memoria: permisos ---
class _Agent:
    def __init__(self, name):
        self.name = name
        self.group = "local"


async def test_tool_memoria_respeta_permisos(tmp_path):
    store = _store(tmp_path)
    await store.add_nodo("hecho", "dato guardado", texto="un dato guardado importante")
    reg = Registry()
    register_default_tools(reg)
    config = {
        "allowlist": ["buscar_memoria"],
        "permisos": {"memoria_contexto": ["buscar_memoria"], "sin_permiso": []},
    }
    ex = ToolExecutor(reg, WorldState(), Registro(tmp_path), config=config, memory=store)

    out = await ex.invoke(_Agent("memoria_contexto"), "buscar_memoria", {"consulta": "dato"})
    assert out.ok
    with pytest.raises(PermisoDenegado):
        await ex.invoke(_Agent("sin_permiso"), "buscar_memoria", {"consulta": "dato"})


# --- integración con el Conductor: recall entre turnos ---
async def test_conductor_recuerda_entre_turnos(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    await conductor.attend("prefiero dificultad media para los trekkings")
    await conductor.attend("armá un plan de trekking al cerro el sábado con mi hermano")
    assert any("dificultad" in m for m in conductor.last_run["memoria"])
