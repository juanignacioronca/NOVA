"""Tools de memoria: `buscar_memoria` (safe) y `recordar` (low).

Usan el motor de memoria local (grafo + vectores) vía `ctx.memory`. El agente
local `memoria_contexto` las tiene en su allowlist; otros según `tools.yaml`.
"""

from __future__ import annotations

from .base import BaseTool, ToolContext, ToolResult, ToolSpec


class BuscarMemoria(BaseTool):
    spec = ToolSpec(
        name="buscar_memoria",
        descripcion="Busca en la memoria de largo plazo (semántico).",
        args_schema={
            "consulta": {"type": "str", "required": True},
            "k": {"type": "int", "required": False, "default": 5},
        },
        riesgo="safe",
    )

    async def run(self, ctx: ToolContext, consulta: str, k: int = 5, **_) -> ToolResult:
        if ctx.memory is None:
            return ToolResult(True, "(memoria no disponible)", fuente="memoria")
        resultados = await ctx.memory.buscar_semantico(consulta, k=int(k))
        if not resultados:
            return ToolResult(True, "No encontré nada en la memoria.", fuente="memoria")
        lineas = [f"- ({nodo.tipo}) {nodo.nombre}" for nodo, _ in resultados]
        return ToolResult(True, "\n".join(lineas), fuente="memoria", data={"ids": [n.id for n, _ in resultados]})


class Recordar(BaseTool):
    spec = ToolSpec(
        name="recordar",
        descripcion="Guarda un hecho/preferencia en la memoria de largo plazo.",
        args_schema={
            "texto": {"type": "str", "required": True},
            "tipo": {"type": "str", "required": False, "default": "hecho"},
        },
        riesgo="low",
    )

    async def run(self, ctx: ToolContext, texto: str, tipo: str = "hecho", **_) -> ToolResult:
        if ctx.memory is None:
            return ToolResult(True, "(memoria no disponible)", fuente="memoria")
        nid = await ctx.memory.add_nodo(tipo, texto[:48], props={"frase": texto}, texto=texto)
        return ToolResult(True, f"Anotado en memoria: «{texto[:60]}».", fuente="memoria", data={"id": nid})
