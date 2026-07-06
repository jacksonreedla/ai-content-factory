# tests/test_voice_engine.py
import wave

import pytest

from plugins.voice.base import VoiceOpts
from plugins.voice.piper.engine import PiperVoiceEngine


def test_silence_fallback_writes_wav(tmp_path):
    # piper binary almost certainly not on PATH in CI → exercises fallback.
    eng = PiperVoiceEngine(fallback_silence=True)
    out = tmp_path / "voice.wav"
    clip = eng.synthesize("hello world this is a test", VoiceOpts(), out)
    assert out.exists()
    assert clip.duration_sec > 0
    # Verify it's a real wav.
    with wave.open(str(out), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getframerate() == 22050


def test_empty_text_raises(tmp_path):
    eng = PiperVoiceEngine()
    with pytest.raises(ValueError):
        eng.synthesize("   ", VoiceOpts(), tmp_path / "x.wav")


def test_speed_affects_duration(tmp_path):
    eng = PiperVoiceEngine()
    slow = eng.synthesize("one two three four", VoiceOpts(speed=0.5),
                          tmp_path / "slow.wav")
    fast = eng.synthesize("one two three four", VoiceOpts(speed=2.0),
                          tmp_path / "fast.wav")
    assert slow.duration_sec > fast.duration_sec
