"""Salidas de NOVA: voz (Piper) + pantalla. Gestor de salidas en modo voz/texto.
La librería de voz se importa de forma perezosa y degrada si no está. Barge-in
(cortar cuando el usuario habla) queda anotado para Prompt 7.
"""

from .voz import OutputManager, VozTTS

__all__ = ["OutputManager", "VozTTS"]
