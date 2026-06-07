"""Registro JSONL: una línea por acción de agente. Es el insumo de la auditoría
(ver CLAUDE.md §8, §9). Nota: este subpaquete se llama `nova.logging`; no pisa
al módulo estándar `logging` (los imports absolutos lo resuelven bien).
"""

from .registro import Registro, log

__all__ = ["Registro", "log"]
