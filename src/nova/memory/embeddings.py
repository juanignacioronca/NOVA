"""Embeddings locales: Ollama (`nomic-embed-text`) con **fallback stub** determinista.

El stub es un bag-of-tokens hasheado y normalizado: da similitud por solapamiento
léxico (suficiente a escala personal y para correr offline/tests sin modelos).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import unicodedata
from typing import List

STUB_DIM = 256


def _norm(texto: str) -> str:
    d = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in d if unicodedata.category(c) != "Mn")


def tokens(texto: str) -> List[str]:
    """Tokeniza con un stemming crudo (saca la 's' final) para que singular/plural
    matcheen (ej. 'trekking' ~ 'trekkings')."""
    out = []
    for w in re.findall(r"[a-z0-9]+", _norm(texto)):
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.append(w)
    return out


def stub_embed(texto: str, dim: int = STUB_DIM) -> List[float]:
    """Vector determinista por bag-of-tokens hasheado y L2-normalizado."""
    vec = [0.0] * dim
    for tok in tokens(texto):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0
        vec[(h // dim) % dim] += 0.5  # segunda proyección, baja colisiones
    norma = math.sqrt(sum(x * x for x in vec))
    return [x / norma for x in vec] if norma else vec


def _force_stub() -> bool:
    return os.environ.get("NOVA_FORCE_STUB", "").lower() in ("1", "true", "yes")


class Embedder:
    def __init__(self, model: str = "nomic-embed-text", dim: int = STUB_DIM, host: str = None) -> None:
        self.model = model
        self.dim = dim
        self.host = host
        # Qué backend produjo el último embedding ("ollama" | "stub"). Lo usa la
        # búsqueda semántica para elegir un umbral de relevancia acorde.
        self.last_via: str = "stub"

    async def embed(self, texto: str) -> List[float]:
        if _force_stub():
            self.last_via = "stub"
            return stub_embed(texto, self.dim)
        try:
            vec = await self._ollama(texto)
            self.last_via = "ollama"
            return vec
        except Exception:
            self.last_via = "stub"
            return stub_embed(texto, self.dim)  # degrada offline

    async def _ollama(self, texto: str) -> List[float]:
        import httpx

        host = (self.host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(f"{host}/api/embeddings", json={"model": self.model, "prompt": texto})
            resp.raise_for_status()
            emb = resp.json().get("embedding")
        if not emb:
            raise RuntimeError("ollama no devolvió embedding")
        return [float(x) for x in emb]
