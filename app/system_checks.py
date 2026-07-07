# app/system_checks.py
"""Availability checks for external tools / services. Pure, no side effects."""
import logging
import shutil
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def check_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def check_ffprobe() -> bool:
    return shutil.which("ffprobe") is not None


def check_piper(piper_bin: str = "piper") -> bool:
    return shutil.which(piper_bin) is not None


def check_whisper() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def check_ollama(host: str = "http://localhost:11434", timeout: float = 1.5) -> bool:
    """Best-effort ping of the Ollama API. Never raises."""
    try:
        req = urllib.request.Request(host + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def check_all(config=None, ollama_host: str = "http://localhost:11434") -> dict:
    """Return a status dict for the Dashboard / wizard.

    Keys: ffmpeg, ffprobe, piper, whisper, ollama, models_dir (exists?).
    """
    return {
        "ffmpeg": check_ffmpeg(),
        "ffprobe": check_ffprobe(),
        "piper": check_piper(),
        "whisper": check_whisper(),
        "ollama": check_ollama(ollama_host),
    }
