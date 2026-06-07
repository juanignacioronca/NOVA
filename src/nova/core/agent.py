"""`BaseAgent`: interfaz común de todo agente (ver CLAUDE.md §8).

Cada agente declara `name`, `group` (`local`|`nube`), `model_key` (clave en
`models.yaml`) y `skills`. Implementa `handle(task) -> Result`. Se conecta al
`MessageBus` para enviar/recibir, y piensa vía `model_router` con `think()`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..models import model_router
from .message_bus import MessageBus
from .task import Result, Task
from .world_state import WorldState


class BaseAgent:
    # Se sobreescriben en cada subclase.
    name: str = "base"
    group: str = "local"          # "local" | "nube"
    model_key: str = ""           # clave en config/models.yaml
    skills: List[str] = []

    def __init__(
        self,
        bus: Optional[MessageBus] = None,
        world: Optional[WorldState] = None,
        registro: Optional[Any] = None,
    ) -> None:
        self.bus = bus
        self.world = world
        self.registro = registro
        if bus is not None:
            self.bind(bus)

    # --- conexión al bus ---
    def bind(self, bus: MessageBus) -> None:
        """Registra este agente como handler de su `name` en el bus."""
        self.bus = bus
        bus.register_handler(self.name, self.on_request)

    async def on_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Entrada desde el bus: reconstruye la Task, ejecuta y serializa."""
        result = await self.handle(Task.from_payload(payload))
        return result.to_payload()

    async def request(self, to: str, payload: Dict[str, Any]) -> Any:
        """Request crudo a otro agente por el bus."""
        if self.bus is None:
            raise RuntimeError(f"{self.name}: no está conectado a un MessageBus")
        return await self.bus.request(to, payload)

    async def ask(self, to: str, task: Task) -> Result:
        """Pide a otro agente que resuelva una Task y devuelve su Result."""
        reply = await self.request(to, task.to_payload())
        return Result.from_payload(reply)

    # --- modelos ---
    async def think(self, messages: List[dict], **opts) -> str:
        """Llama a la capa de modelos con el `model_key` de este agente."""
        return await model_router.complete(self.model_key, messages, **opts)

    # --- registro ---
    def log(self, tarea: str, decision: str, resultado_breve: str) -> None:
        """Escribe una línea de registro si hay un `Registro` conectado."""
        if self.registro is not None:
            self.registro.log(
                agente=self.name,
                grupo=self.group,
                tarea=tarea,
                decision=decision,
                modelo=model_router.model_for(self.model_key) if self.model_key else "-",
                resultado_breve=resultado_breve,
            )

    # --- contrato ---
    async def handle(self, task: Task) -> Result:  # pragma: no cover - abstracto
        raise NotImplementedError(f"{self.name}.handle no implementado")

    def __repr__(self) -> str:  # pragma: no cover - cosmético
        return f"<{type(self).__name__} name={self.name!r} group={self.group!r}>"
