"""El Conductor clasifica complejidad y rutea local vs nube."""

from __future__ import annotations

from nova.core.conductor import Conductor
from nova.logging.registro import Registro


async def test_simple_se_resuelve_en_local(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    final = await conductor.attend("ponme un timer de 10 minutos")

    assert conductor.last_run["complexity"] == "simple"
    assert conductor.last_run["route"] == "local"
    assert conductor.last_run["agents"] == ["respuestas_rapidas"]
    assert final  # respuesta no vacía


async def test_complejo_pasa_por_pmo_y_consulta_estrategia(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    # Pedido complejo YA especificado (fecha + compañía) → no pide aclaración.
    final = await conductor.attend(
        "organizá un finde de trekking el sábado que viene con mi hermano"
    )

    assert conductor.last_run["complexity"] == "complejo"
    assert conductor.last_run["route"] == "nube"
    assert "pmo" in conductor.last_run["agents"]
    assert "estrategia_investigador" in conductor.last_run["agents"]

    # El PMO consultó a Estrategia POR EL BUS (request directo).
    history = conductor.bus.history()
    assert any(
        h["kind"] == "request" and h["to"] == "estrategia_investigador" for h in history
    ), "el PMO no consultó a Estrategia por el bus"
    assert "Plan (PMO)" in final  # en stub, la síntesis cae al plan determinista
