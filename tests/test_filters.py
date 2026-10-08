"""Reddit filter logic tests (pure functions, no network)."""
import time

from api.reddit_client import RedditFilters, passes_filters
from models.story import Story

NOW = time.time()


def make_story(**overrides) -> Story:
    defaults = dict(
        id=None, source="reddit", source_id="x", title="t",
        text="word " * 200, upvotes=1000, num_comments=50,
        created_utc=NOW - 3600, nsfw=False,
    )
    defaults.update(overrides)
    return Story(**defaults)


FILTERS = RedditFilters(min_upvotes=500, min_comments=20, max_age_hours=168,
                        min_words=80, max_words=4000, allow_nsfw=False,
                        skip_external_links=True)


def test_good_story_passes():
    ok, reason = passes_filters(make_story(), FILTERS, now=NOW)
    assert ok, reason


def test_deleted_rejected():
    ok, reason = passes_filters(make_story(text="[deleted]"), FILTERS, now=NOW)
    assert not ok and "deleted" in reason


def test_low_upvotes_rejected():
    ok, reason = passes_filters(make_story(upvotes=10), FILTERS, now=NOW)
    assert not ok and "upvotes" in reason


def test_nsfw_rejected_by_default():
    ok, reason = passes_filters(make_story(nsfw=True), FILTERS, now=NOW)
    assert not ok and reason == "nsfw"


def test_nsfw_allowed_when_enabled():
    filters = RedditFilters(**{**FILTERS.__dict__, "allow_nsfw": True})
    ok, _ = passes_filters(make_story(nsfw=True), filters, now=NOW)
    assert ok


def test_too_old_rejected():
    ok, reason = passes_filters(
        make_story(created_utc=NOW - 200 * 3600), FILTERS, now=NOW)
    assert not ok and "age" in reason


def test_too_short_rejected():
    ok, reason = passes_filters(make_story(text="short story"), FILTERS, now=NOW)
    assert not ok and "short" in reason


def test_external_links_rejected():
    ok, reason = passes_filters(
        make_story(text="word " * 100 + " see https://example.com"),
        FILTERS, now=NOW)
    assert not ok and "links" in reason
