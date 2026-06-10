"""Loop de percepción: orquesta las fuentes (y el scheduler proactivo) como
tasks asyncio en paralelo. Cada runnable se inicia con `start()`; si degrada,
se omite con aviso y el resto sigue. Corre hasta `request_stop()` (Ctrl-C).
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from ..core.trace import EventCallback, TraceEvent, emit
from ..core.world_state import WorldState


class PerceptionLoop:
    def __init__(
        self,
        runnables: List[object],
        world: WorldState,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self.runnables = runnables
        self.world = world
        self.on_event = on_event
        self._stop = asyncio.Event()
        self.activos: List[object] = []

    async def _aviso(self, agente: str, detalle: str, estado: str = "ok") -> None:
        await self.world.append_event({"fuente": "loop", "agente": agente, "detalle": detalle, "estado": estado})
        ev = TraceEvent(etapa="percepcion", agente=agente, grupo="local", modelo="-", detalle=detalle, estado=estado)
        await emit(self.on_event, ev)

    async def run(self) -> None:
        # 1) Iniciar cada runnable; degradar los que fallen.
        for r in self.runnables:
            nombre = getattr(r, "name", r.__class__.__name__)
            if not getattr(r, "enabled", True):
                await self._aviso(nombre, "deshabilitado por config", "alerta")
                continue
            try:
                ok = await r.start()
            except Exception as exc:  # nunca tirar el loop por una fuente
                await self._aviso(nombre, f"error al iniciar: {exc}", "alerta")
                continue
            if ok:
                self.activos.append(r)
            else:
                await self._aviso(nombre, "degradado (no disponible)", "alerta")

        if not self.activos:
            await self._aviso("loop", "ninguna fuente activa", "alerta")
            return

        await self._aviso("loop", "activas: " + ", ".join(getattr(r, "name", "?") for r in self.activos))

        # 2) Correr todas en paralelo hasta stop.
        tasks = [asyncio.create_task(r.run(self._stop)) for r in self.activos]
        try:
            await self._stop.wait()
        finally:
            for r in self.activos:
                try:
                    await r.stop()
                except Exception:
                    pass
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._aviso("loop", "apagado limpio")

    def request_stop(self) -> None:
        self._stop.set()
