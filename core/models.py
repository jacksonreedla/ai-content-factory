# core/models.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional, Any

from core.enums import JobStage, NarrationStyle

# Progress callback: pct (0-100), optional message.
ProgressFn = Callable[..., None]


@dataclass
class SourceQuery:
    subreddits: list[str]
    min_score: int = 1000
    min_comments: int = 50
    max_age_hours: int = 168
    sort: str = "hot"            # hot | top | rising | new
    limit: int = 25


@dataclass
class Story:
    source: str                  # e.g. "reddit"
    source_id: str               # reddit fullname / id
    subreddit: str
    author: str
    title: str
    body_text: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    body_raw: Optional[str] = None


@dataclass
class StoryScore:
    entertainment: float
    suspense: float
    emotion: float
    shock: float
    virality: float
    quality: float
    retention: float
    overall: float
    confidence: float
    model: str = ""

    def passes(self, threshold: float) -> bool:
        return self.overall >= threshold


@dataclass
class Script:
    story_id: int
    style: NarrationStyle
    text: str
    model: str = ""
    word_count: int = 0
    reading_time: float = 0.0    # seconds


@dataclass
class JobContext:
    job_id: int
    story: Optional[Story] = None
    script: Optional[Script] = None
    artifacts: dict[str, Any] = field(default_factory=dict)

    def progress(self, pct: int, msg: str = "") -> None:  # pragma: no cover
        # Hook the runner overwrites; default no-op keeps dataclass usable.
        return None
