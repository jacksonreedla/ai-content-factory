"""RSS source: pure parsing and filtering (no network)."""
import time

from api.rss_client import (RSSFilters, item_to_story, parse_feed,
                            passes_rss_filters, strip_html)

NOW = time.time()

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <title>Example Feed</title>
  <item>
    <title>First &amp; Best</title>
    <description>&lt;p&gt;Hello world, this is the body text.&lt;/p&gt;</description>
    <link>https://ex.com/1</link>
    <guid>abc-1</guid>
    <pubDate>Wed, 02 Oct 2024 13:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Second Story</title>
    <description>Another perfectly ordinary body of text here.</description>
    <link>https://ex.com/2</link>
    <guid>abc-2</guid>
  </item>
</channel></rss>
"""

ATOM_SAMPLE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title>Atom One</title>
    <summary>Atom body text that is long enough to keep.</summary>
    <link href="https://ex.com/a1"/>
    <id>atom-1</id>
    <updated>2024-10-02T13:00:00Z</updated>
  </entry>
</feed>
"""


def test_strip_html():
    assert strip_html("<p>Hi &amp; bye</p>") == "Hi & bye"


def test_parse_rss():
    items = parse_feed(RSS_SAMPLE)
    assert len(items) == 2
    assert items[0].title == "First & Best"
    assert "Hello world" in items[0].text
    assert items[0].url == "https://ex.com/1"
    assert items[0].published_utc > 0


def test_parse_atom():
    items = parse_feed(ATOM_SAMPLE)
    assert len(items) == 1
    assert items[0].title == "Atom One"
    assert "Atom body text" in items[0].text
    assert items[0].url == "https://ex.com/a1"


def test_parse_garbage_returns_empty():
    assert parse_feed("not xml at all") == []


def test_item_to_story_shape():
    items = parse_feed(RSS_SAMPLE)
    story = item_to_story(items[0], "ex.com")
    assert story.source == "rss"
    assert story.source_id == "abc-1"
    assert story.subreddit == "ex.com"


FILTERS = RSSFilters(max_age_hours=336, min_words=5, max_words=4000,
                     skip_external_links=False)


def _story(text, created=None):
    items = parse_feed(RSS_SAMPLE)
    s = item_to_story(items[0], "ex.com")
    s.text = text
    s.created_utc = NOW - 3600 if created is None else created
    return s


def test_good_rss_story_passes():
    ok, reason = passes_rss_filters(_story("one two three four five six"),
                                    FILTERS, now=NOW)
    assert ok, reason


def test_short_rss_rejected():
    ok, reason = passes_rss_filters(_story("too short"), FILTERS, now=NOW)
    assert not ok and "short" in reason


def test_old_rss_rejected():
    ok, reason = passes_rss_filters(
        _story("one two three four five six", created=NOW - 400 * 3600),
        FILTERS, now=NOW)
    assert not ok and "age" in reason


def test_empty_rss_rejected():
    ok, reason = passes_rss_filters(_story(""), FILTERS, now=NOW)
    assert not ok and reason == "empty"
