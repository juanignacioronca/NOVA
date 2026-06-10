"""Grupo Nube (empresa): descomposición, reparto a áreas, transversales cruzando,
skills inter-agente (allowlist + hops), Multifacético, y topes de costo. Offline.
"""

from __future__ import annotations

import pathlib

import pytest

from nova.agents.sub_agent import TopeHops
from nova.core.empresa import Empresa
from nova.core.message_bus import MessageBus
from nova.core.registry import Registry
from nova.core.world_state import WorldState
from nova.logging.registro import Registro
from nova.tools import register_default_tools
from nova.tools.base import PermisoDenegado
from nova.tools.executor import ToolExecutor

CERRO = "organizá un finde de trekking al cerro con $200 de presupuesto"


def _empresa(tmp_path, topes=None) -> Empresa:
    bus, world, registro = MessageBus(), WorldState(), Registro(tmp_path)
    reg = Registry()
    register_default_tools(reg)
    tools = ToolExecutor(reg, world, registro)
    return Empresa(bus, world, registro, tools, topes=topes or {})


# --- descompone, reparte, integra ---
async def test_descompone_reparte_e_integra(tmp_path):
    emp = _empresa(tmp_path)
    res = await emp.ejecutar(CERRO)
    d = res.data
    assert "recreacional" in d["areas"]        # área correcta por tema
    assert d["estrategia"] is True             # research cruzó por Estrategia
    assert d["finanzas"] is True               # el gasto cruzó por Finanzas
    assert d["model_calls"] <= emp.max_calls   # dentro del presupuesto
    assert res.text                            # entregable integrado


async def test_el_gasto_pasa_por_finanzas(tmp_path):
    emp = _empresa(tmp_path)
    res = await emp.ejecutar(CERRO)
    # El área consultó a Finanzas (skill inter-agente registrado en las notas).
    assert any("finanzas_lider" in n for n in res.data["topes"])
    assert res.data["hops"] >= 1


# --- skills inter-agente: allowlist + tope de hops ---
async def test_consulta_respeta_allowlist(tmp_path):
    emp = _empresa(tmp_path)
    emp._reset()
    recreacional = emp.agents["recreacional_lider"]  # puede_consultar: finanzas/estrategia
    with pytest.raises(PermisoDenegado):
        await recreacional.consultar("idiomas_lider", {"goal": "x"})


async def test_consulta_respeta_tope_de_hops(tmp_path):
    emp = _empresa(tmp_path, topes={"max_inter_agent_hops": 1})
    emp._reset()
    recreacional = emp.agents["recreacional_lider"]
    r1 = await recreacional.consultar("finanzas_lider", {"goal": "¿entra en presupuesto?"})
    assert r1.text
    with pytest.raises(TopeHops):
        await recreacional.consultar("estrategia_lider", {"goal": "otra cosa"})


# --- tema desconocido → Multifacético, logueado ---
async def test_tema_desconocido_cae_en_multifacetico(tmp_path):
    emp = _empresa(tmp_path)
    res = await emp.ejecutar("ayudame con un trámite notarial de una herencia")
    assert "multifacetico" in res.data["areas"]
    logs = "\n".join(p.read_text(encoding="utf-8") for p in pathlib.Path(tmp_path).glob("*.jsonl"))
    assert "tema sin equipo" in logs


# --- topes cortan el fan-out ---
async def test_tope_max_subtareas(tmp_path):
    emp = _empresa(tmp_path, topes={"max_subtareas": 1})
    res = await emp.ejecutar(CERRO)
    assert len(res.data["subtareas"]) == 1
    assert any("max_subtareas" in n for n in res.data["topes"])


async def test_tope_max_model_calls(tmp_path):
    emp = _empresa(tmp_path, topes={"max_model_calls": 2})
    res = await emp.ejecutar(CERRO)
    assert any("max_model_calls" in n for n in res.data["topes"])
