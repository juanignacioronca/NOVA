"""Capa de herramientas (tools): las "manos" de NOVA.

Cada tool declara `name`, `descripcion`, `args_schema`, `riesgo` y de qué grupos
es invocable. El `ToolExecutor` valida args, chequea allowlist + permiso + riesgo,
ejecuta, envuelve el contenido externo como no confiable y registra todo.
Ver CLAUDE.md §11. Las claves (cuando las haya) solo desde `.env`.
"""

from __future__ import annotations

from typing import List

from .calendario import AgendarEvento, LeerCalendario
from .clima import Clima
from .correo import EnviarCorreo
from .lugares import BuscarLugar
from .memoria import BuscarMemoria, Recordar
from .pendientes import AnotarPendiente, VerPendientes
from .recordatorios import CrearRecordatorio, SetTimer
from .reloj import Hora
from .web import BuscarWeb


def default_tools() -> List[object]:
    """Instancia el set inicial de herramientas."""
    return [
        Clima(),
        BuscarWeb(),
        BuscarLugar(),
        LeerCalendario(),
        AgendarEvento(),
        CrearRecordatorio(),
        SetTimer(),
        EnviarCorreo(),
        BuscarMemoria(),
        Recordar(),
        Hora(),
        AnotarPendiente(),
        VerPendientes(),
    ]


def register_default_tools(registry) -> None:
    """Registra el set inicial en un Registry (idempotente: pisa por nombre)."""
    for tool in default_tools():
        registry.add_tool(tool)


__all__ = ["default_tools", "register_default_tools"]
