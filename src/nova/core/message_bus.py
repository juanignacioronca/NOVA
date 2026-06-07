"""MessageBus async (en memoria).

Dos modos:
- **request/response directo** entre agentes: `await bus.request(to, payload)`
  invoca el handler del agente destino y devuelve su respuesta. Es el camino que
  usa el Conductor para hablar con el PMO, y el PMO con Estrategia.
- **publish/subscribe** por tópico: `publish(topic, msg)` + `subscribe(topic)`
  para difusión/trabajos mixtos (queda listo para fases siguientes).

Guarda un historial para inspección/auditoría.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, List

# Un handler recibe el payload del request y devuelve (await) la respuesta.
Handler = Callable[[Dict[str, Any]], Awaitable[Any]]


class MessageBus:
    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}
        self._topics: Dict[str, List[asyncio.Queue]] = {}
        self._history: List[Dict[str, Any]] = []

    # --- request / response directo ---
    def register_handler(self, name: str, handler: Handler) -> None:
        """Registra el handler de un agente (su nombre = destino del request)."""
        self._handlers[name] = handler

    def has_handler(self, name: str) -> bool:
        return name in self._handlers

    async def request(self, to: str, payload: Dict[str, Any]) -> Any:
        """Envía un request a `to` y espera su respuesta."""
        handler = self._handlers.get(to)
        if handler is None:
            raise KeyError(f"MessageBus: no hay handler registrado para '{to}'")
        self._history.append({"kind": "request", "to": to, "payload": payload})
        reply = await handler(payload)
        self._history.append({"kind": "reply", "from": to, "reply": reply})
        return reply

    # --- publish / subscribe por tópico ---
    def subscribe(self, topic: str) -> asyncio.Queue:
        """Devuelve una cola que recibirá los mensajes publicados en `topic`."""
        queue: asyncio.Queue = asyncio.Queue()
        self._topics.setdefault(topic, []).append(queue)
        return queue

    async def publish(self, topic: str, msg: Any) -> int:
        """Publica `msg` en `topic`. Devuelve cuántos suscriptores lo recibieron."""
        self._history.append({"kind": "publish", "topic": topic, "msg": msg})
        queues = self._topics.get(topic, [])
        for queue in queues:
            await queue.put(msg)
        return len(queues)

    # --- inspección ---
    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)
