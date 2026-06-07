"""Cliente Gemini (API nativa generateContent). Clave: GEMINI_API_KEY."""

from __future__ import annotations

import os
from typing import List

from .base import Provider, ProviderError, RateLimitError

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _to_gemini(messages: List[dict]):
    """Convierte mensajes estilo chat a `contents` + `systemInstruction`."""
    contents = []
    system_parts = []
    for msg in messages:
        role = (msg or {}).get("role", "user")
        text = str((msg or {}).get("content", ""))
        if role == "system":
            system_parts.append(text)
            continue
        gem_role = "model" if role == "assistant" else "user"
        contents.append({"role": gem_role, "parts": [{"text": text}]})
    system = {"parts": [{"text": "\n".join(system_parts)}]} if system_parts else None
    return contents, system


class GeminiClient(Provider):
    name = "gemini"

    def _key(self) -> str:
        return os.environ.get("GEMINI_API_KEY", "").strip()

    def available(self) -> bool:
        return bool(self._key()) and httpx is not None

    async def complete(self, model: str, messages: List[dict], **opts) -> str:
        if httpx is None:  # pragma: no cover
            raise ProviderError("httpx no está instalado")
        key = self._key()
        if not key:
            raise ProviderError("falta GEMINI_API_KEY")
        contents, system = _to_gemini(messages)
        body = {"contents": contents}
        if system:
            body["systemInstruction"] = system
        gen_cfg = {}
        if "temperature" in opts:
            gen_cfg["temperature"] = opts["temperature"]
        if "max_tokens" in opts:
            gen_cfg["maxOutputTokens"] = opts["max_tokens"]
        if gen_cfg:
            body["generationConfig"] = gen_cfg
        url = f"{BASE_URL}/models/{model}:generateContent"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, params={"key": key}, json=body)
            if resp.status_code == 429:
                raise RateLimitError("gemini 429")
            if resp.status_code >= 400:
                raise ProviderError(f"gemini {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderError("gemini: respuesta sin candidates")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        return "".join(p.get("text", "") for p in parts).strip()
