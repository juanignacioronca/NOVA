"""Cliente OpenAI-compatible: sirve Groq, OpenRouter y DeepSeek con la misma
interfaz; solo cambian `base_url` y la clave. Endpoint: POST /chat/completions.
"""

from __future__ import annotations

import os
from typing import List

from .base import Provider, ProviderError, RateLimitError

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


# Config por proveedor: base_url + variable de entorno de la clave.
PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
    },
}


class OpenAICompatibleClient(Provider):
    """Un mismo cliente para varios proveedores OpenAI-compatibles."""

    def __init__(self, provider: str) -> None:
        if provider not in PROVIDERS:
            raise ProviderError(f"proveedor OpenAI-compatible desconocido: {provider}")
        self.name = provider
        cfg = PROVIDERS[provider]
        self.base_url = cfg["base_url"].rstrip("/")
        self.key_env = cfg["key_env"]

    def _key(self) -> str:
        return os.environ.get(self.key_env, "").strip()

    def available(self) -> bool:
        return bool(self._key()) and httpx is not None

    async def complete(self, model: str, messages: List[dict], **opts) -> str:
        if httpx is None:  # pragma: no cover
            raise ProviderError("httpx no está instalado")
        key = self._key()
        if not key:
            raise ProviderError(f"falta {self.key_env}")
        body = {"model": model, "messages": messages}
        for k in ("temperature", "top_p", "max_tokens"):
            if k in opts:
                body[k] = opts[k]
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
            if resp.status_code == 429:
                raise RateLimitError(f"{self.name} 429")
            if resp.status_code >= 400:
                raise ProviderError(f"{self.name} {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"{self.name}: respuesta sin choices")
        return (choices[0].get("message") or {}).get("content", "").strip()
