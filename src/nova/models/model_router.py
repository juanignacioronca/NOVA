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


def _iter_specs(value) -> List[str]:
    """Normaliza el valor de un agente: string → [spec]; lista → [spec, ...]."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return [str(value)]


def _agent_specs(agent: str) -> List[Tuple[str, str]]:
    """Cadena (proveedor, modelo) configurada para el agente (primario + fallbacks
    por-agente). Si no está en el roster, usa el `defaults.fallback`."""
    agents = load_config().get("agents", {}) or {}
    specs = _iter_specs(agents.get(agent))
    if not specs:
        specs = [_defaults().get("fallback", "ollama:qwen2.5:7b")]
    return [_split_spec(s) for s in specs]


def _resolve_spec(agent: str) -> Tuple[str, str]:
    """(proveedor, modelo) primario del agente."""
    return _agent_specs(agent)[0]


def _fallback_spec() -> Tuple[str, str]:
    return _split_spec(_defaults().get("fallback", "ollama:qwen2.5:7b"))


def model_for(agent: str) -> str:
    """Spec configurado (`proveedor:modelo`) del agente."""
    provider, model = _resolve_spec(agent)
    return f"{provider}:{model}"


def sample_model(provider: str) -> Optional[str]:
    """Un modelo representativo de un proveedor (para `doctor`)."""
    agents = load_config().get("agents", {}) or {}
    for value in agents.values():
        for spec in _iter_specs(value):
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
    """Como `complete`, pero devuelve qué proveedor/modelo respondió de verdad.

    Recorre la cadena: specs del agente (primario + fallbacks por-agente) →
    `defaults.fallback` (Ollama) → stub. Salta los no disponibles (sin clave/host
    caído) sin reintentar en vano; reintenta con backoff solo ante 429/5xx/timeout.
    """
    chain = list(_agent_specs(agent))
    fb = _fallback_spec()
    if fb not in chain:
        chain.append(fb)

    tried: Set[Tuple[str, str]] = set()
    for idx, (prov_name, model) in enumerate(chain):
        if (prov_name, model) in tried:
            continue
        tried.add((prov_name, model))
        provider = _get_provider(prov_name)
        if provider is None:
            continue
        if not provider.available():
            if prov_name != "ollama":
                _notice(prov_name, "sin clave o no disponible; salto al siguiente")
            continue
        try:
            text = await _attempt(provider, model, messages, opts)
            return Completion(text, prov_name, model, "primary" if idx == 0 else "fallback")
        except ProviderError as exc:
            _notice(prov_name, f"falló ({exc}); siguiente en la cadena")

    # Stub (último recurso).
    if _defaults().get("stub_if_unavailable", True):
        return Completion(_stub(agent, messages), "stub", agent, "stub")

    raise ProviderUnavailable(
        f"sin proveedor disponible para '{agent}' y stub_if_unavailable=false"
    )


async def complete(agent: str, messages: List[dict], **opts) -> str:
    """Punto de entrada clásico: devuelve solo el texto."""
    result = await complete_meta(agent, messages, **opts)
    return result.text
