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


def test_voice_clip_and_subtitle_roundtrip(conn):
    from datetime import datetime, timezone
    from core.enums import NarrationStyle
    from core.models import Story, Script
    from infra.db.repositories import (
        insert_story, insert_script, insert_voice_clip, insert_subtitle,
        get_voice_clip_by_job, get_subtitle_by_job,
    )
    jid = create_job(conn, source_id="t3_x")
    sid = insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="T", body_text="B", score=1, num_comments=1,
        created_utc=datetime.now(timezone.utc).timestamp(), permalink=""))
    scid = insert_script(conn, sid, Script(story_id=sid,
        style=NarrationStyle.STORYTELLING, text="hi", word_count=1,
        reading_time=1.0))
    vc_id = insert_voice_clip(conn, scid, "piper", "v", 1.0, 1.0, "n", 2.0, "/x.wav")
    assert get_voice_clip_by_job(conn, jid)["id"] == vc_id
    sub_id = insert_subtitle(conn, vc_id, "ass+srt", "default",
                              "/x.ass", "/x.srt")
    assert get_subtitle_by_job(conn, jid)["id"] == sub_id


def test_video_and_media_roundtrip(conn):
    from infra.db.repositories import (
        insert_video, get_video_by_job, insert_media, list_media,
    )
    jid = create_job(conn, source_id="t3_x")
    vid = insert_video(conn, jid, "shorts_vertical_9_16", "9:16", 1080, 1920,
                       60.0, None, None, "/v.mp4", "", 12345)
    assert get_video_by_job(conn, jid)["id"] == vid
    mid = insert_media(conn, "background", "minecraft_parkour", "clip1", "/bg.mp4")
    rows = list_media(conn, kind="background", category="minecraft_parkour")
    assert rows[0]["id"] == mid
    assert rows[0]["name"] == "clip1"
