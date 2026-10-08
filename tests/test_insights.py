"""Insights engine tests (pure functions)."""
from analytics.insights import (compute_insights, duration_bucket,
                                estimate_revenue, title_question_lift,
                                upload_hour)


def make_row(**overrides) -> dict:
    row = {"video_id": 1, "title": "A story", "format": "shorts",
           "duration_s": 60.0, "subreddit": "tifu", "style": "storytelling",
           "uploaded_at": "2026-07-04 19:03:11", "views": 100.0,
           "likes": 5.0, "comments": 1.0}
    row.update(overrides)
    return row


def test_duration_bucket():
    assert duration_bucket(30) == "under 45s"
    assert duration_bucket(60) == "45-90s"
    assert duration_bucket(120) == "90s-4min"
    assert duration_bucket(400) == "over 4min"


def test_upload_hour():
    assert upload_hour("2026-07-04 19:03:11") == 19
    assert upload_hour(None) is None
    assert upload_hour("bad") is None


def test_insights_need_data():
    result = compute_insights([make_row()])
    assert "Not enough" in result["recommendations"][0]
    assert result["best"] == {}


def test_best_subreddit_found():
    rows = [
        make_row(video_id=1, subreddit="tifu", views=100),
        make_row(video_id=2, subreddit="tifu", views=200),
        make_row(video_id=3, subreddit="AITAH", views=1000),
        make_row(video_id=4, subreddit="AITAH", views=2000),
    ]
    result = compute_insights(rows)
    assert result["best"]["subreddit"]["key"] == "AITAH"
    assert result["best"]["subreddit"]["avg_views"] == 1500
    assert any("AITAH" in r for r in result["recommendations"])


def test_small_groups_ignored():
    rows = [
        make_row(video_id=1, subreddit="tifu", views=100),
        make_row(video_id=2, subreddit="tifu", views=200),
        make_row(video_id=3, subreddit="nosleep", views=99999),  # only 1 video
    ]
    result = compute_insights(rows)
    assert result["best"]["subreddit"]["key"] == "tifu"


def test_question_title_lift():
    rows = ([make_row(title="Why did this happen?", views=300)] * 2 +
            [make_row(title="This happened.", views=100)] * 2)
    lift = title_question_lift(rows)
    assert lift == 3.0
    result = compute_insights(rows)
    assert result["best"]["question_title_lift"] == 3.0
    assert any("Question" in r for r in result["recommendations"])


def test_question_lift_insufficient_data():
    rows = [make_row(title="No questions here", views=10)] * 4
    assert title_question_lift(rows) is None


def test_estimate_revenue():
    rows = [make_row(format="shorts", views=10000),
            make_row(format="landscape", views=1000)]
    total = estimate_revenue(rows, rpm_shorts=0.15, rpm_longform=3.0)
    assert total == 1.5 + 3.0
