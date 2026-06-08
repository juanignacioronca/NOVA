"""Traza estructurada del Conductor.

Cada paso del flujo emite un `TraceEvent`. El Conductor los acumula en
`last_trace` y los empuja por un callback async `on_event`. El REPL los imprime;
más adelante (Prompt 7) el frontend consumirá el MISMO stream para dibujar el
flujo en vivo. Acá solo dejamos el stream listo y documentado, sin frontend.
"""

from __future__ import annotations

import inspect
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Dict, Optional, Union

# Un consumidor de eventos puede ser sync o async (ej. `asyncio.Queue.put`).
EventCallback = Callable[["TraceEvent"], Union[None, Awaitable[None]]]


@dataclass
class TraceEvent:
    etapa: str          # "comprension"|"seguridad"|"aclaracion"|"ruteo"|"agente"|"sintesis"|"respuesta"
    agente: str
    grupo: str          # "local"|"nube"|"-"
    modelo: str
    detalle: str
    estado: str = "ok"  # "ok"|"pregunta"|"alerta"|"error"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compact(self) -> str:
        """Línea compacta para el REPL / logs legibles."""
        marca = {"ok": "·", "pregunta": "?", "alerta": "⚠", "error": "✗"}.get(self.estado, "·")
        modelo = f" [{self.modelo}]" if self.modelo and self.modelo != "-" else ""
        return f"{marca} {self.etapa}/{self.agente}{modelo}: {self.detalle}"


async def emit(callback: Optional[EventCallback], event: TraceEvent) -> None:
    """Empuja un evento al callback (await si es coroutine). No falla si es None."""
    if callback is None:
        return
    result = callback(event)
    if inspect.isawaitable(result):
        await result
