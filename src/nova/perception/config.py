"""Carga de `config/perception.yaml` a dataclasses con defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml

from ..paths import PERCEPTION_YAML


@dataclass
class AudioConfig:
    enabled: bool = True
    sample_rate: int = 16000
    vad_threshold: float = 0.5


@dataclass
class VideoConfig:
    enabled: bool = True
    device: int = 0
    active_interval: float = 0.5
    # Campos de sentinela (se copian acá para que VisionSource tenga todo junto).
    idle_seconds: float = 5.0
    idle_interval: float = 3.0
    change_threshold: float = 12.0


@dataclass
class TTSConfig:
    enabled: bool = True
    voice: str = "es_ES-davefx-medium"


@dataclass
class WakeWordConfig:
    enabled: bool = False
    model: str = "hey_jarvis"


@dataclass
class ProactiveConfig:
    enabled: bool = True
    check_interval: float = 5.0
    demo_reminder_seconds: float = 15.0


@dataclass
class PerceptionConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    video: VideoConfig = field(default_factory=VideoConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    wake_word: WakeWordConfig = field(default_factory=WakeWordConfig)
    proactive: ProactiveConfig = field(default_factory=ProactiveConfig)


def _pick(d: dict, *keys):
    """Subdict con solo las claves presentes (para no romper si faltan campos)."""
    return {k: d[k] for k in keys if isinstance(d, dict) and k in d}


def load_perception_config(path: Optional[str] = None) -> PerceptionConfig:
    """Lee el YAML; si no existe o está incompleto, usa defaults."""
    yaml_path = path or PERCEPTION_YAML
    data: dict = {}
    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        data = {}

    audio = data.get("audio", {}) or {}
    video = data.get("video", {}) or {}
    sentinel = data.get("sentinel", {}) or {}
    tts = data.get("tts", {}) or {}
    wake = data.get("wake_word", {}) or {}
    proactive = data.get("proactive", {}) or {}

    return PerceptionConfig(
        audio=AudioConfig(**_pick(audio, "enabled", "sample_rate", "vad_threshold")),
        video=VideoConfig(
            **_pick(video, "enabled", "device", "active_interval"),
            **_pick(sentinel, "idle_seconds", "idle_interval", "change_threshold"),
        ),
        tts=TTSConfig(**_pick(tts, "enabled", "voice")),
        wake_word=WakeWordConfig(**_pick(wake, "enabled", "model")),
        proactive=ProactiveConfig(**_pick(proactive, "enabled", "check_interval", "demo_reminder_seconds")),
    )
