"""Tipos de mensaje que circulan por el núcleo: `Task` y `Result`."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class Task:
    """Unidad de trabajo que el Conductor arma y enruta a un agente/equipo."""

    goal: str
    intent: str = ""
    entities: Dict[str, Any] = field(default_factory=dict)
    complexity: str = "simple"  # "simple" | "complejo"
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: float = field(default_factory=time.time)

    def to_payload(self) -> Dict[str, Any]:
        """Forma serializable para mandar por el `MessageBus`."""
        return {
            "id": self.id,
            "goal": self.goal,
            "intent": self.intent,
            "entities": dict(self.entities),
            "complexity": self.complexity,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_payload(cls, data: Dict[str, Any]) -> "Task":
        return cls(
            goal=data.get("goal", ""),
            intent=data.get("intent", ""),
            entities=dict(data.get("entities", {})),
            complexity=data.get("complexity", "simple"),
            payload=dict(data.get("payload", {})),
            id=data.get("id", uuid.uuid4().hex[:8]),
        )


@dataclass
class Result:
    """Salida de un agente. `text` es lo que el Conductor integra/responde."""

    ok: bool
    text: str
    agent: str = ""
    data: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {"ok": self.ok, "text": self.text, "agent": self.agent, "data": dict(self.data)}

    @classmethod
    def from_payload(cls, data: Dict[str, Any]) -> "Result":
        return cls(
            ok=bool(data.get("ok", True)),
            text=data.get("text", ""),
            agent=data.get("agent", ""),
            data=dict(data.get("data", {})),
        )
