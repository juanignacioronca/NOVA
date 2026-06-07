"""Cada corrida escribe al menos una línea de registro JSONL válida."""

from __future__ import annotations

import json

from nova.core.conductor import Conductor
from nova.logging.registro import Registro

REQUIRED_KEYS = ("ts", "agente", "grupo", "tarea", "decision", "modelo", "resultado_breve")


async def test_se_escribe_registro_jsonl(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    await conductor.attend("ponme un timer de 10 minutos")

    files = list(tmp_path.glob("*.jsonl"))
    assert files, "no se escribió ningún archivo de registro"

    lines = files[0].read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1

    record = json.loads(lines[0])
    for key in REQUIRED_KEYS:
        assert key in record, f"falta la clave '{key}' en el registro"
