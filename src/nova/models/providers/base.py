"""Interfaz común de proveedores y errores compartidos."""

from __future__ import annotations

from typing import List


class ProviderError(Exception):
    """Error genérico al llamar a un proveedor."""


class RateLimitError(ProviderError):
    """El proveedor devolvió 429 (cuota/rate limit). Dispara retry/backoff."""


class ProviderUnavailable(ProviderError):
    """El proveedor no está configurado/alcanzable (sin clave, host caído)."""


class Provider:
    """Contrato que cumple cada cliente de proveedor.

    `name` identifica al proveedor (ej. "ollama", "groq"). `available()` es una
    comprobación barata usada por el router para decidir si vale la pena llamar
    o caer a stub/fallback. `complete()` hace la llamada real y devuelve texto.
    """

    name: str = "base"

    def available(self) -> bool:  # pragma: no cover - lo implementa cada cliente
        raise NotImplementedError

    async def complete(self, model: str, messages: List[dict], **opts) -> str:  # pragma: no cover
        raise NotImplementedError


def last_user_text(messages: List[dict]) -> str:
    """Devuelve el contenido del último mensaje (para resúmenes/stub)."""
    for msg in reversed(messages):
        content = (msg or {}).get("content")
        if content:
            return str(content)
    return ""
