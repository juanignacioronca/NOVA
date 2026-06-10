"""Fuente de audio: micrófono → VAD (Silero) → STT (faster-whisper) → Conductor.

El texto transcripto entra al pipeline del Conductor **como si lo hubiera escrito
el usuario** (reusa la comprensión + defensa anti-inyección del Prompt 3: lo
percibido es DATO, no instrucción de sistema). Wake-word queda como placeholder
detrás de un flag (off por defecto).

Backends (mic, vad, stt) inyectables → testeable sin hardware ni modelos.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, List, Optional

from ..core.security import detectar_inyeccion
from ..core.trace import EventCallback
from ..core.world_state import WorldState
from .base import BaseSource
from .config import AudioConfig

OnText = Callable[[str], Awaitable[None]]
VadFn = Callable[[object], bool]
SttFn = Callable[[List[object]], Awaitable[str]]


class Microphone:
    """Captura real por micrófono (lazy sounddevice). Genera chunks de audio."""

    def __init__(self, sample_rate: int = 16000, block: float = 0.5) -> None:
        self.sample_rate = sample_rate
        self.block = block
        self._stream = None

    async def open(self) -> bool:
        import sounddevice as sd  # lazy

        self._queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def _callback(indata, frames, time_info, status):  # corre en hilo de audio
            loop.call_soon_threadsafe(self._queue.put_nowait, indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate, channels=1, dtype="float32",
            blocksize=int(self.sample_rate * self.block), callback=_callback,
        )
        self._stream.start()
        return True

    async def chunks(self, stop: asyncio.Event):
        while not stop.is_set():
            try:
                yield await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue

    async def close(self) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None


class SileroVAD:
    """Detección de voz (lazy silero-vad)."""

    def __init__(self, sample_rate: int = 16000, threshold: float = 0.5) -> None:
        self.sample_rate = sample_rate
        self.threshold = threshold
        self._model = None

    def load(self) -> None:
        from silero_vad import load_silero_vad  # lazy

        self._model = load_silero_vad()

    def __call__(self, chunk) -> bool:
        import torch  # lazy

        tensor = torch.as_tensor(chunk).squeeze()
        prob = float(self._model(tensor, self.sample_rate).item())
        return prob >= self.threshold


class WhisperSTT:
    """Transcripción local (lazy faster-whisper)."""

    def __init__(self, model_size: str = "base", sample_rate: int = 16000) -> None:
        self.model_size = model_size
        self.sample_rate = sample_rate
        self._model = None

    def load(self) -> None:
        from faster_whisper import WhisperModel  # lazy

        self._model = WhisperModel(self.model_size, device="auto", compute_type="int8")

    async def __call__(self, chunks: List[object]) -> str:
        import numpy as np  # lazy

        audio = np.concatenate([np.asarray(c).reshape(-1) for c in chunks]).astype("float32")
        loop = asyncio.get_event_loop()
        segments, _ = await loop.run_in_executor(None, lambda: self._model.transcribe(audio, language="es"))
        return " ".join(seg.text for seg in segments).strip()


class AudioSource(BaseSource):
    name = "audio"

    def __init__(
        self,
        world: WorldState,
        on_text: OnText,
        cfg: AudioConfig,
        *,
        mic=None,
        vad: Optional[VadFn] = None,
        stt: Optional[SttFn] = None,
        enabled: bool = True,
        on_event: Optional[EventCallback] = None,
    ) -> None:
        super().__init__(world, enabled, on_event)
        self.on_text = on_text
        self.cfg = cfg
        self._mic = mic
        self._vad = vad
        self._stt = stt

    async def start(self) -> bool:
        try:
            if self._mic is None:
                self._mic = Microphone(self.cfg.sample_rate)
                if not await self._mic.open():
                    await self._emit("audio", "micrófono no disponible", estado="alerta")
                    return False
            if self._vad is None:
                vad = SileroVAD(self.cfg.sample_rate, self.cfg.vad_threshold)
                vad.load()
                self._vad = vad
            if self._stt is None:
                stt = WhisperSTT(sample_rate=self.cfg.sample_rate)
                stt.load()
                self._stt = stt
        except Exception as exc:  # ImportError (sin libs) o error de device/modelo
            await self._emit("audio", f"audio no disponible: {exc}", estado="alerta")
            return False
        await self._emit("audio", "micrófono + VAD + STT listos")
        return True

    async def run(self, stop: asyncio.Event) -> None:
        buffer: List[object] = []
        hablando = False
        async for chunk in self._mic.chunks(stop):
            if stop.is_set():
                break
            if self._vad(chunk):
                hablando = True
                buffer.append(chunk)
            elif hablando:
                # Fin de una intervención: transcribir lo acumulado.
                hablando = False
                pedazos, buffer = buffer, []
                await self._procesar(pedazos)

    async def _procesar(self, chunks: List[object]) -> None:
        try:
            texto = (await self._stt(chunks)).strip()
        except Exception as exc:
            await self._emit("audio", f"STT falló: {exc}", estado="alerta")
            return
        if not texto:
            return
        # Lo percibido es DATO no confiable: se marca si hay intento de override.
        inyeccion = detectar_inyeccion(texto)
        await self.world.append_event(
            {"fuente": "audio", "tipo": "utterance", "texto": texto, "inyeccion": inyeccion}
        )
        await self._emit("audio", f"escuchado: {texto}", estado="alerta" if inyeccion else "ok")
        if self.on_text is not None:
            await self.on_text(texto)

    async def stop(self) -> None:
        if self._mic is not None and hasattr(self._mic, "close"):
            try:
                await self._mic.close()
            except Exception:
                pass
