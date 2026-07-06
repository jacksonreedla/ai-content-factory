# agents/subtitle_agent.py
import logging
import sqlite3
from pathlib import Path

from core.models import JobContext
from infra.db.repositories import (
    get_story_by_job, get_voice_clip_by_job, insert_subtitle,
)
from infra.storage import job_dir

log = logging.getLogger(__name__)


def make_subtitle_agent(conn: sqlite3.Connection, styler, paths,
                        transcribe_fn, model_size: str = "base",
                        language: str | None = None):
    """Build a SUBTITLE-stage agent.

    `transcribe_fn(audio_path) -> list[WordTiming]` is injected so tests can
    pass a fake; production passes `infra.whisper.transcribe.transcribe_words`.
    """
    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        vc = get_voice_clip_by_job(conn, ctx.job_id)
        if vc is None:
            raise RuntimeError(f"no voice clip for job {ctx.job_id}")
        audio = Path(vc["audio_path"])
        ctx.progress(20, "Transcribing for word timings")
        words = transcribe_fn(audio)
        if not words:
            raise RuntimeError("transcription produced no words")
        ctx.progress(60, "Styling captions")
        jd = job_dir(paths, ctx.job_id)
        arts = styler.render(
            words,
            ass_path=str(jd / "captions.ass"),
            srt_path=str(jd / "captions.srt"),
        )
        ctx.progress(90, "Persisting subtitles")
        insert_subtitle(conn, vc["id"], "ass+srt",
                        getattr(styler, "style_name", "default"),
                        arts.ass_path, arts.srt_path)
        ctx.artifacts["ass_path"] = arts.ass_path
        ctx.artifacts["srt_path"] = arts.srt_path
        ctx.progress(100, "Subtitles ready")
        return ctx
    return agent
