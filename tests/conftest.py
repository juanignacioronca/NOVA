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
def hermetic_env(monkeypatch):
    """Fuerza modo stub: Ollama inalcanzable y sin claves cloud → determinista."""
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")  # puerto sin servicio
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
