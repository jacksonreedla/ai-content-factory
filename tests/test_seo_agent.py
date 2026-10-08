"""SEO agent: custom-tag merge, short summary, and no-AI fallback."""
from __future__ import annotations

import json

from agents.base import AgentContext
from agents.seo_agent import SEOAgent, _merge_tags, short_summary
from api.llm.router import LLMRouter
from app.prompt_manager import PromptManager
from database.repositories import NarrationRepo, SettingsRepo, StoryRepo
from models.story import Story, StoryStatus
from tests.fakes import FakeProvider

LONG_NARRATION = (
    "My sister borrowed my car without asking. She returned it with an empty "
    "tank and a fresh dent on the door. When I confronted her she laughed it "
    "off like it was nothing. So I stopped covering for her with our parents. "
    "The fallout was immediate and far bigger than she expected.")


def seed(db, narration=LONG_NARRATION) -> int:
    story_id = StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id="seo1", title="Original Title",
        text="body " * 60, subreddit="aita", upvotes=2000, num_comments=80))
    NarrationRepo(db).add(story_id, "storytelling", 60, narration)
    StoryRepo(db).set_status(story_id, StoryStatus.REWRITTEN)
    return story_id


def make_ctx(config, db, responses=None, available=True) -> AgentContext:
    router = LLMRouter(config, extra_providers={
        "ollama": FakeProvider(responses or [], available=available)})
    return AgentContext(config=config, db=db, llm=router,
                        prompts=PromptManager(), data={})


def stored_metadata(db, story_id) -> dict:
    return json.loads(SettingsRepo(db).get(f"metadata.story.{story_id}"))


# ------------------------------------------------------------------ unit tests
def test_merge_tags_dedups_case_insensitively():
    assert _merge_tags(["Reddit", "story"], ["reddit", "AITA"]) == \
        ["Reddit", "story", "AITA"]


def test_short_summary_breaks_on_sentence_and_fits():
    s = short_summary(LONG_NARRATION, max_chars=80)
    assert len(s) <= 80
    assert s.endswith(".") or s.endswith("...")
    assert s.startswith("My sister borrowed my car")


def test_short_summary_empty_text():
    assert short_summary("", 100) == ""


# ------------------------------------------------------------------ agent tests
def test_custom_tags_merged_into_tags_and_hashtags(config, db):
    config.set("seo.custom_tags", ["reddit stories", "aita"], persist=False)
    ai = json.dumps({"title": "Great hook", "description": "long desc",
                     "hashtags": ["#drama"], "tags": ["family", "revenge"],
                     "pinned_comment": "?"})
    story_id = seed(db)
    result = SEOAgent().execute(make_ctx(config, db, [ai]))
    assert result.ok

    meta = stored_metadata(db, story_id)
    assert meta["tags"] == ["family", "revenge", "reddit stories", "aita"]
    # custom tags also surfaced as #hashtags (spaces stripped)
    assert "#drama" in meta["hashtags"]
    assert "#redditstories" in meta["hashtags"]
    assert "#aita" in meta["hashtags"]


def test_short_summary_replaces_description(config, db):
    config.set("seo.custom_tags", [], persist=False)
    config.set("seo.short_summary", True, persist=False)
    config.set("seo.summary_max_chars", 120, persist=False)
    ai = json.dumps({"title": "t", "description": "AI wrote three long "
                     "paragraphs here " * 20, "hashtags": [], "tags": []})
    story_id = seed(db)
    SEOAgent().execute(make_ctx(config, db, [ai]))

    meta = stored_metadata(db, story_id)
    assert len(meta["description"]) <= 120
    assert meta["description"].startswith("My sister borrowed my car")


def test_fallback_applies_tags_and_summary_without_ai(config, db):
    config.set("seo.custom_tags", ["storytime"], persist=False)
    story_id = seed(db)
    # No provider available -> AI metadata step fails, fallback path runs.
    result = SEOAgent().execute(make_ctx(config, db, available=False))
    assert result.ok
    assert result.data["ai_failed"] == 1

    meta = stored_metadata(db, story_id)
    assert meta["title"] == "Original Title"        # from the story
    assert "storytime" in meta["tags"]
    assert meta["description"].startswith("My sister borrowed my car")
    assert "#storytime" in meta["hashtags"]
