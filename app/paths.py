"""Central definition of every filesystem path the app uses."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Code/data folders shipped with the repo
PROMPTS_DIR = ROOT / "prompts"
ASSETS_DIR = ROOT / "assets"
SETTINGS_DIR = ROOT / "settings"
PLUGINS_DIR = ROOT / "plugins"
DOCS_DIR = ROOT / "docs"

# Runtime folders (created on first launch, gitignored)
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "factory.db"
LOGS_DIR = DATA_DIR / "logs"
OUTPUT_DIR = DATA_DIR / "output"          # finished videos
AUDIO_DIR = DATA_DIR / "audio"            # generated voiceovers
CAPTIONS_DIR = DATA_DIR / "captions"      # .srt / .ass files
THUMBS_DIR = DATA_DIR / "thumbnails"
CARDS_DIR = DATA_DIR / "cards"            # generated Reddit title-card images
MEDIA_LIBRARY_DIR = DATA_DIR / "media_library"   # background gameplay etc.
MUSIC_DIR = DATA_DIR / "music"

CONFIG_PATH = SETTINGS_DIR / "config.json"

_RUNTIME_DIRS = (
    DATA_DIR, LOGS_DIR, OUTPUT_DIR, AUDIO_DIR, CAPTIONS_DIR,
    THUMBS_DIR, CARDS_DIR, MEDIA_LIBRARY_DIR, MUSIC_DIR, SETTINGS_DIR,
)

# Default subfolders of the background media library
MEDIA_CATEGORIES = (
    "minecraft", "subway_surfers", "gta", "satisfying",
    "nature", "rain", "space", "ocean",
)


def ensure_dirs() -> None:
    """Create all runtime directories if they do not exist."""
    for d in _RUNTIME_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    for cat in MEDIA_CATEGORIES:
        (MEDIA_LIBRARY_DIR / cat).mkdir(exist_ok=True)
