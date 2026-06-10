"""Tools de calendario sobre un store local JSON que NOVA maneja.
`leer_calendario` (safe) · `agendar_evento` (low, escritura reversible).
Google Calendar/CalDAV detrás de la misma interfaz = futuro.
"""

from __future__ import annotations

import json
import uuid
from typing import List

from ..paths import data_dir
from .base import BaseTool, ToolContext, ToolResult, ToolSpec


def _cal_path():
    return data_dir() / "calendar.json"


def _load() -> List[dict]:
    path = _cal_path()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")) or []
    except (json.JSONDecodeError, OSError):
        return []


def _save(eventos: List[dict]) -> None:
    path = _cal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(eventos, ensure_ascii=False, indent=2), encoding="utf-8")


class LeerCalendario(BaseTool):
    spec = ToolSpec(
        name="leer_calendario",
        descripcion="Lee los próximos eventos del calendario local.",
        args_schema={"limite": {"type": "int", "required": False, "default": 5}},
        riesgo="safe",
    )

    async def run(self, ctx: ToolContext, limite: int = 5, **_) -> ToolResult:
        eventos = _load()[: max(1, int(limite))]
        if not eventos:
            return ToolResult(True, "No hay eventos en el calendario.", fuente="calendario-local")
        lineas = [f"- {e.get('cuando', '?')}: {e.get('titulo', '?')}" for e in eventos]
        return ToolResult(True, "\n".join(lineas), fuente="calendario-local", data={"eventos": eventos})


class AgendarEvento(BaseTool):
    spec = ToolSpec(
        name="agendar_evento",
        descripcion="Agenda un evento en el calendario local.",
        args_schema={
            "titulo": {"type": "str", "required": True},
            "cuando": {"type": "str", "required": True, "desc": "fecha/hora en texto"},
            "duracion": {"type": "str", "required": False, "default": ""},
        },
        riesgo="low",  # escritura reversible → directo, sin confirmación
    )

    async def run(self, ctx: ToolContext, titulo: str, cuando: str, duracion: str = "", **_) -> ToolResult:
        eventos = _load()
        evento = {"id": uuid.uuid4().hex[:8], "titulo": titulo, "cuando": cuando, "duracion": duracion}
        eventos.append(evento)
        _save(eventos)
        return ToolResult(True, f"Agendado: «{titulo}» para {cuando}.", fuente="calendario-local", data=evento)
