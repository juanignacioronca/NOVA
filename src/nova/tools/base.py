"""Tipos base de la capa de herramientas: spec, tool, resultado, errores."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RIESGOS = ("safe", "low", "high")  # lectura · escritura reversible · efecto sensible


@dataclass
class ToolSpec:
    name: str
    descripcion: str
    # arg -> {"type": "str|int|float|bool", "required": bool, "default": ..., "desc": ...}
    args_schema: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    riesgo: str = "safe"
    externo: bool = False  # trae contenido de afuera → se marca no confiable
    grupos: List[str] = field(default_factory=lambda: ["local", "nube"])


@dataclass
class ToolResult:
    """Lo que devuelve la ejecución de una tool."""

    ok: bool
    content: str
    fuente: str = ""        # de dónde vino (para marcar_no_confiable)
    externo: bool = False   # override del spec.externo (ej. resultado puntual)
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutcome:
    """Lo que el ToolExecutor devuelve al agente (content ya envuelto si externo)."""

    ok: bool
    content: str
    tool: str
    externo: bool = False
    raw: str = ""


@dataclass
class ToolContext:
    """Contexto que recibe cada tool al ejecutarse."""

    world: Any
    stub: bool = False      # True → resultados deterministas sin red
    memory: Any = None      # MemoryStore (tools de memoria), opcional


class BaseTool:
    spec: ToolSpec

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def group(self) -> str:  # para el Registry (no se usa para permisos)
        return "tool"

    def confirm_message(self, **args) -> str:
        """Mensaje de confirmación para tools de riesgo `high` (override opcional)."""
        return f"Voy a ejecutar «{self.spec.name}» con {args}. ¿Confirmás?"

    async def run(self, ctx: ToolContext, **args) -> ToolResult:  # pragma: no cover
        raise NotImplementedError


# --- errores ---
class ToolError(Exception):
    """Base de errores de la capa de herramientas."""


class ToolNoEncontrada(ToolError):
    pass


class PermisoDenegado(ToolError):
    """Tool fuera de allowlist o agente sin permiso (least-privilege)."""


class ArgsInvalidos(ToolError):
    pass


class RequiereConfirmacion(ToolError):
    """Una tool `high` necesita el OK explícito del usuario antes de ejecutarse."""

    def __init__(self, mensaje: str, tool: str, args: Dict[str, Any]) -> None:
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.tool = tool
        self.args = args
