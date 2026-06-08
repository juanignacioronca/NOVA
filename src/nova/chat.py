"""`python -m nova.chat` — chat interactivo por texto con NOVA.

Escribís, NOVA responde (vía Conductor) y se ve el flujo en vivo (stream de
`TraceEvent`). Si falta info, NOVA pregunta y retoma con tu respuesta. Soporta
imágenes: `/img <ruta> <texto>`. `salir`/`exit` o Ctrl-C terminan limpio.
"""

from __future__ import annotations

import asyncio
import shlex
from typing import List, Optional, Tuple

from .core.conductor import Conductor
from .core.trace import TraceEvent
from .env import load_env

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RESET = "\033[0m"

BANNER = (
    f"{BOLD}NOVA{RESET} · chat por texto  "
    f"{DIM}(/img <ruta> <texto> para imágenes · 'salir' o Ctrl-C para terminar){RESET}"
)
EXIT_WORDS = {"salir", "exit", "quit", "q"}


def _parse_img(linea: str) -> Tuple[str, List[str]]:
    """`/img ruta texto...` → (texto, [ruta]). Soporta rutas con comillas."""
    resto = linea[len("/img"):].strip()
    try:
        partes = shlex.split(resto)
    except ValueError:
        partes = resto.split()
    if not partes:
        return "", []
    ruta = partes[0]
    texto = " ".join(partes[1:]) or "¿qué ves en esta imagen?"
    return texto, [ruta]


async def _print_event(ev: TraceEvent) -> None:
    color = {"pregunta": YELLOW, "alerta": YELLOW, "error": "\033[31m"}.get(ev.estado, DIM)
    print(f"{color}   {ev.compact()}{RESET}")


async def _prompt(loop: asyncio.AbstractEventLoop, text: str) -> str:
    return await loop.run_in_executor(None, input, text)


async def _loop() -> None:
    conductor = Conductor(on_event=_print_event)  # stream de eventos al REPL
    print(BANNER)
    print("─" * 64)
    loop = asyncio.get_event_loop()
    while True:
        try:
            linea = (await _prompt(loop, f"{CYAN}tú>{RESET} ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nhasta luego 👋")
            return
        if not linea:
            continue
        if linea.lower() in EXIT_WORDS:
            print("hasta luego 👋")
            return

        if linea.startswith("/img"):
            texto, images = _parse_img(linea)
            if not images:
                print(f"{DIM}   uso: /img <ruta> <texto>{RESET}")
                continue
        else:
            texto, images = linea, None

        try:
            answer = await conductor.attend(texto, images=images)
        except FileNotFoundError as exc:
            print(f"{DIM}   [imagen no encontrada] {exc}{RESET}")
            continue
        except Exception as exc:  # nunca tirar la sesión por un error puntual
            print(f"{DIM}   [error] {exc}{RESET}")
            continue

        run = conductor.last_run
        etiqueta = "NOVA pregunta" if run["route"] == "aclaracion" else "NOVA"
        print(f"{BOLD}{etiqueta}>{RESET} {answer}")
        if run["route"] != "aclaracion":
            traza = " · ".join(
                [run["intent"], run["complexity"], " → ".join(run["agents"]) or "-", run.get("model", "-")]
            )
            print(f"{DIM}      {traza}{RESET}")


def main(argv: Optional[List[str]] = None) -> int:
    load_env()
    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
