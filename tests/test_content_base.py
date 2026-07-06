# tests/test_content_base.py
from datetime import datetime, timedelta

from core.models import Story
from plugins.content.base import dedupe_by_source_id, filter_by_age


def _story(source_id, age_hours, score=100):
    return Story(
        source="reddit", source_id=source_id, subreddit="x", author="a",
        title="t", body_text="b", score=score, num_comments=1,
        created_utc=(datetime.utcnow() - timedelta(hours=age_hours)).timestamp(),
        permalink="",
    )


def test_filter_by_age():
    stories = [_story("a", 1), _story("b", 200)]
    out = filter_by_age(stories, max_age_hours=168)
    assert [s.source_id for s in out] == ["a"]


def test_dedupe_keeps_first():
    stories = [_story("a", 1, 100), _story("a", 1, 500)]
    out = dedupe_by_source_id(stories)
    assert len(out) == 1
    assert out[0].score == 100  # first wins
