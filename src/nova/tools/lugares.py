"""Tool `buscar_lugar` — Nominatim/OpenStreetMap (sin clave, con User-Agent propio).
Riesgo: safe. **externo=True** → resultado marcado como no confiable.
"""

from __future__ import annotations

from .base import BaseTool, ToolContext, ToolResult, ToolSpec

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_UA = "NOVA/0.1 (asistente personal; contacto: local)"


class BuscarLugar(BaseTool):
    spec = ToolSpec(
        name="buscar_lugar",
        descripcion="Busca lugares/direcciones (OpenStreetMap). Contenido externo.",
        args_schema={"consulta": {"type": "str", "required": True, "desc": "lugar a buscar"}},
        riesgo="safe",
        externo=True,
    )

    async def run(self, ctx: ToolContext, consulta: str, **_) -> ToolResult:
        if ctx.stub:
            return ToolResult(
                True,
                f"Lugar 1 para «{consulta}» (lat/lon); Lugar 2; Lugar 3. (stub)",
                fuente="osm-nominatim",
                externo=True,
            )
        try:
            return await self._real(consulta)
        except Exception:
            return ToolResult(True, f"(sin red) no pude buscar lugares para «{consulta}».", fuente="osm-nominatim", externo=True)

    async def _real(self, consulta: str) -> ToolResult:
        import httpx

        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": _UA}) as c:
            r = await c.get(_NOMINATIM, params={"q": consulta, "format": "json", "limit": 3})
            arr = r.json()
        if not arr:
            return ToolResult(True, f"No encontré lugares para «{consulta}».", fuente="osm-nominatim", externo=True)
        items = [f"{a.get('display_name', '')} ({a.get('lat')},{a.get('lon')})" for a in arr[:3]]
        return ToolResult(True, " ; ".join(items), fuente="osm-nominatim", externo=True)
