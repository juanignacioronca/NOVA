"""PMOAgent — Grupo Nube (Orquestación). Descompone el objetivo en subtareas,
consulta a Estrategia **por el bus** y devuelve un plan breve.
"""

from __future__ import annotations

from typing import List

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task

ESTRATEGIA = "estrategia_investigador"


@register
class PMOAgent(BaseAgent):
    name = "pmo"
    group = "nube"
    model_key = "pmo_planificador"
    skills = ["planificar", "descomponer", "orquestar"]

    def _decompose(self, goal: str) -> List[str]:
        """Descompone el objetivo en 2-3 subtareas (heurística determinista)."""
        return [
            f"Investigar opciones y requisitos para: {goal}",
            "Definir logística, fechas y pasos concretos",
            "Estimar costo/tiempo y armar checklist final",
        ]

    async def handle(self, task: Task) -> Result:
        subtasks = self._decompose(task.goal)

        # Consultar a Estrategia POR EL BUS, una vez por subtarea de research.
        findings: List[str] = []
        sub = subtasks[0]
        reply = await self.ask(
            ESTRATEGIA, Task(goal=sub, intent="research", complexity="complejo")
        )
        findings.append(reply.text)

        # Redacción del plan (en stub queda determinista vía render).
        plan_note = await self.think(
            [
                {"role": "system", "content": "Sos un PMO. Redactá un plan breve y accionable."},
                {"role": "user", "content": f"Objetivo: {task.goal}\nSubtareas: {subtasks}"},
            ]
        )

        text = self._render(task.goal, subtasks, findings, plan_note)
        self.log(
            tarea=task.goal,
            decision=f"descompuesto en {len(subtasks)} subtareas; consultó a {ESTRATEGIA}",
            resultado_breve=text,
        )
        return Result(
            ok=True,
            text=text,
            agent=self.name,
            data={"subtasks": subtasks, "findings": findings},
        )

    @staticmethod
    def _render(goal: str, subtasks: List[str], findings: List[str], plan_note: str) -> str:
        lines = [f"Plan (PMO) para: {goal}", "Subtareas:"]
        for i, st in enumerate(subtasks, 1):
            lines.append(f"  {i}. {st}")
        if findings:
            lines.append("Aporte de Estrategia:")
            for f in findings:
                lines.append(f"  - {f}")
        if plan_note and not plan_note.startswith("[stub:"):
            lines.append(f"Nota del PMO: {plan_note}")
        return "\n".join(lines)
