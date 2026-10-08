"""Reddit content source built on PRAW, with pure-function filtering.

Three ways to fetch, in order of data quality:

  1. PRAW (official API)   - needs approved client id/secret. Full data.
  2. Public JSON endpoints - Reddit's ``.json`` listings. No credentials, yet
     they carry the SAME rich data as the API: full post text, real upvote and
     comment counts, and NSFW/stickied flags. This is the preferred fallback.
  3. Public RSS feeds      - last resort. No score/comment counts and bodies
     are often truncated, but works even where JSON is blocked.

Fetching (network) is kept separate from filtering and text-cleaning (pure
functions) so the logic can be unit tested without network or credentials.
"""
from __future__ import annotations

import json as _json
import logging
import random
import re
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Config
from models.story import Story, StoryStatus

log = logging.getLogger("acf.reddit")


# Matches an optional reddit URL / prefix up to and including "r/", so
# "r/funny", "/r/funny", and "https://www.reddit.com/r/funny/" all normalize
# to "funny". Names without the prefix pass through unchanged.
_SUBREDDIT_PREFIX = re.compile(
    r"^\s*(?:https?://)?(?:www\.|old\.|new\.)?(?:reddit\.com)?/?r/",
    re.IGNORECASE)


def normalize_subreddit(name: str) -> str:
    """Clean a user-entered subreddit into the bare name PRAW expects."""
    if not name:
        return ""
    cleaned = str(name).strip().strip(",").strip()
    cleaned = _SUBREDDIT_PREFIX.sub("", cleaned)     # drop r/ or a full URL
    cleaned = cleaned.strip().strip("/")
    # keep only the first token (guards against trailing paths / query strings)
    cleaned = cleaned.split("/")[0].split()[0] if cleaned else ""
    return cleaned


# --------------------------------------------------------------- text cleaning
import html as _html

_ZERO_WIDTH = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
_MD_IMAGE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")          # ![alt](url) -> alt
_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")          # [text](url) -> text
_BARE_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_LINE_MARKER = re.compile(r"(?m)^\s{0,3}(?:#{1,6}|>+|[-*+]|\d+[.)])\s+")
_HR = re.compile(r"(?m)^\s*(?:[-*_]\s*){3,}$")             # --- *** ___ rules
_EMPHASIS = [
    (re.compile(r"\*\*\*(.+?)\*\*\*", re.DOTALL), r"\1"),
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"\1"),
    (re.compile(r"\*(.+?)\*", re.DOTALL), r"\1"),
    (re.compile(r"___(.+?)___", re.DOTALL), r"\1"),
    (re.compile(r"__(.+?)__", re.DOTALL), r"\1"),
    (re.compile(r"~~(.+?)~~", re.DOTALL), r"\1"),
    (re.compile(r"`([^`]+)`", re.DOTALL), r"\1"),
]
_SPACES = re.compile(r"[ \t]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")


def clean_story_text(raw: str) -> str:
    """Turn raw Reddit markdown into clean prose suitable for narration/TTS.

    Strips markdown links/emphasis/headings/quotes/bullets, removes bare URLs
    and HTML entities, and drops zero-width characters (Reddit sprinkles these
    into posts). Paragraph breaks are preserved so TTS keeps natural pauses.
    Pure function - no network, safe to unit test.
    """
    if not raw:
        return ""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _html.unescape(text)              # &amp; -> &, &#x200B; -> zero-width
    text = _ZERO_WIDTH.sub("", text)
    text = _MD_IMAGE.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _BARE_URL.sub("", text)
    text = _HR.sub("", text)
    text = _LINE_MARKER.sub("", text)        # heading/quote/bullet line prefixes
    for pattern, repl in _EMPHASIS:
        text = pattern.sub(repl, text)
    text = _SPACES.sub(" ", text)
    text = _MANY_NEWLINES.sub("\n\n", text)
    # tidy per-line trailing/leading spaces left by prefix removal
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


_RSS_LISTINGS = ("top", "hot", "new", "rising")


def reddit_rss_url(subreddit: str, listing: str = "top",
                   time_filter: str = "day") -> str:
    """Build a subreddit's PUBLIC RSS feed URL (no API key required).

    e.g. https://www.reddit.com/r/tifu/top/.rss?t=day
    'best' isn't an RSS listing, so it maps to 'hot'.
    """
    sub = normalize_subreddit(subreddit)
    listing = listing if listing in _RSS_LISTINGS else "hot"
    if listing == "hot":
        url = f"https://www.reddit.com/r/{sub}/.rss"
    else:
        url = f"https://www.reddit.com/r/{sub}/{listing}.rss"
    if listing == "top":
        url += f"?t={time_filter}"
    return url


# --------------------------------------------------- public JSON (no API key)
_JSON_LISTINGS = ("top", "hot", "new", "rising")


