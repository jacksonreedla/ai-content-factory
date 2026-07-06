# agents/research_agent.py
import logging
import sqlite3

from core.models import JobContext, SourceQuery
from infra.db.repositories import insert_story

log = logging.getLogger(__name__)


def make_research_agent(source, conn: sqlite3.Connection,
                        query: SourceQuery):
    """Build a RESEARCH-stage agent bound to a content source + query.

    Discovers stories, picks the top-scoring one, persists it, and attaches
    it to the JobContext for downstream stages.
    """
    def agent(ctx: JobContext) -> JobContext:
        ctx.progress(10, "Discovering stories")
        stories = source.discover(query)
        if not stories:
            raise RuntimeError("no stories matched the research query")
        ctx.progress(60, f"Found {len(stories)} stories")
        # Pick the top-scoring story.
        top = max(stories, key=lambda s: s.score)
        top = source.fetch_full(top)
        ctx.progress(90, "Persisting story")
        insert_story(conn, ctx.job_id, top)
        ctx.story = top
        ctx.progress(100, "Story ready")
        return ctx
    return agent
