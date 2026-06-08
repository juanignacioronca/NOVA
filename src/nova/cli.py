"""Harness de prueba por texto (one-shot).

Uso::

    python -m nova.cli "ponme un timer de 10 minutos"
    python -m nova.cli "organízame un finde de trekking el sábado con mi hermano"
    python -m nova.cli --img foto.png "¿qué es esto?"

Instancia el Conductor, corre `attend`, imprime la traza estructurada y confirma
dónde quedó el registro JSONL. Corre sin claves ni modelos (modo stub).
"""

from __future__ import annotations

import asyncio
import sys
from typing import List, Optional, Tuple

from .core.conductor import Conductor
from .env import load_env

_BAR = "─" * 64


def _parse_args(argv: List[str]) -> Tuple[str, List[str]]:
    """Extrae `--img <ruta>` (repetible) y devuelve (texto, imagenes)."""
    images: List[str] = []
    rest: List[str] = []
    i = 0
    while i < len(argv):
        if argv[i] in ("--img", "-i") and i + 1 < len(argv):
            images.append(argv[i + 1])
            i += 2
            continue
        rest.append(argv[i])
        i += 1
    return " ".join(rest).strip(), images


def _print_trace(conductor: Conductor) -> None:
    run = conductor.last_run
    print(_BAR)
    print(f"📝 Pedido     : {run['user_text']}")
    if run.get("multimodal"):
        print("   (con imagen)")
    print(_BAR)
    print("Traza")
    for ev in conductor.last_trace:
        print(f"   {ev.compact()}")
    print(_BAR)
    print("① Comprensión")
    print(f"   intención  : {run['intent']}")
    print(f"   complejidad: {run['complexity']}")
    print(f"   confianza  : {run['confianza']:.2f}")
    if run["entities"]:
        print(f"   entidades  : {run['entities']}")
    if run.get("inyeccion_detectada"):
        print("   seguridad  : ⚠ intento de override detectado (no obedecido)")
    if run["route"] == "aclaracion":
        print("② NOVA necesita aclarar")
        print(f"   pregunta   : {run['question']}")
    else:
        print("② Ruteo")
        print(f"   ruta       : {run['route']}")
        print(f"   agentes    : {' → '.join(run['agents']) or '-'}")
        print(f"   modelo     : {run['model']}")
        if run.get("supuesto"):
            print(f"   supuesto   : {run['supuesto']}")
        print("③ Respuesta final")
        for line in run["final"].splitlines() or [""]:
            print(f"   {line}")
    print(_BAR)
    print(f"🗒  Registro   : {run['log_path']}")
    print(_BAR)


async def _run(text: str, images: List[str]) -> None:
    conductor = Conductor()
    await conductor.attend(text, images=images or None)
    _print_trace(conductor)


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    text, images = _parse_args(args)
    if not text and not images:
        print('Uso: python -m nova.cli [--img <ruta>] "<texto>"')
        return 2
    load_env()  # claves desde .env si existe (opcional en modo stub)
    asyncio.run(_run(text, images))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
