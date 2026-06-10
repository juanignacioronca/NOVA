"""ToolExecutor: el guardián de la capa de herramientas.

Por cada invocación: ¿existe la tool? ¿está en la allowlist? ¿el agente tiene
permiso? Valida los args contra el schema. Si la tool es de riesgo `high`, exige
**confirmación** (guarda la acción pendiente en el WorldState). Ejecuta, envuelve
el contenido externo como **no confiable** y registra todo (insumo de auditoría).

También provee el **loop de tool-use acotado** (pensar→tool→pensar, máx. N pasos)
con un protocolo JSON **agnóstico de modelo** (`{"tool": "...", "args": {...}}`).
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

import yaml

from ..core.security import marcar_no_confiable
from ..models import model_router
from ..paths import TOOLS_YAML
from .base import (
    ArgsInvalidos,
    BaseTool,
    PermisoDenegado,
    RequiereConfirmacion,
    ToolContext,
    ToolError,
    ToolNoEncontrada,
    ToolOutcome,
)


def load_tools_config() -> dict:
    with open(TOOLS_YAML, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


# --- protocolo JSON agnóstico de modelo ---
def _extract_json(text: str) -> Optional[dict]:
    inicio, fin = text.find("{"), text.rfind("}")
    if inicio == -1 or fin <= inicio:
        return None
    try:
        data = json.loads(text[inicio : fin + 1])
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, ValueError):
        return None


def parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    """Extrae `{"tool": "...", "args": {...}}` de la salida de un modelo (tolerante)."""
    data = _extract_json(text or "")
    if isinstance(data, dict) and data.get("tool"):
        args = data.get("args")
        return {"tool": str(data["tool"]), "args": args if isinstance(args, dict) else {}}
    return None


def _coerce(value: Any, typ: str) -> Any:
    try:
        if typ == "int":
            return int(value)
        if typ == "float":
            return float(value)
        if typ == "bool":
            return value if isinstance(value, bool) else str(value).lower() in ("1", "true", "si", "sí", "yes")
        return str(value)
    except (ValueError, TypeError):
        raise ArgsInvalidos(f"valor inválido para tipo {typ}: {value!r}")


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


class ToolExecutor:
    def __init__(
        self,
        registry,
        world,
        registro,
        config: Optional[dict] = None,
        max_steps: Optional[int] = None,
    ) -> None:
        self.registry = registry
        self.world = world
        self.registro = registro
        self.config = config if config is not None else load_tools_config()
        self.max_steps = max_steps or int((self.config.get("defaults") or {}).get("max_steps", 4))
        # Modo stub de tools (sin red): forzado por env (tests/offline).
        self.stub = _truthy_env("NOVA_FORCE_STUB")

    # --- permisos ---
    def grant(self, agente: str, tools) -> None:
        """Otorga a un agente (ej. sub-agente del roster) un set de tools.

        Se concede desde `teams.yaml`, pero SIEMPRE acotado por la allowlist global
        (un grant no puede habilitar una tool que no esté en `allowlist`).
        """
        permitidas = [t for t in (tools or []) if self._en_allowlist(t)]
        self.config.setdefault("permisos", {})[agente] = permitidas

    def _en_allowlist(self, name: str) -> bool:
        return name in (self.config.get("allowlist") or [])

    def _agente_puede(self, agente: str, name: str) -> bool:
        perms = (self.config.get("permisos") or {}).get(agente, [])
        return "*" in perms or name in perms

    def _validar(self, tool: BaseTool, args: Optional[dict]) -> Dict[str, Any]:
        args = args or {}
        validado: Dict[str, Any] = {}
        for arg, meta in (tool.spec.args_schema or {}).items():
            if arg in args and args[arg] is not None:
                validado[arg] = _coerce(args[arg], meta.get("type", "str"))
            elif meta.get("required"):
                raise ArgsInvalidos(f"falta el arg requerido '{arg}' para {tool.spec.name}")
            elif "default" in meta:
                validado[arg] = meta["default"]
        return validado

    def _log(self, agente, grupo, tool, args, estado, confirmado=False, resultado="") -> None:
        self.registro.log(
            agente=agente,
            grupo=grupo,
            tarea=f"tool:{tool}",
            decision=f"{estado} | args={args} | confirmado={confirmado}",
            modelo=f"tool:{tool}",
            resultado_breve=str(resultado),
        )

    # --- invocación ---
    async def _invoke(self, agente: str, grupo: str, name: str, args: dict, confirmado: bool) -> ToolOutcome:
        tool = self.registry.get_tool(name)
        if tool is None:
            self._log(agente, grupo, name, args, "DENEGADO: no existe")
            raise ToolNoEncontrada(f"la tool '{name}' no existe")
        if not self._en_allowlist(name):
            self._log(agente, grupo, name, args, "DENEGADO: fuera de allowlist")
            raise PermisoDenegado(f"'{name}' no está en la allowlist")
        if not self._agente_puede(agente, name):
            self._log(agente, grupo, name, args, "DENEGADO: sin permiso")
            raise PermisoDenegado(f"el agente '{agente}' no tiene permiso para '{name}'")

        validado = self._validar(tool, args)

        # Riesgo high → confirmación explícita.
        if tool.spec.riesgo == "high" and not confirmado:
            await self.world.set(
                "pending_action", {"agent": agente, "grupo": grupo, "tool": name, "args": validado}
            )
            mensaje = tool.confirm_message(**validado)
            self._log(agente, grupo, name, validado, "REQUIERE CONFIRMACION")
            raise RequiereConfirmacion(mensaje, name, validado)

        ctx = ToolContext(world=self.world, stub=self.stub)
        result = await tool.run(ctx, **validado)

        content = result.content
        externo = bool(tool.spec.externo or result.externo)
        if externo:
            content = marcar_no_confiable(str(result.content), result.fuente or name)

        self._log(
            agente, grupo, name, validado,
            "OK" if result.ok else "ERROR",
            confirmado=confirmado,
            resultado=content,
        )
        return ToolOutcome(ok=result.ok, content=content, tool=name, externo=externo, raw=str(result.content))

    async def invoke(self, agent, name: str, args: Optional[dict] = None, confirmado: bool = False) -> ToolOutcome:
        return await self._invoke(
            getattr(agent, "name", "?"), getattr(agent, "group", "-"), name, args or {}, confirmado
        )

    # --- confirmación de acción pendiente ---
    async def confirmar_pendiente(self) -> Optional[ToolOutcome]:
        pend = await self.world.get("pending_action")
        if not pend:
            return None
        out = await self._invoke(
            pend["agent"], pend.get("grupo", "-"), pend["tool"], pend["args"], confirmado=True
        )
        await self.world.set("pending_action", None)
        return out

    async def cancelar_pendiente(self) -> None:
        await self.world.set("pending_action", None)

    # --- descubrimiento / exposición a agentes ---
    def tools_for(self, agente: str) -> List[BaseTool]:
        allow = set(self.config.get("allowlist") or [])
        perms = (self.config.get("permisos") or {}).get(agente, [])
        names = allow if "*" in perms else (allow & set(perms))
        out = [self.registry.get_tool(n) for n in sorted(names)]
        return [t for t in out if t is not None]

    def _tools_prompt(self, agente: str) -> Optional[str]:
        tools = self.tools_for(agente)
        if not tools:
            return None
        lineas = [
            "Herramientas disponibles. Para usar una, respondé SOLO un JSON: "
            '{"tool": "<name>", "args": {...}}. Si no necesitás herramienta, respondé normal.',
        ]
        for t in tools:
            lineas.append(f"- {t.spec.name}: {t.spec.descripcion} | args={list(t.spec.args_schema)} | riesgo={t.spec.riesgo}")
        return "\n".join(lineas)

    # --- loop de tool-use acotado ---
    async def tool_loop(self, agent, messages: List[dict], max_steps: Optional[int] = None) -> str:
        """Encadena pensar→tool→pensar con tope N (seguridad). Devuelve texto final."""
        tope = max_steps or self.max_steps
        prompt = self._tools_prompt(getattr(agent, "name", "?"))
        msgs: List[dict] = ([{"role": "system", "content": prompt}] if prompt else []) + list(messages)

        for _ in range(tope):
            reply = await model_router.complete(agent.model_key, msgs)
            call = parse_tool_call(reply)
            if call is None:
                return reply  # respuesta final (no pidió tool)
            try:
                out = await self.invoke(agent, call["tool"], call.get("args", {}))
            except RequiereConfirmacion as rc:
                return rc.mensaje  # burbujea la pregunta de confirmación
            except (PermisoDenegado, ToolNoEncontrada, ArgsInvalidos) as exc:
                msgs.append({"role": "user", "content": f"[tool rechazada: {exc}]"})
                continue
            msgs.append({"role": "user", "content": f"[resultado de {call['tool']}]: {out.content}"})
        return "(límite de pasos de herramientas alcanzado)"
