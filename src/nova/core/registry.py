"""Patrón Registry: registrar y descubrir agentes y herramientas por `name`,
`group` y `skills`. Unidad central del sistema (ver CLAUDE.md §2, §8).
"""

from __future__ import annotations

from typing import Dict, List, Optional

# Registro de CLASES de agente para descubrimiento global vía decorador.
# (Las instancias vivas se manejan con `Registry.add` más abajo.)
_AGENT_CLASSES: Dict[str, type] = {}


def register(cls: type) -> type:
    """Decorador: marca una clase de agente para descubrirla por su nombre.

    Uso::

        @register
        class RespuestasRapidasAgent(BaseAgent): ...
    """
    _AGENT_CLASSES[cls.__name__] = cls
    return cls


def agent_classes() -> Dict[str, type]:
    """Clases de agente registradas vía `@register`."""
    return dict(_AGENT_CLASSES)


class Registry:
    """Contenedor de instancias vivas de agentes y herramientas."""

    def __init__(self) -> None:
        self._agents: Dict[str, object] = {}
        self._tools: Dict[str, object] = {}

    # --- agentes ---
    def add(self, agent: object) -> object:
        """Registra un agente por su `.name`. Devuelve el agente (encadenable)."""
        self._agents[getattr(agent, "name")] = agent
        return agent

    def get(self, name: str) -> Optional[object]:
        return self._agents.get(name)

    def agents(self) -> List[object]:
        return list(self._agents.values())

    def by_group(self, group: str) -> List[object]:
        return [a for a in self._agents.values() if getattr(a, "group", None) == group]

    def by_skill(self, skill: str) -> List[object]:
        return [a for a in self._agents.values() if skill in getattr(a, "skills", [])]

    # --- herramientas ---
    def add_tool(self, tool: object) -> object:
        self._tools[getattr(tool, "name")] = tool
        return tool

    def get_tool(self, name: str) -> Optional[object]:
        return self._tools.get(name)

    def tools(self) -> List[object]:
        return list(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._agents

    def __repr__(self) -> str:  # pragma: no cover - cosmético
        return f"<Registry agents={list(self._agents)} tools={list(self._tools)}>"
