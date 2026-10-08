"""Voice generation (Phase 2): Piper/Kokoro local TTS first, then
ElevenLabs/OpenAI TTS. The TTSEngine interface is defined now."""
from voices.base import TTSEngine, TTSRequest

__all__ = ["TTSEngine", "TTSRequest"]
