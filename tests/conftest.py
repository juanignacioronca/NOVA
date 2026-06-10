"""Configuración de tests: entorno hermético (modo stub) y `src` en el path."""

from __future__ import annotations

import pathlib
import sys

import pytest

# Permite `import nova` aunque no se haya hecho `pip install -e .`.
SRC = pathlib.Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch, tmp_path):
    """Fuerza modo stub (sin red ni claves) y aísla los datos locales por test."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")  # puerto sin servicio
    monkeypatch.setenv("NOVA_FORCE_STUB", "1")               # tools sin red (deterministas)
    monkeypatch.setenv("NOVA_DATA_DIR", str(tmp_path / "data"))  # calendario aislado
    for key in (
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
        "DEEPSEEK_API_KEY",
        "ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    # Resetea el cache de proveedores para que se re-evalúe la disponibilidad.
    from nova.models import model_router

    model_router._providers.clear()
    yield
