"""Capa de modelos: único punto de entrada.

`complete(agent, messages, **opts)` resuelve `proveedor:modelo` desde
`config/models.yaml` y llama al proveedor REAL. Cadena de resiliencia:

    primario → (429/5xx/timeout: retry backoff 1,2,4,8s) → fallback (Ollama local) → stub

El stub es el **último recurso**: si hay un proveedor real disponible, se usa.
`complete_meta` devuelve además qué `proveedor:modelo` respondió de verdad
(incluyendo si fue fallback o stub), para registrarlo en el JSONL. Ver CLAUDE.md §5.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import yaml

from ..paths import MODELS_YAML
from .providers.base import (
    Provider,
    ProviderError,
    ProviderUnavailable,
    RETRYABLE,
    last_user_text,
)
from .providers.openai_compatible import KNOWN_PROVIDERS, OpenAICompatibleClient

# Backoff ante 429/5xx/timeout (segundos). Solo aplica con proveedores reales.
BACKOFF_SECONDS: Tuple[int, ...] = (1, 2, 4, 8)
_STUB_MAX = 160

_config: Optional[dict] = None
_providers: Dict[str, Provider] = {}
_warned: Set[str] = set()


@dataclass
class Completion:
    """Resultado de una llamada: texto + de qué proveedor/modelo vino realmente."""

    text: str
    provider: str
    model: str
    via: str  # "primary" | "fallback" | "stub"

    @property
    def spec(self) -> str:
        return f"{self.provider}:{self.model}"


# --- config ---
def load_config(force: bool = False) -> dict:
    global _config
    if _config is None or force:
        with open(MODELS_YAML, "r", encoding="utf-8") as fh:
            _config = yaml.safe_load(fh) or {}
    return _config


def _defaults() -> dict:
    return load_config().get("defaults", {}) or {}


def _split_spec(spec: str) -> Tuple[str, str]:
    provider, _, model = spec.partition(":")
    return provider.strip(), model.strip()


def _resolve_spec(agent: str) -> Tuple[str, str]:
    """(proveedor, modelo) del agente; si no está en el roster usa el fallback."""
    agents = load_config().get("agents", {}) or {}
    spec = agents.get(agent) or _defaults().get("fallback", "ollama:qwen2.5:7b")
    return _split_spec(spec)


def _fallback_spec() -> Tuple[str, str]:
    return _split_spec(_defaults().get("fallback", "ollama:qwen2.5:7b"))


def model_for(agent: str) -> str:
    """Spec configurado (`proveedor:modelo`) del agente."""
    provider, model = _resolve_spec(agent)
    return f"{provider}:{model}"


def sample_model(provider: str) -> Optional[str]:
    """Un modelo representativo de un proveedor (para `doctor`)."""
    agents = load_config().get("agents", {}) or {}
    for spec in agents.values():
        prov, model = _split_spec(spec)
        if prov == provider:
            return model
    if provider == _fallback_spec()[0]:
        return _fallback_spec()[1]
    return None


# --- proveedores ---
def _get_provider(name: str) -> Optional[Provider]:
    if name in _providers:
        return _providers[name]
    client: Optional[Provider] = None
    if name in KNOWN_PROVIDERS:
        client = OpenAICompatibleClient(name)
    if client is not None:
        _providers[name] = client
    return client


def _notice(provider: str, msg: str) -> None:
    """Aviso a stderr, una sola vez por proveedor (nunca loggea claves)."""
    if provider in _warned:
        return
    _warned.add(provider)
    print(f"[model_router] {provider}: {msg}", file=sys.stderr)


def _stub(agent: str, messages: List[dict]) -> str:
    summary = " ".join(last_user_text(messages).split())
    if len(summary) > _STUB_MAX:
        summary = summary[:_STUB_MAX].rstrip() + "…"
    return f"[stub:{agent}] {summary}"


async def _attempt(provider: Provider, model: str, messages: List[dict], opts: dict) -> str:
    """Llama al proveedor; reintenta con backoff solo ante errores reintentables."""
    last_exc: Optional[Exception] = None
    for delay in (0,) + BACKOFF_SECONDS:
        if delay:
            await asyncio.sleep(delay)
        try:
            return await provider.complete(model, messages, **opts)
        except RETRYABLE as exc:
            last_exc = exc  # reintentar tras backoff
    raise last_exc or ProviderError("agotados los reintentos")


# --- punto de entrada ---
async def complete_meta(agent: str, messages: List[dict], **opts) -> Completion:
    """Como `complete`, pero devuelve qué proveedor/modelo respondió de verdad."""
    prov_name, model = _resolve_spec(agent)
    primary = _get_provider(prov_name)

    # 1) Primario (si está disponible: hay clave / host arriba).
    if primary is not None and primary.available():
        try:
            text = await _attempt(primary, model, messages, opts)
            return Completion(text, prov_name, model, "primary")
        except ProviderError as exc:
            _notice(prov_name, f"falló ({exc}); usando fallback")
    elif primary is not None and primary.name != "ollama":
        _notice(prov_name, "sin clave o no disponible; salto al fallback")

    # 2) Fallback (Ollama local), si es distinto del primario y está disponible.
    fb_name, fb_model = _fallback_spec()
    fb = _get_provider(fb_name)
    if fb is not None and fb is not primary and fb.available():
        try:
            text = await _attempt(fb, fb_model, messages, opts)
            return Completion(text, fb_name, fb_model, "fallback")
        except ProviderError as exc:
            _notice(fb_name, f"fallback falló ({exc}); usando stub")

    # 3) Stub (último recurso).
    if _defaults().get("stub_if_unavailable", True):
        return Completion(_stub(agent, messages), "stub", agent, "stub")

    raise ProviderUnavailable(
        f"sin proveedor disponible para '{agent}' y stub_if_unavailable=false"
    )


async def complete(agent: str, messages: List[dict], **opts) -> str:
    """Punto de entrada clásico: devuelve solo el texto."""
    result = await complete_meta(agent, messages, **opts)
    return result.text
