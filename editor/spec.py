"""Render specification consumed by the Phase 3 video editor."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class VideoFormat(str, Enum):
    SHORTS = "shorts"          # 1080x1920 (9:16) - Shorts/TikTok/Reels
    LANDSCAPE = "landscape"    # 1920x1080 (16:9)

    @property
    def resolution(self) -> tuple[int, int]:
        return (1080, 1920) if self is VideoFormat.SHORTS else (1920, 1080)


@dataclass
class RenderSpec:
    """Everything the editor needs to assemble one video."""

    audio_path: Path
    background_path: Path
    output_path: Path
    format: VideoFormat = VideoFormat.SHORTS
    captions_path: Path | None = None
    music_path: Path | None = None
    music_volume_db: float = -18.0
    duck_music: bool = True
    intro_path: Path | None = None
    outro_path: Path | None = None
    watermark_path: Path | None = None
    background_effects: dict = field(default_factory=dict)  # blur, zoom, speed...
    # Reddit-style title card overlaid at the start, then faded out.
    title_card_path: Path | None = None
    intro_seconds: float = 0.0          # how long the card stays before fading
    card_fade_seconds: float = 0.5      # fade-out duration
