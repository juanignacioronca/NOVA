"""Estado del Mundo: store compartido async-safe (memoria de trabajo).

Guarda hechos del contexto y una lista de eventos recientes. Caché vivo de la
memoria (la memoria persistente llega en una fase posterior). Ver CLAUDE.md §3.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional


class WorldState:
    def __init__(self, max_events: int = 200) -> None:
        self._lock = asyncio.Lock()
        self._facts: Dict[str, Any] = {}
        self._events: List[Dict[str, Any]] = []
        self._max_events = max_events

    async def get(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._facts.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._facts[key] = value

    async def append_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Agrega un evento (con timestamp) a la cola reciente."""
        entry = {"ts": time.time(), **event}
        async with self._lock:
            self._events.append(entry)
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events :]
        return entry

    async def events(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._events)

    async def snapshot(self) -> Dict[str, Any]:
        async with self._lock:
            return {"facts": dict(self._facts), "events": list(self._events)}
