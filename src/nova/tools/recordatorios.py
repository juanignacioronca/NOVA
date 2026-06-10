"""Tools `crear_recordatorio` y `set_timer` (riesgo low). Escriben en el
WorldState (`reminders`) → alimentan los **avisos proactivos** del Prompt 4.
"""

from __future__ import annotations

import re
import time
import uuid

from .base import BaseTool, ToolContext, ToolResult, ToolSpec

_EN_RE = re.compile(r"en\s+(\d+)\s*(seg|segundos?|min|minutos?|h|horas?)")
_UNIT_SECONDS = {"seg": 1, "segundo": 1, "segundos": 1, "min": 60, "minuto": 60, "minutos": 60, "h": 3600, "hora": 3600, "horas": 3600}


def _segundos(cantidad: str, unidad: str) -> float:
    base = _UNIT_SECONDS.get(unidad.rstrip("s"), _UNIT_SECONDS.get(unidad, 60))
    try:
        return float(cantidad) * base
    except (ValueError, TypeError):
        return 60.0


async def _add_reminder(ctx: ToolContext, text: str, due: float) -> None:
    reminders = list(await ctx.world.get("reminders", []) or [])
    reminders.append({"id": uuid.uuid4().hex[:8], "text": text, "due": due})
    await ctx.world.set("reminders", reminders)


class CrearRecordatorio(BaseTool):
    spec = ToolSpec(
        name="crear_recordatorio",
        descripcion="Crea un recordatorio (dispara un aviso proactivo a su hora).",
        args_schema={
            "texto": {"type": "str", "required": True},
            "cuando": {"type": "str", "required": False, "default": "en 1 hora"},
        },
        riesgo="low",
    )

    async def run(self, ctx: ToolContext, texto: str, cuando: str = "en 1 hora", **_) -> ToolResult:
        m = _EN_RE.search((cuando or "").lower())
        segundos = _segundos(m.group(1), m.group(2)) if m else 3600.0
        await _add_reminder(ctx, texto, time.time() + segundos)
        return ToolResult(True, f"Recordatorio creado: «{texto}» ({cuando}).", fuente="recordatorios")


class SetTimer(BaseTool):
    spec = ToolSpec(
        name="set_timer",
        descripcion="Pone un timer (avisa al terminar).",
        args_schema={
            "duracion": {"type": "str", "required": True},
            "unidad": {"type": "str", "required": False, "default": "minutos"},
        },
        riesgo="low",
    )

    async def run(self, ctx: ToolContext, duracion: str, unidad: str = "minutos", **_) -> ToolResult:
        segundos = _segundos(duracion, unidad)
        await _add_reminder(ctx, f"timer de {duracion} {unidad}", time.time() + segundos)
        return ToolResult(True, f"⏱️ Timer de {duracion} {unidad} puesto.", fuente="recordatorios")
