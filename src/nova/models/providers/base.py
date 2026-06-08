"""Interfaz común de proveedores y errores compartidos.

Taxonomía de errores (la usa el router para decidir retry vs. fallback):
- `RateLimitError` (429), `ServerError` (5xx), `ProviderTimeout` → **reintentables**.
- `ProviderUnavailable` (sin clave/host caído) y `ProviderError` (otros) → **no**.
"""

from __future__ import annotations

from typing import List


class ProviderError(Exception):
    """Error genérico al llamar a un proveedor (no reintentable por defecto)."""


class RateLimitError(ProviderError):
    """El proveedor devolvió 429 (cuota/rate limit). Reintentable."""


class ServerError(ProviderError):
    """El proveedor devolvió 5xx. Reintentable."""


class ProviderTimeout(ProviderError):
    """Timeout de red al proveedor. Reintentable."""


class ProviderUnavailable(ProviderError):
    """El proveedor no está configurado/alcanzable (sin clave, host caído)."""


# Excepciones que ameritan retry con backoff antes de caer al fallback.
RETRYABLE = (RateLimitError, ServerError, ProviderTimeout)


class Provider:
    """Contrato que cumple cada cliente de proveedor.

    `available()` es una comprobación barata (¿hay clave? ¿host arriba?) que el
    router usa para no llamar en vano. `complete()` hace la llamada real.
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
