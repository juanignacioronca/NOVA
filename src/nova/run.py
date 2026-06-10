"""`python -m nova.run` — daemon de NOVA con el loop de percepción completo.

Arranca audio + texto + video + avisos proactivos en paralelo, con la traza en
vivo. Le hablás (o escribís) y responde por voz/pantalla; el modo Sentinela baja
el muestreo si no hay cambios. Se apaga limpio con Ctrl-C. Cada fuente degrada
sola si falta su hardware/modelo.
"""

from __future__ import annotations

import asyncio
import signal
import time

from .core.conductor import Conductor
from .core.proactivo import ProactiveScheduler
from .core.trace import TraceEvent
from .core.world_state import WorldState
from .env import load_env
from .output.voz import OutputManager, VozTTS
from .perception.audio import AudioSource
from .perception.config import load_perception_config
from .perception.loop import PerceptionLoop
from .perception.text import TextSource
from .perception.vision import VisionSource, make_describe

DIM = "\033[2m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _printer(ev: TraceEvent) -> None:
    color = {"alerta": YELLOW, "pregunta": YELLOW, "error": RED}.get(ev.estado, DIM)
    print(f"{color}  {ev.compact()}{RESET}")


async def _main() -> None:
    load_env()
    cfg = load_perception_config()

    world = WorldState()
    conductor = Conductor(world=world, on_event=_printer)

    # Voz (degrada a texto si Piper/voz no están).
    tts = None
    if cfg.tts.enabled:
        candidate = VozTTS(cfg.tts.voice)
        if await candidate.start():
            tts = candidate
        else:
            print(f"{YELLOW}  voz: Piper/voz '{cfg.tts.voice}' no disponible → salida solo por pantalla{RESET}")
    output = OutputManager(world, tts=tts, on_event=_printer)

    async def on_text(texto: str) -> None:
        answer = await conductor.attend(texto)
        await output.say(answer)

    # Fuentes de percepción (cada una degrada sola).
    sentinela = conductor.registry.get("sentinela")
    audio = AudioSource(world, on_text, cfg.audio, enabled=cfg.audio.enabled, on_event=_printer)
    video = VisionSource(
        world, cfg.video, describe=make_describe(sentinela, world),
        enabled=cfg.video.enabled, on_event=_printer,
    )
    texto = TextSource(world, on_text, on_event=_printer)
    proactivo = ProactiveScheduler(world, output, cfg.proactive, on_event=_printer)

    # Recordatorio demo para ver un aviso proactivo sin configurar nada.
    if cfg.proactive.demo_reminder_seconds > 0:
        await world.set("reminders", [{
            "id": "demo",
            "text": "tomar agua 💧",
            "due": time.time() + cfg.proactive.demo_reminder_seconds,
        }])

    loop = PerceptionLoop([audio, video, texto, proactivo], world, on_event=_printer)

    # Ctrl-C → apagado limpio.
    runloop = asyncio.get_event_loop()
    try:
        runloop.add_signal_handler(signal.SIGINT, loop.request_stop)
        runloop.add_signal_handler(signal.SIGTERM, loop.request_stop)
    except NotImplementedError:  # pragma: no cover - algunos entornos
        pass

    print(f"{BOLD}NOVA{RESET} · daemon de percepción  {DIM}(Ctrl-C para salir){RESET}")
    print("─" * 64)
    await loop.run()
    print("hasta luego 👋")


def main() -> int:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
