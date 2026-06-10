"""Fuente de texto: lee líneas de stdin y las enruta al Conductor.

Permite escribirle a NOVA mientras el daemon corre (sin micrófono). Degrada si
no hay terminal interactiva (ej. corriendo headless / con stdin redirigido).
"""

from __future__ import annotations

import asyncio
import sys
from typing import Awaitable, Callable, Optional

from ..core.trace import EventCallback
from ..core.world_state import WorldState
from .base import BaseSource

OnText = Callable[[str], Awaitable[None]]
EXIT_WORDS = {"salir", "exit", "quit"}


class TextSource(BaseSource):
    name = "texto"

    def __init__(
        self,
        world: WorldState,
        on_text: OnText,
        *,
        enabled: bool = True,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        super().__init__(world, enabled, on_event)
        self.on_text = on_text

    async def start(self) -> bool:
        if not sys.stdin or not sys.stdin.isatty():
            await self._emit("texto", "sin terminal interactiva; fuente de texto off", estado="alerta")
            return False
        await self._emit("texto", "escribí para hablarle a NOVA (o 'salir')")
        return True

    async def run(self, stop: asyncio.Event) -> None:
        loop = asyncio.get_event_loop()
        while not stop.is_set():
            try:
                linea = (await loop.run_in_executor(None, sys.stdin.readline))
            except (EOFError, ValueError):
                break
            if linea == "":  # EOF
                break
            texto = linea.strip()
            if not texto:
                continue
            if texto.lower() in EXIT_WORDS:
                stop.set()
                break
            await self.world.append_event({"fuente": "texto", "tipo": "utterance", "texto": texto})
            if self.on_text is not None:
                await self.on_text(texto)
