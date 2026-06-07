"""Conductor: comprensión + orquestación + respuesta.

Única cara que habla con el usuario (ver CLAUDE.md §3). `attend(user_text)`:
  1. **comprende** (intención + entidades) y **clasifica complejidad**,
  2. **rutea**: simple → Grupo Local; complejo → Grupo Nube (PMO, vía bus),
  3. **responde** integrando el resultado.
En cada paso escribe un registro y agrega un evento al WorldState.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from ..agents import DEFAULT_AGENTS
from ..logging.registro import Registro
from ..models import model_router
from .message_bus import MessageBus
from .registry import Registry
from .task import Result, Task
from .world_state import WorldState

# Heurística de complejidad (cuando no hay modelo real que clasifique).
COMPLEX_KEYWORDS = (
    "organiz", "planif", "plane", "research", "investig", "compar",
    "estrateg", "finde", "viaje", "itinerario", "presupuesto", "analiz",
)
SIMPLE_KEYWORDS = (
    "timer", "temporizador", "alarma", "clima", "tiempo", "weather",
    "calendario", "agenda", "hora", "recordar", "recordatorio",
    "recuerda", "recorda", "remind",
)
# keyword → etiqueta de intención (se evalúa en orden).
INTENT_MAP = (
    (("timer", "temporizador", "alarma"), "set_timer"),
    (("clima", "weather", "tiempo"), "weather"),
    (("recordar", "recordatorio", "recuerda", "recorda", "remind"), "reminder"),
    (("calendario", "agenda", "hora"), "calendar"),
    (("organiz", "planif", "plane"), "plan"),
    (("research", "investig"), "research"),
    (("compar", "analiz", "estrateg", "finde", "viaje", "itinerario", "presupuesto"), "strategy"),
)
_DURATION_RE = re.compile(r"(\d+)\s*(horas?|minutos?|min|m|segundos?|seg|s)\b")


def _norm(text: str) -> str:
    """Minúsculas sin acentos, para matchear keywords de forma robusta."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


class Conductor:
    def __init__(
        self,
        registry: Optional[Registry] = None,
        bus: Optional[MessageBus] = None,
        world: Optional[WorldState] = None,
        registro: Optional[Registro] = None,
    ) -> None:
        self.bus = bus or MessageBus()
        self.world = world or WorldState()
        self.registro = registro or Registro()
        self.registry = registry or Registry()
        self.understand_model = "conductor_simple"
        self.integrate_model = "conductor_complex"
        self.last_run: Dict[str, Any] = {}
        self._ensure_agents()

    def _ensure_agents(self) -> None:
        """Instancia y registra los agentes stub (conectados al mismo bus)."""
        for cls in DEFAULT_AGENTS:
            if self.registry.get(cls.name) is None:
                agent = cls(bus=self.bus, world=self.world, registro=self.registro)
                self.registry.add(agent)

    # --- paso 1: comprensión ---
    def _classify(self, user_text: str) -> Tuple[str, str, Dict[str, Any]]:
        """Heurística: intención, complejidad y entidades."""
        norm = _norm(user_text)
        complexity = "complejo" if any(k in norm for k in COMPLEX_KEYWORDS) else "simple"
        intent = "general"
        for keys, label in INTENT_MAP:
            if any(k in norm for k in keys):
                intent = label
                break
        entities: Dict[str, Any] = {}
        match = _DURATION_RE.search(norm)
        if match:
            entities["duration"] = match.group(1)
            entities["unit"] = match.group(2)
        return intent, complexity, entities

    async def _understand(self, user_text: str) -> Dict[str, Any]:
        intent, complexity, entities = self._classify(user_text)
        # El modelo `conductor_simple` produce una nota de comprensión (best-effort).
        try:
            note = await model_router.complete(
                self.understand_model,
                [
                    {"role": "system", "content": "Resumí en una frase qué pide el usuario."},
                    {"role": "user", "content": user_text},
                ],
            )
        except Exception:  # pragma: no cover - el stub no falla
            note = ""
        return {"intent": intent, "complexity": complexity, "entities": entities, "note": note}

    # --- paso 3 (helper): integración ---
    async def _integrate(self, user_text: str, pmo: Result) -> str:
        """Arma la respuesta final a partir del resultado del PMO.

        Con un modelo real, el `conductor_complex` integra; en stub, cae a una
        redacción determinista (el plan estructurado del PMO).
        """
        try:
            woven = await model_router.complete(
                self.integrate_model,
                [
                    {"role": "system", "content": "Integrá el plan del equipo en una respuesta clara al usuario."},
                    {"role": "user", "content": f"Pedido: {user_text}\n\n{pmo.text}"},
                ],
            )
        except Exception:  # pragma: no cover
            woven = ""
        if woven and not woven.startswith("[stub:"):
            return woven
        return pmo.text

    # --- orquestación ---
    async def attend(self, user_text: str) -> str:
        # Paso 1 — comprensión
        u = await self._understand(user_text)
        intent, complexity, entities = u["intent"], u["complexity"], u["entities"]
        self.registro.log(
            agente="conductor",
            grupo="local",
            tarea=user_text,
            decision=f"comprension intent={intent} complejidad={complexity} entities={entities}",
            modelo=model_router.model_for(self.understand_model),
            resultado_breve=u["note"] or f"intent={intent}",
        )
        await self.world.append_event(
            {"agente": "conductor", "fase": "comprension", "intent": intent, "complejidad": complexity}
        )

        task = Task(goal=user_text, intent=intent, entities=entities, complexity=complexity)

        # Paso 2 — ruteo
        if complexity == "simple":
            agente_local = self.registry.get("respuestas_rapidas")
            result = await agente_local.handle(task)  # delegación directa (local)
            final = result.text
            agents_involved = ["respuestas_rapidas"]
            ruta = "local"
            decision = "ruteo → Grupo Local (respuestas_rapidas)"
        else:
            reply = await self.bus.request("pmo", task.to_payload())  # vía bus
            pmo_result = Result.from_payload(reply)
            final = await self._integrate(user_text, pmo_result)
            agents_involved = ["pmo", "estrategia_investigador"]
            ruta = "nube"
            decision = "ruteo → Grupo Nube (PMO → Estrategia)"

        self.registro.log(
            agente="conductor",
            grupo=ruta,
            tarea=user_text,
            decision=decision,
            modelo=model_router.model_for(self.understand_model),
            resultado_breve=", ".join(agents_involved),
        )
        await self.world.append_event(
            {"agente": "conductor", "fase": "ruteo", "ruta": ruta, "agentes": agents_involved}
        )

        # Paso 3 — respuesta
        path = self.registro.log(
            agente="conductor",
            grupo=ruta,
            tarea=user_text,
            decision="respuesta final entregada",
            modelo=model_router.model_for(self.integrate_model if ruta == "nube" else self.understand_model),
            resultado_breve=final,
        )
        await self.world.append_event({"agente": "conductor", "fase": "respuesta", "ruta": ruta})

        self.last_run = {
            "user_text": user_text,
            "intent": intent,
            "complexity": complexity,
            "entities": entities,
            "understanding_note": u["note"],
            "route": ruta,
            "agents": agents_involved,
            "final": final,
            "log_path": str(path),
        }
        return final
