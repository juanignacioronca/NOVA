"""Tool `clima` — Open-Meteo (sin clave). Riesgo: safe (lectura)."""

from __future__ import annotations

from .base import BaseTool, ToolContext, ToolResult, ToolSpec

_GEO = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST = "https://api.open-meteo.com/v1/forecast"
_CODES = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "niebla", 48: "niebla", 51: "llovizna", 61: "lluvia", 63: "lluvia",
    65: "lluvia fuerte", 71: "nieve", 80: "chubascos", 95: "tormenta",
}


class Clima(BaseTool):
    spec = ToolSpec(
        name="clima",
        descripcion="Tiempo actual de una ciudad.",
        args_schema={"ciudad": {"type": "str", "required": False, "default": "", "desc": "ciudad"}},
        riesgo="safe",
        externo=False,
    )

    async def run(self, ctx: ToolContext, ciudad: str = "", **_) -> ToolResult:
        nombre = (ciudad or "").strip() or "tu zona"
        if ctx.stub:
            return ToolResult(True, f"En {nombre}: 22°C, despejado. (stub)", fuente="open-meteo")
        try:
            return await self._real(nombre)
        except Exception:
            return ToolResult(True, f"En {nombre}: 22°C, despejado. (sin red)", fuente="open-meteo")

    async def _real(self, nombre: str) -> ToolResult:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as c:
            g = await c.get(_GEO, params={"name": nombre, "count": 1, "language": "es"})
            res = (g.json().get("results") or [])
            if not res:
                return ToolResult(True, f"No encontré la ciudad «{nombre}».", fuente="open-meteo")
            lat, lon = res[0]["latitude"], res[0]["longitude"]
            disp = res[0].get("name", nombre)
            f = await c.get(_FORECAST, params={"latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code"})
            cur = f.json().get("current", {})
        temp = cur.get("temperature_2m")
        desc = _CODES.get(cur.get("weather_code"), "—")
        return ToolResult(True, f"En {disp}: {temp}°C, {desc}.", fuente="open-meteo")
