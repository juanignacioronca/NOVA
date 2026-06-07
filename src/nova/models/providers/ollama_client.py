"""Cliente Ollama (local, $0). Usa la API nativa /api/chat."""

from __future__ import annotations

import os
from typing import List, Optional

from .base import Provider, ProviderError, RateLimitError

try:  # httpx es dependencia, pero el import lazy mantiene robusto el modo stub
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


class OllamaClient(Provider):
    name = "ollama"

    def __init__(self) -> None:
        self._available: Optional[bool] = None  # cache de la sonda

    def available(self) -> bool:
        """Sonda barata a /api/tags. Cachea el resultado por proceso."""
        if self._available is not None:
            return self._available
        if httpx is None:
            self._available = False
            return False
        try:
            resp = httpx.get(f"{_host()}/api/tags", timeout=0.5)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    async def complete(self, model: str, messages: List[dict], **opts) -> str:
        if httpx is None:  # pragma: no cover
            raise ProviderError("httpx no está instalado")
        payload = {"model": model, "messages": messages, "stream": False}
        options = {k: v for k, v in opts.items() if k in ("temperature", "top_p", "num_predict")}
        if options:
            payload["options"] = options
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{_host()}/api/chat", json=payload)
            if resp.status_code == 429:
                raise RateLimitError("ollama 429")
            if resp.status_code >= 400:
                raise ProviderError(f"ollama {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()
