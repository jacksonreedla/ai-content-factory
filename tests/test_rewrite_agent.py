"""Rewrite agent: closing engagement question (LLM path, fallback, toggle)."""
from __future__ import annotations

from agents.base import AgentContext
from agents.rewrite_agent import RewriteAgent
from api.llm.base import LLMError
from api.llm.router import LLMRouter
from app.prompt_manager import PromptManager
from database.repositories import NarrationRepo, StoryRepo
from models.story import Story, StoryStatus
from tests.fakes import FakeProvider

# 45 words - comfortably above the agent's minimum-length guard.
NARRATION = (
    "My sister crashed my car and blamed me for lending it to her in the "
    "first place. I refused to pay for the repairs, so our whole family "
    "turned on me overnight. I still think standing my ground was the only "
    "reasonable thing left to do here.")


def seed_approved(db) -> int:
    story_id = StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id="rw1", title="My sister crashed my car",
        text="body " * 80, subreddit="aita", upvotes=3000, num_comments=120))
    StoryRepo(db).set_status(story_id, StoryStatus.APPROVED)
    return story_id


def make_ctx(config, db, responses=None, available=True) -> AgentContext:
    router = LLMRouter(config, extra_providers={
        "ollama": FakeProvider(responses or [], available=available)})
    return AgentContext(config=config, db=db, llm=router,
                        prompts=PromptManager(), data={})


def latest(db, story_id) -> str:
    return NarrationRepo(db).latest_for_story(story_id)["text"]


# ------------------------------------------------------------------ unit tests
def test_clean_question_adds_mark_and_strips_noise():
    assert RewriteAgent._clean_question('"Am I the bad guy"') == "Am I the bad guy?"
    assert RewriteAgent._clean_question("Question: Was I wrong.") == "Was I wrong?"
    assert RewriteAgent._clean_question("Who is right?\nextra") == "Who is right?"
    assert RewriteAgent._clean_question("") == ""


def test_closing_question_falls_back_when_llm_raises(config, db):
    config.set("rewrite.engagement_fallbacks", ["Only fallback?"], persist=False)

    class Raising:
        def complete(self, *a, **k):
            raise LLMError("offline")

    ctx = AgentContext(config=config, db=db, llm=Raising(),
                       prompts=PromptManager(), data={})
    story = Story(id=1, source="reddit", source_id="x", title="t", text="t")
    assert RewriteAgent()._closing_question(ctx, story, NARRATION) == "Only fallback?"


# ------------------------------------------------------------------ agent tests
def test_engagement_question_appended_from_llm(config, db):
    story_id = seed_approved(db)
    ctx = make_ctx(config, db, [NARRATION, "Am I the villain here"])
    result = RewriteAgent().execute(ctx)
    assert result.ok

    text = latest(db, story_id)
    assert text.endswith("Am I the villain here?")
    assert text.count("?") == 1          # exactly one closing question
    assert NARRATION.split(".")[0] in text  # body preserved


def test_no_double_question_when_body_already_ends_with_one(config, db):
    story_id = seed_approved(db)
    body = NARRATION.rstrip(".") + ", so was I really the problem?"
    ctx = make_ctx(config, db, [body, "A second question"])
    RewriteAgent().execute(ctx)

    text = latest(db, story_id)
    assert text.count("?") == 1
    assert "A second question" not in text


def test_toggle_off_leaves_narration_unchanged(config, db):
    config.set("rewrite.engagement_question", False, persist=False)
    story_id = seed_approved(db)
    ctx = make_ctx(config, db, [NARRATION])
    RewriteAgent().execute(ctx)

    text = latest(db, story_id)
    assert text == NARRATION            # nothing appended
    assert "?" not in text
