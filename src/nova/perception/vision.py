"""Fuente de video + **modo Sentinela** (muestreo adaptativo).

Compara frames consecutivos (diferencia simple). Si no hay cambios por
`idle_seconds`, baja a un frame cada `idle_interval` (Sentinela); ante un cambio
relevante vuelve a `active_interval` y manda el frame al modelo de visión local
(`sentinela_vision`) para describir la escena → entra al WorldState.

Backends (cámara, diff, describe) son inyectables → testeable sin cámara ni numpy.
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, Optional

from ..core.trace import EventCallback
from ..core.world_state import WorldState
from .base import BaseSource
from .config import VideoConfig

# Backends inyectables.
Camera = "OpenCVCamera"  # solo para doc; ver clase abajo
DiffFn = Callable[[object, object], float]
DescribeFn = Callable[[object], Awaitable[str]]


def _numpy_diff(a: object, b: object) -> float:
    """Diferencia media de píxel entre dos frames (lazy numpy)."""
    import numpy as np

    aa = np.asarray(a, dtype="int16")
    bb = np.asarray(b, dtype="int16")
    if aa.shape != bb.shape:
        return 255.0
    return float(np.abs(aa - bb).mean())


class OpenCVCamera:
    """Cámara real (lazy opencv). `read()` es no bloqueante (executor)."""

    def __init__(self, device: int = 0) -> None:
        self.device = device
        self._cap = None

    async def open(self) -> bool:
        import cv2  # lazy

        self._cap = cv2.VideoCapture(self.device)
        return bool(self._cap is not None and self._cap.isOpened())

    async def read(self):
        if self._cap is None:
            return None
        loop = asyncio.get_event_loop()
        ok, frame = await loop.run_in_executor(None, self._cap.read)
        return frame if ok else None

    async def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def frame_to_data_url(frame) -> str:
    """Codifica un frame BGR (opencv) a data URL JPEG base64 (lazy opencv)."""
    import base64

    import cv2

    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        raise RuntimeError("no se pudo codificar el frame")
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


class VisionSource(BaseSource):
    name = "video"

    def __init__(
        self,
        world: WorldState,
        cfg: VideoConfig,
        *,
        camera=None,
        diff: Optional[DiffFn] = None,
        describe: Optional[DescribeFn] = None,
        enabled: bool = True,
        on_event: Optional[EventCallback] = None,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        super().__init__(world, enabled, on_event)
        self.cfg = cfg
        self._camera = camera
        self._diff = diff
        self._describe = describe
        self._clock = clock
        self._sleeper = sleeper
        self.sentinel = False          # estado actual (para inspección/tests)
        self.last_interval = cfg.active_interval

    async def start(self) -> bool:
        # Cámara real si no se inyectó una.
        if self._camera is None:
            try:
                self._camera = OpenCVCamera(self.cfg.device)
                if not await self._camera.open():
                    await self._emit("video", "cámara no disponible", estado="alerta")
                    return False
            except Exception as exc:  # ImportError (sin opencv) o error de device
                await self._emit("video", f"cámara/opencv no disponible: {exc}", estado="alerta")
                return False
        # Detector de cambios real (numpy) si no se inyectó.
        if self._diff is None:
            try:
                import numpy  # noqa: F401

                self._diff = _numpy_diff
            except ImportError:
                await self._emit("video", "numpy no disponible (sin detección de cambios)", estado="alerta")
                return False
        await self._emit("video", "cámara lista; muestreo activo")
        return True

    async def run(self, stop: asyncio.Event) -> None:
        prev = None
        last_change = self._clock()
        while not stop.is_set():
            frame = await self._camera.read()
            if frame is None:
                await self._emit("video", "sin frame (fin de stream / cámara caída)", estado="alerta")
                break
            now = self._clock()
            changed = prev is not None and self._diff(prev, frame) >= self.cfg.change_threshold

            if changed:
                last_change = now
                if self.sentinel:
                    self.sentinel = False
                    await self._emit("sentinela", "cambio detectado → muestreo activo")
                detalle = await self._describir(frame)
                await self.world.append_event(
                    {"fuente": "video", "tipo": "vision", "detalle": detalle, "sentinel": False}
                )
                await self._emit("video", detalle)
            elif not self.sentinel and (now - last_change) >= self.cfg.idle_seconds:
                self.sentinel = True
                await self._emit("sentinela", "sin cambios → modo Sentinela (muestreo lento)")

            prev = frame
            self.last_interval = self.cfg.idle_interval if self.sentinel else self.cfg.active_interval
            await self._sleeper(self.last_interval)

    async def _describir(self, frame) -> str:
        if self._describe is None:
            return "cambio en cámara"
        try:
            return await self._describe(frame)
        except Exception as exc:  # describe degrada sin tirar el loop
            await self._emit("video", f"visión local no disponible: {exc}", estado="alerta")
            return "cambio en cámara (sin descripción)"

    async def stop(self) -> None:
        if self._camera is not None and hasattr(self._camera, "close"):
            try:
                await self._camera.close()
            except Exception:
                pass


def make_describe(sentinela, world: WorldState) -> DescribeFn:
    """Crea el `describe` real: codifica el frame y se lo pasa al SentinelaAgent."""

    async def describe(frame) -> str:
        data_url = frame_to_data_url(frame)
        desc = await sentinela.observar(data_url)
        await world.set("escena", desc)
        return desc

    return describe
