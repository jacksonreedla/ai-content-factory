"""Public JSON scraper: URL building, parsing, fetch + research wiring."""
from __future__ import annotations

import json

from agents.base import AgentContext
from agents.research_agent import ResearchAgent
from api.llm.router import LLMRouter
from api.reddit_client import (RedditJSONClient, parse_listing_json,
                               reddit_json_url)
from app.prompt_manager import PromptManager
from database.repositories import StoryRepo
from models.story import StoryStatus
from tests.fakes import FakeProvider


def _listing(children):
    return json.dumps({"data": {"after": None, "children": children}}).encode()


def _post(**over):
    d = dict(id="abc", title="A wild title", selftext="word " * 200,
             author="someone", subreddit="tifu", permalink="/r/tifu/abc",
             score=1200, num_comments=80, created_utc=0.0, over_18=False,
             stickied=False, is_self=True)
    d.update(over)
    return {"kind": "t3", "data": d}


# ------------------------------------------------------------------- url + parse
def test_json_url_top_has_time_and_limit():
    url = reddit_json_url("r/tifu", "top", "week", 25)
    assert url.startswith("https://www.reddit.com/r/tifu/top.json?")
    assert "t=week" in url and "limit=25" in url and "raw_json=1" in url


def test_json_url_hot_has_no_time():
    # 'hot' takes no time filter (guard against matching 'limit=').
    assert "&t=" not in reddit_json_url("tifu", "hot")


def test_json_url_best_maps_to_hot():
    assert "/hot.json" in reddit_json_url("AITAH", "best")


def test_parse_extracts_full_metadata():
    stories, after = parse_listing_json(_listing([_post()]), "tifu")
    assert after is None
    assert len(stories) == 1
    s = stories[0]
    assert s.source == "reddit" and s.subreddit == "tifu"
    assert s.upvotes == 1200 and s.num_comments == 80
    assert s.url == "https://reddit.com/r/tifu/abc"


def test_parse_skips_stickied_link_and_removed():
    children = [
        _post(id="1", stickied=True),
        _post(id="2", is_self=False),          # link post
        _post(id="3", selftext="[removed]"),
        _post(id="4"),                         # the only keeper
    ]
    stories, _ = parse_listing_json(_listing(children), "tifu")
    assert [s.source_id for s in stories] == ["4"]


def test_parse_cleans_markdown_when_enabled():
    stories, _ = parse_listing_json(
        _listing([_post(selftext="**bold** " + "w " * 200)]), "tifu", clean=True)
    assert "**" not in stories[0].text


def test_fetch_stories_uses_raw(monkeypatch):
    from app.config import DEFAULTS, Config
    import copy
    import threading
    cfg = Config.__new__(Config)
    cfg._data = copy.deepcopy(DEFAULTS)
    cfg._lock = threading.RLock()
    cfg.save = lambda: None  # type: ignore[method-assign]

    monkeypatch.setattr(RedditJSONClient, "_fetch_raw",
                        lambda self, url: _listing([_post()]))
    stories = RedditJSONClient(cfg).fetch_stories("tifu", "top", "day", 25)
    assert len(stories) == 1 and stories[0].upvotes == 1200


# --------------------------------------------------------- research integration
def _ctx(config, db, llm):
    return AgentContext(config=config, db=db, llm=llm,
                        prompts=PromptManager(), data={})


def test_reddit_no_creds_uses_public_json(config, db, monkeypatch):
    """No API key + method 'json' -> full-quality stories via .json endpoints."""
    monkeypatch.setattr(RedditJSONClient, "_fetch_raw",
                        lambda self, url: _listing([_post(score=1200,
                                                          num_comments=80)]))
    config.set("sources.enabled", ["reddit"], persist=False)
    config.set("reddit.client_id", "", persist=False)      # no credentials
    config.set("reddit.public_method", "json", persist=False)
    config.set("reddit.subreddits", ["tifu"], persist=False)
    config.set("reddit.min_words", 5, persist=False)
    config.set("reddit.max_age_hours", 0, persist=False)

    router = LLMRouter(config, extra_providers={"fake": FakeProvider(["[]"])})
    result = ResearchAgent().execute(_ctx(config, db, router))
    assert result.ok, result.message
    assert result.data["added"] >= 1

    stories = StoryRepo(db).by_status(StoryStatus.NEW)
    reddit_stories = [s for s in stories if s.source == "reddit"]
    assert reddit_stories
    # Real engagement metrics survived (RSS path would have left these at 0).
    assert reddit_stories[0].upvotes == 1200
    assert reddit_stories[0].num_comments == 80


