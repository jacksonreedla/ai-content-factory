# tests/test_analyzer_agent.py
from datetime import datetime

import pytest

from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_score_by_story, insert_story,
)

from agents.analyzer_agent import make_analyzer_agent


class FakeLLM:
    def __init__(self, payload):
        self.payload = payload
    def json_complete(self, prompt, schema, **kw):
        return self.payload


def _seed_story(conn, jid):
    return insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="T", body_text="B", score=1, num_comments=1,
        created_utc=datetime.utcnow().timestamp(), permalink=""))


def test_analyzer_persists_score(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    sid = _seed_story(conn, jid)
    payload = {"entertainment": 8, "suspense": 7, "emotion": 6, "shock": 5,
               "virality": 9, "quality": 7, "retention": 8,
               "overall": 78.0, "confidence": 0.9}
    agent = make_analyzer_agent(FakeLLM(payload), conn, min_overall=70)
    agent(JobContext(job_id=jid, story=_story()))
    row = get_score_by_story(conn, sid)
    assert row["overall"] == 78.0
    assert row["confidence"] == 0.9
    assert row["virality"] == 9


def test_analyzer_rejects_below_threshold(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    _seed_story(conn, jid)
    payload = {"entertainment": 3, "suspense": 3, "emotion": 3, "shock": 3,
               "virality": 3, "quality": 3, "retention": 3,
               "overall": 30.0, "confidence": 0.5}
    agent = make_analyzer_agent(FakeLLM(payload), conn, min_overall=70)
    with pytest.raises(RuntimeError, match="below threshold"):
        agent(JobContext(job_id=jid, story=_story()))


def _story():
    return Story(source="reddit", source_id="t3_x", subreddit="n", author="u",
                 title="T", body_text="B", score=1, num_comments=1,
                 created_utc=datetime.utcnow().timestamp(), permalink="")
