"""TTS engine contract - Phase 2 implements Piper/Kokoro/ElevenLabs/XTTS."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TTSRequest:
    text: str
    output_path: Path
    voice_id: str = ""
    speed: float = 1.0
    pitch: float = 0.0
    normalize_volume: bool = True
    trim_silence: bool = True


class TTSEngine(ABC):
    name: str = "tts"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def list_voices(self) -> list[str]: ...

    @abstractmethod
    def synthesize(self, request: TTSRequest) -> Path:
        """Generate speech audio; returns the written file path."""
