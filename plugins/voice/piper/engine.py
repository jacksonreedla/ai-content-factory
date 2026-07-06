# plugins/voice/piper/engine.py
import logging
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from plugins.voice.base import VoiceOpts, AudioClip

log = logging.getLogger(__name__)


class PiperVoiceEngine:
    """VoiceEngine over the `piper` phonemizer binary.

    Satisfies the VoiceEngine protocol. If the piper binary is not on PATH,
    `synthesize` falls back to a silent PCM wav of the right duration so the
    pipeline stays runnable in environments without TTS (and tests don't need
    the binary). The fallback is logged at WARNING.
    """

    def __init__(self, piper_bin: str = "piper",
                 models_dir: str = "",
                 fallback_silence: bool = True) -> None:
        self.piper_bin = piper_bin
        self.models_dir = models_dir
        self.fallback_silence = fallback_silence

    def available(self) -> bool:
        return shutil.which(self.piper_bin) is not None

    def synthesize(self, text: str, opts: VoiceOpts,
                   out_path: Path) -> AudioClip:
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if not text.strip():
            raise ValueError("cannot synthesize empty text")
        if self.available():
            try:
                return self._synth_piper(text, opts, out_path)
            except Exception as e:
                log.warning("piper failed (%s); falling back to silence", e)
        if self.fallback_silence:
            return self._synth_silence(text, opts, out_path)
        raise RuntimeError(f"piper unavailable and fallback disabled")

    def _synth_piper(self, text: str, opts: VoiceOpts,
                     out_path: Path) -> AudioClip:
        # Piper reads text on stdin and writes wav on stdout.
        cmd = [self.piper_bin, "--model", opts.voice,
               "--output_file", str(out_path)]
        if opts.speed != 1.0:
            cmd += ["--length-scale", str(1.0 / opts.speed)]
        subprocess.run(cmd, input=text.encode("utf-8"),
                       check=True, capture_output=True)
        dur = _wav_duration(out_path)
        return AudioClip(path=out_path, duration_sec=dur)

    @staticmethod
    def _synth_silence(text: str, opts: VoiceOpts,
                       out_path: Path) -> AudioClip:
        # Generate a short silent wav whose length tracks word count so the
        # downstream editor has something to chew on. ~0.4s per word at speed.
        words = max(1, len(text.split()))
        duration = max(1.0, words * 0.4 / max(0.1, opts.speed))
        sample_rate = 22050
        n_samples = int(duration * sample_rate)
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            # Silent frames (zeros).
            w.writeframes(struct.pack("<" + "h" * n_samples, *([0] * n_samples)))
        log.warning("piper unavailable; wrote %.1fs silent wav as fallback",
                    duration)
        return AudioClip(path=out_path, duration_sec=duration)


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()
