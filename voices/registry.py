"""TTS engine factory with graceful fallback.

Order: the configured engine, then Windows SAPI (pyttsx3) if allowed -
so the pipeline always produces audio even before Piper/keys are set up.
Kokoro and XTTS slots exist in config and will be added here when
implemented; selecting them falls back with a clear log message.
"""
from __future__ import annotations

import logging

from app.config import Config
from voices.base import TTSEngine
from voices.elevenlabs_engine import ElevenLabsEngine
from voices.kokoro_engine import KokoroEngine
from voices.openai_tts_engine import OpenAITTSEngine
from voices.piper_engine import PiperEngine
from voices.sapi_engine import SapiEngine

log = logging.getLogger("acf.tts")


class TTSUnavailableError(RuntimeError):
    pass


def _make(name: str, config: Config) -> TTSEngine | None:
    if name == "piper":
        return PiperEngine(exe=config.get("voice.piper_exe", "piper"),
                           model_path=config.get("voice.piper_model", ""))
    if name == "kokoro":
        return KokoroEngine(
            voice=config.get("voice.voice_id", "") or "am_adam",
            lang_code=config.get("voice.kokoro_lang", "a"),
            model_path=config.get("voice.kokoro_model_path", ""),
            voices_path=config.get("voice.kokoro_voices_path", ""),
            quantized=config.get("voice.kokoro_quantized", True))
    if name == "sapi":
        return SapiEngine()
    if name == "elevenlabs":
        return ElevenLabsEngine(
            api_key=config.get("voice.elevenlabs_api_key", ""),
            model_id=config.get("voice.elevenlabs_model", "eleven_multilingual_v2"))
    if name == "openai":
        return OpenAITTSEngine(api_key=config.get("ai.openai.api_key", ""))
    log.warning("TTS engine '%s' is not implemented yet", name)
    return None


def build_engine(config: Config) -> TTSEngine:
    """Return the first available engine: configured -> SAPI fallback."""
    preferred = config.get("voice.engine", "piper")
    candidates = [preferred]
    if config.get("voice.fallback_to_sapi", True) and preferred != "sapi":
        candidates.append("sapi")

    for name in candidates:
        engine = _make(name, config)
        if engine and engine.is_available():
            if name != preferred:
                log.warning("Voice engine '%s' unavailable - falling back to '%s'",
                            preferred, name)
            return engine

    raise TTSUnavailableError(
        f"No TTS engine available. '{preferred}' is not set up "
        f"(Settings -> Voice) and the SAPI fallback needs: pip install pyttsx3"
    )
