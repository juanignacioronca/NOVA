"""Presencia: detectar quién se acerca y por qué (jala sus pendientes de la
memoria). Hace real el ejemplo del Prompt 4/8: *"se acerca [nombre]; probablemente
por [tarea pendiente]"* → detecta → embedding → match → memoria → aviso proactivo.
"""

from __future__ import annotations

from typing import List, Optional

from ..core.world_state import WorldState
from ..memory.store import MemoryStore
from .faces import FaceRecognizer


async def pendientes_de(store: MemoryStore, nombre: str) -> List[str]:
    """Tareas pendientes ligadas a la persona en el grafo de memoria."""
    nid = store.node_id("persona", nombre)
    return [n.nombre for n in await store.vecinos(nid) if n.tipo == "tarea"]


def aviso_presencia(nombre: str, pendientes: List[str]) -> str:
    base = f"Se acerca {nombre}"
    if pendientes:
        return f"{base}; probablemente por: {', '.join(pendientes)}."
    return f"{base}."


async def detectar_presencia(
    store: MemoryStore,
    faces: FaceRecognizer,
    frame,
    world: WorldState,
    umbral: Optional[float] = None,
) -> Optional[dict]:
    """Matchea una cara → si es conocida, deja un evento de presencia en el
    WorldState (que el scheduler proactivo anuncia). None si es desconocido."""
    nombre, conf = await faces.match(frame, umbral)
    if nombre == "desconocido":
        return None
    pend = await pendientes_de(store, nombre)
    aviso = aviso_presencia(nombre, pend)
    await world.append_event(
        {"fuente": "sentinela", "tipo": "presencia", "nombre": nombre, "conf": conf,
         "pendientes": pend, "detalle": aviso}
    )
    return {"nombre": nombre, "conf": conf, "pendientes": pend, "aviso": aviso}
