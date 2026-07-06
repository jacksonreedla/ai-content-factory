# tests/test_phase4_agents.py
"""Thumbnail, SEO, and publishing agent tests with fakes."""
import json
from datetime import datetime, timezone

import pytest

from core.enums import NarrationStyle
from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_publish_by_job, get_seo_by_job, get_thumbnails_by_job,
    insert_media, insert_script, insert_story, insert_video,
)

from agents.thumbnail_agent import make_thumbnail_agent
from agents.seo_agent import make_seo_agent
from agents.publishing_agent import make_publishing_agent


def _seed_full_job(conn, tmp_path):
    jid = create_job(conn, source_id="t3_x")
    sid = insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="The Cat Stole My Homework", body_text="B", score=1,
        num_comments=1, created_utc=datetime.now(timezone.utc).timestamp(),
        permalink=""))
    scid = insert_script(conn, sid, Script(story_id=sid,
        style=NarrationStyle.STORYTELLING, text="a script", word_count=2,
        reading_time=1.0))
    vid = insert_video(conn, jid, "shorts_vertical_9_16", "9:16", 1080, 1920,
                       60.0, None, None, str(tmp_path / "v.mp4"), "", 100)
    return jid, sid, vid


def _script(story_id):
    from core.models import Script
    return Script(story_id=story_id, style=NarrationStyle.STORYTELLING,
                  text="a script", word_count=2, reading_time=1.0)


def test_thumbnail_agent_renders_variants(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    conn = connect(tmp_path / "t.db"); migrate(conn)
    from app.paths import AppPaths
    paths = AppPaths(); paths.ensure()
    jid, sid, vid = _seed_full_job(conn, tmp_path)
    calls = []
    class FakeRenderer:
        def render(self, tpl, lines, out_path=None, bg_path=None):
            from pathlib import Path
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            Path(out_path).write_bytes(b"\x89PNG")
            calls.append((tpl, lines))
            return out_path
    agent = make_thumbnail_agent(FakeRenderer(), conn, paths)
    agent(JobContext(job_id=jid))
    thumbs = get_thumbnails_by_job(conn, jid)
    assert len(thumbs) == 3   # three variants
    assert len(calls) == 3


def test_seo_agent_persists_seo(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid, sid, vid = _seed_full_job(conn, tmp_path)
    class FakeGen:
        def generate(self, video, script):
            return type("R", (), {
                "title": "Title", "description": "Desc",
                "tags": ["t1"], "hashtags": ["#h"],
                "pinned_comment": "pc", "community_post": "cp",
                "ctr_score": 70.0, "seo_score": 85.0,
            })()
    agent = make_seo_agent(FakeGen(), conn, llm=object())
    agent(JobContext(job_id=jid))
    seo = get_seo_by_job(conn, jid)
    assert seo["title"] == "Title"
    assert json.loads(seo["tags_json"]) == ["t1"]
    assert seo["seo_score"] == 85.0


def test_publishing_agent_persists_on_success(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid, sid, vid = _seed_full_job(conn, tmp_path)
    # Seed a SEO row so the agent has one to read.
    from infra.db.repositories import insert_seo
    insert_seo(conn, vid, "Title", "Desc", "[]", "[]", "", "", 70.0, 85.0)
    class FakePublisher:
        def upload(self, video, seo, privacy, playlist_id=None):
            return PublishResultStub(remote_id="yt1", status="done",
                                     response={"id": "yt1"})
    agent = make_publishing_agent(FakePublisher(), conn,
                                  default_privacy="private")
    agent(JobContext(job_id=jid))
    pub = get_publish_by_job(conn, jid)
    assert pub["status"] == "done"
    assert pub["remote_id"] == "yt1"
    assert pub["privacy"] == "private"


def test_publishing_agent_records_failure_and_raises(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid, sid, vid = _seed_full_job(conn, tmp_path)
    from infra.db.repositories import insert_seo
    insert_seo(conn, vid, "Title", "Desc", "[]", "[]", "", "", 70.0, 85.0)
    class FakePublisher:
        def upload(self, video, seo, privacy, playlist_id=None):
            raise RuntimeError("network down")
    agent = make_publishing_agent(FakePublisher(), conn, default_privacy="private")
    with pytest.raises(RuntimeError, match="network down"):
        agent(JobContext(job_id=jid))
    pub = get_publish_by_job(conn, jid)
    assert pub["status"] == "failed"
    assert pub["attempt_count"] == 1


class PublishResultStub:
    def __init__(self, remote_id, status, response):
        self.remote_id = remote_id; self.status = status; self.response = response


# Pull in Script for the helper.
from core.models import Script  # noqa: E402
