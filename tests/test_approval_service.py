# tests/test_approval_service.py
import time

from core.enums import ApprovalState, JobStage, JobStatus
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_job, get_publish_by_job, insert_media, insert_video,
    update_job_stage,
)

from app.approval_service import ApprovalService


class FakePool:
    def __init__(self): self.submitted = []
    def submit(self, job_id, stage): self.submitted.append((job_id, stage))


class FakeContainer:
    def __init__(self, db): self.db = db; self.pool = FakePool()


def _seed_pending_job(conn, tmp_path):
    jid = create_job(conn, source_id="t3_x")
    update_job_stage(conn, jid, JobStage.AWAITING_APPROVAL)
    # Need a video + story for list_pending to return it.
    from datetime import datetime, timezone
    from core.models import Story
    from infra.db.repositories import insert_story
    insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="A Title", body_text="body", score=1, num_comments=1,
        created_utc=datetime.now(timezone.utc).timestamp(), permalink=""))
    insert_video(conn, jid, "shorts_vertical_9_16", "9:16", 1080, 1920,
                 60.0, None, None, str(tmp_path / "v.mp4"), "", 100)
    return jid


def test_list_pending_returns_gated_jobs(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = _seed_pending_job(conn, tmp_path)
    svc = ApprovalService(FakeContainer(conn))
    pending = svc.list_pending()
    assert len(pending) == 1
    assert pending[0]["job_id"] == jid


def test_approve_enqueues_at_thumbnail(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = _seed_pending_job(conn, tmp_path)
    c = FakeContainer(conn)
    svc = ApprovalService(c)
    assert svc.approve(jid, privacy="private") is True
    job = get_job(conn, jid)
    assert job["approval_state"] == ApprovalState.APPROVED.value
    assert c.pool.submitted == [(jid, JobStage.THUMBNAIL)]


def test_approve_wrong_stage_fails(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")  # still at RESEARCH
    c = FakeContainer(conn)
    assert ApprovalService(c).approve(jid) is False
    assert c.pool.submitted == []


def test_reject_marks_done(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = _seed_pending_job(conn, tmp_path)
    svc = ApprovalService(FakeContainer(conn))
    assert svc.reject(jid) is True
    job = get_job(conn, jid)
    assert job["approval_state"] == ApprovalState.REJECTED.value
    assert job["status"] == JobStatus.DONE.value


def test_edit_creates_seo_placeholder(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = _seed_pending_job(conn, tmp_path)
    svc = ApprovalService(FakeContainer(conn))
    assert svc.edit(jid, title="Custom Title", description="d") is True
    from infra.db.repositories import get_seo_by_job
    seo = get_seo_by_job(conn, jid)
    assert seo["title"] == "Custom Title"
    job = get_job(conn, jid)
    assert job["approval_state"] == ApprovalState.EDITED.value
