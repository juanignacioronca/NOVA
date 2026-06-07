"""La capa de modelos cae a stub determinista sin claves ni Ollama."""

from __future__ import annotations

from nova.models import model_router


async def test_router_cae_a_stub():
    out = await model_router.complete(
        "respuestas_rapidas", [{"role": "user", "content": "hola mundo"}]
    )
    assert out.startswith("[stub:respuestas_rapidas]")
    assert "hola mundo" in out


def test_model_for_resuelve_spec():
    assert model_router.model_for("conductor_simple") == "ollama:qwen2.5:7b"
    # Agente inexistente → usa defaults.fallback.
    assert model_router.model_for("no_existe") == "ollama:qwen2.5:7b"
