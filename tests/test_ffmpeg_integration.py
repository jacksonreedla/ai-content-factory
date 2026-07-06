# tests/test_ffmpeg_integration.py
"""Real ffmpeg integration tests. Skipped if ffmpeg is not on PATH."""
import shutil
import subprocess

import pytest
from datetime import datetime, timezone

from core.enums import NarrationStyle
from core.models import JobContext, Script, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, insert_media, insert_script, insert_story,
)
from app.paths import AppPaths

needs_ffmpeg = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg/ffprobe not on PATH",
)


def _make_assets(tmp_path):
    """Generate a tiny background mp4 and a narration wav via ffmpeg."""
    bg = tmp_path / "bg.mp4"
    voice = tmp_path / "voice.wav"
    # 6s of test pattern at 320x568 (9:16-ish).
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "testsrc=duration=6:size=320x568:rate=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(bg),
    ], check=True, capture_output=True)
    # 2s silent wav.
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        "anullsrc=r=22050:cl=mono", "-t", "2",
        str(voice),
    ], check=True, capture_output=True)
    return bg, voice


@needs_ffmpeg
def test_ffmpeg_editor_composes_video(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    from plugins.editor.ffmpeg_editor import FFmpegEditor, EditSpec
    bg, voice = _make_assets(tmp_path)
    out = tmp_path / "out.mp4"
    editor = FFmpegEditor()
    spec = EditSpec(
        voice_path=str(voice), background_path=str(bg),
        format="shorts_vertical_9_16", out_path=str(out),
    )
    video = editor.compose(spec)
    assert video.path.exists()
    assert video.size_bytes > 0
    assert video.width == 1080 and video.height == 1920


@needs_ffmpeg
def test_editor_agent_end_to_end(tmp_path, monkeypatch):
    """Full EDIT agent run with real ffmpeg + a seeded library background."""
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    conn = connect(tmp_path / "t.db"); migrate(conn)
    paths = AppPaths(); paths.ensure()
    bg, voice = _make_assets(tmp_path)
    # Seed a job with story→script→voice_clip + a library background.
    jid = create_job(conn, source_id="t3_x")
    sid = insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="T", body_text="B", score=1, num_comments=1,
        created_utc=datetime.now(timezone.utc).timestamp(), permalink=""))
    scid = insert_script(conn, sid, Script(story_id=sid,
        style=NarrationStyle.STORYTELLING, text="hi", word_count=1,
        reading_time=1.0))
    from infra.db.repositories import insert_voice_clip, get_video_by_job
    insert_voice_clip(conn, scid, "piper", "v", 1.0, 1.0, "n", 2.0, str(voice))
    insert_media(conn, "background", "minecraft_parkour", "bg", str(bg))

    from agents.editor_agent import make_editor_agent
    from plugins.editor.ffmpeg_editor import FFmpegEditor
    agent = make_editor_agent(FFmpegEditor(), conn, paths,
                              default_format="shorts_vertical_9_16")
    ctx = JobContext(job_id=jid)
    agent(ctx)
    row = get_video_by_job(conn, jid)
    assert row is not None
    assert row["format"] == "shorts_vertical_9_16"
    assert row["size_bytes"] > 0
