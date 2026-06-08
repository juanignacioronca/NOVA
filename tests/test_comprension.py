"""Motor de comprensión: Intent estructurado + clasificación + faltantes."""

from __future__ import annotations

from nova.core import comprension


async def test_comprender_devuelve_intent_estructurado():
    intent = await comprension.comprender("ponme un timer de 10 minutos")
    assert intent.complejidad == "simple"
    assert intent.intencion == "set_timer"
    assert intent.faltantes == []
    assert intent.entidades.get("duracion") == "10"
    assert 0.0 <= intent.confianza <= 1.0
    assert intent.multimodal is False


async def test_comprender_ambiguo_marca_faltantes():
    intent = await comprension.comprender("organízame un finde")
    assert intent.complejidad == "complejo"
    assert intent.faltantes  # falta fecha y compañía
    assert intent.necesita_aclaracion()


async def test_comprender_complejo_completo_no_pide_nada():
    intent = await comprension.comprender(
        "organizá un finde de trekking el sábado que viene con mi hermano"
    )
    assert intent.complejidad == "complejo"
    assert intent.faltantes == []
    assert not intent.necesita_aclaracion()
