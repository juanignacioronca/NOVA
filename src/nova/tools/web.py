"""Tool `buscar_web` — DuckDuckGo (sin clave; pluggable a Brave/Tavily después).
Riesgo: safe. **externo=True** → el resultado se marca como NO confiable.
"""

from __future__ import annotations

from .base import BaseTool, ToolContext, ToolResult, ToolSpec

_DDG = "https://api.duckduckgo.com/"


class BuscarWeb(BaseTool):
    spec = ToolSpec(
        name="buscar_web",
        descripcion="Busca en la web (texto). El resultado es contenido externo no confiable.",
        args_schema={"consulta": {"type": "str", "required": True, "desc": "qué buscar"}},
        riesgo="safe",
        externo=True,
    )

    async def run(self, ctx: ToolContext, consulta: str, **_) -> ToolResult:
        if ctx.stub:
            return ToolResult(
                True,
                f"Resultado A sobre «{consulta}»; Resultado B; Resultado C. (stub)",
                fuente="duckduckgo",
                externo=True,
            )
        try:
            return await self._real(consulta)
        except Exception:
            return ToolResult(True, f"(sin red) no pude buscar «{consulta}».", fuente="duckduckgo", externo=True)

    async def _real(self, consulta: str) -> ToolResult:
        import httpx

        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "NOVA/0.1"}) as c:
            r = await c.get(_DDG, params={"q": consulta, "format": "json", "no_html": 1, "t": "nova"})
            j = r.json()
        abstract = (j.get("AbstractText") or "").strip()
        relacionados = [
            t.get("Text", "")
            for t in (j.get("RelatedTopics") or [])
            if isinstance(t, dict) and t.get("Text")
        ][:3]
        texto = abstract or " | ".join(relacionados) or f"Sin resultados directos para «{consulta}»."
        return ToolResult(True, texto, fuente="duckduckgo", externo=True)
