"""Windows SAPI voices via pyttsx3 - the zero-install fallback engine.

Quality is basic, but it guarantees the pipeline produces audio on any
Windows machine before the user sets up Piper/Kokoro/ElevenLabs.
"""
from __future__ import annotations

import logging
from pathlib import Path

from voices.base import TTSEngine, TTSRequest

log = logging.getLogger("acf.tts.sapi")

_BASE_RATE = 200  # pyttsx3 default words-per-minute


class SapiEngine(TTSEngine):
    name = "sapi"

    def is_available(self) -> bool:
        try:
            import pyttsx3  # noqa: F401
            return True
        except ImportError:
            return False

    def _engine(self):
        import pyttsx3
        return pyttsx3.init()

    def list_voices(self) -> list[str]:
        try:
            engine = self._engine()
            return [v.id for v in engine.getProperty("voices")]
        except Exception as exc:
            log.warning("Could not list SAPI voices: %s", exc)
            return []

    def synthesize(self, request: TTSRequest) -> Path:
        engine = self._engine()
        engine.setProperty("rate", int(_BASE_RATE * request.speed))
        if request.voice_id:
            engine.setProperty("voice", request.voice_id)
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        engine.save_to_file(request.text, str(request.output_path))
        engine.runAndWait()
        if not request.output_path.exists():
            raise RuntimeError("SAPI produced no output file")
        return request.output_path
