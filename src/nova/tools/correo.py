"""Tool `enviar_correo` — riesgo **high** → requiere confirmación del usuario.
Backend stub (no envía de verdad). SMTP/OAuth real = futuro, misma interfaz.
Demuestra el patrón de **acción gated**.
"""

from __future__ import annotations

from .base import BaseTool, ToolContext, ToolResult, ToolSpec


class EnviarCorreo(BaseTool):
    spec = ToolSpec(
        name="enviar_correo",
        descripcion="Envía un correo (acción sensible).",
        args_schema={
            "para": {"type": "str", "required": True},
            "asunto": {"type": "str", "required": True},
            "cuerpo": {"type": "str", "required": False, "default": ""},
        },
        riesgo="high",  # → confirmación obligatoria antes de ejecutar
    )

    def confirm_message(self, para: str = "", asunto: str = "", **_) -> str:
        return f"Voy a enviar un correo a {para} (asunto: «{asunto}»). ¿Confirmás?"

    async def run(self, ctx: ToolContext, para: str, asunto: str, cuerpo: str = "", **_) -> ToolResult:
        # Backend stub: NO envía nada. Real (SMTP/OAuth) = futuro, detrás de esta misma interfaz.
        return ToolResult(
            True,
            f"Correo enviado a {para} (asunto: «{asunto}»). [backend stub — no se envió de verdad]",
            fuente="correo",
        )
