# tests/test_reddit_source.py
import time

from core.models import SourceQuery, Story
from plugins.content.reddit.source import RedditSource


class FakeSubmission:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeSubreddit:
    def __init__(self, submissions):
        self._subs = submissions

    def top(self, limit=None): return list(self._subs)[:limit]
    def hot(self, limit=None): return list(self._subs)[:limit]
    def new(self, limit=None): return list(self._subs)[:limit]
    def rising(self, limit=None): return list(self._subs)[:limit]


class FakeReddit:
    def __init__(self, submissions_by_sub):
        self._map = submissions_by_sub

    def subreddit(self, name):
        return FakeSubreddit(self._map.get(name, []))


def _sub(name, sid, score=1500, comments=100, hours=2,
         body="body text", title="A title"):
    return FakeSubmission(
        id=sid, name="t3_" + sid,
        subreddit=type("S", (), {"display_name": name})(),
        author=type("A", (), {"name": "u"})(),
        title=title, selftext=body, score=score, num_comments=comments,
        created_utc=time.time() - hours * 3600, permalink=f"/r/{name}/comments/{sid}/",
    )


def test_discover_returns_stories_and_filters_by_score():
    reddit = FakeReddit({
        "nosleep": [_sub("nosleep", "a1", score=100)],
        "tifu":    [_sub("tifu", "b1", score=2000)],
    })
    src = RedditSource(client=reddit)
    q = SourceQuery(subreddits=["nosleep", "tifu"], min_score=150,
                    min_comments=50, max_age_hours=168, sort="hot", limit=10)
    stories = src.discover(q)
    ids = sorted(s.source_id for s in stories)
    assert ids == ["b1"]   # a1 below min_score


def test_discover_filters_by_comments_and_age():
    reddit = FakeReddit({
        "x": [
            _sub("x", "low_comments", score=2000, comments=10),
            _sub("x", "old", score=2000, comments=100, hours=999),
            _sub("x", "good", score=2000, comments=100, hours=2),
        ]
    })
    src = RedditSource(client=reddit)
    q = SourceQuery(subreddits=["x"], min_score=100, min_comments=50,
                    max_age_hours=168, sort="hot", limit=10)
    out = [s.source_id for s in src.discover(q)]
    assert out == ["good"]


def test_fetch_full_returns_story_unchanged_without_body():
    src = RedditSource(client=FakeReddit({}))
    s = Story(source="reddit", source_id="x", subreddit="n", author="a",
              title="t", body_text="", score=1, num_comments=0,
              created_utc=0, permalink="")
    out = src.fetch_full(s)
    assert out.source_id == "x"


def test_to_story_maps_fields():
    s = _sub("nosleep", "abc", score=42)
    story = RedditSource._to_story(s)
    assert story.source == "reddit"
    assert story.source_id == "abc"
    assert story.subreddit == "nosleep"
    assert story.score == 42
    assert story.body_text == "body text"
