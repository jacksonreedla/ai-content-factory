"""Publisher agent tests with a fake TikTok client."""
from __future__ import annotations

import json

import agents.publisher_agent as publisher_module
from agents.publisher_agent import PublisherAgent
from app.pipeline import Pipeline
from database.repositories import (SettingsRepo, StoryRepo, UploadRepo,
                                   VideoRepo)
from models.story import StoryStatus
from tests.test_voice_and_caption_agents import seed_rewritten_story


class FakeTikTok:
    def __init__(self, fail: bool = False,
                 privacy_options=("PUBLIC_TO_EVERYONE", "SELF_ONLY")):
        self.fail = fail
        self.privacy_options = list(privacy_options)
        self.uploads: list[dict] = []

    def is_configured(self) -> bool:
        return True

    def is_authorized(self) -> bool:
        return True

    def resolve_privacy(self, requested: str) -> str:
        want = {"public": "PUBLIC_TO_EVERYONE", "private": "SELF_ONLY",
                "friends": "MUTUAL_FOLLOW_FRIENDS"}.get(requested, "SELF_ONLY")
        return want if want in self.privacy_options else self.privacy_options[0]

    def upload_video(self, file_path, *, title, privacy_level="SELF_ONLY",
                     disable_comment=False, disable_duet=False,
                     disable_stitch=False, is_aigc=True,
                     cover_timestamp_ms=1000):
        if self.fail:
            from api.tiktok_client import TikTokError
            raise TikTokError("spam_risk_too_many_posts")
        self.uploads.append({
            "file": str(file_path), "title": title,
            "privacy_level": privacy_level, "is_aigc": is_aigc,
            "disable_comment": disable_comment,
        })
        return f"v_pub_file~v2-1.{len(self.uploads)}"


def seed_rendered_video(db, tmp_path, with_metadata: bool = True):
    story_id = seed_rewritten_story(db)
    repo = VideoRepo(db)
    video_id = repo.add(story_id, 1, "shorts", title="Publisher test")
    video_file = tmp_path / f"video_{video_id}.mp4"
    video_file.write_bytes(b"mp4")
    repo.set_audio(video_id, str(tmp_path / "a.wav"), 2.0)
    repo.set_file(video_id, str(video_file), 2.5)
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"jpg")
    repo.set_thumbnail(video_id, str(thumb))
    if with_metadata:
        SettingsRepo(db).set(f"metadata.story.{story_id}", json.dumps({
            "title": "AI Title", "description": "AI description",
            "hashtags": ["#story"], "tags": ["reddit", "stories"],
        }))
    return story_id, video_id


def test_publisher_posts_with_metadata(config, db, monkeypatch, tmp_path):
    fake = FakeTikTok()
    monkeypatch.setattr(publisher_module, "_make_client", lambda ctx: fake)
    config.set("upload.default_visibility", "public", persist=False)
    story_id, video_id = seed_rendered_video(db, tmp_path)

    result = Pipeline(config, db).run_stage("upload")
    assert result.ok

    assert len(fake.uploads) == 1
    upload = fake.uploads[0]
    # Caption combines title, description and hashtags.
    assert "AI Title" in upload["title"]
    assert "#story" in upload["title"]
    assert upload["privacy_level"] == "PUBLIC_TO_EVERYONE"
    assert upload["is_aigc"] is True

    rows = UploadRepo(db).recent(5)
    assert rows[0]["status"] == "uploaded"
    assert rows[0]["platform"] == "tiktok"
    assert rows[0]["remote_id"].startswith("v_pub_file")
    assert StoryRepo(db).get(story_id).status == StoryStatus.PUBLISHED
    assert VideoRepo(db).get(video_id)["status"] == "published"


def test_publisher_privacy_falls_back_when_unavailable(config, db, monkeypatch,
                                                       tmp_path):
    # Unaudited/private accounts often only allow SELF_ONLY.
    fake = FakeTikTok(privacy_options=("SELF_ONLY",))
    monkeypatch.setattr(publisher_module, "_make_client", lambda ctx: fake)
    config.set("upload.default_visibility", "public", persist=False)
    seed_rendered_video(db, tmp_path)

    result = Pipeline(config, db).run_stage("upload")
    assert result.ok
    assert fake.uploads[0]["privacy_level"] == "SELF_ONLY"


def test_publisher_failure_marks_and_retries(config, db, monkeypatch, tmp_path):
    fake = FakeTikTok(fail=True)
    monkeypatch.setattr(publisher_module, "_make_client", lambda ctx: fake)
    seed_rendered_video(db, tmp_path)

    result = Pipeline(config, db).run_stage("upload")
    assert not result.ok
    rows = UploadRepo(db).recent(5)
    assert rows[0]["status"] == "failed"
    assert "spam_risk" in rows[0]["error"]

    # retry succeeds and reuses the same upload row
    fake.fail = False
    result = Pipeline(config, db).run_stage("upload")
    assert result.ok
    rows = UploadRepo(db).recent(5)
    assert len(rows) == 1
    assert rows[0]["status"] == "uploaded"


def test_publisher_skips_when_nothing(config, db, monkeypatch):
    monkeypatch.setattr(publisher_module, "_make_client",
                        lambda ctx: FakeTikTok())
    result = Pipeline(config, db).run_stage("upload")
    assert result.ok
    assert result.stage_results["upload"].skipped


def test_publisher_skips_when_unconfigured(config, db, monkeypatch, tmp_path):
    """No client key/secret yet -> pipeline completes, videos wait."""
    class Unconfigured(FakeTikTok):
        def is_configured(self) -> bool:
            return False

    monkeypatch.setattr(publisher_module, "_make_client",
                        lambda ctx: Unconfigured())
    seed_rendered_video(db, tmp_path)
    result = Pipeline(config, db).run_stage("upload")
    assert result.ok
    assert result.stage_results["upload"].skipped
    assert "not" in result.stage_results["upload"].message


def test_publisher_requires_auth(config, db, monkeypatch, tmp_path):
    class Unauthorized(FakeTikTok):
        def is_authorized(self) -> bool:
            return False

    monkeypatch.setattr(publisher_module, "_make_client",
                        lambda ctx: Unauthorized())
    seed_rendered_video(db, tmp_path)
    result = Pipeline(config, db).run_stage("upload")
    assert not result.ok
    assert "not connected" in result.stage_results["upload"].message


def test_upload_not_repeated(config, db, monkeypatch, tmp_path):
    fake = FakeTikTok()
    monkeypatch.setattr(publisher_module, "_make_client", lambda ctx: fake)
    seed_rendered_video(db, tmp_path)
    assert Pipeline(config, db).run_stage("upload").ok
    result = Pipeline(config, db).run_stage("upload")
    assert result.stage_results["upload"].skipped
    assert len(fake.uploads) == 1


def test_caption_trims_to_limit():
    long_title = "x" * 3000
    caption = PublisherAgent._build_caption(
        {"title": long_title, "hashtags": ["#a"]}, {})
    assert len(caption) <= 2200
