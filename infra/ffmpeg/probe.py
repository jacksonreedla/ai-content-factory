# infra/ffmpeg/probe.py
import json
import logging
from pathlib import Path

from infra.ffmpeg.run import ffprobe_bin
import subprocess

log = logging.getLogger(__name__)


def _probe(path: Path) -> dict:
    cmd = [
        ffprobe_bin(), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    out = subprocess.run(cmd, capture_output=True, check=True)
    return json.loads(out.stdout)


def probe_duration(path: Path) -> float:
    data = _probe(path)
    fmt = data.get("format", {})
    if "duration" in fmt:
        return float(fmt["duration"])
    for s in data.get("streams", []):
        if "duration" in s:
            return float(s["duration"])
    return 0.0


def probe_resolution(path: Path) -> tuple[int, int]:
    data = _probe(path)
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            return int(s.get("width", 0)), int(s.get("height", 0))
    return 0, 0
