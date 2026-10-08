"""Audio post-processing: normalization, silence trim, duration probing.

Uses FFmpeg when present; degrades gracefully when it isn't.
"""
from __future__ import annotations

import contextlib
import logging
import shutil
import subprocess
import wave
from pathlib import Path

log = logging.getLogger("acf.audio")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def post_process(path: Path, *, normalize: bool = True,
                 trim_silence: bool = True) -> Path:
    """Loudness-normalize and trim leading/trailing silence in place.

    No-op (with a log line) if FFmpeg is not installed.
    """
    if not ffmpeg_available():
        log.info("FFmpeg not found - skipping normalize/trim for %s", path.name)
        return path
    filters = []
    if trim_silence:
        # trim leading silence, then reverse-trim trailing silence
        filters.append("silenceremove=start_periods=1:start_threshold=-45dB")
        filters.append("areverse")
        filters.append("silenceremove=start_periods=1:start_threshold=-45dB")
        filters.append("areverse")
    if normalize:
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if not filters:
        return path

    tmp = path.with_suffix(".tmp" + path.suffix)
    cmd = ["ffmpeg", "-y", "-i", str(path), "-af", ",".join(filters), str(tmp)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        tmp.replace(path)
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("FFmpeg post-processing failed (%s); keeping raw audio", exc)
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)
    return path


def _wave_concat_with_gap(first: Path, second: Path, output: Path,
                          gap_s: float) -> Path:
    """Concatenate two WAVs with a silence gap using the stdlib wave module.

    Assumes both files share sample rate / width / channels (true for a single
    TTS engine). Raises on mismatch so the caller can fall back.
    """
    with wave.open(str(first), "rb") as a, wave.open(str(second), "rb") as b:
        if a.getparams()[:3] != b.getparams()[:3]:  # channels, width, rate
            raise wave.Error("wav parameter mismatch")
        params = a.getparams()
        frames_a = a.readframes(a.getnframes())
        frames_b = b.readframes(b.getnframes())
        silence = b"\x00" * (int(gap_s * a.getframerate())
                             * a.getsampwidth() * a.getnchannels())
    with wave.open(str(output), "wb") as out:
        out.setparams(params)
        out.writeframes(frames_a + silence + frames_b)
    return output


def concat_with_gap(first: Path, second: Path, output: Path,
                    gap_s: float = 0.4) -> Path:
    """Join ``first`` + silence + ``second`` into ``output``.

    Prefers FFmpeg (handles any format); falls back to a stdlib WAV concat.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    if ffmpeg_available():
        cmd = ["ffmpeg", "-y", "-i", str(first), "-i", str(second),
               "-filter_complex",
               f"[0]apad=pad_dur={gap_s}[a0];[a0][1]concat=n=2:v=0:a=1[out]",
               "-map", "[out]", str(output)]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            return output
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("FFmpeg concat failed (%s); trying stdlib WAV concat", exc)
    return _wave_concat_with_gap(first, second, output, gap_s)


def audio_duration_s(path: Path) -> float:
    """Duration in seconds. WAV natively, anything else via ffprobe."""
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate() or 1)
        except (wave.Error, OSError) as exc:
            log.warning("Could not read wav duration: %s", exc)
    if ffprobe_available():
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                check=True, capture_output=True, text=True, timeout=60,
            ).stdout.strip()
            return float(out)
        except (subprocess.SubprocessError, ValueError, OSError) as exc:
            log.warning("ffprobe failed for %s: %s", path.name, exc)
    return 0.0
