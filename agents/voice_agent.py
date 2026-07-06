# agents/voice_agent.py
import logging
import sqlite3

from core.models import JobContext
from infra.db.repositories import get_script_by_story, insert_voice_clip
from infra.storage import job_dir
from plugins.voice.base import VoiceOpts

log = logging.getLogger(__name__)


def make_voice_agent(engine, conn: sqlite3.Connection, opts: VoiceOpts,
                     paths, model_name: str = ""):
    """Build a VOICE-stage agent that synthesizes the script via the engine."""
    def agent(ctx: JobContext) -> JobContext:
        from infra.db.repositories import get_story_by_job
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        script = get_script_by_story(conn, row["id"])
        if script is None:
            raise RuntimeError(f"no script for story {row['id']}")
        ctx.progress(20, "Synthesizing voice")
        out = job_dir(paths, ctx.job_id) / "voice.wav"
        clip = engine.synthesize(script["text"], opts, out)
        ctx.progress(90, "Persisting voice clip")
        insert_voice_clip(
            conn, script["id"], engine_name(model_name),
            opts.voice, opts.speed, opts.pitch, opts.emotion,
            clip.duration_sec, str(clip.path),
        )
        ctx.artifacts["voice_path"] = str(clip.path)
        ctx.artifacts["duration"] = clip.duration_sec
        ctx.progress(100, "Voice ready")
        return ctx
    return agent


def engine_name(label: str) -> str:
    return label or "piper"
