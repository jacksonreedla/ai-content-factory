# agents/seo_agent.py
import json
import logging
import sqlite3

from core.models import JobContext
from infra.db.repositories import (
    get_script_by_story, get_seo_by_job, get_story_by_job,
    get_video_by_job, insert_seo,
)

log = logging.getLogger(__name__)


def make_seo_agent(generator, conn: sqlite3.Connection, llm=None,
                   model_name: str = ""):
    """Build an SEO-stage agent.

    `generator` is the SEOGenerator plugin. The script + llm are bundled into a
    small context object so the generator's `generate(video, script)` contract
    holds.
    """
    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        video = get_video_by_job(conn, ctx.job_id)
        if video is None:
            raise RuntimeError(f"no video for job {ctx.job_id}")
        script = get_script_by_story(conn, row["id"])
        ctx.progress(30, "Generating SEO metadata")
        # Bundle llm into a "video" wrapper so the generator can fetch it.
        class _VideoWithLLM:
            def __init__(self, v, l): self.video = v; self.llm = l
        bundle = _VideoWithLLM(video, llm)
        result = generator.generate(bundle, script)
        ctx.progress(80, "Persisting SEO")
        # If the user manually edited a placeholder row earlier, replace it.
        existing = get_seo_by_job(conn, ctx.job_id)
        if existing:
            conn.execute("DELETE FROM seo WHERE id=?", (existing["id"],))
            conn.commit()
        insert_seo(
            conn, video["id"], result.title, result.description,
            json.dumps(result.tags), json.dumps(result.hashtags),
            result.pinned_comment, result.community_post,
            result.ctr_score, result.seo_score, model_name,
        )
        ctx.progress(100, "SEO ready")
        return ctx
    return agent
