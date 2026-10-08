"""Database + repository tests."""
from database.repositories import JobRepo, NarrationRepo, SettingsRepo, StoryRepo
from models.job import Job, JobStatus
from models.story import Story, StoryScores, StoryStatus


def make_story(source_id: str = "abc123") -> Story:
    return Story(
        id=None, source="reddit", source_id=source_id,
        title="Test story", text="word " * 200, subreddit="tifu",
        upvotes=1000, num_comments=50, created_utc=1000.0,
    )


def test_story_roundtrip(db):
    repo = StoryRepo(db)
    story_id = repo.upsert(make_story())
    loaded = repo.get(story_id)
    assert loaded is not None
    assert loaded.title == "Test story"
    assert loaded.status == StoryStatus.NEW
    assert loaded.word_count == 200


def test_story_upsert_is_idempotent(db):
    repo = StoryRepo(db)
    id1 = repo.upsert(make_story())
    id2 = repo.upsert(make_story())
    assert id1 == id2
    assert db.scalar("SELECT COUNT(*) FROM stories") == 1


def test_scores_persist(db):
    repo = StoryRepo(db)
    story_id = repo.upsert(make_story())
    scores = StoryScores(values={"entertainment": 8.0}, overall=7.5, reasoning="good")
    repo.set_scores(story_id, scores, StoryStatus.SCORED)
    loaded = repo.get(story_id)
    assert loaded.scores.overall == 7.5
    assert loaded.status == StoryStatus.SCORED


def test_job_lifecycle(db):
    repo = JobRepo(db)
    job_id = repo.add(Job(id=None, type="full_pipeline", payload={"a": 1}))
    repo.update(job_id, status=JobStatus.RUNNING, stage="score", progress=0.5)
    job = repo.get(job_id)
    assert job.status == JobStatus.RUNNING
    assert job.stage == "score"
    assert job.payload == {"a": 1}
    repo.update(job_id, status=JobStatus.COMPLETED, progress=1.0)
    assert repo.get(job_id).status == JobStatus.COMPLETED


def test_narrations(db):
    story_id = StoryRepo(db).upsert(make_story())
    narrations = NarrationRepo(db)
    narrations.add(story_id, "storytelling", 60, "Once upon a time...")
    latest = narrations.latest_for_story(story_id)
    assert latest["text"].startswith("Once upon")


def test_settings_kv(db):
    settings = SettingsRepo(db)
    settings.set("k", "v1")
    settings.set("k", "v2")
    assert settings.get("k") == "v2"
    assert settings.get("missing", "default") == "default"


def test_mark_for_rerender_makes_video_eligible_again():
    from database.db import Database
    from database.repositories import VideoRepo
    from tests.test_publisher import seed_rendered_video

    db = Database.in_memory()
    _story_id, video_id = seed_rendered_video(db, __import__("pathlib").Path("/tmp"))
    repo = VideoRepo(db)
    # freshly rendered -> not awaiting render
    assert all(v["id"] != video_id for v in repo.needing_render())
    repo.mark_for_rerender(video_id)
    # now it's picked up again by the editor stage
    assert any(v["id"] == video_id for v in repo.needing_render())
    assert repo.get(video_id)["audio_path"]        # audio kept
