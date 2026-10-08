"""ResearchAgent multi-source behaviour: resilience and non-fatal failures."""
from agents.base import AgentContext
from agents.research_agent import ResearchAgent
from api.llm.router import LLMRouter
from app.prompt_manager import PromptManager
from database.repositories import StoryRepo
from models.story import StoryStatus
from tests.fakes import FakeProvider

RSS_BYTES = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Feed Story</title>
    <description>A body of text long enough to survive the word filter easily.</description>
    <link>https://ex.com/1</link>
    <guid>feed-1</guid>
  </item>
</channel></rss>
"""

AI_JSON = '[{"title": "Generated", "text": "An original tale with a twist at the end."}]'


def _ctx(config, db, llm):
    return AgentContext(config=config, db=db, llm=llm,
                        prompts=PromptManager(), data={})


def _router(config):
    config.set("ai.tasks.generate_story", {"provider": "fake", "model": ""},
               persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    return LLMRouter(config, extra_providers={"fake": FakeProvider([AI_JSON])})


def test_rss_and_ai_sources_add_stories(config, db, monkeypatch):
    monkeypatch.setattr("api.rss_client.RSSClient._fetch_raw",
                        lambda self, url: RSS_BYTES)
    config.set("sources.enabled", ["rss", "ai"], persist=False)
    config.set("rss.feeds", ["https://ex.com/feed.xml"], persist=False)
    config.set("rss.min_words", 5, persist=False)
    config.set("rss.max_age_hours", 0, persist=False)  # 0 disables the age check

    result = ResearchAgent().execute(_ctx(config, db, _router(config)))
    assert result.ok, result.message

    stories = StoryRepo(db).by_status(StoryStatus.NEW)
    sources = {s.source for s in stories}
    assert "rss" in sources and "ai" in sources


def test_reddit_falls_back_to_public_rss_without_creds(config, db, monkeypatch):
    """No API key -> the Reddit source uses public RSS feeds automatically."""
    monkeypatch.setattr("api.rss_client.RSSClient._fetch_raw",
                        lambda self, url: RSS_BYTES)
    config.set("sources.enabled", ["reddit"], persist=False)
    config.set("reddit.client_id", "", persist=False)     # no credentials
    config.set("reddit.public_method", "rss", persist=False)  # test RSS path
    config.set("ai_stories.topup_enabled", False, persist=False)
    config.set("reddit.subreddits", ["funny", "tifu"], persist=False)
    config.set("rss.min_words", 5, persist=False)
    config.set("rss.max_age_hours", 0, persist=False)
    config.set("rss.request_delay_s", 0, persist=False)

    result = ResearchAgent().execute(_ctx(config, db, _router(config)))
    assert result.ok, result.message
    assert result.data["added"] >= 1

    stories = StoryRepo(db).by_status(StoryStatus.NEW)
    assert any(s.source == "reddit" for s in stories)
    assert {s.subreddit for s in stories} <= {"funny", "tifu"}


def test_reddit_no_creds_and_no_subreddits_is_fatal(config, db):
    config.set("sources.enabled", ["reddit"], persist=False)
    config.set("reddit.client_id", "", persist=False)
    config.set("reddit.subreddits", [], persist=False)     # nothing to fall back to
    config.set("ai_stories.topup_enabled", False, persist=False)

    result = ResearchAgent().execute(_ctx(config, db, _router(config)))
    assert not result.ok
    assert "reddit" in result.message.lower()


def test_reddit_public_failure_non_fatal_when_rss_works(config, db, monkeypatch):
    """If the public Reddit feed errors, other sources still carry the run."""
    def fetch(self, url):
        if "reddit.com" in url:
            raise OSError("reddit blocked")
        return RSS_BYTES

    monkeypatch.setattr("api.rss_client.RSSClient._fetch_raw", fetch)
    config.set("sources.enabled", ["reddit", "rss"], persist=False)
    config.set("reddit.client_id", "", persist=False)
    config.set("reddit.public_method", "rss", persist=False)  # test RSS path
    config.set("reddit.subreddits", ["funny"], persist=False)
    config.set("rss.feeds", ["https://ex.com/feed.xml"], persist=False)
    config.set("rss.min_words", 5, persist=False)
    config.set("rss.max_age_hours", 0, persist=False)
    config.set("rss.request_delay_s", 0, persist=False)

    result = ResearchAgent().execute(_ctx(config, db, _router(config)))
    assert result.ok                         # rss carried the run
    assert result.data["added"] >= 1
    assert any("reddit" in e.lower() for e in result.data["errors"])