def reddit_json_url(subreddit: str, listing: str = "top",
                    time_filter: str = "day", limit: int = 25,
                    after: str | None = None) -> str:
    """Build a subreddit's PUBLIC ``.json`` listing URL (no API key required).

    e.g. https://www.reddit.com/r/tifu/top.json?limit=25&raw_json=1&t=day

    These endpoints return the same fields as the official API: full selftext,
    real score/num_comments, over_18, stickied, is_self. 'best' isn't a valid
    subreddit listing, so it maps to 'hot'.
    """
    sub = normalize_subreddit(subreddit)
    listing = listing if listing in _JSON_LISTINGS else "hot"
    params = [f"limit={max(1, min(int(limit), 100))}", "raw_json=1"]
    if listing == "top":
        params.append(f"t={time_filter}")
    if after:
        params.append(f"after={after}")
    return f"https://www.reddit.com/r/{sub}/{listing}.json?" + "&".join(params)


def parse_listing_json(raw: bytes | str, subreddit: str = "",
                       clean: bool = True) -> tuple[list[Story], str | None]:
    """Parse a Reddit listing JSON payload into Stories. Pure - no network.

    Returns ``(stories, after)`` where ``after`` is the pagination cursor for
    the next page (or None). Non-self posts and stickied posts are skipped, as
    in the PRAW path. Selftext is run through :func:`clean_story_text` when
    ``clean`` is set.
    """
    data = _json.loads(raw) if isinstance(raw, (bytes, str)) else raw
    listing = (data or {}).get("data", {}) if isinstance(data, dict) else {}
    children = listing.get("children", []) or []

    stories: list[Story] = []
    for child in children:
        if child.get("kind") != "t3":       # t3 == a link/submission
            continue
        d = child.get("data", {}) or {}
        if d.get("stickied") or not d.get("is_self", False):
            continue
        text = d.get("selftext", "") or ""
        if text in ("[deleted]", "[removed]"):
            continue
        if clean:
            text = clean_story_text(text)
        sub = d.get("subreddit") or normalize_subreddit(subreddit)
        permalink = d.get("permalink", "")
        stories.append(Story(
            id=None, source="reddit", source_id=d.get("id", ""),
            title=d.get("title", "") or "", text=text,
            author=d.get("author", "") or "[deleted]",
            subreddit=sub,
            url=f"https://reddit.com{permalink}" if permalink else "",
            upvotes=int(d.get("score") or 0),
            num_comments=int(d.get("num_comments") or 0),
            created_utc=float(d.get("created_utc") or 0),
            nsfw=bool(d.get("over_18", False)),
            status=StoryStatus.NEW,
        ))
    return stories, listing.get("after")


class RedditJSONClient:
    """Fetch subreddits via Reddit's public ``.json`` endpoints - no API key.

    A drop-in alternative to :class:`RedditClient` for when API credentials
    aren't configured. Yields full-quality Story objects (real score/comments,
    full text) that the upvote/comment RedditFilters can act on properly.
    """

    # HTTP codes worth retrying: Reddit throttles unauthenticated traffic with
    # 429 (rate limit) and, inconsistently, 403; 5xx are transient server errors.
    _RETRYABLE = (429, 500, 502, 503, 504)

    def __init__(self, config: Config, timeout_s: int = 20):
        self.config = config
        self.timeout_s = timeout_s
        # A descriptive, unique User-Agent is what keeps Reddit from blocking
        # you. Generic or placeholder UAs get 403'd - set a real reddit handle.
        self.user_agent = config.get("reddit.user_agent",
                                     "ai-content-factory/0.1")
        self.clean = bool(config.get("reddit.clean_text", True))
        self.max_retries = int(config.get("reddit.max_retries", 3))
        # 403 from Reddit unauth is usually a hard block, not a
        # transient throttle, so by default we fail fast on it.
        self.retry_on_403 = bool(config.get("reddit.retry_on_403", False))
        self.backoff_base_s = float(config.get("reddit.backoff_base_s", 5.0))

    def _fetch_raw(self, url: str) -> bytes:
        """GET a URL, retrying throttled/transient responses with backoff.

        On 403/429/5xx we wait and retry up to ``max_retries`` times, honoring
        Reddit's ``Retry-After`` header when present, otherwise using an
        exponential backoff (base * 2**attempt) with jitter. Non-retryable
        errors and the final failure propagate to the caller.
        """
        req = Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                    return resp.read()
            except HTTPError as exc:
                retryable = (exc.code in self._RETRYABLE
                             or (exc.code == 403 and self.retry_on_403))
                if not retryable or attempt >= self.max_retries:
                    raise
                wait = self._retry_after(exc) or (
                    self.backoff_base_s * (2 ** attempt))
                wait += random.uniform(0, self.backoff_base_s)   # jitter
                log.info("HTTP %s on %s; backing off %.1fs (retry %d/%d)",
                         exc.code, url, wait, attempt + 1, self.max_retries)
                time.sleep(wait)
            except URLError as exc:
                if attempt >= self.max_retries:
                    raise
                wait = self.backoff_base_s * (2 ** attempt)
                log.info("Network error on %s (%s); retrying in %.1fs",
                         url, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"unreachable: exhausted retries for {url}")

    @staticmethod
    def _retry_after(exc: HTTPError) -> float | None:
        """Parse a Retry-After header (seconds) if the server sent one."""
        val = exc.headers.get("Retry-After") if exc.headers else None
        if not val:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    def fetch_stories(self, subreddit: str, listing: str = "top",
                      time_filter: str = "day", limit: int = 25) -> list[Story]:
        """Fetch up to ``limit`` self-post submissions (paginating past 100)."""
        subreddit = normalize_subreddit(subreddit)
        stories: list[Story] = []
        after: str | None = None
        remaining = max(1, int(limit))
        while remaining > 0:
            page = min(remaining, 100)
            url = reddit_json_url(subreddit, listing, time_filter, page, after)
            batch, after = parse_listing_json(
                self._fetch_raw(url), subreddit, clean=self.clean)
            stories.extend(batch)
            remaining -= page
            if not after or not batch:
                break
            if remaining > 0:
                time.sleep(1.0)             # gentle pacing between pages
        stories = stories[:int(limit)]
        log.info("Fetched %d submissions from r/%s (%s, public JSON)",
                 len(stories), subreddit, listing)
        return stories


