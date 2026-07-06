# tests/test_models.py
from core.models import Story, StoryScore, SourceQuery, JobContext


def test_source_query_defaults():
    q = SourceQuery(subreddits=["nosleep"])
    assert q.subreddits == ["nosleep"]
    assert q.sort == "hot"
    assert q.limit == 25


def test_story_score_subscores():
    s = StoryScore(
        entertainment=8, suspense=7, emotion=6, shock=5,
        virality=9, quality=7, retention=8, overall=7.8, confidence=0.9,
    )
    assert s.overall == 7.8
    assert s.passes(7.0)
    assert not s.passes(8.0)


def test_job_context_progress_callback():
    ctx = JobContext(job_id=1)
    captured = []
    ctx.progress = lambda pct, msg="": captured.append((pct, msg))  # type: ignore
    ctx.progress(50, "halfway")  # type: ignore
    assert captured == [(50, "halfway")]


def test_job_context_default_progress_noop():
    ctx = JobContext(job_id=1)
    # Default progress should not raise.
    ctx.progress(10, "x")  # type: ignore
