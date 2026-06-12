"""Conductor real: comprensión (con modelo) + multimodal + aclaración + síntesis.

`attend(texto, images=None)`:
  1. comprende con `comprension.comprender` (modelo → JSON; stub → heurística),
  2. si falta info o la confianza es baja → **pregunta** (máx. 2 rondas) y retoma,
  3. rutea: imágenes → visión; simple → local; complejo → PMO (bus) + síntesis,
  4. responde, emitiendo una **traza estructurada** (`TraceEvent`) por paso.

Seguridad (CLAUDE.md §11): instrucciones de NOVA solo en `system`; el texto del
usuario es DATO. Un intento de override se marca en la traza y NO se obedece.
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from ..agents import DEFAULT_AGENTS
from ..agents.respuestas_rapidas import _ciudad
from ..logging.registro import Registro
from ..memory import Extractor, MemoryStore, ObsidianVault
from ..models import model_router
from ..tools import register_default_tools
from ..tools.base import RequiereConfirmacion, ToolError
from ..tools.executor import ToolExecutor
from . import comprension, prompts
from .comprension import Intent
from .empresa import Empresa
from .message_bus import MessageBus
from .registry import Registry
from .security import _norm  # normaliza (minúsculas, sin acentos)
from .task import Result, Task
from .trace import EventCallback, TraceEvent, emit
from .world_state import WorldState

MAX_RONDAS_ACLARACION = 2
_AFIRMATIVO = {"si", "dale", "ok", "okay", "confirmo", "confirmar", "hacelo", "hazlo", "obvio", "sip", "yes", "claro", "de una", "adelante"}
_NEGATIVO = {"no", "cancela", "cancelar", "nop", "mejor no", "para", "negativo", "cancelalo"}

# Muestreo por tipo de llamada: charla/respuestas con algo de calidez, síntesis
# más sobria. (Sin esto, el default del proveedor (~0.8) hace alucinar a los 7B/3B.)
_OPTS_DIRECTO = {"temperature": 0.6, "max_tokens": 700}
_OPTS_SINTESIS = {"temperature": 0.4, "max_tokens": 900}

_SALUDOS = (
    "¡Hola! ¿En qué te ayudo?",
    "¡Buenas! Contame, ¿qué necesitás?",
    "¡Hola! Acá estoy, decime.",
)


def _afirmativo(texto: str) -> bool:
    return _norm(texto).strip(" .!") in _AFIRMATIVO


def _negativo(texto: str) -> bool:
    return _norm(texto).strip(" .!") in _NEGATIVO


def _respuesta_charla(texto: str) -> str:
    """Respuesta instantánea (sin modelo) para charla trivial. Un 3B local con
    saludos tiende a alucinar; esto lo resuelve determinístico y en 0 ms."""
    n = _norm(texto)
    if "gracias" in n:
        return "¡De nada! Cualquier cosa, acá estoy."
    if any(k in n for k in ("chau", "adios", "hasta luego", "nos vemos", "hasta manana")):
        return "¡Hasta luego! Acá quedo si necesitás algo."
    if any(k in n for k in ("como estas", "como andas", "como va", "que tal", "todo bien")):
        return "¡Todo en orden por acá! ¿En qué te puedo ayudar?"
    if any(k in n for k in ("estas ahi", "me escuchas", "probando", "test")):
        return "Acá estoy, te escucho. ¿Qué necesitás?"
    return random.choice(_SALUDOS)


class Conductor:
    def __init__(
        self,
        registry: Optional[Registry] = None,
        bus: Optional[MessageBus] = None,
        world: Optional[WorldState] = None,
        registro: Optional[Registro] = None,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        self.bus = bus or MessageBus()
        self.world = world or WorldState()
        self.registro = registro or Registro()
        self.registry = registry or Registry()
        self.on_event = on_event  # consumidor del stream de TraceEvent (REPL/frontend)
        self.understand_model = "conductor_simple"
        self.integrate_model = "conductor_complex"
        self.vision_model = "conductor_vision"
        self.last_run: Dict[str, Any] = {}
        self.last_trace: List[TraceEvent] = []
        self._tarea = ""
        # Memoria de largo plazo (local, $0): motor (grafo+vectores) + bóveda Obsidian.
        self.memory = MemoryStore()
        self.obsidian = ObsidianVault()
        self.extractor = Extractor(self.memory, self.obsidian)
        self._memoria: List[str] = []
        # Capa de herramientas: registra el set y crea el executor (allowlist+permisos).
        register_default_tools(self.registry)
        self.tools = ToolExecutor(self.registry, self.world, self.registro, memory=self.memory)
        self._ensure_agents()
        # Grupo Nube: la "empresa" (PMO + transversales + áreas), data-driven.
        self.empresa = Empresa(self.bus, self.world, self.registro, self.tools, on_event=self.on_event)

    def _ensure_agents(self) -> None:
        for cls in DEFAULT_AGENTS:
            if self.registry.get(cls.name) is None:
                agent = cls(
                    bus=self.bus, world=self.world, registro=self.registro, tools=self.tools
                )
                self.registry.add(agent)

    # --- traza: escribe JSONL (opcional) + emite TraceEvent al stream ---
    async def _emit(
        self,
        etapa: str,
        agente: str,
        grupo: str,
        modelo: str,
        detalle: str,
        estado: str = "ok",
        resultado: str = "",
        escribir_log: bool = True,
    ) -> TraceEvent:
        if escribir_log:
            self.registro.log(
                agente=agente,
                grupo=grupo,
                tarea=self._tarea,
                decision=f"{etapa}: {detalle}",
                modelo=modelo or "-",
                resultado_breve=resultado or detalle,
            )
            await self.world.append_event({"agente": agente, "etapa": etapa, "estado": estado})
        ev = TraceEvent(
            etapa=etapa, agente=agente, grupo=grupo, modelo=modelo or "-", detalle=detalle, estado=estado
        )
        self.last_trace.append(ev)
        await emit(self.on_event, ev)
        return ev

    @staticmethod
    def _formular_pregunta(intent: Intent) -> str:
        if intent.faltantes:
            return "¿" + " y ".join(intent.faltantes) + "?"
        return "¿Podés darme un poco más de detalle para arrancar?"

    # --- síntesis (complejo) ---
    async def _sintetizar(self, texto: str, pmo: Result) -> Tuple[str, str]:
        """Respuesta final coherente a partir del trabajo del PMO (no un pegoteo)."""
        try:
            comp = await model_router.complete_meta(
                self.integrate_model,
                [
                    {"role": "system", "content": prompts.get("sintesis")},
                    {"role": "user", "content": f"Pedido: {texto}\n\nResultados del equipo:\n{pmo.text}"},
                ],
                **_OPTS_SINTESIS,
            )
        except Exception:  # pragma: no cover
            comp = None
        if comp is not None and comp.text and not comp.text.startswith("[stub:"):
            return comp.text, comp.spec
        spec = comp.spec if comp is not None else model_router.model_for(self.integrate_model)
        return pmo.text, spec  # stub → redacción determinista del PMO

    # --- visión ---
    async def _responder_vision(self, texto: str, images: List[str]) -> Tuple[str, str]:
        messages = comprension.mensajes_vision(prompts.get("vision"), texto, images)
        comp = await model_router.complete_meta(self.vision_model, messages)
        return comp.text, comp.spec

    # --- respuesta directa (pedidos simples): el Conductor MISMO responde, con tools ---
    def _agente_conductor(self):
        return SimpleNamespace(name="conductor", model_key=self.understand_model)

    async def _use_conductor_tool(self, name: str, args: dict) -> str:
        """Invoca una tool como el 'conductor' (respeta allowlist/permisos/confirmación)."""
        out = await self.tools.invoke(self._agente_conductor(), name, args)
        return out.content

    async def _tool_por_intencion(self, texto: str) -> Optional[str]:
        """Ruteo DETERMINÍSTICO a herramienta por palabras clave (confiable con modelos
        chicos, que no llaman bien a tools). Devuelve el texto de la tool o None."""
        n = _norm(texto)
        ents = comprension._extraer_entidades(n)

        if n.strip(" .!?¿¡") in ("hora", "la hora", "fecha", "la fecha") or any(
            k in n for k in ("que hora", "la hora", "hora es", "que dia es hoy", "que fecha", "fecha de hoy", "dia de hoy", "que dia es")
        ):
            return await self._use_conductor_tool("hora", {})
        if any(k in n for k in ("no podes hacer", "no sabes hacer", "no puede hacer", "pendiente", "limitacion", "que te falta", "que no sabes")):
            return await self._use_conductor_tool("ver_pendientes", {})
        if any(k in n for k in ("clima", "tiempo hace", "temperatura", "pronostico", "va a llover", "lluvia")):
            ciudad = _ciudad(texto)
            if not ciudad:
                await self._use_conductor_tool(
                    "anotar_pendiente",
                    {"descripcion": "No sé dónde vive el usuario, no puedo darle el clima local",
                     "contexto": texto},
                )
                await self._emit("pendiente", "conductor", "local", "-", "anoté: falta ubicación del usuario (clima)")
                return ("No sé todavía dónde vivís, así que no puedo darte el clima de tu zona. "
                        "Lo anoté como pendiente. Decime tu ciudad y te lo busco, o cargámela para tenerla siempre.")
            return await self._use_conductor_tool("clima", {"ciudad": ciudad})
        if any(k in n for k in ("timer", "temporizador", "alarma")):
            return await self._use_conductor_tool("set_timer", {"duracion": ents.get("duracion", "10"), "unidad": ents.get("unidad", "minutos")})
        if any(k in n for k in ("recordame", "recordar", "recordatorio", "recuerdame", "acordame")):
            return await self._use_conductor_tool("crear_recordatorio", {"texto": texto, "cuando": ents.get("cuando", "en 1 hora")})
        if any(k in n for k in ("mi calendario", "mi agenda", "que tengo agendado", "mis eventos", "que tengo hoy")):
            return await self._use_conductor_tool("leer_calendario", {"limite": 5})
        return None

    async def _responder_directo(self, texto: str) -> Tuple[str, str]:
        """El Conductor resuelve lo simple por su cuenta. Charla trivial → respuesta
        instantánea sin modelo. Después, ruteo determinístico a herramienta
        (hora/clima/timer/...); si no aplica, responde el modelo con su
        conocimiento (recetas, ideas, charla) sin pedir detalle."""
        if comprension.es_smalltalk(texto):
            return _respuesta_charla(texto), "-"
        tool_txt = await self._tool_por_intencion(texto)
        if tool_txt is not None:
            return tool_txt, model_router.model_for(self.understand_model)
        contexto = ("\n\n[memoria relevante: " + ", ".join(self._memoria) + "]") if self._memoria else ""
        comp = await model_router.complete_meta(
            self.understand_model,
            [
                {"role": "system", "content": prompts.get("nova_directo")},
                {"role": "user", "content": texto + contexto},
            ],
            **_OPTS_DIRECTO,
        )
        if comp.via == "stub":
            # Sin ningún modelo vivo, mejor avisar claro que devolver el stub crudo.
            return (
                "Ahora mismo no tengo ningún modelo disponible para responder eso "
                "(Ollama no contesta y no hay claves de nube cargadas). "
                "Revisá la pestaña Estado en la configuración (⚙) o corré `python -m nova.doctor`.",
                comp.spec,
            )
        return comp.text, comp.spec

    # --- memoria de largo plazo ---
    async def _recuperar_memoria(self, texto: str) -> List[str]:
        """Recall: semántico sobre la consulta + vecinos del mejor match. Carga el
        contexto en el WorldState (caché vivo) y lo emite a la traza.

        Se saltea la charla trivial y los mensajes muy cortos: recuperar memoria
        para "hola" solo mete ruido en el prompt (y hace alucinar al modelo chico).
        """
        if comprension.es_smalltalk(texto) or len(texto.split()) < 3:
            return []
        try:
            hits = await self.memory.buscar_semantico(texto, k=3)
        except Exception:  # pragma: no cover
            return []
        recuerdos = [n.nombre for n, _ in hits]
        if hits:
            try:
                recuerdos += [n.nombre for n in await self.memory.vecinos(hits[0][0].id)]
            except Exception:  # pragma: no cover
                pass
        recuerdos = list(dict.fromkeys(recuerdos))[:5]
        if recuerdos:
            await self.world.set("memoria_relevante", recuerdos)
            await self._emit("memoria", "memoria_contexto", "local", "-", "recuperé: " + " · ".join(recuerdos))
        return recuerdos

    async def _recordar_turno(self, texto: str) -> None:
        """Extrae y persiste lo nuevo del turno (entidades/relaciones/hechos)."""
        try:
            await self.extractor.extraer(texto, fuente="conversacion")
        except Exception:  # pragma: no cover - la memoria nunca rompe la respuesta
            pass

    async def _pedir_confirmacion(self, texto: str, intent: Intent, rc: RequiereConfirmacion) -> str:
        """Una tool `high` pidió confirmación: devolvemos la pregunta (la acción ya
        quedó pendiente en el WorldState; se ejecuta cuando el usuario diga "sí")."""
        await self._emit("confirmacion", "conductor", "-", f"tool:{rc.tool}", rc.mensaje, estado="pregunta")
        return self._finish(texto, intent, "confirmacion", [rc.tool], f"tool:{rc.tool}", rc.mensaje, question=rc.mensaje)

    # --- orquestación ---
    async def attend(self, texto: str, images: Optional[List[str]] = None) -> str:
        images = images or []
        self.last_trace = []
        self._tarea = texto
        self._memoria = []
        self._empresa_data = {}

        # 0a) ¿Hay una acción de riesgo (tool `high`) esperando confirmación?
        accion = await self.world.get("pending_action")
        if accion and not images:
            if _afirmativo(texto):
                outcome = await self.tools.confirmar_pendiente()
                final = outcome.content if outcome else "No había ninguna acción pendiente."
                await self._emit("accion", "conductor", accion.get("grupo", "-"),
                                 f"tool:{accion['tool']}", "acción confirmada y ejecutada", resultado=final)
                ok_intent = Intent(intencion="confirmar", complejidad="simple", confianza=1.0)
                return self._finish(texto, ok_intent, "accion", [accion["tool"]], f"tool:{accion['tool']}", final)
            if _negativo(texto):
                await self.tools.cancelar_pendiente()
                await self._emit("accion", "conductor", "-", "-", "acción cancelada por el usuario")
                no_intent = Intent(intencion="cancelar", complejidad="simple", confianza=1.0)
                return self._finish(texto, no_intent, "accion", [], "-", "Listo, lo cancelé.")
            # Si no es sí/no, la acción queda pendiente y seguimos con el pedido nuevo.

        # 0b) Fusión con aclaración pendiente (solo texto; una imagen es un pedido nuevo).
        pendiente = await self.world.get("pending_clarification")
        rondas = 0
        texto_efectivo = texto
        if pendiente and not images:
            texto_efectivo = (pendiente.get("text", "") + " " + texto).strip()
            rondas = int(pendiente.get("rounds", 0))

        # 1) Comprensión (modelo → JSON; stub → heurística).
        intent = await comprension.comprender(texto_efectivo, images=images or None)
        modelo_comp = intent.fuente
        await self._emit(
            "comprension", "conductor", "local", modelo_comp,
            f"intent={intent.intencion} complejidad={intent.complejidad} conf={intent.confianza:.2f}"
            + (" multimodal" if intent.multimodal else ""),
            resultado=", ".join(intent.entidades) or "-",
        )

        # 1b) Seguridad: intento de override → se marca, NO se obedece.
        if intent.inyeccion_detectada:
            await self._emit(
                "seguridad", "conductor", "-", "-",
                "intento de override detectado; tratado como dato, no obedecido",
                estado="alerta",
            )

        # 1c) Memoria: recall semántico + relaciones → caché vivo (WorldState).
        self._memoria = await self._recuperar_memoria(texto_efectivo)

        # 2) Aclaración: SOLO para lo complejo con datos imprescindibles faltantes
        #    (ej. planear un viaje sin fecha). Lo simple NUNCA se traba pidiendo detalle:
        #    el Conductor responde directo (y si le falta un dato, lo anota como pendiente).
        necesita = intent.complejidad == "complejo" and bool(intent.faltantes)
        if not images and necesita and rondas < MAX_RONDAS_ACLARACION:
            await self.world.set("pending_clarification", {"text": texto_efectivo, "rounds": rondas + 1})
            pregunta = self._formular_pregunta(intent)
            await self._emit("aclaracion", "conductor", "local", modelo_comp, pregunta, estado="pregunta")
            return self._finish(texto, intent, "aclaracion", [], modelo_comp, pregunta, question=pregunta)

        # Procede: limpiar pendiente; anotar supuesto si quedaban faltantes.
        await self.world.set("pending_clarification", None)
        supuesto = ""
        if intent.faltantes:
            supuesto = "asumo la interpretación más general (" + ", ".join(intent.faltantes) + ")"
            await self._emit("aclaracion", "conductor", "local", modelo_comp,
                             f"sin más rondas; {supuesto}")

        task = Task(
            goal=texto_efectivo, intent=intent.intencion,
            entities=intent.entidades, complexity=intent.complejidad,
        )

        # 3) Ruteo + síntesis.
        if images:
            final, responder = await self._responder_vision(texto_efectivo, images)
            agents_involved, ruta, grupo = ["conductor_vision"], "vision", "nube"
            await self._emit("agente", "conductor_vision", grupo, responder, "respuesta multimodal", resultado=final)
        elif intent.complejidad == "simple":
            try:
                final, responder = await self._responder_directo(texto_efectivo)  # el Conductor mismo
            except RequiereConfirmacion as rc:
                return await self._pedir_confirmacion(texto, intent, rc)
            agents_involved, ruta, grupo = ["conductor"], "local", "local"
            await self._emit("agente", "conductor", grupo, responder, "respondió directo (local + tools)",
                             resultado=final, escribir_log=False)
        else:
            await self._emit("ruteo", "conductor", "nube", "-", "→ Empresa (PMO + áreas)")
            try:
                entregable = await self.empresa.ejecutar(texto_efectivo)  # descompone, reparte, integra
            except RequiereConfirmacion as rc:
                return await self._pedir_confirmacion(texto, intent, rc)
            self._empresa_data = entregable.data
            areas = entregable.data.get("areas", [])
            await self._emit("agente", "empresa", "nube", "-",
                             f"áreas: {', '.join(areas) or '-'} | subtareas: {len(entregable.data.get('subtareas', []))}"
                             + (" | finanzas" if entregable.data.get("finanzas") else ""),
                             resultado=entregable.text, escribir_log=False)
            final, responder = await self._sintetizar(texto_efectivo, entregable)
            agents_involved, ruta, grupo = ["empresa", *areas], "nube", "nube"
            await self._emit("sintesis", "conductor", "nube", responder, "síntesis final", resultado=final)

        await self._emit("respuesta", "conductor", grupo, responder, "respuesta final entregada", resultado=final)
        # Persistir lo nuevo del turno (entidades/relaciones/hechos) en la memoria.
        await self._recordar_turno(texto)
        return self._finish(texto, intent, ruta, agents_involved, responder, final, supuesto=supuesto)

    def _finish(
        self,
        texto: str,
        intent: Intent,
        ruta: str,
        agents: List[str],
        modelo: str,
        final: str,
        question: str = "",
        supuesto: str = "",
    ) -> str:
        self.last_run = {
            "user_text": texto,
            "intent": intent.intencion,
            "complexity": intent.complejidad,
            "entities": intent.entidades,
            "understanding_note": f"{intent.intencion}/{intent.complejidad} conf={intent.confianza:.2f}",
            "route": ruta,
            "agents": agents,
            "model": modelo,
            "final": final,
            "question": question,
            "inyeccion_detectada": intent.inyeccion_detectada,
            "multimodal": intent.multimodal,
            "confianza": intent.confianza,
            "faltantes": intent.faltantes,
            "supuesto": supuesto,
            "memoria": list(self._memoria),
            "empresa": dict(self._empresa_data),
            "log_path": str(self.registro.last_path) if self.registro.last_path else "",
            "trace": [e.to_dict() for e in self.last_trace],
        }
        return final
