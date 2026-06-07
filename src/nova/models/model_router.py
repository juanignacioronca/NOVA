"""Capa de modelos: único punto de entrada.

`complete(agent, messages, **opts)` resuelve `proveedor:modelo` desde
`config/models.yaml`, llama al cliente correcto, maneja 429 con backoff
exponencial, cae al `fallback` y, si nada está disponible y
`stub_if_unavailable` está activo, devuelve una respuesta determinista (stub)
para poder testear el cableado sin claves ni modelos. Ver CLAUDE.md §5.
"""

from __future__ import annotations

import asyncio
from typing import Dict, List, Optional, Tuple

import yaml

from ..paths import MODELS_YAML
from .providers.base import Provider, ProviderError, RateLimitError, last_user_text
from .providers.gemini_client import GeminiClient
from .providers.ollama_client import OllamaClient
from .providers.openai_compatible import PROVIDERS as OPENAI_PROVIDERS
from .providers.openai_compatible import OpenAICompatibleClient

# Backoff ante 429 (segundos). Solo se usa si un proveedor real responde 429.
BACKOFF_SECONDS = (1, 2, 4, 8)
_STUB_MAX = 160

_config: Optional[dict] = None
_providers: Dict[str, Provider] = {}


def load_config(force: bool = False) -> dict:
    """Lee y cachea `config/models.yaml`."""
    global _config
    if _config is None or force:
        with open(MODELS_YAML, "r", encoding="utf-8") as fh:
            _config = yaml.safe_load(fh) or {}
    return _config


def _defaults() -> dict:
    return load_config().get("defaults", {}) or {}


def _resolve_spec(agent: str) -> Tuple[str, str]:
    """Devuelve (proveedor, modelo) para un agente. Si el agente no está en el
    roster, usa `defaults.fallback`."""
    agents = load_config().get("agents", {}) or {}
    spec = agents.get(agent) or _defaults().get("fallback", "ollama:qwen2.5:7b")
    provider, _, model = spec.partition(":")
    return provider.strip(), model.strip()


def model_for(agent: str) -> str:
    """Spec configurado (`proveedor:modelo`) del agente — útil para el registro."""
    provider, model = _resolve_spec(agent)
    return f"{provider}:{model}"


def _get_provider(name: str) -> Optional[Provider]:
    """Instancia (cacheada) del cliente de un proveedor."""
    if name in _providers:
        return _providers[name]
    if name == "ollama":
        client: Optional[Provider] = OllamaClient()
    elif name == "gemini":
        client = GeminiClient()
    elif name in OPENAI_PROVIDERS:
        client = OpenAICompatibleClient(name)
    else:
        client = None
    if client is not None:
        _providers[name] = client
    return client


def _stub(agent: str, messages: List[dict]) -> str:
    """Respuesta determinista para correr sin claves ni modelos."""
    summary = " ".join(last_user_text(messages).split())
    if len(summary) > _STUB_MAX:
        summary = summary[:_STUB_MAX].rstrip() + "…"
    return f"[stub:{agent}] {summary}"


async def _attempt(provider: Provider, model: str, messages: List[dict], opts: dict) -> str:
    """Llama al proveedor con retry/backoff exponencial ante 429."""
    last_exc: Optional[Exception] = None
    for delay in (0,) + BACKOFF_SECONDS:
        if delay:
            await asyncio.sleep(delay)
        try:
            return await provider.complete(model, messages, **opts)
        except RateLimitError as exc:
            last_exc = exc  # reintentar tras backoff
        except ProviderError as exc:
            raise exc  # otros errores no se reintentan
    raise last_exc or ProviderError("429 persistente")


async def complete(agent: str, messages: List[dict], **opts) -> str:
    """Punto de entrada de la capa de modelos.

    Orden: proveedor del agente → (429: backoff) → `fallback` → stub.
    """
    provider_name, model = _resolve_spec(agent)
    provider = _get_provider(provider_name)

    if provider is not None and provider.available():
        try:
            return await _attempt(provider, model, messages, opts)
        except ProviderError:
            pass  # cae a fallback

    # Fallback (otro proveedor / local)
    fb_name, fb_model = _resolve_spec("__fallback__")  # no existe → usa defaults.fallback
    fb = _get_provider(fb_name)
    if fb is not None and fb is not provider and fb.available():
        try:
            return await _attempt(fb, fb_model, messages, opts)
        except ProviderError:
            pass

    # Stub (cableado sin claves ni modelos)
    if _defaults().get("stub_if_unavailable", True):
        return _stub(agent, messages)

    raise ProviderError(
        f"sin proveedor disponible para '{agent}' y stub_if_unavailable=false"
    )
