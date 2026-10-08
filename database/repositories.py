"""Typed repository classes - the only place raw SQL for each table lives."""
from __future__ import annotations

import json
import logging
from typing import Any

from database.db import Database
from models.job import Job, JobStatus
from models.story import Story, StoryScores, StoryStatus

log = logging.getLogger("acf.repo")


# --------------------------------------------------------------------- stories
class StoryRepo:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, story: Story) -> int:
        """Insert if new (by source+source_id); return story id."""
        existing = self.db.query_one(
            "SELECT id FROM stories WHERE source = ? AND source_id = ?",
            (story.source, story.source_id),
        )
        if existing:
            return int(existing["id"])
        cur = self.db.execute(
            """INSERT INTO stories (source, source_id, subreddit, title, author,
                   url, text, upvotes, num_comments, created_utc, nsfw, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (story.source, story.source_id, story.subreddit, story.title,
             story.author, story.url, story.text, story.upvotes,
             story.num_comments, story.created_utc, int(story.nsfw),
             story.status.value),
        )
        return int(cur.lastrowid)

    def _row_to_story(self, row: Any) -> Story:
        return Story(
            id=row["id"], source=row["source"], source_id=row["source_id"],
            subreddit=row["subreddit"], title=row["title"], author=row["author"],
            url=row["url"], text=row["text"], upvotes=row["upvotes"],
            num_comments=row["num_comments"], created_utc=row["created_utc"],
            nsfw=bool(row["nsfw"]), status=StoryStatus(row["status"]),
            scores=StoryScores.from_json(row["scores_json"]),
            rejected_reason=row["rejected_reason"],
        )

    def get(self, story_id: int) -> Story | None:
        row = self.db.query_one("SELECT * FROM stories WHERE id = ?", (story_id,))
        return self._row_to_story(row) if row else None

    def by_status(self, status: StoryStatus, limit: int = 200) -> list[Story]:
        rows = self.db.query(
            "SELECT * FROM stories WHERE status = ? ORDER BY overall_score DESC, id DESC LIMIT ?",
            (status.value, limit),
        )
        return [self._row_to_story(r) for r in rows]

    def recent(self, limit: int = 200) -> list[Story]:
        rows = self.db.query("SELECT * FROM stories ORDER BY id DESC LIMIT ?", (limit,))
        return [self._row_to_story(r) for r in rows]

    def set_status(self, story_id: int, status: StoryStatus, reason: str = "") -> None:
        self.db.execute(
            "UPDATE stories SET status = ?, rejected_reason = ? WHERE id = ?",
            (status.value, reason, story_id),
        )

    def set_scores(self, story_id: int, scores: StoryScores, status: StoryStatus) -> None:
        self.db.execute(
            "UPDATE stories SET scores_json = ?, overall_score = ?, status = ? WHERE id = ?",
            (scores.to_json(), scores.overall, status.value, story_id),
        )

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.query("SELECT status, COUNT(*) AS n FROM stories GROUP BY status")
        return {r["status"]: r["n"] for r in rows}

    def delete(self, story_id: int) -> list[str]:
        """Delete a story, its narrations and any generated videos.

        Returns the on-disk file paths that belonged to the story's videos so
        the caller can remove them from disk. Narrations cascade automatically;
        videos reference the story with ON DELETE SET NULL, so we delete them
        explicitly to also clean up their audio/caption/thumbnail/video files.
        """
        video_repo = VideoRepo(self.db)
        paths: list[str] = []
        for video in video_repo.videos_for_story(story_id):
            paths += video_repo.delete(int(video["id"]))
        self.db.execute("DELETE FROM stories WHERE id = ?", (story_id,))
        return paths


# ------------------------------------------------------------------ narrations
class NarrationRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, story_id: int, style: str, target_seconds: int, text: str,
            provider: str = "", model: str = "") -> int:
        cur = self.db.execute(
            """INSERT INTO narrations (story_id, style, target_seconds, text, provider, model)
               VALUES (?,?,?,?,?,?)""",
            (story_id, style, target_seconds, text, provider, model),
        )
        return int(cur.lastrowid)

    def latest_for_story(self, story_id: int) -> dict[str, Any] | None:
        row = self.db.query_one(
            "SELECT * FROM narrations WHERE story_id = ? ORDER BY id DESC LIMIT 1",
            (story_id,),
        )
        return dict(row) if row else None


# ------------------------------------------------------------------------ jobs
class JobRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, job: Job) -> int:
        cur = self.db.execute(
            """INSERT INTO jobs (type, status, priority, stage, progress, payload_json)
               VALUES (?,?,?,?,?,?)""",
            (job.type, job.status.value, job.priority, job.stage,
             job.progress, job.payload_json()),
        )
        return int(cur.lastrowid)

    def _row_to_job(self, row: Any) -> Job:
        return Job(
            id=row["id"], type=row["type"], status=JobStatus(row["status"]),
            priority=row["priority"], stage=row["stage"], progress=row["progress"],
            payload=Job.payload_from_json(row["payload_json"]), error=row["error"],
        )

    def get(self, job_id: int) -> Job | None:
        row = self.db.query_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
        return self._row_to_job(row) if row else None

    def recent(self, limit: int = 100) -> list[Job]:
        rows = self.db.query("SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,))
        return [self._row_to_job(r) for r in rows]

    def next_pending(self) -> Job | None:
        row = self.db.query_one(
            "SELECT * FROM jobs WHERE status = 'pending' ORDER BY priority, id LIMIT 1"
        )
        return self._row_to_job(row) if row else None

    def update(self, job_id: int, *, status: JobStatus | None = None,
               stage: str | None = None, progress: float | None = None,
               error: str | None = None) -> None:
        sets, params = [], []
        if status is not None:
            sets.append("status = ?")
            params.append(status.value)
            if status == JobStatus.RUNNING:
                sets.append("started_at = datetime('now')")
            if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                sets.append("finished_at = datetime('now')")
        if stage is not None:
            sets.append("stage = ?")
            params.append(stage)
        if progress is not None:
            sets.append("progress = ?")
            params.append(progress)
        if error is not None:
            sets.append("error = ?")
            params.append(error)
        if not sets:
            return
        params.append(job_id)
        self.db.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", params)


# ---------------------------------------------------------------------- videos
class VideoRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, story_id: int, narration_id: int, fmt: str, title: str = "") -> int:
        cur = self.db.execute(
            "INSERT INTO videos (story_id, narration_id, format, title) VALUES (?,?,?,?)",
            (story_id, narration_id, fmt, title),
        )
        return int(cur.lastrowid)

    def set_metadata(self, video_id: int, metadata: dict[str, Any]) -> None:
        self.db.execute("UPDATE videos SET metadata_json = ? WHERE id = ?",
                        (json.dumps(metadata, ensure_ascii=False), video_id))

    def set_audio(self, video_id: int, audio_path: str, duration_s: float) -> None:
        self.db.execute(
            "UPDATE videos SET audio_path = ?, duration_s = ? WHERE id = ?",
            (audio_path, duration_s, video_id))

    def set_captions(self, video_id: int, captions_path: str) -> None:
        self.db.execute("UPDATE videos SET captions_path = ? WHERE id = ?",
                        (captions_path, video_id))

    def story_has_audio(self, story_id: int) -> bool:
        return bool(self.db.scalar(
            "SELECT COUNT(*) FROM videos WHERE story_id = ? AND audio_path != ''",
            (story_id,)))

    def needing_captions(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM videos WHERE audio_path != '' AND captions_path = ''")
        return [dict(r) for r in rows]

    def get(self, video_id: int) -> dict[str, Any] | None:
        row = self.db.query_one("SELECT * FROM videos WHERE id = ?", (video_id,))
        return dict(row) if row else None

    def needing_render(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM videos WHERE audio_path != '' AND file_path = ''")
        return [dict(r) for r in rows]

    def mark_for_rerender(self, video_id: int) -> None:
        """Clear the rendered file so the edit stage rebuilds it with the
        current settings (background, music, effects, title card)."""
        self.db.execute("UPDATE videos SET file_path = '' WHERE id = ?",
                        (video_id,))

    def set_file(self, video_id: int, file_path: str,
                 duration_s: float | None = None) -> None:
        if duration_s is None:
            self.db.execute("UPDATE videos SET file_path = ?, status = 'rendered' "
                            "WHERE id = ?", (file_path, video_id))
        else:
            self.db.execute(
                "UPDATE videos SET file_path = ?, duration_s = ?, "
                "status = 'rendered' WHERE id = ?",
                (file_path, duration_s, video_id))

    def set_thumbnail(self, video_id: int, thumbnail_path: str) -> None:
        self.db.execute("UPDATE videos SET thumbnail_path = ? WHERE id = ?",
                        (thumbnail_path, video_id))

    def set_intro(self, video_id: int, intro_seconds: float) -> None:
        self.db.execute("UPDATE videos SET intro_seconds = ? WHERE id = ?",
                        (float(intro_seconds), video_id))

    def set_card(self, video_id: int, card_path: str) -> None:
        self.db.execute("UPDATE videos SET card_path = ? WHERE id = ?",
                        (card_path, video_id))

    def set_account(self, video_id: int, account: str) -> None:
        self.db.execute("UPDATE videos SET account = ? WHERE id = ?",
                        (account, video_id))

    def needing_thumbnail(self) -> list[dict[str, Any]]:
        rows = self.db.query(
            "SELECT * FROM videos WHERE file_path != '' AND thumbnail_path = ''")
        return [dict(r) for r in rows]

    def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT * FROM videos ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in rows]

    def count(self) -> int:
        return int(self.db.scalar("SELECT COUNT(*) FROM videos") or 0)

    def videos_for_story(self, story_id: int) -> list[dict[str, Any]]:
        rows = self.db.query("SELECT * FROM videos WHERE story_id = ?", (story_id,))
        return [dict(r) for r in rows]

    @staticmethod
    def file_paths(video: dict[str, Any]) -> list[str]:
        """All on-disk file paths tracked on a video row."""
        keys = ("file_path", "audio_path", "captions_path", "thumbnail_path",
                "card_path")
        return [video[k] for k in keys if video.get(k)]

    def delete(self, video_id: int) -> list[str]:
        """Delete a video row (uploads/analytics cascade) and return its file
        paths so the caller can remove them from disk."""
        video = self.get(video_id)
        if not video:
            return []
        paths = self.file_paths(video)
        self.db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        return paths


# --------------------------------------------------------------------- uploads
class UploadRepo:
    def __init__(self, db: Database):
        self.db = db

    def add(self, video_id: int, platform: str = "tiktok",
            visibility: str = "private", scheduled_at: str | None = None) -> int:
        cur = self.db.execute(
            """INSERT INTO uploads (video_id, platform, visibility, scheduled_at)
               VALUES (?,?,?,?)""",
            (video_id, platform, visibility, scheduled_at))
        return int(cur.lastrowid)

    def mark_uploaded(self, upload_id: int, remote_id: str) -> None:
        self.db.execute(
            """UPDATE uploads SET status = 'uploaded', remote_id = ?,
               uploaded_at = datetime('now'), error = '' WHERE id = ?""",
            (remote_id, upload_id))

    def mark_failed(self, upload_id: int, error: str) -> None:
        self.db.execute("UPDATE uploads SET status = 'failed', error = ? "
                        "WHERE id = ?", (error[:500], upload_id))

    def failed_for_video(self, video_id: int) -> int | None:
        row = self.db.query_one(
            "SELECT id FROM uploads WHERE video_id = ? AND status = 'failed' "
            "ORDER BY id DESC LIMIT 1", (video_id,))
        return int(row["id"]) if row else None

    def is_uploaded(self, video_id: int) -> bool:
        return bool(self.db.scalar(
            "SELECT COUNT(*) FROM uploads WHERE video_id = ? AND "
            "status = 'uploaded'", (video_id,)))

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self.db.query(
            """SELECT u.*, v.title AS video_title FROM uploads u
               LEFT JOIN videos v ON v.id = u.video_id
               ORDER BY u.id DESC LIMIT ?""", (limit,))
        return [dict(r) for r in rows]


# ------------------------------------------------------------------- api usage
class UsageRepo:
    def __init__(self, db: Database):
        self.db = db

    def record(self, provider: str, model: str, task: str,
               tokens_in: int, tokens_out: int, cost_usd: float = 0.0) -> None:
        self.db.execute(
            """INSERT INTO api_usage (provider, model, task, tokens_in, tokens_out, cost_usd)
               VALUES (?,?,?,?,?,?)""",
            (provider, model, task, tokens_in, tokens_out, cost_usd),
        )

    def totals_today(self) -> dict[str, Any]:
        row = self.db.query_one(
            """SELECT COUNT(*) AS calls,
                      COALESCE(SUM(tokens_in), 0) AS tokens_in,
                      COALESCE(SUM(tokens_out), 0) AS tokens_out,
                      COALESCE(SUM(cost_usd), 0) AS cost
               FROM api_usage WHERE date(created_at) = date('now')"""
        )
        return dict(row) if row else {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0}


# ------------------------------------------------------------------- analytics
class AnalyticsRepo:
    def __init__(self, db: Database):
        self.db = db

    def record(self, video_id: int, metric: str, value: float) -> None:
        self.db.execute(
            "INSERT INTO analytics (video_id, metric, value) VALUES (?,?,?)",
            (video_id, metric, value))

    def latest_all(self) -> dict[int, dict[str, float]]:
        """{video_id: {metric: latest value}}."""
        rows = self.db.query(
            "SELECT video_id, metric, value FROM analytics ORDER BY id")
        out: dict[int, dict[str, float]] = {}
        for row in rows:  # later rows overwrite -> latest snapshot wins
            out.setdefault(row["video_id"], {})[row["metric"]] = row["value"]
        return out

    def performance_rows(self) -> list[dict[str, Any]]:
        """One row per uploaded video with story/upload context for insights."""
        rows = self.db.query(
            """SELECT v.id AS video_id, v.title, v.format, v.duration_s,
                      s.subreddit,
                      n.style,
                      u.uploaded_at, u.remote_id
               FROM videos v
               LEFT JOIN stories s ON s.id = v.story_id
               LEFT JOIN narrations n ON n.id = v.narration_id
               JOIN uploads u ON u.video_id = v.id AND u.status = 'uploaded'
               ORDER BY v.id""")
        latest = self.latest_all()
        out = []
        for row in rows:
            d = dict(row)
            metrics = latest.get(row["video_id"], {})
            d["views"] = metrics.get("views", 0.0)
            d["likes"] = metrics.get("likes", 0.0)
            d["comments"] = metrics.get("comments", 0.0)
            out.append(d)
        return out


# -------------------------------------------------------------------- settings
class SettingsRepo:
    """Small key/value store for runtime state (distinct from config.json)."""

    def __init__(self, db: Database):
        self.db = db

    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.db.query_one("SELECT value FROM app_settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.db.execute(
            """INSERT INTO app_settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (key, value),
        )
