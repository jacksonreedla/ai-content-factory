"""OpenAI TTS - uses the same API key as the OpenAI LLM provider."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from voices.base import TTSEngine, TTSRequest

log = logging.getLogger("acf.tts.openai")

API_URL = "https://api.openai.com/v1/audio/speech"
VOICES = ["alloy", "ash", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer"]


class OpenAITTSEngine(TTSEngine):
    name = "openai"

    def __init__(self, api_key: str = "", model: str = "tts-1", timeout_s: int = 300):
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s

    def is_available(self) -> bool:
        return bool(self.api_key)

    def list_voices(self) -> list[str]:
        return VOICES

    def synthesize(self, request: TTSRequest) -> Path:
        try:
            r = requests.post(
                API_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "voice": request.voice_id or "onyx",
                    "input": request.text,
                    "speed": max(0.25, min(4.0, request.speed)),
                },
                timeout=self.timeout_s,
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"OpenAI TTS request failed: {exc}") from exc
        output = request.output_path.with_suffix(".mp3")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(r.content)
        return output
