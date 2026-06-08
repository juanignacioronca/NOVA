"""Harness de prueba por texto.

Uso::

    python -m nova.cli "ponme un timer de 10 minutos"
    python -m nova.cli "organízame un finde de trekking"

Instancia el Conductor, corre `attend`, imprime la traza (intención,
complejidad, agentes que intervinieron, respuesta final) y confirma dónde quedó
el registro JSONL. Corre sin claves ni modelos (modo stub).
"""

from __future__ import annotations

import asyncio
import sys

from .core.conductor import Conductor
from .env import load_env

_BAR = "─" * 64


def _print_trace(conductor: Conductor) -> None:
    run = conductor.last_run
    print(_BAR)
    print(f"📝 Pedido     : {run['user_text']}")
    print(_BAR)
    print("① Comprensión")
    print(f"   intención  : {run['intent']}")
    print(f"   complejidad: {run['complexity']}")
    if run["entities"]:
        print(f"   entidades  : {run['entities']}")
    if run["understanding_note"]:
        print(f"   nota modelo: {run['understanding_note']}")
    print("② Ruteo")
    destino = "Grupo Local (Ollama)" if run["route"] == "local" else "Grupo Nube (PMO)"
    print(f"   ruta       : {run['route']}  →  {destino}")
    print(f"   agentes    : {' → '.join(run['agents'])}")
    print(f"   modelo     : {run.get('model', '-')}")
    print("③ Respuesta final")
    for line in run["final"].splitlines() or [""]:
        print(f"   {line}")
    print(_BAR)
    print(f"🗒  Registro   : {run['log_path']}")
    print(_BAR)


async def _run(text: str) -> None:
    conductor = Conductor()
    await conductor.attend(text)
    _print_trace(conductor)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('Uso: python -m nova.cli "<texto>"')
        return 2
    load_env()  # claves desde .env si existe (opcional en modo stub)
    text = " ".join(argv).strip()
    asyncio.run(_run(text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
