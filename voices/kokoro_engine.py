"""Kokoro TTS via ONNX runtime - free, local, high-quality voices.

Uses ``kokoro-onnx`` (https://github.com/thewh1teagle/kokoro-onnx) instead of
the PyTorch ``kokoro`` package, because that package pins ``numpy==1.26.4``
which has no wheel for Python 3.13 (it tries to compile numpy from source and
fails without a C++ compiler). The ONNX build installs cleanly on 3.13:

    pip install kokoro-onnx onnxruntime

The two model files download automatically on first use into ``data/models/``
(about 90 MB for the quantized model). Set the voice in Settings -> Voice
("Voice ID"), e.g. ``am_adam`` (US English male).
"""
from __future__ import annotations

import logging
import re
import urllib.request
import wave
from pathlib import Path

from app.paths import DATA_DIR
from voices.base import TTSEngine, TTSRequest

log = logging.getLogger("acf.tts.kokoro")

DEFAULT_VOICE = "am_adam"          # US English male "Adam"
SAMPLE_RATE = 24000                # Kokoro always outputs 24 kHz
MODELS_DIR = DATA_DIR / "models"

_RELEASE = ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
            "model-files-v1.0/")
MODEL_FILES = {
    True:  ("kokoro-v1.0.int8.onnx", _RELEASE + "kokoro-v1.0.int8.onnx"),
    False: ("kokoro-v1.0.onnx", _RELEASE + "kokoro-v1.0.onnx"),
}
VOICES_FILE = ("voices-v1.0.bin", _RELEASE + "voices-v1.0.bin")

# Map the app's lang_code ('a'/'b') to kokoro-onnx's espeak language.
_LANG_MAP = {"a": "en-us", "b": "en-gb"}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_MAX_CHUNK_CHARS = 400             # keep chunks well under the token limit

# A curated list for the UI / list_voices(); not exhaustive.
AMERICAN_VOICES = [
    "am_adam", "am_michael", "am_echo", "am_eric", "am_liam", "am_onyx",
    "am_puck", "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "af_alloy", "af_aoede",
]


class KokoroEngine(TTSEngine):
    name = "kokoro"

    def __init__(self, voice: str = DEFAULT_VOICE, lang_code: str = "a",
                 model_path: str = "", voices_path: str = "",
                 quantized: bool = True):
        self.voice = voice or DEFAULT_VOICE
        self.lang_code = lang_code or "a"
        self.quantized = bool(quantized)
        model_name = MODEL_FILES[self.quantized][0]
        self.model_path = Path(model_path) if model_path else MODELS_DIR / model_name
        self.voices_path = (Path(voices_path) if voices_path
                            else MODELS_DIR / VOICES_FILE[0])
        self._kokoro = None

    # --------------------------------------------------------------- availability
    def is_available(self) -> bool:
        """True if the ONNX libraries are importable (model auto-downloads)."""
        try:
            import importlib.util
            for mod in ("kokoro_onnx", "onnxruntime", "numpy"):
                if importlib.util.find_spec(mod) is None:
                    return False
            return True
        except Exception:  # pragma: no cover - defensive
            return False

    def list_voices(self) -> list[str]:
        return list(AMERICAN_VOICES)

    # ------------------------------------------------------------------ model io
    @staticmethod
    def _download(url: str, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        log.info("Downloading Kokoro model file %s ...", dest.name)
        urllib.request.urlretrieve(url, tmp)   # noqa: S310 (trusted GitHub URL)
        tmp.replace(dest)
        log.info("Saved %s", dest)

    def _ensure_models(self) -> None:
        if not self.model_path.exists():
            self._download(MODEL_FILES[self.quantized][1], self.model_path)
        if not self.voices_path.exists():
            self._download(VOICES_FILE[1], self.voices_path)

    @staticmethod
    def _init_espeak() -> None:
        """Point phonemizer at the bundled espeak-ng library.

        kokoro-onnx usually does this itself, but on Windows the lookup can
        fail; setting it explicitly (best-effort) avoids a first-run error.
        """
        try:
            import espeakng_loader
            from phonemizer.backend.espeak.wrapper import EspeakWrapper
            EspeakWrapper.set_library(espeakng_loader.get_library_path())
            try:
                EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
            except Exception:
                pass  # older phonemizer has no set_data_path
        except Exception as exc:  # espeak not needed / different backend
            log.debug("espeak auto-config skipped: %s", exc)

    def _get_kokoro(self):
        if self._kokoro is None:
            self._ensure_models()
            self._init_espeak()
            # phonemizer emits noisy "words count mismatch" WARNINGs on normal
            # punctuation/numbers; they don't affect the audio, so quiet them.
            logging.getLogger("phonemizer").setLevel(logging.ERROR)
            from kokoro_onnx import Kokoro
            log.info("Loading Kokoro ONNX model %s", self.model_path.name)
            self._kokoro = Kokoro(str(self.model_path), str(self.voices_path))
        return self._kokoro

    @staticmethod
    def _to_numpy(chunk):
        """Kokoro chunks may be torch tensors or numpy arrays."""
        import numpy as np
        if hasattr(chunk, "detach"):        # torch.Tensor
            chunk = chunk.detach().cpu().numpy()
        return np.asarray(chunk, dtype="float32")

    @staticmethod
    def _chunk_text(text: str) -> list[str]:
        """Split long text into sentence groups under the token limit."""
        chunks: list[str] = []
        current = ""
        for sentence in _SENTENCE_SPLIT.split(text):
            candidate = (current + " " + sentence).strip()
            if len(candidate) > _MAX_CHUNK_CHARS and current:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks or [text]

    def _write_wav(self, path: Path, samples) -> None:
        import numpy as np
        data = np.clip(np.asarray(samples, dtype="float32"), -1.0, 1.0)
        int16 = (data * 32767.0).astype("<i2")
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(int16.tobytes())

    # ----------------------------------------------------------------- synthesize
    def synthesize(self, request: TTSRequest) -> Path:  # type: ignore[name-defined]
        text = (request.text or "").strip()
        if not text:
            raise RuntimeError("Kokoro received empty text")

        import numpy as np

        voice = request.voice_id or self.voice
        speed = max(0.1, float(request.speed or 1.0))
        lang = _LANG_MAP.get(self.lang_code, "en-us")

        try:
            kokoro = self._get_kokoro()
            pieces = []
            gap = np.zeros(int(SAMPLE_RATE * 0.15), dtype="float32")
            for chunk in self._chunk_text(text):
                samples, _sr = kokoro.create(chunk, voice=voice, speed=speed,
                                             lang=lang)
                pieces.append(self._to_numpy(samples))
                pieces.append(gap)
            audio = np.concatenate(pieces[:-1]) if len(pieces) > 1 else pieces[0]
        except Exception as exc:
            raise RuntimeError(f"Kokoro synthesis failed: {exc}") from exc

        self._write_wav(request.output_path, audio)
        if not request.output_path.exists():
            raise RuntimeError("Kokoro produced no output file")
        return request.output_path
