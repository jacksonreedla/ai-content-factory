"""FFmpeg-based video assembly.

``build_render_command`` is a pure function (fully unit-testable) that
turns a RenderSpec into an ffmpeg argv list. ``render`` executes it.

Pipeline per video:
  background clip -> loop to narration length -> scale/crop to format
  -> optional speed/blur/brightness -> burn .ass captions
  -> optional Reddit title card overlay (fades out after the title is read)
  voiceover -> optional music (volume + sidechain ducking) -> mix
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from editor.spec import RenderSpec

log = logging.getLogger("acf.render")


class RenderError(RuntimeError):
    pass


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def escape_filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter argument (Windows-safe)."""
    text = str(path).replace("\\", "/")
    return text.replace(":", "\\:").replace("'", "\\'")


def build_render_command(spec: RenderSpec, duration_s: float) -> list[str]:
    """Build the full ffmpeg argv. Pure - no filesystem access."""
    width, height = spec.format.resolution
    effects = spec.background_effects or {}

    cmd: list[str] = ["ffmpeg", "-y",
                      "-stream_loop", "-1", "-i", str(spec.background_path),
                      "-i", str(spec.audio_path)]
    has_music = spec.music_path is not None
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", str(spec.music_path)]

    has_card = bool(spec.title_card_path) and spec.intro_seconds > 0
    if has_card:
        card_index = 2 + (1 if has_music else 0)
        cmd += ["-loop", "1", "-i", str(spec.title_card_path)]

    # ---------------- video filter chain
    vf = [f"scale={width}:{height}:force_original_aspect_ratio=increase",
          f"crop={width}:{height}"]
    speed = float(effects.get("speed", 1.0))
    if speed and speed != 1.0:
        vf.append(f"setpts=PTS/{speed:.3f}")
    if effects.get("blur"):
        vf.append("boxblur=8")
    brightness = float(effects.get("brightness", 0.0))
    if brightness:
        vf.append(f"eq=brightness={brightness:.2f}")
    # Slow Ken Burns zoom pulse so the background is never fully static (a key
    # trigger for "unoriginal/low-quality" flags). Applied before captions are
    # burned in, so the text overlay stays crisp and does not scale.
    zoom = float(effects.get("zoom", 0.0))
    if zoom:
        # zoompan re-stamps output at a fixed fps while keeping every input
        # frame (d=1). If the source clip runs faster than this fps (gameplay
        # clips are usually 60fps), those extra frames get stretched across the
        # timeline -> the background plays in slow motion. Resample to the same
        # fps *first* so frame count matches the output timeline and speed is
        # preserved regardless of the clip's native frame rate.
        vf.append("fps=30")
        vf.append(
            f"zoompan=z='1+{zoom:.3f}*(1-cos(on/45))/2'"
            f":d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":s={width}x{height}:fps=30")
    if spec.captions_path:
        vf.append(f"ass='{escape_filter_path(spec.captions_path)}'")

    video_parts = []
    if has_card:
        fade = float(spec.card_fade_seconds)
        show_until = spec.intro_seconds + fade
        video_parts.append(f"[0:v]{','.join(vf)}[vbase]")
        video_parts.append(
            f"[{card_index}:v]format=rgba,"
            # No fade-in: the card is fully visible the instant the video starts.
            f"fade=t=out:st={spec.intro_seconds:.2f}:d={fade:.2f}:alpha=1[card]")
        video_parts.append(
            f"[vbase][card]overlay=x=(W-w)/2:y=(H-h)*0.28:"
            f"enable='lte(t,{show_until:.2f})'[vout]")
    else:
        video_parts.append(f"[0:v]{','.join(vf)}[vout]")
    video_chain = ";".join(video_parts)

    # ---------------- audio filter chain
    if has_music:
        duck = ("sidechaincompress=threshold=0.03:ratio=10:attack=20:release=400"
                if spec.duck_music else "anull")
        audio_chain = (
            f"[1:a]asplit=2[voice][sc];"
            f"[2:a]volume={spec.music_volume_db:.1f}dB[m];"
            f"[m][sc]{duck}[ducked];"
            f"[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        audio_chain = "[1:a]anull[aout]"

    cmd += ["-filter_complex", f"{video_chain};{audio_chain}",
            "-map", "[vout]", "-map", "[aout]",
            "-t", f"{duration_s:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(spec.output_path)]
    return cmd


def render(spec: RenderSpec, duration_s: float, timeout_s: int = 1800) -> Path:
    """Run ffmpeg; raises RenderError with the tail of stderr on failure."""
    if not ffmpeg_available():
        raise RenderError(
            "FFmpeg not found. Install it (winget install ffmpeg) and restart.")
    spec.output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = build_render_command(spec, duration_s)
    log.info("Rendering %s (%.1fs, %s)...", spec.output_path.name, duration_s,
             spec.format.value)
    log.debug("ffmpeg cmd: %s", " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"Render timed out after {timeout_s}s") from exc
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", "replace")
        raise RenderError(f"FFmpeg failed:\n{stderr[-800:]}")
    if not spec.output_path.exists():
        raise RenderError("FFmpeg reported success but produced no file")
    return spec.output_path
