"""Interfaz común de las fuentes de percepción y del scheduler proactivo.

Cada *runnable* del loop cumple: `start() -> bool` (inicializa; False = degradado),
`run(stop)` (corre hasta que se setea el `asyncio.Event`), `stop()` (limpieza).
`_emit` empuja un evento al WorldState y al stream de `TraceEvent` (flujo en vivo).
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..core.trace import EventCallback, TraceEvent, emit
from ..core.world_state import WorldState


class BaseSource:
    name: str = "source"

    def __init__(
        self,
        world: WorldState,
        enabled: bool = True,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self.world = world
        self.enabled = enabled
        self.on_event = on_event

    async def start(self) -> bool:  # pragma: no cover - lo implementa cada fuente
        return True

    async def run(self, stop: asyncio.Event) -> None:  # pragma: no cover
        raise NotImplementedError

    async def stop(self) -> None:  # pragma: no cover
        return None

    async def _emit(
        self, etapa: str, detalle: str, estado: str = "ok", grupo: str = "local", **extra: Any
    ) -> None:
        """Registra un evento de percepción (WorldState + stream de traza)."""
        await self.world.append_event(
            {"fuente": self.name, "etapa": etapa, "detalle": detalle, "estado": estado, **extra}
        )
        ev = TraceEvent(
            etapa=etapa, agente=self.name, grupo=grupo, modelo="-", detalle=detalle, estado=estado
        )
        await emit(self.on_event, ev)


async def interruptible_sleep(stop: asyncio.Event, seconds: float) -> None:
    """Duerme `seconds`, pero corta apenas se pide `stop` (apagado rápido)."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass
