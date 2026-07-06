# plugins/music/ducker.py
import logging
from pathlib import Path
from typing import Optional

from infra.ffmpeg.probe import probe_duration
from infra.ffmpeg.run import run_ffmpeg

log = logging.getLogger(__name__)


class MusicDucker:
    """MusicTrack implementation: loop a music clip to a target length, fade
    in/out, and lower its volume (ducking side-chain is applied in the editor).

    Satisfies the MusicTrack protocol (a marker protocol).
    """

    def apply(self, track_path: str, target_seconds: float,
              out_path: str, volume: float = 0.5,
              fade_in: float = 1.0, fade_out: float = 2.0) -> str:
        src = Path(track_path)
        if not src.exists():
            raise FileNotFoundError(track_path)
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        dur = probe_duration(src) or 1.0
        loops = max(1, int(target_seconds // dur) + 1)
        afade_out_start = max(0.0, target_seconds - fade_out)
        af = (
            f"aloop=loop={loops}:size={int(dur*48000)},"
            f"atrim=duration={target_seconds:.3f},"
            f"afade=t=in:st=0:d={fade_in:.2f},"
            f"afade=t=out:st={afade_out_start:.3f}:d={fade_out:.2f},"
            f"volume={volume}"
        )
        run_ffmpeg([
            "-y", "-i", str(src),
            "-af", af,
            "-c:a", "aac", "-b:a", "160k",
            "-t", f"{target_seconds:.3f}",
            str(out),
        ])
        return str(out)
