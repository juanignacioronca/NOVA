"""Cliente OpenAI-compatible ÚNICO para TODOS los proveedores.

Cambia solo `base_url` + clave (y headers extra para OpenRouter). Sirve Ollama
(local, /v1, clave dummy), Groq, OpenRouter, DeepSeek y Gemini (su endpoint
compatible). Endpoint estándar: POST `{base_url}/chat/completions`.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import (
    Provider,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    RateLimitError,
    ServerError,
)

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

KNOWN_PROVIDERS = ("ollama", "groq", "openrouter", "deepseek", "gemini")


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    key_env: Optional[str]  # None = no requiere clave (Ollama)
    extra_headers: Dict[str, str] = field(default_factory=dict)


def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def provider_config(name: str) -> ProviderConfig:
    """Resuelve base_url + clave + headers para un proveedor."""
    key = name.lower()
    if key == "ollama":
        return ProviderConfig("ollama", f"{_ollama_host()}/v1", None)
    if key == "groq":
        return ProviderConfig("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY")
    if key == "openrouter":
        return ProviderConfig(
            "openrouter",
            "https://openrouter.ai/api/v1",
            "OPENROUTER_API_KEY",
            {"HTTP-Referer": "https://nova.local", "X-Title": "NOVA"},
        )
    if key == "deepseek":
        return ProviderConfig("deepseek", "https://api.deepseek.com/v1", "DEEPSEEK_API_KEY")
    if key == "gemini":
        return ProviderConfig(
            "gemini", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"
        )
    raise ProviderError(f"proveedor desconocido: {name}")


PROBE_TTL_SECONDS = 20.0  # revalidar la sonda de Ollama (puede arrancar/caerse después que NOVA)


class OpenAICompatibleClient(Provider):
    """Un mismo cliente async para todos los proveedores OpenAI-compatibles."""

    def __init__(self, provider: str) -> None:
        cfg = provider_config(provider)
        self.name = cfg.name
        self.base_url = cfg.base_url
        self.key_env = cfg.key_env
        self.extra_headers = dict(cfg.extra_headers)
        self._ollama_ok: Optional[bool] = None  # cache de la sonda local
        self._ollama_probed_at: float = 0.0

    def _key(self) -> str:
        if self.key_env is None:
            return "ollama"  # dummy: Ollama no valida la clave
        return os.environ.get(self.key_env, "").strip()

    def available(self) -> bool:
        if httpx is None:  # pragma: no cover
            return False
        if self.name == "ollama":
            return self._probe_ollama()
        return bool(self._key())

    def _probe_ollama(self) -> bool:
        """Sonda barata a /api/tags, cacheada con TTL (Ollama puede levantarse o
        caerse mientras NOVA corre; un cache eterno lo dejaba pegado al estado viejo)."""
        ahora = time.monotonic()
        if self._ollama_ok is not None and (ahora - self._ollama_probed_at) < PROBE_TTL_SECONDS:
            return self._ollama_ok
        try:
            host = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
            resp = httpx.get(f"{host}/api/tags", timeout=0.5)
            self._ollama_ok = resp.status_code == 200
        except Exception:
            self._ollama_ok = False
        self._ollama_probed_at = ahora
        return self._ollama_ok

    async def complete(self, model: str, messages: List[dict], **opts) -> str:
        if httpx is None:  # pragma: no cover
            raise ProviderError("httpx no está instalado")
        key = self._key()
        if self.key_env is not None and not key:
            raise ProviderUnavailable(f"falta {self.key_env}")

        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        headers.update(self.extra_headers)
        body: Dict[str, object] = {"model": model, "messages": messages}
        for k in ("temperature", "top_p", "max_tokens", "response_format"):
            if k in opts and opts[k] is not None:
                body[k] = opts[k]
        timeout = float(opts.get("timeout", 60.0))

        resp = await self._post(body, headers, timeout)
        if resp.status_code == 400 and "response_format" in body:
            # No todos los modelos soportan modo JSON → reintento sin forzarlo.
            body.pop("response_format")
            resp = await self._post(body, headers, timeout)

        if resp.status_code == 429:
            raise RateLimitError(f"{self.name} 429")
        if resp.status_code >= 500:
            raise ServerError(f"{self.name} {resp.status_code}")
        if resp.status_code >= 400:
            raise ProviderError(f"{self.name} {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"{self.name}: respuesta sin choices")
        return (choices[0].get("message") or {}).get("content", "").strip()

    async def _post(self, body: Dict[str, object], headers: Dict[str, str], timeout: float):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await client.post(
                    f"{self.base_url}/chat/completions", json=body, headers=headers
                )
        except httpx.TimeoutException as exc:
            raise ProviderTimeout(f"{self.name}: timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.name}: error de red: {exc}") from exc
