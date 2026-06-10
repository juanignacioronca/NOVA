"""Agentes de NOVA.

Grupo Local (reales): `RespuestasRapidasAgent`, `SentinelaAgent` (visión),
`MemoriaContextoAgent` (memoria de trabajo). Grupo Nube (aún stubs): `PMOAgent`,
`EstrategiaInvestigadorAgent`. Los equipos de nube completos llegan más adelante.
"""

from .estrategia import EstrategiaInvestigadorAgent
from .memoria import MemoriaContextoAgent
from .pmo import PMOAgent
from .respuestas_rapidas import RespuestasRapidasAgent
from .sentinela import SentinelaAgent

# Agentes que el Conductor instancia y registra por defecto.
DEFAULT_AGENTS = (
    RespuestasRapidasAgent,
    PMOAgent,
    EstrategiaInvestigadorAgent,
    SentinelaAgent,
    MemoriaContextoAgent,
)

__all__ = [
    "RespuestasRapidasAgent",
    "PMOAgent",
    "EstrategiaInvestigadorAgent",
    "SentinelaAgent",
    "MemoriaContextoAgent",
    "DEFAULT_AGENTS",
]
