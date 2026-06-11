"""Reconocimiento de personas (offline, embedders stub deterministas): enrolar,
match sobre/bajo umbral, borrar, presencia → aviso proactivo, y privacidad
(los biométricos no se escriben en las notas Obsidian).
"""

from __future__ import annotations

import pathlib

from nova.core.proactivo import ProactiveScheduler
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.memory.obsidian import ObsidianVault
from nova.memory.store import MemoryStore
from nova.perception.config import ProactiveConfig
from nova.recognition.faces import FaceRecognizer
from nova.recognition.presencia import detectar_presencia
from nova.recognition.voices import VoiceRecognizer


def _store(tmp_path) -> MemoryStore:
    return MemoryStore(path=str(tmp_path / "m.db"))


# --- cara: enrolar + match + umbral + borrar ---
async def test_enrolar_y_match_cara(tmp_path):
    store = _store(tmp_path)
    faces = FaceRecognizer(store)
    await faces.enrolar("Juan", [b"foto-1", b"foto-2", b"foto-3"])

    # El vector quedó en el nodo de la persona.
    nodo = await store.get_nodo(store.node_id("persona", "Juan"))
    assert nodo is not None and "face_vec" in nodo.props

    # Match con una muestra enrolada → Juan, sobre el umbral.
    nombre, conf = await faces.match(b"foto-1")
    assert nombre == "Juan" and conf >= 0.45

    # Cara desconocida → 'desconocido'.
    desco, _ = await faces.match(b"otra-persona-distinta")
    assert desco == "desconocido"


async def test_borrar_biometricos(tmp_path):
    store = _store(tmp_path)
    faces = FaceRecognizer(store)
    await faces.enrolar("Ana", [b"a1", b"a2"])
    await faces.borrar("Ana")
    nodo = await store.get_nodo(store.node_id("persona", "Ana"))
    assert not nodo.props.get("face_vec")  # ya no hay biométrico
    nombre, _ = await faces.match(b"a1")
    assert nombre == "desconocido"


# --- voz ---
async def test_enrolar_y_match_voz(tmp_path):
    store = _store(tmp_path)
    voces = VoiceRecognizer(store)
    await voces.enrolar("Lu", [b"voz-1", b"voz-2"])
    nombre, conf = await voces.match(b"voz-1")
    assert nombre == "Lu" and conf >= 0.40
    # cara y voz conviven en el mismo nodo (no se pisan).
    faces = FaceRecognizer(store)
    await faces.enrolar("Lu", [b"cara-1", b"cara-2"])
    nodo = await store.get_nodo(store.node_id("persona", "Lu"))
    assert "voice_vec" in nodo.props and "face_vec" in nodo.props


# --- presencia → aviso proactivo ("se acerca X + pendientes") ---
async def test_presencia_dispara_aviso(tmp_path):
    store = _store(tmp_path)
    world = WorldState()
    faces = FaceRecognizer(store)
    await faces.enrolar("Papá", [b"p1", b"p2"])
    tarea = await store.add_nodo("tarea", "la lista del súper")
    await store.add_arista(tarea, store.node_id("persona", "Papá"), "de")

    res = await detectar_presencia(store, faces, b"p1", world)
    assert res and res["nombre"] == "Papá" and res["pendientes"]

    salidas = []

    class _Out:
        async def say(self, t, proactivo=False):
            salidas.append(t)

    sched = ProactiveScheduler(world, _Out(), ProactiveConfig(), clock=lambda: 0.0)
    await sched.tick()
    assert any("Papá" in s for s in salidas)


# --- privacidad: los biométricos no van a las notas Obsidian ---
async def test_biometricos_no_se_escriben_en_obsidian(tmp_path):
    store = _store(tmp_path)
    vault = ObsidianVault(tmp_path / "vault")
    faces = FaceRecognizer(store)
    await faces.enrolar("Seba", [b"s1", b"s2"])
    await vault.escribir(store, store.node_id("persona", "Seba"))
    nota = pathlib.Path(tmp_path / "vault" / "seba.md").read_text(encoding="utf-8")
    assert "face_vec" not in nota
