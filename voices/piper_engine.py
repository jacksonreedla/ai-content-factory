"""Piper TTS - fast, free, local neural voices (https://github.com/rhasspy/piper).

Setup: download piper.exe and a voice model (.onnx), then set
Settings -> Voice: engine=piper, the exe path, and the model path.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from voices.base import TTSEngine, TTSRequest

log = logging.getLogger("acf.tts.piper")


class PiperEngine(TTSEngine):
    name = "piper"

    def __init__(self, exe: str = "piper", model_path: str = ""):
        self.exe = exe
        self.model_path = model_path

    def is_available(self) -> bool:
        exe_found = shutil.which(self.exe) is not None or Path(self.exe).exists()
        return exe_found and bool(self.model_path) and Path(self.model_path).exists()

    def list_voices(self) -> list[str]:
        return [Path(self.model_path).stem] if self.model_path else []

    def synthesize(self, request: TTSRequest) -> Path:
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        length_scale = 1.0 / max(request.speed, 0.1)  # piper: >1 = slower
        cmd = [
            self.exe, "--model", self.model_path,
            "--output_file", str(request.output_path),
            "--length_scale", f"{length_scale:.2f}",
        ]
        try:
            subprocess.run(cmd, input=request.text.encode("utf-8"),
                           check=True, capture_output=True, timeout=600)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", "replace")[:400] if exc.stderr else ""
            raise RuntimeError(f"Piper failed: {stderr}") from exc
        except (subprocess.SubprocessError, OSError) as exc:
            raise RuntimeError(f"Piper failed: {exc}") from exc
        if not request.output_path.exists():
            raise RuntimeError("Piper produced no output file")
        return request.output_path
