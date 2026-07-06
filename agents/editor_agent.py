# agents/editor_agent.py
import logging
import sqlite3
from pathlib import Path

from core.models import JobContext
from infra.db.repositories import (
    get_story_by_job, get_subtitle_by_job, get_voice_clip_by_job,
    insert_video, list_media,
)
from infra.storage import job_dir

log = logging.getLogger(__name__)


def make_editor_agent(editor, conn: sqlite3.Connection, paths,
                      default_format: str = "shorts_vertical_9_16",
                      background_category: str = ""):
    """Build an EDIT-stage agent that composes the final video."""
    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        vc = get_voice_clip_by_job(conn, ctx.job_id)
        if vc is None:
            raise RuntimeError(f"no voice clip for job {ctx.job_id}")
        sub = get_subtitle_by_job(conn, ctx.job_id)
        jd = job_dir(paths, ctx.job_id)
        out = jd / "video.mp4"
        # Pick a background from the library if available.
        bg = ctx.artifacts.get("background_path") or _pick_background(
            conn, background_category) or ""
        if not bg:
            raise RuntimeError(
                "no background video available in the library — add one in Library")
        from plugins.editor.ffmpeg_editor import EditSpec
        spec = EditSpec(
            voice_path=vc["audio_path"],
            background_path=bg,
            music_path=ctx.artifacts.get("music_path"),
            ass_path=sub["ass_path"] if sub else None,
            format=ctx.artifacts.get("format", default_format),
            out_path=str(out),
        )
        ctx.progress(40, "Composing video (this can take a while)")
        video = editor.compose(spec)
        ctx.progress(95, "Persisting video row")
        insert_video(
            conn, ctx.job_id, spec.format, _aspect_for(spec.format),
            video.width, video.height, video.duration_sec,
            None, None, str(video.path), "",
            video.size_bytes,
        )
        ctx.artifacts["video_path"] = str(video.path)
        ctx.progress(100, "Video rendered")
        return ctx
    return agent


def _pick_background(conn, category: str) -> str | None:
    rows = list_media(conn, kind="background", category=category)
    if not rows:
        rows = list_media(conn, kind="background")
    return rows[0]["path"] if rows else None


def _aspect_for(fmt: str) -> str:
    return {
        "shorts_vertical_9_16": "9:16", "tiktok_9_16": "9:16",
        "reels_9_16": "9:16", "youtube_16_9": "16:9",
    }.get(fmt, "9:16")
