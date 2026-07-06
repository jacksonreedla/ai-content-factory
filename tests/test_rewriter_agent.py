# tests/test_rewriter_agent.py
from datetime import datetime

from core.enums import NarrationStyle
from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import (
    create_job, get_script_by_story, insert_story,
)

from agents.rewriter_agent import make_rewriter_agent


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.last_prompt = ""
    def complete(self, prompt, system="", **kw):
        self.last_prompt = prompt
        return self.text


def test_rewriter_persists_script(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    sid = insert_story(conn, jid, Story(
        source="reddit", source_id="t3_x", subreddit="n", author="u",
        title="The Cat", body_text="I saw a cat.", score=1, num_comments=1,
        created_utc=datetime.utcnow().timestamp(), permalink=""))
    narration = "So there I was. A cat. Staring right at me."
    agent = make_rewriter_agent(FakeLLM(narration), conn,
                                style=NarrationStyle.STORYTELLING)
    ctx = JobContext(job_id=jid, story=_story())
    agent(ctx)
    row = get_script_by_story(conn, sid)
    assert row["style"] == "storytelling"
    assert "cat" in row["text"].lower()
    assert row["word_count"] == len(narration.split())
    assert row["reading_time"] > 0


def test_rewriter_uses_style_template(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    insert_story(conn, jid, _story())
    fake = FakeLLM("a dark and stormy night")
    agent = make_rewriter_agent(fake, conn, style=NarrationStyle.HORROR)
    agent(JobContext(job_id=jid, story=_story()))
    assert "horror" in fake.last_prompt


def _story():
    return Story(source="reddit", source_id="t3_x", subreddit="n", author="u",
                 title="The Cat", body_text="I saw a cat.", score=1,
                 num_comments=1, created_utc=datetime.utcnow().timestamp(),
                 permalink="")
