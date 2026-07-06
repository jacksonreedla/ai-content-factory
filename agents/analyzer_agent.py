# agents/analyzer_agent.py
import json
import logging
import sqlite3
from pathlib import Path

from core.models import JobContext, StoryScore
from infra.db.repositories import get_story_by_job, insert_score

log = logging.getLogger(__name__)
_PROMPT = Path(__file__).resolve().parent.parent / "config" / "prompts" / "analyzer.txt"
_SCHEMA = Path(__file__).resolve().parent.parent / "config" / "scoring_schema.json"


def make_analyzer_agent(llm, conn: sqlite3.Connection, min_overall: float,
                        model_name: str = ""):
    """Build an ANALYZE-stage agent that scores a story via the LLM.

    Raises RuntimeError if the story's overall score falls below `min_overall`,
    which the runner records as a job failure (rejected story).
    """
    prompt_tmpl = _PROMPT.read_text(encoding="utf-8")
    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))

    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        ctx.progress(20, "Scoring story")
        prompt = prompt_tmpl.format(title=row["title"], body=row["body_text"])
        data = llm.json_complete(prompt, schema)
        ctx.progress(70, "Validating score")
        score = StoryScore(
            entertainment=float(data["entertainment"]),
            suspense=float(data["suspense"]),
            emotion=float(data["emotion"]),
            shock=float(data["shock"]),
            virality=float(data["virality"]),
            quality=float(data["quality"]),
            retention=float(data["retention"]),
            overall=float(data["overall"]),
            confidence=float(data["confidence"]),
            model=model_name,
        )
        if not score.passes(min_overall):
            raise RuntimeError(
                f"story score {score.overall} below threshold {min_overall}")
        insert_score(conn, row["id"], score)
        ctx.progress(100, "Scored")
        return ctx
    return agent
