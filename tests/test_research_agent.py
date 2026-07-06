# tests/test_research_agent.py
from datetime import datetime

from core.models import JobContext, SourceQuery, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_story_by_job

from agents.research_agent import make_research_agent


class FakeSource:
    def __init__(self, stories):
        self._s = stories
        self.fetched = []

    def discover(self, q):
        return self._s

    def fetch_full(self, s):
        self.fetched.append(s.source_id)
        return s


def test_research_agent_persists_top_story(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_seed")
    story = Story(source="reddit", source_id="t3_top", subreddit="nosleep",
                  author="u", title="T", body_text="B", score=9001,
                  num_comments=500, created_utc=datetime.utcnow().timestamp(),
                  permalink="/x")
    agent = make_research_agent(FakeSource([story]), conn,
                                query=SourceQuery(subreddits=["nosleep"]))
    ctx = JobContext(job_id=jid)
    out = agent(ctx)
    row = get_story_by_job(conn, jid)
    assert row["source_id"] == "t3_top"
    assert row["title"] == "T"
    assert out.story is not None
    assert out.story.source_id == "t3_top"


def test_research_agent_picks_top_score(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="seed")
    s_low = Story(source="reddit", source_id="low", subreddit="n", author="u",
                  title="L", body_text="b", score=100, num_comments=1,
                  created_utc=datetime.utcnow().timestamp(), permalink="")
    s_high = Story(source="reddit", source_id="high", subreddit="n", author="u",
                   title="H", body_text="b", score=9999, num_comments=1,
                   created_utc=datetime.utcnow().timestamp(), permalink="")
    agent = make_research_agent(FakeSource([s_low, s_high]), conn,
                                query=SourceQuery(subreddits=["n"]))
    out = agent(JobContext(job_id=jid))
    assert out.story.source_id == "high"


def test_research_agent_raises_on_empty(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="seed")
    agent = make_research_agent(FakeSource([]), conn,
                                query=SourceQuery(subreddits=["n"]))
    import pytest
    with pytest.raises(RuntimeError, match="no stories"):
        agent(JobContext(job_id=jid))
