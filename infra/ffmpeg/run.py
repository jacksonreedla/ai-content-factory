# infra/ffmpeg/run.py
import logging
import shutil
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class MissingFFmpeg(RuntimeError):
    """Raised when the ffmpeg/ffprobe binary is not on PATH."""


def ffmpeg_bin() -> str:
    b = shutil.which("ffmpeg")
    if not b:
        raise MissingFFmpeg("ffmpeg not found on PATH")
    return "ffmpeg"


def ffprobe_bin() -> str:
    b = shutil.which("ffprobe")
    if not b:
        raise MissingFFmpeg("ffprobe not found on PATH")
    return "ffprobe"


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def run_ffmpeg(args: list[str], timeout: float = 1800.0,
               check: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with the given arg list (without the leading 'ffmpeg')."""
    cmd = [ffmpeg_bin()] + args
    log.debug("ffmpeg %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, check=check, timeout=timeout)
