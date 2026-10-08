"""Caption contracts - Phase 2 implements faster-whisper + ASS styling."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CaptionStyle:
    mode: str = "word"                 # word | sentence
    font: str = "Montserrat ExtraBold"
    font_size: int = 90
    color: str = "#FFFFFF"
    highlight_color: str = "#FFD400"   # current word highlight
    outline: int = 7                   # thick black border -> "bubble" pop
    shadow: int = 3
    position: str = "center"           # top | center | bottom
    animation: str = "pop"             # none | pop | slide | karaoke


class Captioner(ABC):
    @abstractmethod
    def transcribe(self, audio_path: Path) -> list[dict]:
        """Return word-level timestamps: [{word, start, end}, ...]."""

    @abstractmethod
    def build_captions(self, words: list[dict], style: CaptionStyle,
                       output_path: Path) -> Path:
        """Write a styled .ass/.srt file and return its path."""
