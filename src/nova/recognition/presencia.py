"""Presencia: detectar quién se acerca y por qué (jala sus pendientes de la
memoria). Hace real el ejemplo del Prompt 4/8: *"se acerca [nombre]; probablemente
por [tarea pendiente]"* → detecta → embedding → match → memoria → aviso proactivo.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from ..core.world_state import WorldState
from ..memory.store import MemoryStore
from .faces import FaceRecognizer


async def contexto_de(store: MemoryStore, nombre: str) -> Dict[str, List[str]]:
    """Todo lo de la persona en el grafo de memoria, por tipo: sus pendientes,
    eventos y preferencias (ej. su plan nutricional). Es lo que NOVA tiene
    'disponible' cuando reconoce a alguien."""
    nid = store.node_id("persona", nombre)
    ctx: Dict[str, List[str]] = {"pendientes": [], "eventos": [], "preferencias": []}
    for n in await store.vecinos(nid):
        if n.tipo == "tarea":
            ctx["pendientes"].append(n.nombre)
        elif n.tipo == "evento":
            ctx["eventos"].append(n.nombre)
        elif n.tipo == "preferencia":
            ctx["preferencias"].append(n.nombre)
    return ctx


async def pendientes_de(store: MemoryStore, nombre: str) -> List[str]:
    """Tareas pendientes ligadas a la persona en el grafo de memoria."""
    return (await contexto_de(store, nombre))["pendientes"]


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
    ctx = await contexto_de(store, nombre)
    pend = ctx["pendientes"]
    aviso = aviso_presencia(nombre, pend)
    await world.append_event(
        {"fuente": "sentinela", "tipo": "presencia", "nombre": nombre, "conf": conf,
         "pendientes": pend, "contexto": ctx, "detalle": aviso}
    )
    # Quién está presente queda en el WorldState: los próximos turnos del Conductor
    # tienen su contexto (eventos, plan nutricional, pendientes) disponible.
    await world.set("persona_presente", {"nombre": nombre, "conf": conf, "contexto": ctx,
                                         "ts": time.time()})
    return {"nombre": nombre, "conf": conf, "pendientes": pend, "contexto": ctx, "aviso": aviso}
