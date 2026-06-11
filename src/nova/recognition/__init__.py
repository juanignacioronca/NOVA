"""Reconocimiento de personas (cara + voz), TODO LOCAL.

No se entrena un modelo propio: se usan **embeddings** de modelos pre-entrenados
(la cara/voz → vector), se **enrola** a la persona con pocas muestras (promedio) y
al runtime se compara por **coseno**. Los vectores viven en el **nodo de la persona
de la memoria** (Prompt 8). Biométricos = datos sensibles → nunca salen del equipo
(ver CLAUDE.md §11). Libs pesadas con import perezoso + stub determinista.
"""

from .base import Biometrico, promedio, stub_vector
from .faces import FaceRecognizer
from .presencia import aviso_presencia, detectar_presencia, pendientes_de
from .voices import VoiceRecognizer

__all__ = [
    "Biometrico", "promedio", "stub_vector",
    "FaceRecognizer", "VoiceRecognizer",
    "detectar_presencia", "pendientes_de", "aviso_presencia",
]
