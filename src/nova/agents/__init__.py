"""Agentes de NOVA.

Grupo Local (reales, en `DEFAULT_AGENTS`): `RespuestasRapidasAgent`,
`SentinelaAgent` (visión), `MemoriaContextoAgent` (memoria de trabajo).

Grupo Nube: la "empresa" (PMO + transversales + áreas) se construye **data-driven**
desde `config/teams.yaml` con el `SubAgent` genérico (ver `core/empresa.py`); no se
hand-codean los sub-agentes.
"""

from .memoria import MemoriaContextoAgent
from .respuestas_rapidas import RespuestasRapidasAgent
from .sentinela import SentinelaAgent
from .sub_agent import SubAgent

# Agentes locales que el Conductor instancia y registra por defecto.
DEFAULT_AGENTS = (
    RespuestasRapidasAgent,
    SentinelaAgent,
    MemoriaContextoAgent,
)

__all__ = [
    "RespuestasRapidasAgent",
    "SentinelaAgent",
    "MemoriaContextoAgent",
    "SubAgent",
    "DEFAULT_AGENTS",
]
