"""Wrapper fino para Ollama (local, /v1, clave dummy) sobre el cliente
OpenAI-compatible, más un helper para listar los modelos pulled (/api/tags).
"""

from __future__ import annotations

from typing import List

from .openai_compatible import OpenAICompatibleClient, _ollama_host

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


class OllamaClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        super().__init__("ollama")


def ollama_models(timeout: float = 1.0) -> List[str]:
    """Modelos pulled en Ollama (GET /api/tags). [] si no está disponible."""
    if httpx is None:  # pragma: no cover
        return []
    try:
        resp = httpx.get(f"{_ollama_host()}/api/tags", timeout=timeout)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
