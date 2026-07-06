# plugins/captions/word_timing.py
from dataclasses import dataclass


@dataclass
class WordTiming:
    word: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class SubtitleArtifacts:
    ass_path: str
    srt_path: str
