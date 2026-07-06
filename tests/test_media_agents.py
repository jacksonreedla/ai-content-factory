# tests/test_media_agents.py
"""Tests for voice/subtitle/editor agents using fakes (no ffmpeg/whisper)."""
from datetime import datetime, timezone

import pytest

from core.enums import NarrationStyle
from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_video_by_job, get_voice_clip_by_job,
    get_subtitle_by_job, insert_script, insert_story,
)
from app.paths import AppPaths

from agents.voice_agent import make_voice_agent
from agents.subtitle_agent import make_subtitle_agent


class FakeEngine:
    def __init__(self): self.called = []
    def synthesize(self, text, opts, out):
        self.called.append(text)
        from plugins.voice.base import AudioClip
        # write a stub wav
        import wave, struct
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050)
            w.writeframes(struct.pack("<h", 0))
        return AudioClip(path=out, duration_sec=2.0)


class FakeStyler:
    style_name = "default"
    def render(self, words, style=None, ass_path=None, srt_path=None):
        Path = __import__("pathlib").Path
        if ass_path:
            Path(ass_path).parent.mkdir(parents=True, exist_ok=True)
            Path(ass_path).write_text("[Script Info]\n")
        if srt_path:
            Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
            Path(srt_path).write_text("1\n0:00:00,000 --> 0:00:01,000\nhello\n")
        from plugins.captions.word_timing import SubtitleArtifacts
        return SubtitleArtifacts(ass_path=ass_path or "", srt_path=srt_path or "")


def _seed(conn, jid, with_script=True):
    sid = insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="T", body_text="B", score=1, num_comments=1,
        created_utc=datetime.now(timezone.utc).timestamp(), permalink=""))
    if with_script:
        from core.models import Script
        insert_script(conn, sid, Script(story_id=sid, style=NarrationStyle.STORYTELLING,
                                        text="hello world", word_count=2,
                                        reading_time=1.0))
    return sid


def test_voice_agent_synthesizes_and_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    conn = connect(tmp_path / "t.db"); migrate(conn)
    paths = AppPaths(); paths.ensure()
    jid = create_job(conn, source_id="t3_x"); _seed(conn, jid)
    eng = FakeEngine()
    from plugins.voice.base import VoiceOpts
    agent = make_voice_agent(eng, conn, VoiceOpts(), paths)
    ctx = agent(JobContext(job_id=jid))
    vc = get_voice_clip_by_job(conn, jid)
    assert vc["engine"] == "piper"
    assert vc["duration_sec"] == 2.0
    assert ctx.artifacts["voice_path"].endswith("voice.wav")
    assert eng.called == ["hello world"]


def test_voice_agent_raises_without_script(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    conn = connect(tmp_path / "t.db"); migrate(conn)
    paths = AppPaths(); paths.ensure()
    jid = create_job(conn, source_id="t3_x"); _seed(conn, jid, with_script=False)
    from plugins.voice.base import VoiceOpts
    agent = make_voice_agent(FakeEngine(), conn, VoiceOpts(), paths)
    with pytest.raises(RuntimeError, match="no script"):
        agent(JobContext(job_id=jid))


def test_subtitle_agent_builds_captions(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    conn = connect(tmp_path / "t.db"); migrate(conn)
    paths = AppPaths(); paths.ensure()
    jid = create_job(conn, source_id="t3_x")
    sid = _seed(conn, jid)
    # First insert a voice clip so the subtitle agent has something to read.
    from infra.db.repositories import insert_voice_clip
    vc_id = insert_voice_clip(conn, sid, "piper", "v", 1.0, 1.0, "neutral",
                              2.0, str(tmp_path / "voice.wav"))
    fake_words = lambda audio: [
        __import__("plugins.captions.word_timing", fromlist=["WordTiming"]).WordTiming(
            "hello", 0.0, 0.5),
        __import__("plugins.captions.word_timing", fromlist=["WordTiming"]).WordTiming(
            "world", 0.5, 1.0),
    ]
    agent = make_subtitle_agent(conn, FakeStyler(), paths, fake_words)
    agent(JobContext(job_id=jid))
    sub = get_subtitle_by_job(conn, jid)
    assert sub["format"] == "ass+srt"
    assert sub["ass_path"].endswith("captions.ass")
