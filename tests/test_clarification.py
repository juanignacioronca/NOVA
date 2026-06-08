"""Diálogo de aclaración: pedido ambiguo → pregunta → se fusiona y procede."""

from __future__ import annotations

from nova.core.conductor import Conductor
from nova.logging.registro import Registro


async def test_pregunta_y_luego_retoma(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))

    # 1) Ambiguo → NOVA pregunta (no actúa todavía).
    pregunta = await conductor.attend("organízame un finde")
    assert conductor.last_run["route"] == "aclaracion"
    assert "?" in pregunta
    assert conductor.last_run["agents"] == []

    # 2) La respuesta de seguimiento se fusiona con el pendiente y procede.
    final = await conductor.attend("el sábado que viene con amigos")
    assert conductor.last_run["route"] == "nube"
    assert "pmo" in conductor.last_run["agents"]
    assert final
