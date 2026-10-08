"""AI top-up safety net: fill thin research runs so no account runs dry."""
from __future__ import annotations

import agents.research_agent as ra
from agents.base import AgentContext
from agents.research_agent import ResearchAgent
from app.prompt_manager import PromptManager
from database.repositories import StoryRepo
from models.story import Story, StoryStatus


class FakeGen:
    """Stand-in StoryGenerator returning N distinct original stories."""
    def __init__(self, *a, **k):
        pass

    def generate(self, count):
        return [Story(id=None, source="ai", source_id=f"ai_top_{i}",
                      title=f"AI story {i}", text="word " * 200,
                      status=StoryStatus.NEW) for i in range(count)]


class BoomGen(FakeGen):
    def generate(self, count):
        raise RuntimeError("llm offline")


def _ctx(config, db):
    return AgentContext(config=config, db=db, llm=None,
                        prompts=PromptManager(), data={})


def _three_accounts(config):
    config.set("accounts", [{"name": "a"}, {"name": "b"}, {"name": "c"}],
               persist=False)


def test_topup_fills_the_gap(config, db, monkeypatch):
    monkeypatch.setattr(ra, "StoryGenerator", FakeGen)
    _three_accounts(config)
    config.set("ai_stories.topup_per_account", 2, persist=False)   # target 6
    n = ResearchAgent()._maybe_topup(_ctx(config, db), StoryRepo(db), [], added=2)
    assert n == 4                       # 6 target - 2 already = 4 generated


def test_topup_noop_when_target_met(config, db, monkeypatch):
    monkeypatch.setattr(ra, "StoryGenerator", FakeGen)
    _three_accounts(config)
    config.set("ai_stories.topup_per_account", 2, persist=False)   # target 6
    n = ResearchAgent()._maybe_topup(_ctx(config, db), StoryRepo(db), [], added=10)
    assert n == 0


def test_topup_respects_max(config, db, monkeypatch):
    monkeypatch.setattr(ra, "StoryGenerator", FakeGen)
    _three_accounts(config)
    config.set("ai_stories.topup_target", 50, persist=False)       # huge target
    config.set("ai_stories.topup_max", 3, persist=False)           # but capped
    n = ResearchAgent()._maybe_topup(_ctx(config, db), StoryRepo(db), [], added=0)
    assert n == 3


def test_topup_can_be_disabled(config, db, monkeypatch):
    monkeypatch.setattr(ra, "StoryGenerator", FakeGen)
    _three_accounts(config)
    config.set("ai_stories.topup_enabled", False, persist=False)
    n = ResearchAgent()._maybe_topup(_ctx(config, db), StoryRepo(db), [], added=0)
    assert n == 0


def test_topup_failure_is_non_fatal(config, db, monkeypatch):
    monkeypatch.setattr(ra, "StoryGenerator", BoomGen)
    _three_accounts(config)
    errors: list[str] = []
    n = ResearchAgent()._maybe_topup(_ctx(config, db), StoryRepo(db), errors, added=0)
    assert n == 0
    assert any("top-up" in e for e in errors)


def test_topup_rescues_run_with_no_working_sources(config, db, monkeypatch):
    """Even if every content source is off/failed, top-up keeps the run alive."""
    monkeypatch.setattr(ra, "StoryGenerator", FakeGen)
    _three_accounts(config)
    config.set("sources.enabled", [], persist=False)     # nothing runs
    config.set("ai_stories.topup_per_account", 1, persist=False)   # target 3

    result = ResearchAgent().execute(_ctx(config, db))
    assert result.ok, result.message
    assert result.data["topup"] == 3
    assert result.data["added"] == 3
    assert "AI top-up" in result.message
    stories = StoryRepo(db).by_status(StoryStatus.NEW)
    assert len([s for s in stories if s.source == "ai"]) == 3
