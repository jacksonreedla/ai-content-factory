"""Editor + Thumbnail agent tests with fake render/extract functions."""
from __future__ import annotations

from pathlib import Path

import agents.editor_agent as editor_module
import agents.thumbnail_agent as thumb_module
from app.pipeline import Pipeline
from database.repositories import StoryRepo, VideoRepo
from models.story import StoryStatus
from tests.fakes import FakeProvider
from tests.test_voice_and_caption_agents import seed_rewritten_story, write_silent_wav


def seed_video_with_audio(db, tmp_path) -> tuple[int, int]:
    """Story + video row that already has audio and captions."""
    story_id = seed_rewritten_story(db)
    audio = tmp_path / "voice.wav"
    write_silent_wav(audio, 2.0)
    captions = tmp_path / "caps.ass"
    captions.write_text("[Script Info]\n", encoding="utf-8")
    repo = VideoRepo(db)
    video_id = repo.add(story_id, 1, "shorts", title="Editor test")
    repo.set_audio(video_id, str(audio), 2.0)
    repo.set_captions(video_id, str(captions))
    return story_id, video_id


def patch_editor(monkeypatch, tmp_path) -> list:
    """Fake ffmpeg + background library; returns list of render calls."""
    calls: list = []

    def fake_render(spec, duration_s, timeout_s=1800):
        spec.output_path.parent.mkdir(parents=True, exist_ok=True)
        spec.output_path.write_bytes(b"fake mp4")
        calls.append((spec, duration_s))
        return spec.output_path

    bg = tmp_path / "bg.mp4"
    bg.write_bytes(b"bg")
    monkeypatch.setattr(editor_module, "ffmpeg_available", lambda: True)
    monkeypatch.setattr(editor_module, "render", fake_render)
    monkeypatch.setattr(editor_module, "pick_clip",
                        lambda *a, **k: bg)
    monkeypatch.setattr(editor_module, "pick_music", lambda *_: None)
    monkeypatch.setattr(editor_module, "OUTPUT_DIR", tmp_path / "out")
    return calls


def test_editor_agent_renders_and_marks_produced(config, db, monkeypatch, tmp_path):
    calls = patch_editor(monkeypatch, tmp_path)
    story_id, video_id = seed_video_with_audio(db, tmp_path)

    result = Pipeline(config, db).run_stage("edit")
    assert result.ok

    video = VideoRepo(db).get(video_id)
    assert video["file_path"].endswith(f"video_{video_id}.mp4")
    assert video["status"] == "rendered"
    assert StoryRepo(db).get(story_id).status == StoryStatus.PRODUCED
    spec, duration = calls[0]
    assert duration == 2.5  # audio 2.0s + 0.5s tail
    assert spec.captions_path is not None


def test_editor_agent_requires_ffmpeg(config, db, monkeypatch, tmp_path):
    monkeypatch.setattr(editor_module, "ffmpeg_available", lambda: False)
    seed_video_with_audio(db, tmp_path)
    result = Pipeline(config, db).run_stage("edit")
    assert not result.ok
    assert "FFmpeg" in result.stage_results["edit"].message


def test_editor_agent_skips_when_empty(config, db):
    result = Pipeline(config, db).run_stage("edit")
    assert result.ok
    assert result.stage_results["edit"].skipped


def test_thumbnail_agent(config, db, monkeypatch, tmp_path):
    calls = patch_editor(monkeypatch, tmp_path)
    _story_id, video_id = seed_video_with_audio(db, tmp_path)
    Pipeline(config, db).run_stage("edit")
    assert calls

    def fake_extract(video_path, output_path, at_s=1.0):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"jpg")
        return output_path

    def fake_generate(frame, text, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"thumb")
        return output_path

    monkeypatch.setattr(thumb_module, "extract_frame", fake_extract)
    monkeypatch.setattr(thumb_module, "generate_thumbnail", fake_generate)
    monkeypatch.setattr(thumb_module, "THUMBS_DIR", tmp_path / "thumbs")

    config.set("ai.tasks.thumbnail_text.provider", "fake", persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    pipeline = Pipeline(config, db)
    pipeline.llm.providers = {"fake": FakeProvider(
        ['{"options": ["HE LOST EVERYTHING"]}'])}

    result = pipeline.run_stage("thumbnail")
    assert result.ok
    video = VideoRepo(db).get(video_id)
    assert video["thumbnail_path"].endswith(f"thumb_{video_id}.jpg")


def test_wrap_text():
    from editor.thumbnail import wrap_text
    lines = wrap_text("he lost absolutely everything overnight", 12, 3)
    assert 1 < len(lines) <= 3
    assert all(len(line) <= 12 or " " not in line for line in lines)
