"""Agentes stub del esqueleto.

- `RespuestasRapidasAgent` (local) — resuelve lo simple, corto.
- `PMOAgent` (nube) — descompone el objetivo y consulta a Estrategia por el bus.
- `EstrategiaInvestigadorAgent` (nube) — devuelve un "hallazgo".

La lógica real (equipos completos, herramientas) llega en fases siguientes.
"""

from .estrategia import EstrategiaInvestigadorAgent
from .pmo import PMOAgent
from .respuestas_rapidas import RespuestasRapidasAgent

# Agentes que el Conductor instancia por defecto.
DEFAULT_AGENTS = (RespuestasRapidasAgent, PMOAgent, EstrategiaInvestigadorAgent)

__all__ = [
    "RespuestasRapidasAgent",
    "PMOAgent",
    "EstrategiaInvestigadorAgent",
    "DEFAULT_AGENTS",
]
