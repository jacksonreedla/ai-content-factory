"""RSS/Atom content source.

No API key, no approval process - works anywhere the feed URLs are
reachable. Mirrors the shape of ``reddit_client``: fetching (network) is
kept separate from parsing and filtering (pure functions) so the logic can
be unit tested without network access.

Uses ``feedparser`` when installed for robustness, and falls back to a small
stdlib (xml.etree) parser so the app never hard-fails if it is missing.
"""
from __future__ import annotations

import html
import logging
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from urllib.request import Request, urlopen

from app.config import Config
from models.story import Story, StoryStatus

log = logging.getLogger("acf.rss")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(raw: str) -> str:
    """Turn an HTML/entity-laden feed snippet into clean plain text."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    return _WS_RE.sub(" ", text).strip()


@dataclass
class RSSItem:
    """A single parsed feed entry, before it becomes a Story."""

    guid: str
    title: str
    text: str
    url: str = ""
    author: str = ""
    published_utc: float = 0.0


@dataclass
class RSSFilters:
    max_age_hours: int = 336
    min_words: int = 40
    max_words: int = 4000
    skip_external_links: bool = False

    @classmethod
    def from_config(cls, config: Config) -> "RSSFilters":
        r = config.get("rss", {})
        return cls(
            max_age_hours=r.get("max_age_hours", 336),
            min_words=r.get("min_words", 40),
            max_words=r.get("max_words", 4000),
            skip_external_links=r.get("skip_external_links", False),
        )


def passes_rss_filters(story: Story, filters: RSSFilters,
                       now: float | None = None) -> tuple[bool, str]:
    """Return (ok, reason). Pure function - unit testable."""
    now = now if now is not None else time.time()
    if not story.text:
        return False, "empty"
    age_hours = (now - story.created_utc) / 3600 if story.created_utc else 0
    if filters.max_age_hours and age_hours > filters.max_age_hours:
        return False, f"age {age_hours:.0f}h > {filters.max_age_hours}h"
    words = story.word_count
    if words < filters.min_words:
        return False, f"too short ({words} words)"
    if filters.max_words and words > filters.max_words:
        return False, f"too long ({words} words)"
    if filters.skip_external_links and ("http://" in story.text or "https://" in story.text):
        return False, "contains external links"
    return True, ""


def _parse_date(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        dt = parsedate_to_datetime(value)
        return dt.timestamp() if dt else 0.0
    except (TypeError, ValueError, OverflowError):
        # Try ISO 8601 (Atom <updated>/<published>)
        try:
            from datetime import datetime
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0


def parse_feed(content: bytes | str) -> list[RSSItem]:
    """Parse raw RSS/Atom bytes into RSSItems. Pure - no network.

    Prefers feedparser; falls back to a minimal xml.etree parser that
    understands both RSS 2.0 <item> and Atom <entry> elements.
    """
    if isinstance(content, bytes):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
    else:
        text = content

    try:
        import feedparser  # type: ignore
    except ImportError:
        return _parse_feed_stdlib(text)

    parsed = feedparser.parse(text)
    items: list[RSSItem] = []
    for e in parsed.entries:
        body = ""
        if e.get("content"):
            body = e["content"][0].get("value", "")
        body = body or e.get("summary", "") or e.get("description", "")
        published = ""
        if e.get("published_parsed") or e.get("updated_parsed"):
            tm = e.get("published_parsed") or e.get("updated_parsed")
            published_utc = time.mktime(tm)
        else:
            published = e.get("published", "") or e.get("updated", "")
            published_utc = _parse_date(published)
        items.append(RSSItem(
            guid=e.get("id", "") or e.get("link", "") or e.get("title", ""),
            title=strip_html(e.get("title", "")),
            text=strip_html(body),
            url=e.get("link", ""),
            author=e.get("author", ""),
            published_utc=published_utc,
        ))
    return items


def _parse_feed_stdlib(text: str) -> list[RSSItem]:
    """Dependency-free fallback parser for RSS 2.0 and Atom."""
    import xml.etree.ElementTree as ET

    def local(tag: str) -> str:
        return tag.rsplit("}", 1)[-1].lower()

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        log.warning("Could not parse feed: %s", exc)
        return []

    items: list[RSSItem] = []
    nodes = [n for n in root.iter() if local(n.tag) in ("item", "entry")]
    for node in nodes:
        fields: dict[str, str] = {}
        link = ""
        for child in node:
            name = local(child.tag)
            if name == "link":
                # Atom uses an href attribute; RSS uses element text.
                link = child.get("href") or (child.text or "") or link
            elif name in fields:
                continue
            else:
                fields[name] = (child.text or "").strip()
        body = (fields.get("encoded") or fields.get("content")
                or fields.get("summary") or fields.get("description") or "")
        items.append(RSSItem(
            guid=fields.get("guid") or fields.get("id") or link or fields.get("title", ""),
            title=strip_html(fields.get("title", "")),
            text=strip_html(body),
            url=link,
            author=fields.get("author") or fields.get("creator", ""),
            published_utc=_parse_date(fields.get("pubdate") or fields.get("published")
                                      or fields.get("updated")),
        ))
    return items


def item_to_story(item: RSSItem, feed_label: str) -> Story:
    """Convert a parsed RSSItem into a Story (source='rss')."""
    return Story(
        id=None, source="rss",
        source_id=item.guid or item.url or item.title,
        title=item.title, text=item.text,
        author=item.author, subreddit=feed_label, url=item.url,
        upvotes=0, num_comments=0,
        created_utc=item.published_utc,
        nsfw=False, status=StoryStatus.NEW,
    )


class RSSClient:
    """Fetches feeds over HTTP and yields Story objects (unfiltered)."""

    def __init__(self, config: Config, timeout_s: int = 20):
        self.config = config
        self.timeout_s = timeout_s
        self.user_agent = config.get("reddit.user_agent", "ai-content-factory/0.1")

    def _fetch_raw(self, url: str) -> bytes:
        req = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310 (trusted feed URLs)
            return resp.read()

    def fetch_stories(self, feed_url: str, limit: int = 25) -> list[Story]:
        raw = self._fetch_raw(feed_url)
        items = parse_feed(raw)
        label = _feed_label(feed_url)
        stories = [item_to_story(it, label) for it in items[:limit]]
        log.info("Fetched %d entries from %s", len(stories), feed_url)
        return stories


def _feed_label(feed_url: str) -> str:
    """A short human label for a feed, used where subreddit would be."""
    from urllib.parse import urlparse
    host = urlparse(feed_url).netloc or feed_url
    return host.replace("www.", "").replace("feeds.", "")