def test_auto_falls_back_to_rss_when_archive_fails(config, db, monkeypatch):
    """method 'auto': a subreddit whose archive fetch fails is retried over RSS."""
    from api.reddit_archive import RedditArchiveClient

    RSS_BYTES = (b'<?xml version="1.0"?><rss version="2.0"><channel><item>'
                 b'<title>Feed Story</title>'
                 b'<description>Plenty of words here to survive the filter.</description>'
                 b'<link>https://ex.com/1</link><guid>g1</guid></item></channel></rss>')

    def archive_down(self, subreddit, listing="top", time_filter="day", limit=25):
        raise OSError("archive unreachable")

    monkeypatch.setattr(RedditArchiveClient, "fetch_stories", archive_down)
    monkeypatch.setattr("api.rss_client.RSSClient._fetch_raw",
                        lambda self, url: RSS_BYTES)
    config.set("sources.enabled", ["reddit"], persist=False)
    config.set("reddit.client_id", "", persist=False)
    config.set("reddit.public_method", "auto", persist=False)
    config.set("reddit.subreddits", ["tifu"], persist=False)
    config.set("reddit.request_delay_s", 0, persist=False)
    config.set("rss.min_words", 5, persist=False)
    config.set("rss.max_age_hours", 0, persist=False)
    config.set("rss.request_delay_s", 0, persist=False)

    router = LLMRouter(config, extra_providers={"fake": FakeProvider(["[]"])})
    result = ResearchAgent().execute(_ctx(config, db, router))
    assert result.ok, result.message
    assert result.data["added"] >= 1
    assert any(s.source == "reddit" for s in StoryRepo(db).by_status(StoryStatus.NEW))


# ------------------------------------------------------------------ retry logic
def _bare_cfg():
    from app.config import DEFAULTS, Config
    import copy
    import threading
    cfg = Config.__new__(Config)
    cfg._data = copy.deepcopy(DEFAULTS)
    cfg._lock = threading.RLock()
    cfg.save = lambda: None  # type: ignore[method-assign]
    return cfg


class _FakeResp:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._body


def test_fetch_raw_retries_then_succeeds(monkeypatch):
    """A 429 (rate limit) is retried with backoff and eventually succeeds."""
    import api.reddit_client as rc
    from urllib.error import HTTPError

    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)
        return _FakeResp(b'{"data":{"children":[]}}')

    monkeypatch.setattr(rc, "urlopen", fake_urlopen)
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)   # no real waiting

    client = rc.RedditJSONClient(_bare_cfg())
    client.backoff_base_s = 0        # keep jitter/backoff instant
    data = client._fetch_raw("https://www.reddit.com/r/tifu/top.json")
    assert calls["n"] == 3 and b"children" in data


def test_fetch_raw_gives_up_after_max_retries(monkeypatch):
    """Persistent 429s propagate once retries are exhausted."""
    import api.reddit_client as rc
    from urllib.error import HTTPError

    calls = {"n": 0}

    def always_429(req, timeout=None):
        calls["n"] += 1
        raise HTTPError(req.full_url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(rc, "urlopen", always_429)
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)

    client = rc.RedditJSONClient(_bare_cfg())
    client.max_retries = 2
    client.backoff_base_s = 0
    try:
        client._fetch_raw("https://www.reddit.com/r/tifu/top.json")
        assert False, "should have raised"
    except HTTPError as exc:
        assert exc.code == 429
    assert calls["n"] == 3        # initial try + 2 retries


def test_retry_after_header_is_honored(monkeypatch):
    """When Reddit sends Retry-After, we wait exactly that long."""
    import api.reddit_client as rc
    from urllib.error import HTTPError

    waits = []
    state = {"n": 0}

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        if state["n"] == 1:
            raise HTTPError(req.full_url, 429, "slow down",
                            {"Retry-After": "7"}, None)
        return _FakeResp(b"{}")

    monkeypatch.setattr(rc, "urlopen", fake_urlopen)
    monkeypatch.setattr(rc.time, "sleep", lambda s: waits.append(s))

    client = rc.RedditJSONClient(_bare_cfg())
    client.backoff_base_s = 0        # so wait == Retry-After + 0 jitter
    client._fetch_raw("https://www.reddit.com/r/tifu/top.json")
    assert waits and abs(waits[0] - 7.0) < 0.001
def test_403_fails_fast_by_default(monkeypatch):
    """403 is treated as a hard block: no retries unless retry_on_403 is set."""
    import api.reddit_client as rc
    from urllib.error import HTTPError

    calls = {"n": 0}

    def always_403(req, timeout=None):
        calls["n"] += 1
        raise HTTPError(req.full_url, 403, "Blocked", {}, None)

    monkeypatch.setattr(rc, "urlopen", always_403)
    monkeypatch.setattr(rc.time, "sleep", lambda s: None)

    client = rc.RedditJSONClient(_bare_cfg())      # retry_on_403 defaults False
    try:
        client._fetch_raw("https://www.reddit.com/r/tifu/top.json")
        assert False, "should have raised"
    except HTTPError as exc:
        assert exc.code == 403
    assert calls["n"] == 1                          # tried once, no retries
