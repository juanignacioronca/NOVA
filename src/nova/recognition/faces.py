"""Reconocimiento de cara: InsightFace/ArcFace (onnxruntime-cpu, 512-d) como
primario, vía import perezoso; stub determinista si no está. Como Face ID en
concepto: detecta → embeb → coseno contra los enrolados. Sin GPU ni entrenamiento.
"""

from __future__ import annotations

from typing import List, Optional

from ..memory.store import MemoryStore
from .base import Biometrico

FACE_UMBRAL = 0.45
FACE_STUB_DIM = 128  # dim del stub (el real ArcFace devuelve 512)

_app = None  # FaceAnalysis cacheada


def _get_app():
    global _app
    if _app is None:
        from insightface.app import FaceAnalysis  # lazy

        app = FaceAnalysis(providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _app = app
    return _app


def embed_real(data: bytes) -> List[float]:
    import cv2  # lazy
    import numpy as np  # lazy

    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise RuntimeError("imagen ilegible")
    caras = _get_app().get(img)
    if not caras:
        raise RuntimeError("no se detectó cara")
    return [float(x) for x in caras[0].normed_embedding]


class FaceRecognizer(Biometrico):
    def __init__(self, store: MemoryStore, umbral: float = FACE_UMBRAL) -> None:
        super().__init__(
            store, kind="cara", props_key="face_vec",
            embed_real=embed_real, dim=FACE_STUB_DIM, umbral=umbral,
        )
