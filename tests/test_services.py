# tests/test_services.py
from datetime import datetime

from core.enums import JobStage
from core.models import SourceQuery, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import get_job, get_story_by_job

from app.services import ResearchService


class FakeContainer:
    def __init__(self, db, src):
        self.db = db
        self.registry = self
        self._src = src
        self.pool = self
        self._submitted = None

    def active(self, contract, label=None):
        return self._src

    def submit(self, job_id, stage):
        self._submitted = (job_id, stage)


def _story(sid="t3_a"):
    return Story(source="reddit", source_id=sid, subreddit="n", author="u",
                 title="T", body_text="B", score=1, num_comments=1,
                 created_utc=datetime.utcnow().timestamp(), permalink="/x")


class FakeSource:
    def __init__(self, stories):
        self._s = stories
    def discover(self, q):
        return self._s
    def fetch_full(self, s):
        return s


def test_service_discover_returns_from_source(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    src = FakeSource([_story("t3_a"), _story("t3_b")])
    svc = ResearchService(FakeContainer(conn, src))
    out = svc.discover(SourceQuery(subreddits=["n"]))
    assert [s.source_id for s in out] == ["t3_a", "t3_b"]


def test_service_enqueue_creates_job_with_story(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    c = FakeContainer(conn, FakeSource([]))
    svc = ResearchService(c)
    jid = svc.enqueue(_story("t3_a"))
    job = get_job(conn, jid)
    row = get_story_by_job(conn, jid)
    assert job["source_id"] == "t3_a"
    assert row["title"] == "T"
    svc.start_job(jid, JobStage.ANALYZE)
    assert c._submitted == (jid, JobStage.ANALYZE)


def test_service_discover_returns_empty_when_no_source(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    class NoSrc:
        def active(self, c, l=None): return None
    c = FakeContainer(conn, None)
    c.registry = NoSrc()
    svc = ResearchService(c)
    assert svc.discover(SourceQuery(subreddits=["n"])) == []
