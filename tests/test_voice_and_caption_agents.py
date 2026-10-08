"""Voice + Caption agent tests using fake engines (no TTS/whisper installs)."""
from __future__ import annotations

import wave
from pathlib import Path

import agents.caption_agent as caption_module
import agents.voice_agent as voice_module
from app.pipeline import Pipeline
from database.repositories import NarrationRepo, StoryRepo, VideoRepo
from models.story import Story, StoryStatus
from voices.base import TTSEngine, TTSRequest


def write_silent_wav(path: Path, seconds: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))


class FakeTTS(TTSEngine):
    name = "fake_tts"

    def is_available(self) -> bool:
        return True

    def list_voices(self) -> list[str]:
        return ["fake"]

    def synthesize(self, request: TTSRequest) -> Path:
        write_silent_wav(request.output_path, 1.0)
        return request.output_path


class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> list[dict]:
        return [{"word": "Hello", "start": 0.0, "end": 0.4},
                {"word": "world.", "start": 0.4, "end": 0.9}]


def _base_flow_config(config):
    """Deterministic base path: no title card, no ffmpeg post-processing."""
    config.set("video.title_card.enabled", False, persist=False)
    config.set("voice.normalize", False, persist=False)
    config.set("voice.trim_silence", False, persist=False)


def seed_rewritten_story(db) -> int:
    story_id = StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id="v1", title="Voice test",
        text="word " * 100, subreddit="tifu", upvotes=1000, num_comments=50))
    NarrationRepo(db).add(story_id, "storytelling", 60, "Hello world.")
    StoryRepo(db).set_status(story_id, StoryStatus.REWRITTEN)
    return story_id


def test_voice_agent_creates_video_with_audio(config, db, monkeypatch, tmp_path):
    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    _base_flow_config(config)
    story_id = seed_rewritten_story(db)

    pipeline = Pipeline(config, db)
    result = pipeline.run_stage("voice")
    assert result.ok

    videos = VideoRepo(db).recent(5)
    assert len(videos) == 1
    assert videos[0]["story_id"] == story_id
    assert videos[0]["audio_path"].endswith(".wav")
    assert videos[0]["duration_s"] > 0.5
    assert videos[0]["intro_seconds"] == 0        # no title card
    assert Path(videos[0]["audio_path"]).exists()


def test_voice_agent_skips_when_nothing_to_do(config, db):
    pipeline = Pipeline(config, db)
    result = pipeline.run_stage("voice")
    assert result.ok
    assert result.stage_results["voice"].skipped


def test_caption_agent_writes_ass(config, db, monkeypatch, tmp_path):
    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    monkeypatch.setattr(caption_module, "_make_transcriber",
                        lambda ctx: FakeTranscriber())
    monkeypatch.setattr(caption_module, "CAPTIONS_DIR", tmp_path)
    _base_flow_config(config)
    seed_rewritten_story(db)

    pipeline = Pipeline(config, db)
    assert pipeline.run_stage("voice").ok
    result = pipeline.run_stage("captions")
    assert result.ok

    video = VideoRepo(db).recent(1)[0]
    captions = Path(video["captions_path"])
    assert captions.suffix == ".ass"
    content = captions.read_text(encoding="utf-8")
    assert "HELLO" in content and "WORLD." in content


def test_caption_agent_sentence_mode(config, db, monkeypatch, tmp_path):
    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    monkeypatch.setattr(caption_module, "_make_transcriber",
                        lambda ctx: FakeTranscriber())
    monkeypatch.setattr(caption_module, "CAPTIONS_DIR", tmp_path)
    _base_flow_config(config)
    config.set("captions.mode", "sentence", persist=False)
    seed_rewritten_story(db)

    pipeline = Pipeline(config, db)
    assert pipeline.run_stage("voice").ok
    assert pipeline.run_stage("captions").ok
    video = VideoRepo(db).recent(1)[0]
    assert video["captions_path"].endswith(".srt")


class TitleIntroTranscriber:
    """Returns words that straddle a title intro at ~1.4s."""
    def transcribe(self, audio_path: Path) -> list[dict]:
        return [{"word": "TitleWord", "start": 0.5, "end": 1.0},   # in intro
                {"word": "Body", "start": 1.6, "end": 2.0},         # after intro
                {"word": "text.", "start": 2.0, "end": 2.5}]


def test_captions_skip_title_words(config, db, monkeypatch, tmp_path):
    """With the title card on, words spoken during the title are dropped."""
    monkeypatch.setattr(caption_module, "_make_transcriber",
                        lambda ctx: TitleIntroTranscriber())
    monkeypatch.setattr(caption_module, "CAPTIONS_DIR", tmp_path)

    # Build a video that already has audio + a 1.4s title intro recorded.
    story_id = seed_rewritten_story(db)
    audio = tmp_path / "story.wav"
    write_silent_wav(audio, 3.0)
    repo = VideoRepo(db)
    vid = repo.add(story_id, 1, "shorts", title="Voice test")
    repo.set_audio(vid, str(audio), 3.0)
    repo.set_intro(vid, 1.4)

    pipeline = Pipeline(config, db)
    assert pipeline.run_stage("captions").ok

    content = Path(repo.get(vid)["captions_path"]).read_text(encoding="utf-8")
    assert "TITLEWORD" not in content     # spoken during the card -> dropped
    assert "BODY" in content and "TEXT." in content


def test_voice_agent_rotates_accounts_round_robin(config, db, monkeypatch, tmp_path):
    """Produced videos are spread A->B->C across accounts; index persists."""
    from database.repositories import SettingsRepo

    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    _base_flow_config(config)
    config.set("accounts", [{"name": "acc_a"}, {"name": "acc_b"},
                            {"name": "acc_c"}], persist=False)
    config.set("publish.rotate_accounts", True, persist=False)

    for k in range(4):
        sid = StoryRepo(db).upsert(Story(
            id=None, source="reddit", source_id=f"r{k}", title=f"Story {k}",
            text="word " * 100, subreddit="tifu", upvotes=1000, num_comments=50))
        NarrationRepo(db).add(sid, "storytelling", 60, "Hello world.")
        StoryRepo(db).set_status(sid, StoryStatus.REWRITTEN)

    assert Pipeline(config, db).run_stage("voice").ok

    videos = sorted(VideoRepo(db).recent(10), key=lambda v: v["id"])
    assert [v["account"] for v in videos] == ["acc_a", "acc_b", "acc_c", "acc_a"]
    # Counter persisted so the next run keeps cycling instead of restarting.
    assert SettingsRepo(db).get("account_rotation_index") == "4"


def test_voice_agent_no_rotation_when_disabled(config, db, monkeypatch, tmp_path):
    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    _base_flow_config(config)
    config.set("accounts", [{"name": "acc_a"}, {"name": "acc_b"}], persist=False)
    config.set("publish.rotate_accounts", False, persist=False)
    seed_rewritten_story(db)

    assert Pipeline(config, db).run_stage("voice").ok
    # No account stamped -> editor falls back to the default at render time.
    assert (VideoRepo(db).recent(1)[0]["account"] or "") == ""
