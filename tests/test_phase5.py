# tests/test_phase5.py
"""Tests for system checks, analytics agent, and the new views build."""
from datetime import datetime, timezone

from app.system_checks import check_all
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import insert_publish, insert_video, create_job

from agents.analytics_agent import run_once
from plugins.analytics.youtube.source import YouTubeAnalyticsSource, AnalyticsPoint


def test_check_all_returns_dict():
    s = check_all()
    assert set(s.keys()) == {"ffmpeg", "ffprobe", "piper", "whisper", "ollama"}
    # ffmpeg is known available in this env.
    assert s["ffmpeg"] is True


class FakeAnalyticsClient:
    def __init__(self, stats): self.stats = stats
    def videos(self):
        outer = self
        class V:
            def list(self, **kw):
                class L:
                    def execute(self_inner): return {"items": [{"statistics": outer.stats}]}
                return L()
        return V()


def test_analytics_source_fetch_returns_counts():
    src = YouTubeAnalyticsSource(client=FakeAnalyticsClient(
        {"viewCount": "100", "likeCount": "10", "commentCount": "3"}))
    point = src.fetch({"remote_id": "abc"})
    assert point.views == 100
    assert point.likes == 10
    assert point.comments == 3


def test_analytics_source_no_client_returns_zeros():
    src = YouTubeAnalyticsSource()
    point = src.fetch({"remote_id": "x"})
    assert point.views == 0


def test_analytics_source_empty_remote_returns_zeros():
    src = YouTubeAnalyticsSource(client=FakeAnalyticsClient({}))
    assert src.fetch({"remote_id": ""}).views == 0


def test_run_once_inserts_rows(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    vid = insert_video(conn, jid, "x", "9:16", 1080, 1920, 5.0,
                       None, None, "/v.mp4", "", 1)
    insert_publish(conn, vid, "youtube", "yt1", "private", "", "done", 1)
    class FakeSource:
        def fetch(self, p): return AnalyticsPoint(views=42, likes=7)
    n = run_once(conn, FakeSource())
    assert n == 1
    row = conn.execute("SELECT views, likes FROM analytics WHERE publish_id=?",
                       (1,)).fetchone()
    assert row["views"] == 42
    assert row["likes"] == 7


def test_run_once_skips_failed_publishes(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    vid = insert_video(conn, jid, "x", "9:16", 1080, 1920, 5.0,
                       None, None, "/v.mp4", "", 1)
    insert_publish(conn, vid, "youtube", "yt1", "private", "", "failed", 1)
    class FakeSource:
        def fetch(self, p): return AnalyticsPoint(views=1)
    assert run_once(conn, FakeSource()) == 0
