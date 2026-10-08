"""Reddit archive content source (credential-free, WITH real vote counts).

Reddit blocks unauthenticated access to its own ``.json`` listings, and the
public RSS feeds carry no score/comment data - so neither lets you filter by
popularity without an approved API key. This source solves that by reading a
public Reddit *archive* API (a Pushshift successor) that mirrors submissions
and periodically re-scans them, so older posts carry their **matured** score
and comment counts.

Because scores are real here, the normal upvote/comment ``RedditFilters``
apply - restoring ``min_upvotes`` filtering with no credentials at all.

Fetching (network) is kept separate from parsing/cleaning (pure functions) so
the logic is unit-testable without network access.
"""
from __future__ import annotations

import json as _json
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import Config
from api.reddit_client import clean_story_text, normalize_subreddit
from models.story import Story, StoryStatus

log = logging.getLogger("acf.reddit_archive")

# Public archive endpoint. Read-only, no key. Mirrors Reddit submission JSON.
ARCHIVE_ENDPOINT = "https://arctic-shift.photon-reddit.com/api/posts/search"


def _iso_date(ts: float) -> str:
    """Epoch seconds -> 'YYYY-MM-DD' (UTC), the format the archive accepts."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def reddit_archive_url(subreddit: str, limit: int = 100,
                       after: str | None = None, before: str | None = None,
                       sort: str = "desc") -> str:
    """Build an archive search URL for one subreddit's submissions.

    ``after``/``before`` are 'YYYY-MM-DD' date bounds; ``sort='desc'`` returns
    newest-first within the window.
    """
    params = {
        "subreddit": normalize_subreddit(subreddit),
        "limit": max(1, min(int(limit), 100)),   # API caps a page at 100
        "sort": sort,
    }
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    return f"{ARCHIVE_ENDPOINT}?{urlencode(params)}"


def parse_archive_json(raw: bytes | str, clean: bool = True,
                       require_matured: bool = True) -> list[Story]:
    """Parse an archive search payload into Stories. Pure - no network.

    The payload is ``{"data": [ <submission>, ... ]}`` where each submission
    has the same fields as Reddit's API. We skip link posts, stickied posts,
    removed/deleted bodies, and (when ``require_matured``) posts whose score is
    still hidden by Reddit (``hide_score``) - those carry an unreliable ~1 score
    that would defeat upvote filtering.
    """
    data = _json.loads(raw) if isinstance(raw, (bytes, str)) else raw
    posts = (data or {}).get("data", []) if isinstance(data, dict) else []

    stories: list[Story] = []
    for d in posts:
        if not isinstance(d, dict):
            continue
        if d.get("stickied") or not d.get("is_self", False):
            continue
        if require_matured and d.get("hide_score"):
            continue                       # score not yet revealed -> unreliable
        text = d.get("selftext", "") or ""
        if text in ("[deleted]", "[removed]", ""):
            continue
        if clean:
            text = clean_story_text(text)
        permalink = d.get("permalink", "")
        score = d.get("score")
        if score is None:
            score = d.get("ups", 0)
        stories.append(Story(
            id=None, source="reddit", source_id=d.get("id", ""),
            title=d.get("title", "") or "", text=text,
            author=d.get("author", "") or "[deleted]",
            subreddit=d.get("subreddit", "") or "",
            url=f"https://reddit.com{permalink}" if permalink else "",
            upvotes=int(score or 0),
            num_comments=int(d.get("num_comments") or 0),
            created_utc=float(d.get("created_utc") or 0),
            nsfw=bool(d.get("over_18", False)),
            status=StoryStatus.NEW,
        ))
    return stories


class RedditArchiveClient:
    """Fetch subreddit submissions (with real scores) from the archive API."""

    _RETRYABLE = (429, 500, 502, 503, 504)

    def __init__(self, config: Config, timeout_s: int = 30):
        self.config = config
        self.timeout_s = timeout_s
        self.user_agent = config.get("reddit.user_agent",
                                     "ai-content-factory/0.1")
        self.clean = bool(config.get("reddit.clean_text", True))
        self.max_retries = int(config.get("reddit.max_retries", 3))
        self.backoff_base_s = float(config.get("reddit.backoff_base_s", 5.0))
        # Window: look back this many days, but skip posts newer than this many
        # hours so their scores have had time to settle.
        self.window_days = int(config.get("reddit.archive_window_days", 45))
        self.min_maturity_hours = int(
            config.get("reddit.archive_min_maturity_hours", 24))
        # Busy subreddits 422 ("too much matched") on a wide window; we halve
        # the window and retry down to this floor before giving up.
        self.min_window_days = int(config.get("reddit.archive_min_window_days", 5))

    def _fetch_raw(self, url: str) -> bytes:
        req = Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        })
        for attempt in range(self.max_retries + 1):
            try:
                with urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                    return resp.read()
            except HTTPError as exc:
                if exc.code not in self._RETRYABLE or attempt >= self.max_retries:
                    raise
                wait = self.backoff_base_s * (2 ** attempt) + random.uniform(
                    0, self.backoff_base_s)
                log.info("HTTP %s on archive; backing off %.1fs (retry %d/%d)",
                         exc.code, wait, attempt + 1, self.max_retries)
                time.sleep(wait)
            except URLError as exc:
                if attempt >= self.max_retries:
                    raise
                time.sleep(self.backoff_base_s * (2 ** attempt))
        raise RuntimeError(f"unreachable: exhausted retries for {url}")

    def fetch_stories(self, subreddit: str, listing: str = "top",
                      time_filter: str = "day", limit: int = 25) -> list[Story]:
        """Fetch recent-but-matured submissions for a subreddit.

        ``listing``/``time_filter`` are accepted for signature-compatibility with
        the other Reddit clients but don't map onto the archive; the window is
        controlled by ``archive_window_days`` / ``archive_min_maturity_hours``.
        We over-fetch (up to 100) so upvote filtering downstream still yields
        enough stories after low-score posts are dropped.
        """
        now = time.time()
        before = _iso_date(now - self.min_maturity_hours * 3600)
        page = max(int(limit), 100)        # grab a full page to filter from
        sub = normalize_subreddit(subreddit)
        window = self.window_days
        while True:
            after = _iso_date(now - window * 86400)
            url = reddit_archive_url(subreddit, limit=page, after=after,
                                     before=before, sort="desc")
            try:
                raw = self._fetch_raw(url)
            except HTTPError as exc:
                # 422 = the window matched too much for this (busy) subreddit.
                # Narrow it and retry; busy subs still have plenty within days.
                if exc.code == 422 and window > self.min_window_days:
                    window = max(self.min_window_days, window // 2)
                    log.info("Archive 422 on r/%s; window too broad, "
                             "narrowing to %dd and retrying", sub, window)
                    time.sleep(0.5)
                    continue
                raise
            stories = parse_archive_json(raw, clean=self.clean)
            log.info("Fetched %d matured submissions from r/%s (archive, %s..%s)",
                     len(stories), sub, after, before)
            return stories
