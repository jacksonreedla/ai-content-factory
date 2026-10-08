"""Background media library: category folders of gameplay/ambient clips.

Users drop .mp4/.mkv/.webm/.mov files into data/media_library/<category>/.
Selection is random or sequential (round-robin state kept by the caller,
usually in the app_settings table).
"""
from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Callable

from app.paths import MEDIA_LIBRARY_DIR

log = logging.getLogger("acf.media")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi"}


class MediaLibraryError(RuntimeError):
    pass


def list_categories(root: Path = MEDIA_LIBRARY_DIR) -> list[str]:
    if not root.exists():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())


def list_clips(category: str, root: Path = MEDIA_LIBRARY_DIR) -> list[Path]:
    folder = root / category
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.suffix.lower() in VIDEO_EXTENSIONS and p.is_file())


def pick_clip(category: str, mode: str = "random",
              state_get: Callable[[str], str | None] | None = None,
              state_set: Callable[[str, str], None] | None = None,
              root: Path = MEDIA_LIBRARY_DIR) -> Path:
    """Pick a background clip. Raises MediaLibraryError with setup help."""
    clips = list_clips(category, root)
    if not clips:
        raise MediaLibraryError(
            f"No background clips in '{root / category}'. Drop .mp4 gameplay "
            f"files there (or change the category in Settings -> Pipeline)."
        )
    if mode == "sequential" and state_get and state_set:
        key = f"media.seq.{category}"
        try:
            index = int(state_get(key) or 0)
        except ValueError:
            index = 0
        clip = clips[index % len(clips)]
        state_set(key, str((index + 1) % len(clips)))
        return clip
    return random.choice(clips)


def pick_music(music_dir: Path) -> Path | None:
    """Random royalty-free track from data/music, or None if empty."""
    if not music_dir.exists():
        return None
    tracks = sorted(p for p in music_dir.iterdir()
                    if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"})
    return random.choice(tracks) if tracks else None
