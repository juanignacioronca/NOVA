#!/usr/bin/env python3
"""Smoke end-to-end de NOVA (en stub): ejercita la cadena completa y verifica que
todo enlaza — percepción/texto → Conductor → (Local + Empresa) → herramientas →
memoria → reconocimiento (presencia + pendientes) → payload de presentación.

    python scripts/smoke_e2e.py

Es la "revisión total" en versión liviana: corre sin red, modelos ni hardware.
"""

from __future__ import annotations

import asyncio
import os
import tempfile

# Determinista y offline (no pisa overrides del entorno, ej. en tests).
os.environ.setdefault("NOVA_FORCE_STUB", "1")
os.environ.setdefault("OLLAMA_HOST", "http://127.0.0.1:9")
os.environ.setdefault("NOVA_DATA_DIR", tempfile.mkdtemp(prefix="nova_smoke_"))

from nova.core.conductor import Conductor  # noqa: E402
from nova.core.proactivo import ProactiveScheduler  # noqa: E402
from nova.logging.registro import Registro  # noqa: E402
from nova.output.presentacion import construir_presentacion  # noqa: E402
from nova.perception.config import ProactiveConfig  # noqa: E402
from nova.recognition.faces import FaceRecognizer  # noqa: E402
from nova.recognition.presencia import detectar_presencia  # noqa: E402

CERRO = "organizá un finde de trekking al cerro el sábado que viene con mi hermano con $200 de presupuesto"


class _OutSpy:
    def __init__(self):
        self.dichos = []

    async def say(self, texto, proactivo=False):
        self.dichos.append(texto)


async def correr() -> list[str]:
    pasos: list[str] = []
    c = Conductor(registro=Registro(tempfile.mkdtemp(prefix="nova_logs_")))

    # 1) Texto → Conductor → Grupo Local + herramienta.
    await c.attend("ponme un timer de 10 minutos")
    assert c.last_run["route"] == "local", c.last_run["route"]
    pasos.append("✓ texto → Conductor → Grupo Local + tool (timer)")

    # 2) Complejo → Empresa (descompone, reparte, el gasto pasa por Finanzas) → síntesis.
    await c.attend(CERRO)
    assert c.last_run["route"] == "nube" and "recreacional" in c.last_run["agents"]
    assert (c.last_run.get("empresa") or {}).get("finanzas") is True
    pasos.append("✓ complejo → Empresa (reparte a áreas, gasto por Finanzas) → síntesis")

    # 3) Memoria: guarda una preferencia y la recupera en un turno posterior.
    await c.attend("prefiero dificultad media para los trekkings")
    await c.attend("¿qué dificultad me conviene para el trekking del cerro?")
    assert any("dificultad" in m for m in c.last_run["memoria"]), c.last_run["memoria"]
    pasos.append("✓ memoria: preferencia guardada y recuperada (recall)")

    # 4) Reconocimiento: enrolar → match (umbral) → memoria → aviso proactivo de presencia.
    store, faces = c.memory, FaceRecognizer(c.memory)
    await faces.enrolar("Tester", [b"foto-A", b"foto-B", b"foto-C"])
    tarea = await store.add_nodo("tarea", "traer la lista del súper")
    await store.add_arista(tarea, store.node_id("persona", "Tester"), "de")

    nombre, conf = await faces.match(b"foto-A")
    assert nombre == "Tester" and conf >= 0.45, (nombre, conf)
    desconocido, _ = await faces.match(b"una-cara-totalmente-distinta")
    assert desconocido == "desconocido", desconocido

    res = await detectar_presencia(store, faces, b"foto-A", c.world)
    assert res and "Tester" in res["aviso"] and res["pendientes"], res
    out = _OutSpy()
    sched = ProactiveScheduler(c.world, out, ProactiveConfig(), clock=lambda: 0.0)
    await sched.tick()
    assert any("Tester" in d for d in out.dichos), out.dichos
    pasos.append("✓ reconocimiento: enrolar → match → memoria → aviso proactivo de presencia")

    # 5) Salida: payload de presentación (proceso + resultado dinámico).
    pres = construir_presentacion(c.last_run)
    assert pres["type"] == "presentacion" and "resultado" in pres
    pasos.append("✓ salida: payload de presentación (proceso + resultado dinámico)")

    return pasos


def main() -> int:
    pasos = asyncio.run(correr())
    print("NOVA — smoke end-to-end (stub)")
    print("-" * 56)
    for p in pasos:
        print("  " + p)
    print("-" * 56)
    print("OK: la cadena completa enlaza ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
