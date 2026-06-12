"""Modo configuración: prompts editables, modelos del núcleo y panel de estado.
Offline; los YAML se redirigen a archivos temporales (no se toca el repo).
"""

from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient

from nova import config_api
from nova.core import prompts
from nova.paths import MODELS_YAML


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # prompts.yaml temporal (vacío = todo default).
    prompts_yaml = tmp_path / "prompts.yaml"
    prompts_yaml.write_text("prompts: {}\n", encoding="utf-8")
    monkeypatch.setattr(prompts, "PROMPTS_YAML", prompts_yaml)
    prompts.load(force=True)
    # models.yaml temporal (copia del real) para el editor del núcleo.
    models_yaml = tmp_path / "models.yaml"
    shutil.copy2(MODELS_YAML, models_yaml)
    monkeypatch.setattr(config_api, "MODELS_YAML", models_yaml)
    config_api._FILES = dict(config_api._FILES, models=models_yaml, prompts=prompts_yaml)

    from nova.app import app

    with TestClient(app) as c:
        yield c
    prompts.load(force=True)


# --- prompts del sistema ---
def test_prompts_lista_los_defaults(client):
    r = client.get("/api/config/prompts")
    assert r.status_code == 200
    items = {p["name"]: p for p in r.json()["prompts"]}
    assert "nova_directo" in items and "comprension" in items
    assert items["nova_directo"]["es_default"] is True
    assert items["nova_directo"]["texto"]


def test_prompt_override_y_vuelta_al_default(client):
    r = client.put("/api/config/prompts/nova_directo", json={"text": "Sos NOVA versión pirata."})
    assert r.status_code == 200 and r.json()["es_default"] is False
    assert prompts.get("nova_directo") == "Sos NOVA versión pirata."

    # Texto vacío = volver al default de fábrica.
    r = client.put("/api/config/prompts/nova_directo", json={"text": ""})
    assert r.status_code == 200 and r.json()["es_default"] is True
    assert "pirata" not in prompts.get("nova_directo")


def test_prompt_inexistente_404(client):
    assert client.put("/api/config/prompts/nada", json={"text": "x"}).status_code == 404


# --- modelos del núcleo (models.yaml) ---
def test_core_lista_agentes_del_roster(client):
    r = client.get("/api/config/core")
    assert r.status_code == 200
    body = r.json()
    keys = {a["key"] for a in body["agents"]}
    assert "conductor_simple" in keys and "pmo_planificador" in keys
    assert body["fallback"].startswith("ollama:")


def test_core_cambia_el_modelo_primario(client):
    r = client.put("/api/config/core/conductor_simple", json={"spec": "ollama:qwen2.5:7b"})
    assert r.status_code == 200
    r = client.get("/api/config/core")
    spec = next(a["spec"] for a in r.json()["agents"] if a["key"] == "conductor_simple")
    assert spec == "ollama:qwen2.5:7b"
    # Una clave con cadena de fallback conserva los secundarios al cambiar el primario.
    r = client.put("/api/config/core/conductor_vision", json={"spec": "ollama:llava:7b"})
    assert r.status_code == 200
    r = client.get("/api/config/core")
    vision = next(a for a in r.json()["agents"] if a["key"] == "conductor_vision")
    assert vision["cadena"][0] == "ollama:llava:7b" and len(vision["cadena"]) == 2


def test_core_valida_la_spec(client):
    assert client.put("/api/config/core/conductor_simple", json={"spec": "sin-proveedor"}).status_code == 400
    assert client.put("/api/config/core/no_existe", json={"spec": "ollama:x"}).status_code == 404


# --- estado de proveedores ---
def test_estado_reporta_proveedores_offline(client):
    r = client.get("/api/config/estado")
    assert r.status_code == 200
    body = r.json()
    estados = {p["name"]: p for p in body["proveedores"]}
    assert set(estados) == {"ollama", "gemini", "groq", "openrouter", "deepseek"}
    # Entorno hermético: nada disponible, pero el panel responde igual.
    assert all(not p["ok"] for p in estados.values())
