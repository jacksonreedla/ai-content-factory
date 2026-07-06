# tests/test_repositories.py
import pytest

from core.enums import JobStage, JobStatus
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_job, update_job_stage, update_job_status,
    set_approval_state, count_jobs_by_status,
)


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.db")
    migrate(c)
    return c


def test_create_and_get_job(conn):
    jid = create_job(conn, source_id="t3_abc", story_url="https://reddit/x")
    job = get_job(conn, jid)
    assert job["source_id"] == "t3_abc"
    assert job["stage"] == JobStage.RESEARCH.value
    assert job["status"] == "queued"


def test_update_stage_and_status(conn):
    jid = create_job(conn, source_id="t3_abc")
    update_job_stage(conn, jid, JobStage.REWRITE)
    update_job_status(conn, jid, JobStatus.RUNNING)
    job = get_job(conn, jid)
    assert job["stage"] == "rewrite"
    assert job["status"] == "running"


def test_set_approval_state(conn):
    jid = create_job(conn, source_id="t3_x")
    set_approval_state(conn, jid, "approved")
    job = get_job(conn, jid)
    assert job["approval_state"] == "approved"


def test_count_by_status(conn):
    create_job(conn, source_id="t3_a")
    j2 = create_job(conn, source_id="t3_b")
    update_job_status(conn, j2, JobStatus.RUNNING)
    assert count_jobs_by_status(conn, "queued") == 1
    assert count_jobs_by_status(conn, "running") == 1
