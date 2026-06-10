"""Voz (TTS con Piper) + gestor de salidas.

`OutputManager.say(texto)` muestra en pantalla y, si el TTS está activo, lo dice
en voz. `VozTTS` usa Piper (lazy) y reproduce el wav con `afplay` (macOS). Si
Piper o la voz no están, el gestor sigue en modo texto (degrada con aviso).

Barge-in (cortar la voz cuando el usuario empieza a hablar) → Prompt 7.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import wave
from typing import Optional

from ..core.trace import EventCallback, TraceEvent, emit
from ..core.world_state import WorldState


class VozTTS:
    """Síntesis de voz con Piper. Degrada si falta la lib o el modelo de voz."""

    def __init__(self, voice: str = "es_ES-davefx-medium") -> None:
        self.voice = voice
        self._voice_obj = None

    async def start(self) -> bool:
        try:
            from piper import PiperVoice  # lazy

            path = self._voice_path()
            if path is None:
                return False
            self._voice_obj = PiperVoice.load(path)
            return True
        except Exception:
            return False

    def _voice_path(self) -> Optional[str]:
        """Busca el modelo `.onnx` de la voz (env NOVA_PIPER_DIR o ~/.local/share/piper)."""
        candidates = []
        env_dir = os.environ.get("NOVA_PIPER_DIR")
        if env_dir:
            candidates.append(os.path.join(env_dir, f"{self.voice}.onnx"))
        candidates.append(
            os.path.expanduser(f"~/.local/share/piper/{self.voice}.onnx")
        )
        for c in candidates:
            if os.path.exists(c):
                return c
        return None

    async def speak(self, texto: str) -> None:
        if self._voice_obj is None:
            return
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._synth_and_play, texto)

    def _synth_and_play(self, texto: str) -> None:  # corre en executor (bloqueante)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            with wave.open(path, "wb") as wav:
                self._voice_obj.synthesize(texto, wav)
            # Reproducción: afplay (macOS). En otros SO, ajustar acá.
            os.system(f'afplay "{path}" >/dev/null 2>&1')
        finally:
            try:
                os.remove(path)
            except OSError:
                pass


class OutputManager:
    """Gestor de salidas: pantalla siempre; voz si hay TTS activo."""

    def __init__(
        self,
        world: Optional[WorldState] = None,
        tts: Optional[VozTTS] = None,
        on_event: Optional[EventCallback] = None,
        to_screen: bool = True,
    ) -> None:
        self.world = world
        self.tts = tts
        self.on_event = on_event
        self.to_screen = to_screen

    async def say(self, texto: str, proactivo: bool = False) -> None:
        etiqueta = "NOVA(aviso)" if proactivo else "NOVA"
        if self.to_screen:
            print(f"{etiqueta}> {texto}")
        if self.world is not None:
            await self.world.append_event(
                {"fuente": "salida", "tipo": "voz" if self.tts else "texto", "texto": texto, "proactivo": proactivo}
            )
        if self.on_event is not None:
            ev = TraceEvent(
                etapa="salida", agente="voz" if self.tts else "pantalla", grupo="local",
                modelo="-", detalle=texto, estado="ok",
            )
            await emit(self.on_event, ev)
        if self.tts is not None:
            try:
                await self.tts.speak(texto)
            except Exception:
                pass  # si la voz falla, ya quedó en pantalla
