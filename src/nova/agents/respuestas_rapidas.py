"""RespuestasRapidasAgent — Grupo Local. Resuelve lo simple, corto y barato."""

from __future__ import annotations

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task


@register
class RespuestasRapidasAgent(BaseAgent):
    name = "respuestas_rapidas"
    group = "local"
    model_key = "respuestas_rapidas"
    skills = ["respuesta_corta", "timer", "clima", "recordatorio", "calendario"]

    async def handle(self, task: Task) -> Result:
        messages = [
            {
                "role": "system",
                "content": (
                    "Sos NOVA en modo local. Respondé en español, corto y directo. "
                    "Si es un timer/recordatorio/clima, confirmá la acción en una línea."
                ),
            },
            {"role": "user", "content": task.goal},
        ]
        answer = await self.think(messages)
        self.log(
            tarea=task.goal,
            decision="resuelto en local (respuesta rápida)",
            resultado_breve=answer,
        )
        return Result(ok=True, text=answer, agent=self.name, data={"intent": task.intent})
