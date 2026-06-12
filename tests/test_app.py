"""El servicio FastAPI levanta y responde offline (Conductor en stub)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nova.app import app


def test_health():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["service"] == "nova"


def test_chat_simple_es_local():
    with TestClient(app) as client:
        r = client.post("/chat", json={"text": "ponme un timer de 5 minutos"})
        assert r.status_code == 200
        body = r.json()
        assert body["route"] == "local"
        assert body["answer"]
        assert isinstance(body["trace"], list) and body["trace"]


def test_index_sirve_pagina():
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "NOVA" in r.text
        # La página mínima (respaldo, sin build) vive en /lite y se conecta por WS.
        r2 = client.get("/lite")
        assert r2.status_code == 200
        assert "/ws" in r2.text


def test_ws_streamea_traza_y_respuesta():
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_text("hola")
            etapas = []
            answer = None
            for _ in range(30):
                msg = ws.receive_json()
                if msg["type"] == "trace":
                    etapas.append(msg["etapa"])
                elif msg["type"] == "answer":
                    answer = msg["text"]
                    break
            assert "comprension" in etapas
            assert answer
