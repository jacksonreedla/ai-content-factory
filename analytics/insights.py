"""Performance insights - pure functions over local analytics rows.

Input rows (from AnalyticsRepo.performance_rows):
    {video_id, title, format, duration_s, subreddit, style,
     uploaded_at, views, likes, comments}
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

MIN_GROUP = 2  # need at least this many videos before trusting a group


def duration_bucket(seconds: float) -> str:
    if seconds < 45:
        return "under 45s"
    if seconds < 90:
        return "45-90s"
    if seconds < 240:
        return "90s-4min"
    return "over 4min"


def upload_hour(uploaded_at: str | None) -> int | None:
    """'2026-07-04 19:03:11' -> 19."""
    if not uploaded_at:
        return None
    try:
        return int(uploaded_at[11:13])
    except (ValueError, IndexError):
        return None


def _best_group(rows: list[dict], key_fn) -> tuple[Any, float, int] | None:
    """Highest average-views group with at least MIN_GROUP members."""
    groups: dict[Any, list[float]] = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key is not None and key != "":
            groups[key].append(float(row.get("views", 0)))
    qualified = {k: v for k, v in groups.items() if len(v) >= MIN_GROUP}
    if not qualified:
        return None
    best_key = max(qualified, key=lambda k: sum(qualified[k]) / len(qualified[k]))
    values = qualified[best_key]
    return best_key, sum(values) / len(values), len(values)


def title_question_lift(rows: list[dict]) -> float | None:
    """Avg views of '?' titles / avg views of others (None if not enough data)."""
    questions = [float(r["views"]) for r in rows if "?" in (r.get("title") or "")]
    others = [float(r["views"]) for r in rows if "?" not in (r.get("title") or "")]
    if len(questions) < MIN_GROUP or len(others) < MIN_GROUP:
        return None
    other_avg = sum(others) / len(others)
    if other_avg == 0:
        return None
    return (sum(questions) / len(questions)) / other_avg


def compute_insights(rows: list[dict]) -> dict:
    """Returns {'best': {...}, 'recommendations': [str, ...]}."""
    recommendations: list[str] = []
    best: dict[str, Any] = {}

    if len(rows) < MIN_GROUP:
        return {"best": best, "recommendations": [
            f"Not enough uploaded videos yet ({len(rows)}). Insights unlock "
            f"after a few uploads have collected stats."]}

    checks = [
        ("subreddit", lambda r: r.get("subreddit"),
         "Source r/{key} performs best (avg {avg:.0f} views over {n} videos) "
         "- fetch more from it on the Research page."),
        ("style", lambda r: r.get("style"),
         "The '{key}' narration style performs best (avg {avg:.0f} views "
         "over {n} videos)."),
        ("length", lambda r: duration_bucket(float(r.get("duration_s") or 0)),
         "Videos {key} get the most views (avg {avg:.0f} over {n} videos) "
         "- adjust target length in Settings."),
        ("hour", lambda r: upload_hour(r.get("uploaded_at")),
         "Uploads around {key}:00 perform best (avg {avg:.0f} views over "
         "{n} videos) - align your publish slots."),
    ]
    for name, key_fn, template in checks:
        result = _best_group(rows, key_fn)
        if result:
            key, avg, n = result
            best[name] = {"key": key, "avg_views": round(avg, 1), "count": n}
            recommendations.append(template.format(key=key, avg=avg, n=n))

    lift = title_question_lift(rows)
    if lift is not None:
        best["question_title_lift"] = round(lift, 2)
        if lift > 1.15:
            recommendations.append(
                f"Question-style titles get {lift:.1f}x the views - "
                f"lean into them.")
        elif lift < 0.85:
            recommendations.append(
                f"Statement titles outperform questions ({1 / lift:.1f}x) - "
                f"prefer bold statements.")

    if not recommendations:
        recommendations.append(
            "Groups are too small for confident insights yet - keep "
            "uploading, recommendations sharpen with data.")
    return {"best": best, "recommendations": recommendations}


def estimate_revenue(rows: list[dict], rpm_shorts: float,
                     rpm_longform: float) -> float:
    """Sum of views/1000 * RPM by format."""
    total = 0.0
    for row in rows:
        rpm = rpm_shorts if row.get("format") == "shorts" else rpm_longform
        total += float(row.get("views", 0)) / 1000.0 * rpm
    return round(total, 2)
