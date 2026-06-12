"""Tools de calendario sobre un store local JSON que NOVA maneja.
`leer_calendario` (safe) · `agendar_evento` (low, escritura reversible).
Google Calendar/CalDAV detrás de la misma interfaz = futuro.

Además: `proximos(...)` (eventos que arrancan dentro de una ventana, para los
avisos proactivos) y `sugerir_llevar(titulo)` (qué conviene llevar a actividades
comunes: playa → protector solar, tenis → raqueta, etc.).
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

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


def _norm(s: str) -> str:
    d = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


# --- qué llevar a actividades comunes (sugerencia local, $0) ---
_SUGERENCIAS = {
    "playa": ["protector solar", "toalla", "agua"],
    "tenis": ["raqueta", "pelotas", "agua"],
    "padel": ["paleta", "pelotas", "agua"],
    "futbol": ["botines", "canilleras", "agua"],
    "gym": ["ropa de entrenamiento", "toalla", "botella de agua"],
    "pileta": ["malla", "toalla", "antiparras"],
    "piscina": ["malla", "toalla", "antiparras"],
    "camping": ["carpa", "bolsa de dormir", "linterna", "repelente"],
    "trekking": ["zapatillas de trekking", "agua", "protector solar", "abrigo"],
    "cerro": ["zapatillas de trekking", "agua", "protector solar", "abrigo"],
    "picnic": ["mantel", "comida", "repelente"],
    "viaje": ["documentos", "cargador", "equipaje"],
}


def sugerir_llevar(titulo: str) -> List[str]:
    """Sugiere qué llevar según la actividad del título (vacío si no reconoce)."""
    n = _norm(titulo)
    for actividad, items in _SUGERENCIAS.items():
        if actividad in n:
            return list(items)
    return []


# --- parseo de `cuando` (texto) → timestamp, para los avisos proactivos ---
_HORA_RE = re.compile(r"(?:a las\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:hs?|horas)?\b")
_ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?")
_DMY_RE = re.compile(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?(?:\s+(?:a las\s+)?(\d{1,2})(?::(\d{2}))?)?")


def parse_cuando(cuando: str, now: Optional[float] = None) -> Optional[float]:
    """Convierte `cuando` (texto) a timestamp si tiene forma reconocible:
    ISO (`2026-06-12 17:00`), `12/6 17:00`, `hoy a las 17`, `mañana 9:30`.
    Texto libre sin fecha/hora → None (no se puede avisar proactivamente)."""
    now_ts = time.time() if now is None else now
    base = datetime.fromtimestamp(now_ts)
    texto = _norm(cuando or "")

    m = _ISO_RE.search(texto)
    if m:
        y, mo, d, h, mi = m.groups()
        # Sin hora explícita: se asume 09:00 (un evento de día entero avisa a la mañana).
        return datetime(int(y), int(mo), int(d), int(h or 9), int(mi or 0)).timestamp()

    m = _DMY_RE.search(texto)
    if m and "/" in texto:
        d, mo, y, h, mi = m.groups()
        anio = int(y) + (2000 if y and int(y) < 100 else 0) if y else base.year
        try:
            dt = datetime(anio, int(mo), int(d), int(h or 9), int(mi or 0))
        except ValueError:
            return None
        if not y and dt.timestamp() < now_ts - 86400:  # sin año y ya pasó → año que viene
            dt = dt.replace(year=anio + 1)
        return dt.timestamp()

    dia = None
    if "pasado manana" in texto:
        dia = base + timedelta(days=2)
    elif "manana" in texto:
        dia = base + timedelta(days=1)
    elif "hoy" in texto or texto.strip().startswith("a las"):
        dia = base
    if dia is not None:
        m = _HORA_RE.search(texto.replace("pasado manana", "").replace("manana", "").replace("hoy", ""))
        h, mi = (int(m.group(1)), int(m.group(2) or 0)) if m else (9, 0)
        if h > 23:
            return None
        return dia.replace(hour=h, minute=mi, second=0, microsecond=0).timestamp()
    return None


def proximos(horizonte_horas: float = 2.0, now: Optional[float] = None) -> List[dict]:
    """Eventos cuyo `cuando` es parseable y cae dentro de la ventana
    [ahora, ahora + horizonte]. Cada uno sale con su `ts` resuelto."""
    now_ts = time.time() if now is None else now
    fin = now_ts + horizonte_horas * 3600
    out: List[dict] = []
    for e in _load():
        ts = parse_cuando(e.get("cuando", ""), now=now_ts)
        if ts is not None and now_ts <= ts <= fin:
            out.append({**e, "ts": ts})
    out.sort(key=lambda e: e["ts"])
    return out


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
            "llevar": {"type": "str", "required": False, "default": "",
                       "desc": "qué hay que llevar, separado por comas"},
        },
        riesgo="low",  # escritura reversible → directo, sin confirmación
    )

    async def run(self, ctx: ToolContext, titulo: str, cuando: str, duracion: str = "",
                  llevar: str = "", **_) -> ToolResult:
        eventos = _load()
        items = [it.strip() for it in str(llevar).split(",") if it.strip()] or sugerir_llevar(titulo)
        evento = {"id": uuid.uuid4().hex[:8], "titulo": titulo, "cuando": cuando,
                  "duracion": duracion, "llevar": items}
        eventos.append(evento)
        _save(eventos)
        msg = f"Agendado: «{titulo}» para {cuando}."
        if items:
            msg += f" Te voy a recordar llevar: {', '.join(items)}."
        return ToolResult(True, msg, fuente="calendario-local", data=evento)
