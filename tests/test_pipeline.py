"""End-to-end pipeline test with fake LLM and pre-seeded stories."""
import json

from app.pipeline import Pipeline
from database.repositories import NarrationRepo, SettingsRepo, StoryRepo
from models.story import Story, StoryStatus
from tests.fakes import FakeProvider

SCORE_JSON = json.dumps({
    "entertainment": 8, "emotional": 7, "shock": 6, "suspense": 7,
    "length_fit": 8, "narration_quality": 8, "click_potential": 9,
    "virality": 7, "originality": 6, "retention": 8,
    "overall": 8.2, "reasoning": "strong hook",
})
NARRATION = ("So there I was, minding my own business, when everything "
             "went sideways. " * 10)
METADATA_JSON = json.dumps({
    "title": "He Never Saw It Coming", "description": "A wild story.",
    "hashtags": ["#storytime"], "tags": ["reddit stories"],
    "pinned_comment": "What would you have done?",
})


def seed_story(db, source_id="s1") -> int:
    return StoryRepo(db).upsert(Story(
        id=None, source="reddit", source_id=source_id,
        title="I accidentally became a hero", text="word " * 300,
        subreddit="tifu", upvotes=2000, num_comments=100,
    ))


def make_pipeline(config, db, responses):
    config.set("scoring.auto_approve", True, persist=False)
    for task in ("score", "rewrite", "metadata", "engagement"):
        config.set(f"ai.tasks.{task}.provider", "fake", persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    pipeline = Pipeline(config, db)
    pipeline.llm.providers = {"fake": FakeProvider(responses)}
    return pipeline


def test_score_stage(config, db):
    story_id = seed_story(db)
    pipeline = make_pipeline(config, db, [SCORE_JSON])
    result = pipeline.run_stage("score")
    assert result.ok
    story = StoryRepo(db).get(story_id)
    assert story.status == StoryStatus.APPROVED
    assert story.scores.overall == 8.2


def test_low_score_rejected(config, db):
    story_id = seed_story(db)
    low = json.loads(SCORE_JSON)
    low["overall"] = 2.0
    pipeline = make_pipeline(config, db, [json.dumps(low)])
    pipeline.run_stage("score")
    assert StoryRepo(db).get(story_id).status == StoryStatus.REJECTED


def test_rewrite_stage(config, db):
    story_id = seed_story(db)
    pipeline = make_pipeline(config, db, [SCORE_JSON, NARRATION])
    pipeline.run_stage("score")
    result = pipeline.run_stage("rewrite")
    assert result.ok
    assert StoryRepo(db).get(story_id).status == StoryStatus.REWRITTEN
    narration = NarrationRepo(db).latest_for_story(story_id)
    assert "sideways" in narration["text"]


def test_stage_pipeline_score_rewrite_seo(config, db):
    story_id = seed_story(db)
    pipeline = make_pipeline(config, db,
                             [SCORE_JSON, NARRATION, "Was I wrong here",
                              METADATA_JSON])
    assert pipeline.run_stage("score").ok
    assert pipeline.run_stage("rewrite").ok
    assert pipeline.run_stage("seo").ok
    raw = SettingsRepo(db).get(f"metadata.story.{story_id}")
    assert raw is not None
    assert json.loads(raw)["title"] == "He Never Saw It Coming"


def test_stub_stages_skip(config, db):
    pipeline = make_pipeline(config, db, [])
    result = pipeline.run_stage("voice")
    assert result.ok
    assert result.stage_results["voice"].skipped


def test_run_all_chain_rewrite_voice_captions(config, db, monkeypatch, tmp_path):
    """Mirrors the Stories page 'All' button: rewrite -> voice -> captions."""
    import agents.voice_agent as voice_module
    import agents.caption_agent as caption_module
    from database.repositories import VideoRepo
    from tests.test_voice_and_caption_agents import FakeTTS, FakeTranscriber

    monkeypatch.setattr(voice_module, "build_engine", lambda cfg: FakeTTS())
    monkeypatch.setattr(voice_module, "AUDIO_DIR", tmp_path)
    monkeypatch.setattr(caption_module, "_make_transcriber",
                        lambda ctx: FakeTranscriber())
    monkeypatch.setattr(caption_module, "CAPTIONS_DIR", tmp_path)
    config.set("video.title_card.enabled", False, persist=False)
    config.set("voice.normalize", False, persist=False)
    config.set("voice.trim_silence", False, persist=False)

    story_id = seed_story(db)
    pipeline = make_pipeline(config, db, [SCORE_JSON, NARRATION])
    assert pipeline.run_stage("score").ok        # -> approved (auto_approve)

    # The three stages the "All" button chains, in order:
    assert pipeline.run_stage("rewrite").ok
    assert pipeline.run_stage("voice").ok
    assert pipeline.run_stage("captions").ok

    assert StoryRepo(db).get(story_id).status == StoryStatus.REWRITTEN
    video = VideoRepo(db).recent(1)[0]
    assert video["audio_path"].endswith(".wav")
    assert video["captions_path"].endswith(".ass")
