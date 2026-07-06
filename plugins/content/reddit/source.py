# plugins/content/reddit/source.py
import logging

import praw

from core.models import SourceQuery, Story
from plugins.content.base import filter_by_age, dedupe_by_source_id

log = logging.getLogger(__name__)

_SORT_ATTRS = {"hot": "hot", "top": "top", "new": "new", "rising": "rising"}


class RedditSource:
    """PRAW-backed ContentSource.

    Pass `client=<praw.Reddit or fake>` for tests. Otherwise construct from
    secrets via `from_secrets`. Satisfies the ContentSource protocol.
    """

    def __init__(self, client=None, client_id: str = "", client_secret: str = "",
                 user_agent: str = "", username: str = "",
                 password: str = "") -> None:
        if client is not None:
            self._reddit = client
        else:
            self._reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent or "ai-content-factory/0.1",
                username=username or None,
                password=password or None,
            )

    @classmethod
    def from_secrets(cls, secrets) -> "RedditSource":
        return cls(
            client_id=secrets.reddit_client_id,
            client_secret=secrets.reddit_client_secret,
            user_agent=secrets.reddit_user_agent,
        )

    def discover(self, query: SourceQuery) -> list[Story]:
        stories: list[Story] = []
        sort_fn = _SORT_ATTRS.get(query.sort, "hot")
        for sub_name in query.subreddits:
            try:
                sub = self._reddit.subreddit(sub_name)
                submissions = list(getattr(sub, sort_fn)(limit=query.limit))
            except Exception as e:
                log.warning("reddit discover failed for r/%s: %s", sub_name, e)
                continue
            for s in submissions:
                if (getattr(s, "score", 0) or 0) < query.min_score:
                    continue
                if (getattr(s, "num_comments", 0) or 0) < query.min_comments:
                    continue
                stories.append(self._to_story(s))
        stories = filter_by_age(stories, query.max_age_hours)
        return dedupe_by_source_id(stories)

    def fetch_full(self, story: Story) -> Story:
        # Most listing endpoints already include selftext; fill only if missing.
        try:
            if not story.body_text:
                sub = self._reddit.submission(id=story.source_id)
                story.body_text = getattr(sub, "selftext", "") or ""
                story.body_raw = story.body_text
        except Exception as e:
            log.warning("reddit fetch_full failed for %s: %s", story.source_id, e)
        return story

    @staticmethod
    def _to_story(s) -> Story:
        author = getattr(s, "author", None)
        return Story(
            source="reddit",
            source_id=s.id,
            subreddit=getattr(getattr(s, "subreddit", None), "display_name", ""),
            author=getattr(author, "name", "[deleted]") if author else "[deleted]",
            title=getattr(s, "title", ""),
            body_text=getattr(s, "selftext", "") or "",
            body_raw=getattr(s, "selftext", "") or "",
            score=getattr(s, "score", 0) or 0,
            num_comments=getattr(s, "num_comments", 0) or 0,
            created_utc=getattr(s, "created_utc", 0.0),
            permalink=getattr(s, "permalink", ""),
        )
