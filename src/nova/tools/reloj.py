"""Tool `hora`: fecha y hora actual (local). NOVA no tenía reloj — por eso fallaba
"¿qué hora es?". Lectura pura, riesgo safe, sin red."""

from __future__ import annotations

from datetime import datetime

from .base import BaseTool, ToolContext, ToolResult, ToolSpec

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


class Hora(BaseTool):
    spec = ToolSpec(
        name="hora",
        descripcion="Devuelve la fecha y hora actual. Usala para '¿qué hora es?' o '¿qué día es hoy?'.",
        args_schema={},
        riesgo="safe",
    )

    async def run(self, ctx: ToolContext, **_) -> ToolResult:
        ahora = datetime.now()
        dia = _DIAS[ahora.weekday()]
        mes = _MESES[ahora.month - 1]
        texto = f"Son las {ahora.strftime('%H:%M')} del {dia} {ahora.day} de {mes} de {ahora.year}."
        return ToolResult(True, texto, fuente="reloj")
