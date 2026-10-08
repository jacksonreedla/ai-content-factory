"""ElevenLabs TTS - premium cloud voices, key-gated like Claude/OpenAI."""
from __future__ import annotations

import logging
from pathlib import Path

import requests

from voices.base import TTSEngine, TTSRequest

log = logging.getLogger("acf.tts.elevenlabs")

BASE_URL = "https://api.elevenlabs.io/v1"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"  # "Rachel"


class ElevenLabsEngine(TTSEngine):
    name = "elevenlabs"

    def __init__(self, api_key: str = "", model_id: str = "eleven_multilingual_v2",
                 timeout_s: int = 300):
        self.api_key = api_key
        self.model_id = model_id
        self.timeout_s = timeout_s

    def is_available(self) -> bool:
        return bool(self.api_key)

    def list_voices(self) -> list[str]:
        try:
            r = requests.get(f"{BASE_URL}/voices",
                             headers={"xi-api-key": self.api_key}, timeout=15)
            r.raise_for_status()
            return [f'{v["voice_id"]} ({v["name"]})' for v in r.json().get("voices", [])]
        except requests.RequestException as exc:
            log.warning("Could not list ElevenLabs voices: %s", exc)
            return []

    def synthesize(self, request: TTSRequest) -> Path:
        voice = request.voice_id or DEFAULT_VOICE
        try:
            r = requests.post(
                f"{BASE_URL}/text-to-speech/{voice}",
                headers={"xi-api-key": self.api_key},
                json={"text": request.text, "model_id": self.model_id},
                timeout=self.timeout_s,
            )
            r.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"ElevenLabs request failed: {exc}") from exc
        output = request.output_path.with_suffix(".mp3")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(r.content)
        return output