class RedditConfigError(RuntimeError):
    """Raised when Reddit credentials are missing or praw is not installed."""


@dataclass
class RedditFilters:
    min_upvotes: int = 500
    min_comments: int = 20
    max_age_hours: int = 168
    min_words: int = 80
    max_words: int = 4000
    allow_nsfw: bool = False
    skip_external_links: bool = True

    @classmethod
    def from_config(cls, config: Config) -> "RedditFilters":
        r = config.get("reddit", {})
        return cls(
            min_upvotes=r.get("min_upvotes", 500),
            min_comments=r.get("min_comments", 20),
            max_age_hours=r.get("max_age_hours", 168),
            min_words=r.get("min_words", 80),
            max_words=r.get("max_words", 4000),
            allow_nsfw=r.get("allow_nsfw", False),
            skip_external_links=r.get("skip_external_links", True),
        )


def passes_filters(story: Story, filters: RedditFilters,
                   now: float | None = None) -> tuple[bool, str]:
    """Return (ok, reason). Pure function - unit testable."""
    now = now if now is not None else time.time()
    if not story.text or story.text in ("[deleted]", "[removed]"):
        return False, "deleted or empty"
    if story.nsfw and not filters.allow_nsfw:
        return False, "nsfw"
    if story.upvotes < filters.min_upvotes:
        return False, f"upvotes {story.upvotes} < {filters.min_upvotes}"
    if story.num_comments < filters.min_comments:
        return False, f"comments {story.num_comments} < {filters.min_comments}"
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


class RedditClient:
    """Thin PRAW wrapper. Instantiating checks credentials."""

    def __init__(self, config: Config):
        self.config = config
        client_id = config.get("reddit.client_id", "")
        client_secret = config.get("reddit.client_secret", "")
        user_agent = config.get("reddit.user_agent", "ai-content-factory/0.1")
        if not client_id or not client_secret:
            raise RedditConfigError(
                "Reddit API credentials missing. Create a 'script' app at "
                "https://www.reddit.com/prefs/apps and enter the client id/secret "
                "in Settings -> Reddit."
            )
        try:
            import praw  # imported lazily so the app runs without it installed
        except ImportError as exc:
            raise RedditConfigError(
                "The 'praw' package is not installed. Run: pip install praw"
            ) from exc
        self._reddit = praw.Reddit(
            client_id=client_id, client_secret=client_secret,
            user_agent=user_agent, check_for_async=False,
        )
        self._reddit.read_only = True
        self.clean = bool(config.get("reddit.clean_text", True))

    def fetch_stories(self, subreddit: str, listing: str = "top",
                      time_filter: str = "day", limit: int = 25) -> list[Story]:
        """Fetch submissions from one subreddit as Story objects (unfiltered)."""
        subreddit = normalize_subreddit(subreddit)
        sub = self._reddit.subreddit(subreddit)
        if listing == "top":
            submissions = sub.top(time_filter=time_filter, limit=limit)
        elif listing == "hot":
            submissions = sub.hot(limit=limit)
        elif listing == "rising":
            submissions = sub.rising(limit=limit)
        else:
            submissions = sub.best(limit=limit) if hasattr(sub, "best") else sub.hot(limit=limit)

        stories: list[Story] = []
        for s in submissions:
            if getattr(s, "stickied", False) or not getattr(s, "is_self", True):
                continue
            body = s.selftext or ""
            if self.clean:
                body = clean_story_text(body)
            stories.append(Story(
                id=None, source="reddit", source_id=s.id,
                title=s.title or "", text=body,
                author=str(s.author) if s.author else "[deleted]",
                subreddit=subreddit, url=f"https://reddit.com{s.permalink}",
                upvotes=int(s.score or 0), num_comments=int(s.num_comments or 0),
                created_utc=float(s.created_utc or 0),
                nsfw=bool(getattr(s, "over_18", False)),
                status=StoryStatus.NEW,
            ))
        log.info("Fetched %d submissions from r/%s (%s)", len(stories), subreddit, listing)
        return stories
