"""Registro de PENDIENTES / capacidades faltantes de NOVA.

Cuando NOVA no puede hacer algo (le falta un dato del usuario —ej. dónde vive— o
una herramienta que todavía no tiene), lo **anota** acá en vez de quedarse trabada.
Queda en `data/pendientes.jsonl` (local, persistente) y se puede leer después
(tool `ver_pendientes`, endpoint `/api/pendientes`, o el modo configuración).

Tools:
- `anotar_pendiente` (low): registra una carencia (dedupe por descripción).
- `ver_pendientes` (safe): lista lo anotado.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Dict, List

from ..paths import data_dir
from .base import BaseTool, ToolContext, ToolResult, ToolSpec


def _path():
    return data_dir() / "pendientes.jsonl"


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def listar(incluir_resueltos: bool = False) -> List[Dict]:
    p = _path()
    if not p.exists():
        return []
    out: List[Dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if incluir_resueltos or not e.get("resuelto"):
            out.append(e)
    out.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return out


def anotar(descripcion: str, contexto: str = "", tipo: str = "capacidad") -> Dict:
    """Agrega un pendiente. Si ya existe uno sin resolver con la misma descripción,
    no duplica (suma una marca de repetición)."""
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    objetivo = _norm(descripcion)
    existentes = listar(incluir_resueltos=False)
    for e in existentes:
        if _norm(e.get("descripcion", "")) == objetivo:
            return e  # ya anotado: no duplicar
    entry = {
        "id": uuid.uuid4().hex[:8],
        "ts": time.time(),
        "tipo": tipo,
        "descripcion": descripcion.strip(),
        "contexto": (contexto or "").strip(),
        "resuelto": False,
    }
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


class AnotarPendiente(BaseTool):
    spec = ToolSpec(
        name="anotar_pendiente",
        descripcion=(
            "Registra algo que NOVA todavía NO puede hacer o un dato que le falta del "
            "usuario (ej. no sabe dónde vive, no tiene una herramienta). Usala cuando no "
            "puedas cumplir un pedido por falta de datos o capacidades."
        ),
        args_schema={
            "descripcion": {"type": "str", "required": True, "desc": "qué falta o no se puede hacer"},
            "contexto": {"type": "str", "required": False, "default": "", "desc": "de qué pedido salió"},
        },
        riesgo="low",
    )

    async def run(self, ctx: ToolContext, descripcion: str, contexto: str = "", **_) -> ToolResult:
        anotar(descripcion, contexto)
        return ToolResult(
            True,
            f"Lo anoté como pendiente: «{descripcion}». Lo voy a tener en cuenta para sumarlo más adelante.",
            fuente="pendientes",
        )


class VerPendientes(BaseTool):
    spec = ToolSpec(
        name="ver_pendientes",
        descripcion="Lista lo que NOVA dejó anotado como pendiente o que todavía no puede hacer.",
        args_schema={},
        riesgo="safe",
    )

    async def run(self, ctx: ToolContext, **_) -> ToolResult:
        items = listar()
        if not items:
            return ToolResult(True, "No tengo nada pendiente anotado.", fuente="pendientes")
        txt = "Tengo anotados estos pendientes:\n" + "\n".join(
            f"- {e['descripcion']}" + (f" (de: {e['contexto']})" if e.get("contexto") else "")
            for e in items[:20]
        )
        return ToolResult(True, txt, fuente="pendientes")
