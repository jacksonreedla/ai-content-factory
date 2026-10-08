"""Word-level transcription via faster-whisper.

The model loads lazily on first use and is cached per (model, device).
If a GPU is auto-selected but the CUDA runtime is missing/broken (e.g. the
``cublas64_12.dll``/``cudnn`` libraries are not installed), transcription
transparently falls back to CPU instead of failing.

On Windows the CUDA runtime wheels (``nvidia-cublas-cu12`` /
``nvidia-cudnn-cu12``) install their DLLs under ``site-packages\\nvidia\\*\\bin``,
which is not on the DLL search path by default. We register those folders at
import time so faster-whisper can find them without any manual PATH edits.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger("acf.whisper")

_MODEL_CACHE: dict[tuple[str, str], object] = {}

# Substrings that indicate the failure is a missing/broken GPU runtime rather
# than a genuine transcription problem, so retrying on CPU is worthwhile.
_CUDA_ERROR_HINTS = (
    "cublas", "cudnn", "cuda", "cudart", "libcublas", "gpu", "nvrtc",
    "no kernel image", "cufft",
)


def _register_cuda_dll_dirs() -> None:
    """Add the pip-installed NVIDIA runtime DLL folders to the search path.

    No-op on non-Windows platforms or when the wheels are not installed.
    """
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    try:
        import nvidia  # namespace package created by the nvidia-*-cu12 wheels
    except ImportError:
        return
    import glob
    registered = 0
    for pkg_root in getattr(nvidia, "__path__", []):
        for bin_dir in glob.glob(os.path.join(pkg_root, "*", "bin")):
            if os.path.isdir(bin_dir):
                try:
                    os.add_dll_directory(bin_dir)
                    registered += 1
                except OSError:
                    pass
    if registered:
        log.info("Registered %d NVIDIA CUDA DLL folder(s) for GPU transcription.",
                 registered)


_register_cuda_dll_dirs()


class WhisperNotInstalledError(RuntimeError):
    pass


class WhisperTranscriber:
    def __init__(self, model_size: str = "base", device: str = "auto",
                 language: str = "en"):
        self.model_size = model_size
        self.device = device
        self.language = language
        # Device actually in use; may drop to "cpu" after a GPU failure.
        self._active_device = device

    # ------------------------------------------------------------------ model
    def _build(self, device: str):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise WhisperNotInstalledError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ) from exc
        key = (self.model_size, device)
        if key not in _MODEL_CACHE:
            compute = "int8" if device in ("auto", "cpu") else "float16"
            log.info("Loading Whisper model '%s' (%s, %s)...",
                     self.model_size, device, compute)
            _MODEL_CACHE[key] = WhisperModel(
                self.model_size, device=device, compute_type=compute)
        return _MODEL_CACHE[key]

    @staticmethod
    def _is_cuda_error(exc: Exception) -> bool:
        msg = str(exc).lower()
        return any(hint in msg for hint in _CUDA_ERROR_HINTS)

    # -------------------------------------------------------------- transcribe
    def _run(self, model, audio_path: Path) -> list[dict]:
        segments, _info = model.transcribe(
            str(audio_path), word_timestamps=True,
            language=self.language or None, vad_filter=True,
        )
        words: list[dict] = []
        # Iteration is where faster-whisper actually runs compute, so any
        # GPU-runtime failure surfaces here.
        for segment in segments:
            for w in segment.words or []:
                text = w.word.strip()
                if text:
                    words.append({"word": text, "start": float(w.start),
                                  "end": float(w.end)})
        return words

    def transcribe(self, audio_path: Path) -> list[dict]:
        """Return [{word, start, end}, ...] with clean word text."""
        try:
            words = self._run(self._build(self._active_device), audio_path)
        except WhisperNotInstalledError:
            raise
        except Exception as exc:
            if self._active_device == "cpu" or not self._is_cuda_error(exc):
                raise
            log.warning("GPU transcription failed (%s); retrying on CPU. "
                        "Install the CUDA runtime libraries to use the GPU.", exc)
            _MODEL_CACHE.pop((self.model_size, self._active_device), None)
            self._active_device = "cpu"
            words = self._run(self._build("cpu"), audio_path)
        log.info("Transcribed %s: %d words", audio_path.name, len(words))
        return words
