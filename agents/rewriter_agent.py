# agents/rewriter_agent.py
import logging
import sqlite3
from pathlib import Path

from core.enums import NarrationStyle
from core.models import JobContext, Script
from infra.db.repositories import get_story_by_job, insert_script

log = logging.getLogger(__name__)
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "config" / "prompts"
_WPM = 150  # words per minute for reading-time estimate


def _prompt_for(style: NarrationStyle) -> str:
    p = _PROMPT_DIR / f"rewriter_{style.value}.txt"
    if not p.exists():
        # Fall back to the storytelling template if a style file is missing.
        p = _PROMPT_DIR / "rewriter_storytelling.txt"
    return p.read_text(encoding="utf-8")


def make_rewriter_agent(llm, conn: sqlite3.Connection, style: NarrationStyle,
                        model_name: str = ""):
    """Build a REWRITE-stage agent that produces narration in the given style."""
    prompt_tmpl = _prompt_for(style)

    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        ctx.progress(20, "Rewriting for narration")
        prompt = prompt_tmpl.format(title=row["title"], body=row["body_text"],
                                    style=style.value)
        text = llm.complete(prompt).strip()
        words = text.split()
        script = Script(
            story_id=row["id"], style=style, text=text, model=model_name,
            word_count=len(words),
            reading_time=round(len(words) / _WPM * 60, 1),
        )
        insert_script(conn, row["id"], script)
        ctx.script = script
        ctx.progress(100, "Script ready")
        return ctx
    return agent
