"""The 'prioritize wild titles' toggle boosts out-of-pocket stories at scoring."""
from __future__ import annotations

import json

from database.repositories import StoryRepo
from models.story import SCORE_KEYS, Story, StoryStatus
from tests.test_pipeline import make_pipeline

# A mediocre AI score (5.0) - below the 6.5 default threshold.
_low = {k: 5 for k in SCORE_KEYS}
_low["overall"] = 5.0
_low["reasoning"] = "average story"
LOW_SCORE = json.dumps(_low)


def _seed_wild(db) -> int:
    return StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id="wild1",
        title="I hate my disabled sister", text="word " * 300,
        subreddit="aita", upvotes=2000, num_comments=100))


def test_wild_priority_boosts_above_threshold(config, db):
    config.set("scoring.prioritize_wild_titles", True, persist=False)
    story_id = _seed_wild(db)

    make_pipeline(config, db, [LOW_SCORE]).run_stage("score")

    story = StoryRepo(db).get(story_id)
    assert story.status in (StoryStatus.APPROVED, StoryStatus.SCORED)
    assert story.scores.overall >= 6.5          # 5.0 + boost cleared threshold
    assert story.scores.values.get("wild_title", 0) > 0


def test_without_priority_low_score_is_rejected(config, db):
    config.set("scoring.prioritize_wild_titles", False, persist=False)
    story_id = _seed_wild(db)

    make_pipeline(config, db, [LOW_SCORE]).run_stage("score")

    assert StoryRepo(db).get(story_id).status == StoryStatus.REJECTED


def test_mundane_title_not_rescued_by_toggle(config, db):
    config.set("scoring.prioritize_wild_titles", True, persist=False)
    story_id = StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id="mild1",
        title="My quiet afternoon reading a book", text="word " * 300,
        subreddit="casual", upvotes=100, num_comments=5))

    make_pipeline(config, db, [LOW_SCORE]).run_stage("score")

    # A tame title gets little/no boost, so it stays below threshold.
    assert StoryRepo(db).get(story_id).status == StoryStatus.REJECTED
