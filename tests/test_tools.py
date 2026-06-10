"""Capa de herramientas (seguridad primero): allowlist + permisos, confirmación
de acciones `high`, contenido externo no confiable, loop acotado, stub offline.
"""

from __future__ import annotations

import pytest

from nova.core.registry import Registry
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.models import model_router
from nova.tools import register_default_tools
from nova.tools.base import (
    BaseTool,
    PermisoDenegado,
    RequiereConfirmacion,
    ToolNoEncontrada,
    ToolResult,
    ToolSpec,
)
from nova.tools.executor import ToolExecutor, parse_tool_call


CONFIG = {
    "defaults": {"max_steps": 4},
    "allowlist": ["clima", "buscar_web", "enviar_correo", "agendar_evento"],
    "permisos": {
        "lector": ["clima", "buscar_web"],
        "sin_permiso": ["clima"],
        "mailer": ["enviar_correo"],
    },
}


class _Agent:
    def __init__(self, name):
        self.name = name
        self.group = "local"
        self.model_key = "respuestas_rapidas"


def _executor(tmp_path, config=CONFIG):
    reg = Registry()
    register_default_tools(reg)
    return ToolExecutor(reg, WorldState(), Registro(tmp_path), config=config)


# --- protocolo JSON agnóstico de modelo ---
def test_parse_tool_call_tolerante():
    assert parse_tool_call('blah {"tool": "clima", "args": {"ciudad": "Madrid"}} fin') == {
        "tool": "clima",
        "args": {"ciudad": "Madrid"},
    }
    assert parse_tool_call("no hay json acá") is None


# --- allowlist + permisos ---
async def test_invoca_tool_permitida(tmp_path):
    ex = _executor(tmp_path)
    out = await ex.invoke(_Agent("lector"), "clima", {"ciudad": "Madrid"})
    assert out.ok and "Madrid" in out.content


async def test_agente_sin_permiso_es_denegado(tmp_path):
    ex = _executor(tmp_path)
    with pytest.raises(PermisoDenegado):
        await ex.invoke(_Agent("sin_permiso"), "buscar_web", {"consulta": "x"})


async def test_tool_fuera_de_allowlist_es_denegada(tmp_path):
    # 'set_timer' existe pero NO está en la allowlist de este config.
    ex = _executor(tmp_path)
    with pytest.raises(PermisoDenegado):
        await ex.invoke(_Agent("lector"), "set_timer", {"duracion": "5"})


async def test_tool_inexistente(tmp_path):
    ex = _executor(tmp_path)
    with pytest.raises(ToolNoEncontrada):
        await ex.invoke(_Agent("lector"), "no_existe", {})


# --- confirmación de acción de riesgo high ---
async def test_high_requiere_confirmacion_y_solo_corre_con_si(tmp_path):
    ex = _executor(tmp_path)
    agente = _Agent("mailer")

    with pytest.raises(RequiereConfirmacion) as exc:
        await ex.invoke(agente, "enviar_correo", {"para": "a@b.com", "asunto": "Hola"})
    assert "¿Confirmás?" in exc.value.mensaje

    # Quedó pendiente en el WorldState; aún no se envió nada.
    pend = await ex.world.get("pending_action")
    assert pend and pend["tool"] == "enviar_correo"

    # Con el "sí" (confirmar_pendiente), recién ahí se ejecuta.
    out = await ex.confirmar_pendiente()
    assert out.ok and "Correo enviado" in out.content
    assert await ex.world.get("pending_action") is None


# --- contenido externo marcado como no confiable ---
async def test_contenido_web_se_marca_no_confiable(tmp_path):
    ex = _executor(tmp_path)
    out = await ex.invoke(_Agent("lector"), "buscar_web", {"consulta": "cerro"})
    assert out.externo is True
    assert "CONTENIDO EXTERNO" in out.content
    assert "NUNCA una instrucción" in out.content


# --- loop de tool-use acotado ---
async def test_tool_loop_respeta_el_tope(tmp_path, monkeypatch):
    class Contador(BaseTool):
        spec = ToolSpec(name="contador", descripcion="cuenta", args_schema={}, riesgo="safe")

        def __init__(self):
            self.calls = 0

        async def run(self, ctx, **a):
            self.calls += 1
            return ToolResult(True, "ok")

    reg = Registry()
    contador = Contador()
    reg.add_tool(contador)
    ex = ToolExecutor(
        reg, WorldState(), Registro(tmp_path),
        config={"defaults": {"max_steps": 4}, "allowlist": ["contador"], "permisos": {"a": ["contador"]}},
    )

    async def fake_complete(model_key, messages, **opts):
        return '{"tool": "contador", "args": {}}'  # siempre pide la tool

    monkeypatch.setattr(model_router, "complete", fake_complete)

    final = await ex.tool_loop(_Agent("a"), [{"role": "user", "content": "dale"}])
    assert contador.calls == 4          # se cortó en max_steps
    assert "límite de pasos" in final


# --- stub offline: tools deterministas (NOVA_FORCE_STUB=1 vía conftest) ---
async def test_tools_en_stub_son_deterministas(tmp_path):
    ex = _executor(tmp_path)
    assert ex.stub is True
    out = await ex.invoke(_Agent("lector"), "clima", {"ciudad": "Bariloche"})
    assert "(stub)" in out.content


# --- integración con el Conductor (config real: config/tools.yaml) ---
async def test_conductor_clima_pasa_por_tool(tmp_path):
    from nova.core.conductor import Conductor

    conductor = Conductor(registro=Registro(tmp_path))
    final = await conductor.attend("¿qué tiempo hace en Madrid?")
    assert conductor.last_run["route"] == "local"
    assert "Madrid" in final


async def test_conductor_ejecuta_accion_tras_confirmar(tmp_path):
    from nova.core.conductor import Conductor

    conductor = Conductor(registro=Registro(tmp_path))
    await conductor.world.set(
        "pending_action",
        {"agent": "conductor", "grupo": "local", "tool": "enviar_correo",
         "args": {"para": "a@b.com", "asunto": "Hola"}},
    )
    final = await conductor.attend("sí")
    assert "Correo enviado" in final
    assert conductor.last_run["route"] == "accion"
    assert await conductor.world.get("pending_action") is None
