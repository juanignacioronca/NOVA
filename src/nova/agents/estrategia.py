"""EstrategiaInvestigadorAgent — Grupo Nube (Transversal). Devuelve hallazgos.

En el esqueleto es un stub: produce un "hallazgo" breve para una subtarea. La
investigación real (web, deep research) llega en fases siguientes.
"""

from __future__ import annotations

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task


@register
class EstrategiaInvestigadorAgent(BaseAgent):
    name = "estrategia_investigador"
    group = "nube"
    model_key = "estrategia_investigador"
    skills = ["research", "investigar", "hallazgos"]

    async def handle(self, task: Task) -> Result:
        messages = [
            {
                "role": "system",
                "content": "Sos un investigador. Dado un punto, devolvé un hallazgo útil en 1-2 frases.",
            },
            {"role": "user", "content": task.goal},
        ]
        finding = await self.think(messages)
        breve = f"Hallazgo · {task.goal}: {finding}"
        self.log(
            tarea=task.goal,
            decision="investigación (stub)",
            resultado_breve=breve,
        )
        return Result(ok=True, text=breve, agent=self.name, data={"goal": task.goal})
