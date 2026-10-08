"""Kokoro TTS engine: pure logic + registry wiring (no model download)."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.config import DEFAULTS, Config
from voices.base import TTSRequest
from voices.kokoro_engine import DEFAULT_VOICE, KokoroEngine
from voices.registry import _make


def test_default_voice_is_us_adam():
    engine = KokoroEngine()
    assert engine.name == "kokoro"
    assert engine.voice == "am_adam" == DEFAULT_VOICE
    assert engine.lang_code == "a"


def test_list_voices_includes_am_adam():
    voices = KokoroEngine().list_voices()
    assert "am_adam" in voices
    assert all(isinstance(v, str) for v in voices)


def test_empty_text_raises_before_touching_model():
    # Must raise on empty text without importing kokoro/soundfile.
    engine = KokoroEngine()
    with pytest.raises(RuntimeError, match="empty text"):
        engine.synthesize(TTSRequest(text="   ", output_path=Path("x.wav")))


def test_to_numpy_handles_plain_arrays():
    import numpy as np
    out = KokoroEngine._to_numpy([0.1, -0.2, 0.3])
    assert isinstance(out, np.ndarray)
    assert out.dtype == np.float32
    assert out.shape == (3,)


def test_registry_builds_kokoro_with_configured_voice():
    cfg = Config(dict(DEFAULTS))
    cfg.set("voice.voice_id", "am_michael", persist=False)
    engine = _make("kokoro", cfg)
    assert isinstance(engine, KokoroEngine)
    assert engine.voice == "am_michael"


def test_registry_kokoro_defaults_to_adam_when_blank():
    cfg = Config(dict(DEFAULTS))
    cfg.set("voice.voice_id", "", persist=False)
    engine = _make("kokoro", cfg)
    assert engine.voice == "am_adam"



def test_chunk_text_splits_long_narration():
    long = " ".join([f"Sentence number {i} here." for i in range(200)])
    chunks = KokoroEngine._chunk_text(long)
    assert len(chunks) > 1
    assert all(len(c) <= 800 for c in chunks)   # comfortably bounded
    # No text is lost: every sentence marker survives across the chunks.
    assert "".join(chunks).count("Sentence number") == 200


def test_short_text_is_single_chunk():
    assert KokoroEngine._chunk_text("Just one short line.") == \
        ["Just one short line."]


def test_default_model_paths_point_into_data_models():
    engine = KokoroEngine()
    assert engine.model_path.name.endswith(".onnx")
    assert "models" in engine.model_path.parts
    assert engine.voices_path.name == "voices-v1.0.bin"
