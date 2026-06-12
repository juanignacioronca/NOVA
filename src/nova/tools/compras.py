"""Lista de compras local (estilo Alexa): agregar, ver y quitar ítems.

Store en `data/compras.json` (local, $0). `parsear_pedido(texto)` interpreta
pedidos en lenguaje natural ("agregá pan a la lista", "sacá la leche de la
lista", "¿qué hay en la lista de compras?") para el ruteo determinístico del
Conductor y del grupo local.
"""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from typing import Dict, List, Optional

from ..paths import data_dir
from .base import BaseTool, ToolContext, ToolResult, ToolSpec


def _path():
    return data_dir() / "compras.json"


def _load() -> List[dict]:
    p = _path()
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")) or []
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: List[dict]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm(s: str) -> str:
    d = unicodedata.normalize("NFD", (s or "").lower().strip())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


# --- interpretación en lenguaje natural (ruteo determinístico) ---
_KW_LISTA = ("lista de compras", "lista del super", "lista de super", "lista de la compra",
             "que hay que comprar", "que tengo que comprar", "a la lista", "de la lista")
_AGREGAR_RE = re.compile(
    r"(?:agrega|suma|pone|pon|anota|anade|mete|carga)(?:me|le)?\s+(.+?)\s+(?:a|en)\s+la\s+lista"
)
_QUITAR_RE = re.compile(
    r"(?:saca|quita|borra|elimina|tacha)(?:me|le)?\s+(.+?)\s+de\s+la\s+lista"
)
_ARTICULO_RE = re.compile(r"^(?:el|la|los|las|un|una|unos|unas)\s+")


def _sin_articulo(item: str) -> str:
    return _ARTICULO_RE.sub("", item.strip())


def parsear_pedido(texto: str) -> Optional[Dict[str, str]]:
    """Si el texto es un pedido sobre la lista de compras, devuelve
    `{"accion": "agregar"|"quitar"|"ver", "item": "..."}`; si no, None."""
    n = _norm(texto)
    if not any(k in n for k in _KW_LISTA):
        return None
    m = _QUITAR_RE.search(n)
    if m:
        return {"accion": "quitar", "item": _sin_articulo(m.group(1))}
    m = _AGREGAR_RE.search(n)
    if m:
        return {"accion": "agregar", "item": _sin_articulo(m.group(1))}
    return {"accion": "ver", "item": ""}


class AgregarCompra(BaseTool):
    spec = ToolSpec(
        name="agregar_compra",
        descripcion="Agrega un ítem a la lista de compras local.",
        args_schema={"item": {"type": "str", "required": True, "desc": "qué comprar"}},
        riesgo="low",  # escritura reversible
    )

    async def run(self, ctx: ToolContext, item: str, **_) -> ToolResult:
        items = _load()
        nuevos = [it.strip() for it in str(item).split(",") if it.strip()]
        ya = {_norm(e["item"]) for e in items}
        for it in nuevos:
            if _norm(it) not in ya:
                items.append({"id": uuid.uuid4().hex[:8], "item": it})
        _save(items)
        return ToolResult(True, f"Listo, agregué a la lista de compras: {', '.join(nuevos)}.",
                          fuente="compras-local", data={"items": items})


class VerCompras(BaseTool):
    spec = ToolSpec(
        name="ver_compras",
        descripcion="Lee la lista de compras local.",
        args_schema={},
        riesgo="safe",
    )

    async def run(self, ctx: ToolContext, **_) -> ToolResult:
        items = _load()
        if not items:
            return ToolResult(True, "La lista de compras está vacía.", fuente="compras-local",
                              data={"items": []})
        txt = "Lista de compras:\n" + "\n".join(f"- {e['item']}" for e in items)
        return ToolResult(True, txt, fuente="compras-local", data={"items": items})


class QuitarCompra(BaseTool):
    spec = ToolSpec(
        name="quitar_compra",
        descripcion="Quita un ítem de la lista de compras local.",
        args_schema={"item": {"type": "str", "required": True, "desc": "qué sacar de la lista"}},
        riesgo="low",
    )

    async def run(self, ctx: ToolContext, item: str, **_) -> ToolResult:
        items = _load()
        objetivo = _norm(item)
        restantes = [e for e in items if _norm(e["item"]) != objetivo]
        if len(restantes) == len(items):
            return ToolResult(True, f"No encontré «{item}» en la lista de compras.",
                              fuente="compras-local", data={"items": items})
        _save(restantes)
        return ToolResult(True, f"Saqué «{item}» de la lista de compras.",
                          fuente="compras-local", data={"items": restantes})
