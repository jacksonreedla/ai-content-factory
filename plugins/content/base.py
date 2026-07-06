# plugins/content/base.py
import time
from typing import Iterable

from core.models import Story


def filter_by_age(stories: Iterable[Story], max_age_hours: int) -> list[Story]:
    """Drop stories older than `max_age_hours` from now."""
    cutoff = time.time() - max_age_hours * 3600
    return [s for s in stories if s.created_utc >= cutoff]


def dedupe_by_source_id(stories: Iterable[Story]) -> list[Story]:
    """Keep the first occurrence of each source_id."""
    seen: set[str] = set()
    out: list[Story] = []
    for s in stories:
        if s.source_id in seen:
            continue
        seen.add(s.source_id)
        out.append(s)
    return out
