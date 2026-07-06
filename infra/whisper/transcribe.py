# infra/whisper/transcribe.py
import logging
from pathlib import Path

from plugins.captions.word_timing import WordTiming

log = logging.getLogger(__name__)


class MissingDependency(RuntimeError):
    """Raised when faster-whisper is not installed."""


def transcribe_words(audio_path: Path, model_size: str = "base",
                     language: str | None = None) -> list[WordTiming]:
    """Transcribe audio into word-level timings using faster-whisper.

    Raises MissingDependency if faster-whisper isn't installed.
    """
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as e:
        raise MissingDependency(
            "faster-whisper is not installed; run pip install faster-whisper"
        ) from e

    log.info("loading whisper model %r", model_size)
    model = WhisperModel(model_size, compute_type="int8")
    segments, _info = model.transcribe(
        str(audio_path), word_timestamps=True, language=language or None,
    )
    words: list[WordTiming] = []
    for seg in segments:
        for w in getattr(seg, "words", None) or []:
            words.append(WordTiming(
                word=w.word.strip(),
                start=round(w.start, 3),
                end=round(w.end, 3),
                confidence=getattr(w, "probability", 1.0),
            ))
    return words
