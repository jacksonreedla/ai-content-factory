"""Story domain model: a piece of source content moving through the factory."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StoryStatus(str, Enum):
    NEW = "new"                 # fetched, not yet scored
    SCORED = "scored"           # scored, awaiting approval (or auto-approved)
    APPROVED = "approved"       # user/auto approved for production
    REJECTED = "rejected"       # below threshold or user rejected
    REWRITTEN = "rewritten"     # narration exists
    PRODUCED = "produced"       # video rendered
    PUBLISHED = "published"     # uploaded


# The ten score axes produced by the Story Analyst agent.
SCORE_KEYS = (
    "entertainment", "emotional", "shock", "suspense", "length_fit",
    "narration_quality", "click_potential", "virality", "originality",
    "retention",
)


@dataclass
class StoryScores:
    """0-10 scores per axis plus computed overall."""

    values: dict[str, float] = field(default_factory=dict)
    overall: float = 0.0
    reasoning: str = ""

    @classmethod
    def from_llm_json(cls, data: dict[str, Any]) -> "StoryScores":
        values = {}
        for key in SCORE_KEYS:
            try:
                values[key] = max(0.0, min(10.0, float(data.get(key, 0))))
            except (TypeError, ValueError):
                values[key] = 0.0
        overall = data.get("overall")
        try:
            overall = max(0.0, min(10.0, float(overall)))
        except (TypeError, ValueError):
            overall = round(sum(values.values()) / max(len(values), 1), 2)
        return cls(values=values, overall=overall, reasoning=str(data.get("reasoning", "")))

    def to_json(self) -> str:
        return json.dumps({"values": self.values, "overall": self.overall,
                           "reasoning": self.reasoning})

    @classmethod
    def from_json(cls, raw: str | None) -> "StoryScores | None":
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return cls(values=data.get("values", {}),
                       overall=float(data.get("overall", 0)),
                       reasoning=data.get("reasoning", ""))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None


@dataclass
class Story:
    id: int | None
    source: str                 # "reddit" (later: rss, news, file, ...)
    source_id: str              # e.g. reddit post id - unique per source
    title: str
    text: str
    author: str = ""
    subreddit: str = ""
    url: str = ""
    upvotes: int = 0
    num_comments: int = 0
    created_utc: float = 0.0
    nsfw: bool = False
    status: StoryStatus = StoryStatus.NEW
    scores: StoryScores | None = None
    rejected_reason: str = ""

    @property
    def word_count(self) -> int:
        return len(self.text.split())
