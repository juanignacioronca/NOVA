"""MemoriaContextoAgent — Grupo Local. Memoria de trabajo: actualiza el Estado
del Mundo y hace matching simple ("la lista del papá"). Modelo `memoria_contexto`
(Llama 3.2 3B local). La memoria persistente (grafo/vectores/Obsidian) es fase
posterior; acá es un store liviano sobre el WorldState.
"""

from __future__ import annotations

import unicodedata
from typing import List, Optional

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task

_STOP = {"la", "el", "los", "las", "de", "del", "un", "una", "mi", "lista", "nota"}


def _tokens(texto: str) -> set:
    d = unicodedata.normalize("NFD", (texto or "").lower())
    limpio = "".join(c if c.isalnum() or c.isspace() else " " for c in d if unicodedata.category(c) != "Mn")
    return {t for t in limpio.split() if t and t not in _STOP}


@register
class MemoriaContextoAgent(BaseAgent):
    name = "memoria_contexto"
    group = "local"
    model_key = "memoria_contexto"
    skills = ["memoria", "contexto", "match"]

    async def recordar(self, texto: str) -> None:
        """Guarda una nota en la memoria de trabajo (WorldState)."""
        if self.world is None:
            return
        notas: List[str] = list(await self.world.get("notas", []) or [])
        notas.append(texto)
        await self.world.set("notas", notas)

    async def buscar(self, consulta: str) -> Optional[str]:
        """Matching simple por superposición de palabras (ej. 'la lista del papá')."""
        if self.world is None:
            return None
        notas: List[str] = list(await self.world.get("notas", []) or [])
        objetivo = _tokens(consulta)
        mejor, score = None, 0
        for nota in notas:
            comun = len(objetivo & _tokens(nota))
            if comun > score:
                mejor, score = nota, comun
        return mejor if score > 0 else None

    async def handle(self, task: Task) -> Result:
        if task.intent in ("recordar", "reminder", "nota"):
            await self.recordar(task.goal)
            return Result(ok=True, text="anotado", agent=self.name)
        match = await self.buscar(task.goal)
        texto = match or "no encontré nada relacionado"
        self.log(tarea=task.goal, decision="match en memoria de trabajo", resultado_breve=texto)
        return Result(ok=True, text=texto, agent=self.name, data={"match": match})
