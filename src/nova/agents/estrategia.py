"""EstrategiaInvestigadorAgent — Grupo Nube (Transversal). Devuelve hallazgos.

En el esqueleto es un stub: produce un "hallazgo" breve para una subtarea. La
investigación real (web, deep research) llega en fases siguientes.
"""

from __future__ import annotations

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task
from ..tools.base import ToolError


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

        # Investiga en la web; el resultado entra YA marcado como NO confiable.
        externo = ""
        if self.tools is not None:
            try:
                out = await self.use_tool("buscar_web", {"consulta": task.goal})
                externo = out.content
            except ToolError:
                externo = ""
        if externo:
            breve += f"\nFuente web (no confiable):\n{externo}"

        self.log(tarea=task.goal, decision="investigación + buscar_web", resultado_breve=breve)
        return Result(ok=True, text=breve, agent=self.name, data={"goal": task.goal, "externo": bool(externo)})
