"""Capa de modelos real: parseo de specs, config por proveedor y cadena de
resiliencia (429 → fallback → stub, y salto al fallback si falta la clave).
Todo OFFLINE: se inyectan proveedores falsos, sin red ni claves.
"""

from __future__ import annotations

import pytest

from nova.models import model_router
from nova.models.providers.base import ProviderError, RateLimitError
from nova.models.providers.openai_compatible import OpenAICompatibleClient, provider_config


# --- parseo proveedor:modelo + base_url/clave por proveedor ---
def test_spec_parsing():
    assert model_router._resolve_spec("conductor_simple") == ("ollama", "llama3.2:3b")
    # El modelo lleva ':' interno (deepseek/...:free) — split en el primer ':'.
    assert model_router._resolve_spec("estrategia_analista") == (
        "openrouter",
        "deepseek/deepseek-r1:free",
    )
    assert model_router._fallback_spec() == ("ollama", "llama3.2:3b")


def test_provider_config_base_url_y_clave():
    assert provider_config("groq").base_url == "https://api.groq.com/openai/v1"
    assert provider_config("groq").key_env == "GROQ_API_KEY"
    assert provider_config("deepseek").base_url == "https://api.deepseek.com/v1"
    assert provider_config("gemini").base_url.endswith("/v1beta/openai")
    assert provider_config("openrouter").extra_headers.get("X-Title") == "NOVA"
    ollama = provider_config("ollama")
    assert ollama.key_env is None  # clave dummy
    assert ollama.base_url == "http://127.0.0.1:9/v1"  # respeta OLLAMA_HOST del fixture


def test_ollama_dummy_key_no_revienta():
    # Sin clave configurada, Ollama igual arma Bearer dummy (no ProviderUnavailable).
    client = OpenAICompatibleClient("ollama")
    assert client._key() == "ollama"


# --- cadena de resiliencia (proveedores falsos inyectados) ---
class FakeProvider:
    def __init__(self, name, *, avail=True, raises=None, text="OK"):
        self.name = name
        self._avail = avail
        self._raises = raises
        self._text = text
        self.calls = 0

    def available(self) -> bool:
        return self._avail

    async def complete(self, model, messages, **opts):
        self.calls += 1
        if self._raises is not None:
            raise self._raises
        return self._text


@pytest.fixture
def no_backoff(monkeypatch):
    """Sin esperas de backoff: tests instantáneos."""
    monkeypatch.setattr(model_router, "BACKOFF_SECONDS", ())


async def test_429_cae_a_fallback_local(no_backoff):
    groq = FakeProvider("groq", raises=RateLimitError("429"))
    ollama = FakeProvider("ollama", text="LOCAL-OK")
    model_router._providers["groq"] = groq
    model_router._providers["ollama"] = ollama

    comp = await model_router.complete_meta(
        "estrategia_investigador", [{"role": "user", "content": "hola"}]
    )
    assert groq.calls == 1  # intentó el primario
    assert comp.text == "LOCAL-OK"
    assert comp.provider == "ollama"
    assert comp.via == "fallback"


async def test_falla_todo_cae_a_stub(no_backoff):
    model_router._providers["groq"] = FakeProvider("groq", raises=RateLimitError("429"))
    model_router._providers["ollama"] = FakeProvider("ollama", raises=ProviderError("caído"))

    comp = await model_router.complete_meta(
        "estrategia_investigador", [{"role": "user", "content": "hola mundo"}]
    )
    assert comp.via == "stub"
    assert comp.text.startswith("[stub:estrategia_investigador]")
    assert "hola mundo" in comp.text


async def test_sin_clave_salta_directo_al_fallback(no_backoff):
    # Primario no disponible (sin clave) → ni se intenta; va directo al fallback.
    groq = FakeProvider("groq", avail=False)
    ollama = FakeProvider("ollama", text="LOCAL-OK")
    model_router._providers["groq"] = groq
    model_router._providers["ollama"] = ollama

    comp = await model_router.complete_meta(
        "estrategia_investigador", [{"role": "user", "content": "x"}]
    )
    assert groq.calls == 0  # no se intentó en vano
    assert comp.provider == "ollama"
    assert comp.via == "fallback"


# --- response_format (modo JSON): si el modelo no lo soporta, reintenta sin él ---
class _Resp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


async def test_response_format_reintenta_sin_el(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    client = OpenAICompatibleClient("groq")
    bodies = []

    async def fake_post(self, body, headers, timeout):
        bodies.append(dict(body))
        if "response_format" in body:
            return _Resp(400, text="response_format not supported")
        return _Resp(200, {"choices": [{"message": {"content": "ok JSON"}}]})

    monkeypatch.setattr(OpenAICompatibleClient, "_post", fake_post)
    out = await client.complete(
        "modelo-x",
        [{"role": "user", "content": "dame JSON"}],
        response_format={"type": "json_object"},
    )
    assert out == "ok JSON"
    assert len(bodies) == 2
    assert "response_format" in bodies[0] and "response_format" not in bodies[1]


async def test_response_format_se_envia_cuando_se_pide(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "clave-falsa")
    client = OpenAICompatibleClient("groq")
    bodies = []

    async def fake_post(self, body, headers, timeout):
        bodies.append(dict(body))
        return _Resp(200, {"choices": [{"message": {"content": "{}"}}]})

    monkeypatch.setattr(OpenAICompatibleClient, "_post", fake_post)
    await client.complete(
        "modelo-x",
        [{"role": "user", "content": "JSON"}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    assert bodies[0]["temperature"] == 0.1
    assert bodies[0]["response_format"] == {"type": "json_object"}
