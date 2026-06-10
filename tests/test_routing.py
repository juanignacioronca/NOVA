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


async def test_complejo_pasa_por_la_empresa(tmp_path):
    conductor = Conductor(registro=Registro(tmp_path))
    # Pedido complejo YA especificado (fecha + compañía) → no pide aclaración.
    final = await conductor.attend(
        "organizá un finde de trekking al cerro el sábado que viene con mi hermano con $200 de presupuesto"
    )

    assert conductor.last_run["complexity"] == "complejo"
    assert conductor.last_run["route"] == "nube"
    # La empresa lo manejó y lo ruteó al área correcta.
    assert "empresa" in conductor.last_run["agents"]
    assert "recreacional" in conductor.last_run["agents"]
    assert final
