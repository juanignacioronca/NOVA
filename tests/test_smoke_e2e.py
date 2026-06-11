"""La cadena completa (scripts/smoke_e2e.py) enlaza en stub."""

from __future__ import annotations

import importlib.util
import pathlib


def _cargar_smoke():
    ruta = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "smoke_e2e.py"
    spec = importlib.util.spec_from_file_location("smoke_e2e", ruta)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_smoke_e2e_enlaza_toda_la_cadena():
    smoke = _cargar_smoke()
    pasos = await smoke.correr()
    assert pasos and all(p.startswith("✓") for p in pasos)
    assert len(pasos) >= 5  # percepción, empresa, memoria, reconocimiento, salida
