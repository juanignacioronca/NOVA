"""RespuestasRapidasAgent — Grupo Local. Resuelve lo simple, corto y barato.
Usa herramientas locales según la intención: clima, timer, recordatorio, calendario.
"""

from __future__ import annotations

import re

from ..core.agent import BaseAgent
from ..core.registry import register
from ..core.task import Result, Task

_CITY_RE = re.compile(r"\ben\s+([A-Za-zÁ-ÿ][\wÁ-ÿ'’\- ]{1,40})", re.IGNORECASE)


def _ciudad(texto: str) -> str:
    m = _CITY_RE.search(texto or "")
    return m.group(1).strip(" ?.!").split(" hoy")[0].strip() if m else ""


@register
class RespuestasRapidasAgent(BaseAgent):
    name = "respuestas_rapidas"
    group = "local"
    model_key = "respuestas_rapidas"
    skills = ["respuesta_corta", "timer", "clima", "recordatorio", "calendario"]

    async def handle(self, task: Task) -> Result:
        # Ruteo por intención a la tool correspondiente (si está disponible).
        if self.tools is not None:
            tool_result = await self._maybe_tool(task)
            if tool_result is not None:
                return tool_result

        # Fallback: responder con el modelo (corto).
        messages = [
            {"role": "system", "content": "Sos NOVA en modo local. Respondé en español, corto y directo."},
            {"role": "user", "content": task.goal},
        ]
        answer = await self.think(messages)
        self.log(tarea=task.goal, decision="resuelto en local (sin tool)", resultado_breve=answer)
        return Result(ok=True, text=answer, agent=self.name, data={"intent": task.intent})

    async def _maybe_tool(self, task: Task):
        """Mapea intención → tool. Devuelve Result o None (deja `RequiereConfirmacion`
        / `PermisoDenegado` propagar al Conductor)."""
        intent = task.intent
        ents = task.entities or {}
        if intent == "weather":
            out = await self.use_tool("clima", {"ciudad": _ciudad(task.goal)})
        elif intent == "set_timer":
            out = await self.use_tool(
                "set_timer", {"duracion": ents.get("duracion", "10"), "unidad": ents.get("unidad", "minutos")}
            )
        elif intent == "reminder":
            out = await self.use_tool(
                "crear_recordatorio", {"texto": task.goal, "cuando": ents.get("cuando", "en 1 hora")}
            )
        elif intent == "calendar":
            out = await self.use_tool("leer_calendario", {"limite": 5})
        else:
            return None
        self.log(tarea=task.goal, decision=f"resuelto con tool ({intent})", resultado_breve=out.content)
        return Result(ok=True, text=out.content, agent=self.name, data={"intent": intent, "tool": out.tool})
