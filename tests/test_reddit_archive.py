"""Reddit archive source: URL, parsing (real scores), and research wiring."""
from __future__ import annotations

import json

from agents.base import AgentContext
from agents.research_agent import ResearchAgent
from api.llm.router import LLMRouter
from api.reddit_archive import (RedditArchiveClient, parse_archive_json,
                                reddit_archive_url)
from app.prompt_manager import PromptManager
from database.repositories import StoryRepo
from models.story import StoryStatus
from tests.fakes import FakeProvider


def _sub(**over):
    d = dict(id="p1", title="A wild story", selftext="word " * 200,
             author="someone", subreddit="tifu", permalink="/r/tifu/p1",
             score=631, num_comments=93, created_utc=1777581447,
             over_18=False, stickied=False, is_self=True, hide_score=False)
    d.update(over)
    return d


def _payload(items):
    return json.dumps({"data": items}).encode()


def test_archive_url_has_window_and_subreddit():
    url = reddit_archive_url("r/tifu", limit=100, after="2026-05-01",
                             before="2026-06-01")
    assert "arctic-shift" in url and "subreddit=tifu" in url
    assert "after=2026-05-01" in url and "before=2026-06-01" in url
    assert "limit=100" in url


def test_parse_extracts_real_score():
    stories = parse_archive_json(_payload([_sub()]))
    assert len(stories) == 1
    s = stories[0]
    assert s.source == "reddit" and s.subreddit == "tifu"
    assert s.upvotes == 631 and s.num_comments == 93
    assert s.url == "https://reddit.com/r/tifu/p1"


def test_parse_skips_immature_stickied_link_removed():
    items = [
        _sub(id="a", hide_score=True),        # score not matured yet
        _sub(id="b", stickied=True),
        _sub(id="c", is_self=False),          # link post
        _sub(id="d", selftext="[removed]"),
        _sub(id="e"),                         # the only keeper
    ]
    stories = parse_archive_json(_payload(items))
    assert [s.source_id for s in stories] == ["e"]


def test_parse_falls_back_to_ups_when_score_missing():
    item = _sub(id="f")
    item.pop("score")
    item["ups"] = 415
    stories = parse_archive_json(_payload([item]))
    assert stories[0].upvotes == 415


def test_fetch_stories_uses_raw(monkeypatch):
    from app.config import DEFAULTS, Config
    import copy
    import threading
    cfg = Config.__new__(Config)
    cfg._data = copy.deepcopy(DEFAULTS)
    cfg._lock = threading.RLock()
    cfg.save = lambda: None  # type: ignore[method-assign]

    monkeypatch.setattr(RedditArchiveClient, "_fetch_raw",
                        lambda self, url: _payload([_sub()]))
    stories = RedditArchiveClient(cfg).fetch_stories("tifu")
    assert len(stories) == 1 and stories[0].upvotes == 631


# --------------------------------------------------------- research integration
def _ctx(config, db, llm):
    return AgentContext(config=config, db=db, llm=llm,
                        prompts=PromptManager(), data={})


def test_archive_restores_upvote_filtering(config, db, monkeypatch):
    """No key, method 'auto' -> archive gives real scores, min_upvotes applies."""
    # One post above the 500 threshold, one below: only the popular one survives.
    payload = _payload([_sub(id="big", score=1500, num_comments=200),
                        _sub(id="small", score=50, num_comments=3)])
    monkeypatch.setattr(RedditArchiveClient, "_fetch_raw",
                        lambda self, url: payload)
    config.set("sources.enabled", ["reddit"], persist=False)
    config.set("reddit.client_id", "", persist=False)       # no credentials
    config.set("reddit.public_method", "auto", persist=False)
    config.set("reddit.subreddits", ["tifu"], persist=False)
    config.set("reddit.min_upvotes", 500, persist=False)
    config.set("reddit.min_comments", 20, persist=False)
    config.set("reddit.min_words", 5, persist=False)
    config.set("reddit.max_age_hours", 0, persist=False)     # disable age check
    config.set("reddit.request_delay_s", 0, persist=False)

    router = LLMRouter(config, extra_providers={"fake": FakeProvider(["[]"])})
    result = ResearchAgent().execute(_ctx(config, db, router))
    assert result.ok, result.message

    reddit_stories = [s for s in StoryRepo(db).by_status(StoryStatus.NEW)
                      if s.source == "reddit"]
    assert len(reddit_stories) == 1                # low-score post filtered out
    assert reddit_stories[0].source_id == "big"
    assert reddit_stories[0].upvotes == 1500       # real matured score


def _cfg():
    from app.config import DEFAULTS, Config
    import copy
    import threading
    cfg = Config.__new__(Config)
    cfg._data = copy.deepcopy(DEFAULTS)
    cfg._lock = threading.RLock()
    cfg.save = lambda: None  # type: ignore[method-assign]
    return cfg


def test_fetch_narrows_window_on_422_then_succeeds(monkeypatch):
    """A busy-sub 422 makes the client shrink the window and retry."""
    from urllib.error import HTTPError

    seen_after = []

    def fake_raw(self, url):
        # record the 'after=' bound so we can prove the window shrank
        after = url.split("after=")[1].split("&")[0]
        seen_after.append(after)
        if len(seen_after) < 3:            # 422 on the first two (wide) windows
            raise HTTPError(url, 422, "Unprocessable Entity", {}, None)
        return _payload([_sub()])

    monkeypatch.setattr(RedditArchiveClient, "_fetch_raw", fake_raw)
    monkeypatch.setattr("api.reddit_archive.time.sleep", lambda s: None)

    stories = RedditArchiveClient(_cfg()).fetch_stories("AITAH")
    assert len(stories) == 1
    assert len(seen_after) == 3
    # Window narrowed => 'after' bound moved forward (later date) each retry.
    assert seen_after[0] < seen_after[1] < seen_after[2]


def test_fetch_gives_up_when_422_persists_to_floor(monkeypatch):
    """If 422 persists down to the floor window, it propagates (-> RSS)."""
    from urllib.error import HTTPError

    calls = {"n": 0}

    def always_422(self, url):
        calls["n"] += 1
        raise HTTPError(url, 422, "Unprocessable Entity", {}, None)

    monkeypatch.setattr(RedditArchiveClient, "_fetch_raw", always_422)
    monkeypatch.setattr("api.reddit_archive.time.sleep", lambda s: None)

    try:
        RedditArchiveClient(_cfg()).fetch_stories("AITAH")
        assert False, "should have raised"
    except HTTPError as exc:
        assert exc.code == 422
    # 45 -> 22 -> 11 -> 5 (floor), then raise: 4 attempts, bounded.
    assert calls["n"] == 4
