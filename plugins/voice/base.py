# plugins/voice/base.py
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VoiceOpts:
    voice: str = "en_US-lessac-medium"
    speed: float = 1.0
    pitch: float = 1.0
    emotion: str = "neutral"
    volume: float = 1.0


@dataclass
class AudioClip:
    path: Path
    duration_sec: float
