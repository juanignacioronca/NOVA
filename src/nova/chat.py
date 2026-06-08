"""`python -m nova.chat` — chat interactivo por texto con NOVA.

Escribís, NOVA responde (vía Conductor), y se muestra una línea de traza con
intención · complejidad · agente(s) · `proveedor:modelo` que respondió.
`salir`/`exit` o Ctrl-C terminan limpio.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

from .core.conductor import Conductor
from .env import load_env

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
RESET = "\033[0m"

BANNER = (
    f"{BOLD}NOVA{RESET} · chat por texto  "
    f"{DIM}(escribí 'salir' o Ctrl-C para terminar){RESET}"
)
EXIT_WORDS = {"salir", "exit", "quit", "q"}


async def _prompt(loop: asyncio.AbstractEventLoop, text: str) -> str:
    """Lee de stdin sin bloquear el event loop."""
    return await loop.run_in_executor(None, input, text)


async def _loop() -> None:
    conductor = Conductor()
    print(BANNER)
    print("─" * 64)
    loop = asyncio.get_event_loop()
    while True:
        try:
            user = (await _prompt(loop, f"{CYAN}tú>{RESET} ")).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nhasta luego 👋")
            return
        if not user:
            continue
        if user.lower() in EXIT_WORDS:
            print("hasta luego 👋")
            return
        try:
            answer = await conductor.attend(user)
        except Exception as exc:  # nunca tirar la sesión por un error puntual
            print(f"{DIM}[error] {exc}{RESET}")
            continue
        run = conductor.last_run
        print(f"{BOLD}NOVA>{RESET} {answer}")
        traza = " · ".join(
            [run["intent"], run["complexity"], " → ".join(run["agents"]), run.get("model", "-")]
        )
        print(f"{DIM}      {traza}{RESET}")


def main(argv: Optional[List[str]] = None) -> int:
    load_env()  # claves desde .env (si las hay)
    try:
        asyncio.run(_loop())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
