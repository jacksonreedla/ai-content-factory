# plugins/editor/ffmpeg_editor.py
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from infra.ffmpeg.probe import probe_duration, probe_resolution
from infra.ffmpeg.run import run_ffmpeg

log = logging.getLogger(__name__)


# Target resolutions per export format.
_ASPECTS = {
    "shorts_vertical_9_16": ("9:16", 1080, 1920),
    "tiktok_9_16":          ("9:16", 1080, 1920),
    "reels_9_16":           ("9:16", 1080, 1920),
    "youtube_16_9":         ("16:9", 1920, 1080),
}


@dataclass
class EditSpec:
    voice_path: str
    background_path: str
    music_path: Optional[str] = None
    ass_path: Optional[str] = None
    format: str = "shorts_vertical_9_16"
    watermark_path: Optional[str] = None
    intro_path: Optional[str] = None
    outro_path: Optional[str] = None
    out_path: str = ""


@dataclass
class VideoFile:
    path: Path
    duration_sec: float
    width: int
    height: int
    size_bytes: int


class FFmpegEditor:
    """VideoEditor over ffmpeg subprocess. Builds a filter_complex that:

      - scales + crops the background to the target aspect, looped to narration
        length
      - overlays ASS captions (if provided) via the ass= filter
      - mixes narration + ducked music (sidechaincompress) when music is present
    """

    def compose(self, spec: EditSpec) -> VideoFile:
        if not spec.out_path:
            raise ValueError("EditSpec.out_path is required")
        out_path = Path(spec.out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        aspect, width, height = _ASPECTS.get(
            spec.format, _ASPECTS["shorts_vertical_9_16"])
        voice_dur = probe_duration(Path(spec.voice_path))
        duration = voice_dur or probe_duration(Path(spec.background_path)) or 5.0

        args = ["-y"]
        # Background input (-stream_loop to cover narration length).
        bg_loops = max(1, int(duration // (
            probe_duration(Path(spec.background_path)) or duration)) + 1)
        args += ["-stream_loop", str(bg_loops), "-i", spec.background_path]
        # Narration input.
        args += ["-i", spec.voice_path]
        input_count = 2
        # Optional music input.
        if spec.music_path:
            args += ["-i", spec.music_path]
            music_idx = input_count
            input_count += 1

        # Build filter_complex.
        filters = []
        # [0:v] background: scale to fill target, crop to aspect.
        filters.append(
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},setsar=1,"
            f"trim=duration={duration:.3f},setpts=PTS-STARTPTS[bg]")
        # Audio from narration [1:a].
        filters.append(f"[1:a]atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[voice]")
        # ASS captions, burned onto background.
        if spec.ass_path:
            # ass= needs escaped path; use forward slashes and quote colons.
            ass = Path(spec.ass_path).as_posix()
            ass_escaped = ass.replace(":", r"\:")
            filters.append(f"[bg][voice]ass='{ass_escaped}'[bgv]")
        else:
            filters.append("[bg]null[bgv]")
        # Music ducking.
        if spec.music_path:
            filters.append(
                f"[{music_idx}:a]atrim=duration={duration:.3f},"
                f"asetpts=PTS-STARTPTS,volume=0.5[bgmusic]")
            filters.append(
                "[voice][bgmusic]sidechaincompress=threshold=0.05:ratio=8"
                "[ducked]")
            audio_map = "[ducked]"
        else:
            audio_map = "[voice]"

        args += ["-filter_complex", ";".join(filters)]
        args += ["-map", "[bgv]", "-map", audio_map]
        args += [
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-r", "30",
            "-c:a", "aac", "-b:a", "192k",
            "-t", f"{duration:.3f}",
            str(out_path),
        ]
        run_ffmpeg(args)
        size = out_path.stat().st_size if out_path.exists() else 0
        return VideoFile(path=out_path, duration_sec=duration,
                         width=width, height=height, size_bytes=size)
