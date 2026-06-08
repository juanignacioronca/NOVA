"""Multimodal (paso 1): una petición con imagen se enruta a un modelo de visión."""

from __future__ import annotations

from nova.core.conductor import Conductor
from nova.logging.registro import Registro
from nova.models import model_router


class VisionFake:
    def __init__(self):
        self.name = "gemini"
        self.calls = 0

    def available(self) -> bool:
        return True

    async def complete(self, model, messages, **opts):
        self.calls += 1
        # Verifica que llega en formato visión (algún mensaje con image_url).
        assert _tiene_imagen(messages), "no llegó la imagen en formato visión"
        return "Veo un gato en la foto."


def _tiene_imagen(messages) -> bool:
    for m in messages:
        content = m.get("content")
        if isinstance(content, list) and any(
            isinstance(p, dict) and p.get("type") == "image_url" for p in content
        ):
            return True
    return False


async def test_imagen_se_enruta_a_modelo_de_vision(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")

    fake = VisionFake()
    model_router._providers["gemini"] = fake  # conductor_vision: gemini primario

    conductor = Conductor(registro=Registro(tmp_path))
    final = await conductor.attend("¿qué es esto?", images=[str(img)])

    assert conductor.last_run["multimodal"] is True
    assert conductor.last_run["route"] == "vision"
    assert conductor.last_run["model"].startswith("gemini:")
    assert fake.calls >= 1
    assert "gato" in final
