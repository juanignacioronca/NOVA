"""Reconocimiento de voz (speaker embeddings): Resemblyzer (256-d) vía import
perezoso; stub determinista si no está. Combinado con la cara da más confianza.
"""

from __future__ import annotations

import io
from typing import List

from ..memory.store import MemoryStore
from .base import Biometrico

VOICE_UMBRAL = 0.40
VOICE_STUB_DIM = 128  # dim del stub (Resemblyzer real devuelve 256)

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder  # lazy

        _encoder = VoiceEncoder()
    return _encoder


def embed_real(data: bytes) -> List[float]:
    import soundfile as sf  # lazy
    from resemblyzer import preprocess_wav  # lazy

    wav, sr = sf.read(io.BytesIO(data))
    emb = _get_encoder().embed_utterance(preprocess_wav(wav, source_sr=sr))
    return [float(x) for x in emb]


class VoiceRecognizer(Biometrico):
    def __init__(self, store: MemoryStore, umbral: float = VOICE_UMBRAL) -> None:
        super().__init__(
            store, kind="voz", props_key="voice_vec",
            embed_real=embed_real, dim=VOICE_STUB_DIM, umbral=umbral,
        )
