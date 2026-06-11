"""Salidas (Prompt 9): payload de presentación + contrato del WS (offline)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nova.app import app
from nova.output.presentacion import construir_presentacion
from nova.output.voz import frases


# --- presentación: contenido dinámico por tipo ---
def test_presentacion_simple_es_tarjeta():
    run = {"route": "local", "intent": "weather", "final": "En Madrid: 20°C.", "trace": [], "memoria": []}
    p = construir_presentacion(run, "ambos")
    assert p["type"] == "presentacion"
    assert p["modalidad"] == "ambos"
    assert p["resultado"]["tipo"] == "tarjeta"
    assert p["voz"]  # narración para modalidad con voz


def test_presentacion_compleja_es_itinerario():
    run = {
        "route": "nube", "intent": "plan", "final": "Plan...\nlínea 2",
        "empresa": {"subtareas": [
            {"area": "recreacional", "descripcion": "Diseñar", "requiere_estrategia": True},
            {"area": "recreacional", "descripcion": "Presupuesto", "requiere_finanzas": True},
        ]},
        "trace": [{"etapa": "plan"}], "memoria": [],
    }
    p = construir_presentacion(run, "ambos")
    assert p["resultado"]["tipo"] == "itinerario"
    assert len(p["resultado"]["pasos"]) == 2
    assert p["resultado"]["pasos"][1]["finanzas"] is True
    assert p["proceso"] == run["trace"]


def test_modalidad_pantalla_sin_voz():
    run = {"route": "local", "intent": "general", "final": "hola", "trace": [], "memoria": []}
    p = construir_presentacion(run, "pantalla")
    assert p["voz"] == ""  # en 'pantalla' no se narra


def test_frases_parte_oraciones():
    assert frases("Hola. ¿Qué tal? Bien.") == ["Hola.", "¿Qué tal?", "Bien."]


# --- WS: trace + presentacion + voz + answer ---
def test_ws_envia_presentacion_y_voz():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("ponme un timer de 5 minutos")
            tipos = []
            pres = None
            for _ in range(40):
                m = ws.receive_json()
                tipos.append(m.get("type"))
                if m.get("type") == "presentacion":
                    pres = m
                if m.get("type") == "answer":
                    break
            assert "trace" in tipos
            assert "presentacion" in tipos
            assert "voz" in tipos
            assert "answer" in tipos
            assert pres and pres["resultado"]["tipo"] in ("tarjeta", "texto")


def test_ws_modalidad_se_confirma():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "modalidad", "value": "pantalla"})
            m = ws.receive_json()
            assert m["type"] == "modalidad" and m["value"] == "pantalla"


def test_ws_stop_barge_in():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "stop"})
            assert ws.receive_json()["type"] == "stopped"


# --- /tts degrada sin Piper (204) ---
def test_tts_degrada_sin_voz():
    with TestClient(app) as client:
        r = client.get("/tts", params={"text": "hola"})
        assert r.status_code in (200, 204)  # offline (sin Piper) → 204
