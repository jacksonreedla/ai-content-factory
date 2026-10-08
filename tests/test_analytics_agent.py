"""Analytics agent tests with a fake stats client.

Note: TikTok's Content Posting API does not expose view/like stats, so the
analytics stage uses a separate stats client (YouTube Data API by default).
These tests fake that client and seed uploaded rows directly.
"""
from __future__ import annotations

import json

import agents.analytics_agent as analytics_module
from agents.analytics_agent import INSIGHTS_KEY, REVENUE_KEY
from app.pipeline import Pipeline
from database.repositories import AnalyticsRepo, SettingsRepo, UploadRepo
from tests.test_publisher import seed_rendered_video


class FakeStatsClient:
    """Minimal stand-in for the YouTube stats client the analytics agent uses."""

    def __init__(self, stats: dict[str, dict]):
        self.stats = stats

    def is_configured(self) -> bool:
        return True

    def is_authorized(self) -> bool:
        return True

    def video_stats(self, video_ids):
        return {vid: self.stats[vid] for vid in video_ids if vid in self.stats}


def upload_one(config, db, tmp_path, remote_id: str = "vid1") -> int:
    """Seed a rendered video and mark it uploaded; returns local video id."""
    _story_id, video_id = seed_rendered_video(db, tmp_path)
    upload_repo = UploadRepo(db)
    upload_id = upload_repo.add(video_id, "tiktok", "public")
    upload_repo.mark_uploaded(upload_id, remote_id)
    return video_id


def test_analytics_snapshots_and_insights(config, db, monkeypatch, tmp_path):
    video_id = upload_one(config, db, tmp_path, remote_id="vid1")
    client = FakeStatsClient(
        {"vid1": {"views": 5000, "likes": 200, "comments": 30}})
    monkeypatch.setattr(analytics_module, "_make_client", lambda ctx: client)

    result = Pipeline(config, db).run_stage("analytics")
    assert result.ok

    latest = AnalyticsRepo(db).latest_all()
    assert latest[video_id]["views"] == 5000
    assert latest[video_id]["likes"] == 200

    settings = SettingsRepo(db)
    insights = json.loads(settings.get(INSIGHTS_KEY))
    assert insights["recommendations"]          # always at least one line
    # 5000 views * $0.15/1000 (shorts default)
    assert settings.get(REVENUE_KEY) == "0.75"


def test_analytics_latest_snapshot_wins(config, db, monkeypatch, tmp_path):
    video_id = upload_one(config, db, tmp_path, remote_id="vid1")
    client = FakeStatsClient({"vid1": {"views": 100, "likes": 1, "comments": 0}})
    monkeypatch.setattr(analytics_module, "_make_client", lambda ctx: client)
    Pipeline(config, db).run_stage("analytics")

    client.stats["vid1"]["views"] = 900          # stats grew since last run
    Pipeline(config, db).run_stage("analytics")
    assert AnalyticsRepo(db).latest_all()[video_id]["views"] == 900


def test_analytics_skips_without_uploads(config, db, monkeypatch):
    monkeypatch.setattr(analytics_module, "_make_client",
                        lambda ctx: FakeStatsClient({}))
    result = Pipeline(config, db).run_stage("analytics")
    assert result.ok
    assert result.stage_results["analytics"].skipped


def test_analytics_skips_when_unconfigured(config, db, monkeypatch, tmp_path):
    upload_one(config, db, tmp_path, remote_id="vid1")

    class Unconfigured(FakeStatsClient):
        def is_configured(self):
            return False

    monkeypatch.setattr(analytics_module, "_make_client",
                        lambda ctx: Unconfigured({}))
    result = Pipeline(config, db).run_stage("analytics")
    assert result.ok
    assert result.stage_results["analytics"].skipped
