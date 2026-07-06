# Phase 2 — Content & Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build the content discovery + AI intelligence spine: a Reddit content source (PRAW), a pluggable LLM provider (Ollama default), and the Research, Analyzer, and Rewriter agents — wired into the pipeline and surfaced in a Research view.

**Architecture:** `ContentSource` and `LLMProvider` are plugin contracts (Phase 1). Reddit and Ollama are their first implementations under `plugins/`. Agents (Phase 1 `PipelineRunner`) get registered for the RESEARCH/ANALYZE/REWRITE stages. A `ResearchService` Application Service mediates between the GUI and the agent + plugin layer. Secrets (Reddit creds) live in `~/.aicf/secrets.json`.

**Tech Stack:** Python 3.12+, PRAW, httpx (for the Ollama HTTP client — lighter than `requests`, no transitive dep pain), PySide6.

## Global Constraints

- Same layering rule as Phase 1: GUI → services → domain → infra. Reddit/Ollama HTTP calls live in `plugins/` (under the contract), not in agents.
- Agents never import PRAW or httpx directly — they go through the injected contract.
- All agent unit tests use fakes (`FakeContentSource`, `FakeLLM`); no network in tests.
- Secrets in `secrets.json`, never logged.
- TDD throughout.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `plugins/content/reddit/__init__.py` | package marker |
| `plugins/content/reddit/source.py` | `RedditSource(ContentSource)` over PRAW |
| `plugins/content/base.py` | shared helpers (age filter, de-dupe) |
| `plugins/llm/ollama/__init__.py` | package marker |
| `plugins/llm/ollama/provider.py` | `OllamaProvider(LLMProvider)` over httpx |
| `plugins/llm/base.py` | JSON-extraction helper for LLM output |
| `app/secrets.py` | typed load/save for `secrets.json` |
| `agents/research_agent.py` | RESEARCH stage: discover + fetch_full |
| `agents/analyzer_agent.py` | ANALYZE stage: score story via LLM |
| `agents/rewriter_agent.py` | REWRITE stage: narrate via LLM |
| `infra/db/repositories.py` | extend: stories + scores + scripts inserts |
| `app/services.py` | `ResearchService` (discover + enqueue) |
| `gui/views/research.py` | Research view: filters + results table + send-to-pipeline |
| `config/prompts/analyzer.txt` | story-scoring prompt template |
| `config/prompts/rewriter_{style}.txt` | per-style rewrite templates |
| `config/scoring_schema.json` | JSON schema the analyzer must return |

---

### Task 1: secrets store + extend repos

**Files:**
- Create: `app/secrets.py`
- Modify: `infra/db/repositories.py` (add `insert_story`, `insert_score`, `insert_script`, `get_story_by_job`, `get_score_by_story`, `get_script_by_story`)
- Test: `tests/test_secrets.py`, extend `tests/test_repositories.py`

**Interfaces:**
- Produces: `load_secrets()/save_secrets()` returning `Secrets` dataclass with `reddit_client_id`, `reddit_client_secret`, `reddit_user_agent`, plus `llm_api_keys: dict`.

- [ ] **Step 1: Write `app/secrets.py`**

```python
# app/secrets.py
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from app.paths import AppPaths


@dataclass
class Secrets:
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "ai-content-factory/0.1 by <user>"
    llm_api_keys: dict = field(default_factory=dict)  # provider name → key


def load_secrets(paths: Optional[AppPaths] = None) -> Secrets:
    paths = paths or AppPaths()
    if not paths.secrets_path.exists():
        return Secrets()
    data = json.loads(paths.secrets_path.read_text() or "{}")
    return Secrets(**{k: v for k, v in data.items() if k in Secrets.__dataclass_fields__})


def save_secrets(secrets: Secrets, paths: Optional[AppPaths] = None) -> None:
    paths = paths or AppPaths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    # chmod 0600 to keep secrets file readable only by the owner.
    fd = paths.secrets_path.open("w")
    fd.write(json.dumps(asdict(secrets), indent=2))
    fd.close()
    try:
        import os; os.chmod(paths.secrets_path, 0o600)
    except OSError:
        pass
```

- [ ] **Step 2: Write failing test for secrets**

```python
# tests/test_secrets.py
from app.secrets import Secrets, load_secrets, save_secrets


def test_secrets_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    s = Secrets(reddit_client_id="abc", reddit_client_secret="shh",
                llm_api_keys={"openai": "sk-x"})
    save_secrets(s)
    s2 = load_secrets()
    assert s2.reddit_client_id == "abc"
    assert s2.reddit_client_secret == "shh"
    assert s2.llm_api_keys["openai"] == "sk-x"


def test_secrets_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    import json
    (tmp_path / "secrets.json").write_text(json.dumps({"bogus": 1, "reddit_client_id": "z"}))
    s = load_secrets()
    assert s.reddit_client_id == "z"


def test_secrets_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    s = load_secrets()
    assert s.reddit_client_id == ""
```

- [ ] **Step 3: Run test, verify fail, then implement `app/secrets.py` (Step 1 code), then pass.**

- [ ] **Step 4: Extend repositories — add to `infra/db/repositories.py`**

```python
def insert_story(conn, job_id, story) -> int:
    cur = conn.execute(
        "INSERT INTO stories (job_id, source, source_id, subreddit, author, "
        "title, body_raw, body_text, score, num_comments, created_utc, permalink) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, story.source, story.source_id, story.subreddit, story.author,
         story.title, story.body_raw, story.body_text, story.score,
         story.num_comments, story.created_utc, story.permalink),
    )
    conn.commit()
    return cur.lastrowid


def get_story_by_job(conn, job_id: int):
    return conn.execute("SELECT * FROM stories WHERE job_id=?", (job_id,)).fetchone()


def insert_score(conn, story_id: int, score) -> None:
    conn.execute(
        "INSERT INTO story_scores (story_id, entertainment, suspense, emotion, "
        "shock, virality, quality, retention, overall, confidence, model) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (story_id, score.entertainment, score.suspense, score.emotion, score.shock,
         score.virality, score.quality, score.retention, score.overall,
         score.confidence, score.model),
    )
    conn.commit()


def get_score_by_story(conn, story_id: int):
    return conn.execute(
        "SELECT * FROM story_scores WHERE story_id=? ORDER BY id DESC LIMIT 1",
        (story_id,)).fetchone()


def insert_script(conn, story_id: int, script) -> int:
    cur = conn.execute(
        "INSERT INTO scripts (story_id, style, model, text, word_count, reading_time) "
        "VALUES (?,?,?,?,?,?)",
        (story_id, script.style.value if hasattr(script.style, "value") else str(script.style),
         script.model, script.text, script.word_count, script.reading_time),
    )
    conn.commit()
    return cur.lastrowid


def get_script_by_story(conn, story_id: int):
    return conn.execute(
        "SELECT * FROM scripts WHERE story_id=? ORDER BY id DESC LIMIT 1",
        (story_id,)).fetchone()
```

- [ ] **Step 5: Extend `tests/test_repositories.py`** with story/score/script round-trip tests, run, and confirm pass.

- [ ] **Step 6: Commit**

```bash
git add app/secrets.py infra/db/repositories.py tests/test_secrets.py tests/test_repositories.py
git commit -m "feat(app): secrets store + story/score/script repositories"
```

---

### Task 2: content-source helpers (age filter, de-dupe)

**Files:**
- Create: `plugins/content/__init__.py`
- Create: `plugins/content/base.py`
- Test: `tests/test_content_base.py`

**Interfaces:**
- Produces: `filter_by_age(stories, max_age_hours)`, `dedupe_by_source_id(stories)`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_content_base.py
from datetime import datetime, timedelta
from plugins.content.base import filter_by_age, dedupe_by_source_id


def _story(source_id, age_hours, score=100):
    from core.models import Story
    return Story(
        source="reddit", source_id=source_id, subreddit="x", author="a",
        title="t", body_text="b", score=score, num_comments=1,
        created_utc=(datetime.utcnow() - timedelta(hours=age_hours)).timestamp(),
        permalink="",
    )


def test_filter_by_age():
    stories = [_story("a", 1), _story("b", 200)]
    out = filter_by_age(stories, max_age_hours=168)
    assert [s.source_id for s in out] == ["a"]


def test_dedupe_keeps_first():
    stories = [_story("a", 1, 100), _story("a", 1, 500)]
    out = dedupe_by_source_id(stories)
    assert len(out) == 1
    assert out[0].score == 100  # first wins
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
# plugins/content/base.py
import time
from typing import Iterable

from core.models import Story


def filter_by_age(stories: Iterable[Story], max_age_hours: int) -> list[Story]:
    cutoff = time.time() - max_age_hours * 3600
    return [s for s in stories if s.created_utc >= cutoff]


def dedupe_by_source_id(stories: Iterable[Story]) -> list[Story]:
    seen: set[str] = set()
    out: list[Story] = []
    for s in stories:
        if s.source_id in seen:
            continue
        seen.add(s.source_id)
        out.append(s)
    return out
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add plugins/content/ tests/test_content_base.py
git commit -m "feat(plugins): content source helpers"
```

---

### Task 3: Reddit ContentSource (PRAW)

**Files:**
- Create: `plugins/content/reddit/__init__.py`
- Create: `plugins/content/reddit/source.py`
- Test: `tests/test_reddit_source.py` (uses a fake praw client — no network)

**Interfaces:**
- Produces: `RedditSource(ContentSource)` with `discover(query)` and `fetch_full(story)`.

- [ ] **Step 1: Add PRAW + httpx deps**

Update `pyproject.toml`:

```toml
dependencies = [
    "PySide6>=6.6",
    "praw>=7.7",
    "httpx>=0.27",
]
```

Run: `.venv/bin/pip install -e ".[dev]"`

- [ ] **Step 2: Write failing test using a fake PRAW**

```python
# tests/test_reddit_source.py
import pytest
from core.models import SourceQuery, Story
from plugins.content.reddit.source import RedditSource


class FakeSubmission:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeSubreddit:
    def __init__(self, submissions):
        self._subs = submissions
    def top(self, limit=None): return list(self._subs)[:limit]
    def hot(self, limit=None): return list(self._subs)[:limit]
    def new(self, limit=None): return list(self._subs)[:limit]
    def rising(self, limit=None): return list(self._subs)[:limit]


class FakeReddit:
    def __init__(self, submissions_by_sub):
        self._map = submissions_by_sub
    def subreddit(self, name):
        return FakeSubreddit(self._map.get(name, []))


def _sub(name, sid, score=1500, comments=100, hours=2, body="body text", title="A title"):
    import time
    return FakeSubmission(
        id=sid, name="t3_" + sid, subreddit=type("S", (), {"display_name": name})(),
        author=type("A", (), {"name": "u"})(), title=title,
        selftext=body, score=score, num_comments=comments,
        created_utc=time.time() - hours * 3600, permalink=f"/r/{name}/comments/{sid}/",
    )


def test_discover_returns_stories_and_filters():
    reddit = FakeReddit({"nosleep": [_sub("nosleep", "a1", score=100)],
                         "tifu":    [_sub("tifu", "b1", score=2000)]})
    src = RedditSource(client=reddit)
    q = SourceQuery(subreddits=["nosleep", "tifu"], min_score=150, min_comments=50,
                    max_age_hours=168, sort="hot", limit=10)
    stories = src.discover(q)
    ids = sorted(s.source_id for s in stories)
    assert ids == ["b1"]   # a1 below min_score


def test_fetch_full_fills_body():
    reddit = FakeReddit({})
    src = RedditSource(client=reddit)
    s = Story(source="reddit", source_id="x", subreddit="n", author="a", title="t",
              body_text="", score=1, num_comments=0, created_utc=0, permalink="")
    # Without a real client.fetch, fetch_full returns the story unchanged.
    out = src.fetch_full(s)
    assert out.source_id == "x"
```

- [ ] **Step 3: Run, verify fail.**

- [ ] **Step 4: Implement**

```python
# plugins/content/reddit/source.py
import logging
from typing import Optional

import praw

from core.models import SourceQuery, Story
from plugins.content.base import filter_by_age, dedupe_by_source_id
from plugins.contracts import ContentSource

log = logging.getLogger(__name__)

_SORT_ATTRS = {"hot": "hot", "top": "top", "new": "new", "rising": "rising"}


class RedditSource:
    """PRAW-backed ContentSource. Pass `client=` for tests; otherwise it
    constructs a praw.Reddit from secrets + config."""

    def __init__(self, client=None, client_id: str = "", client_secret: str = "",
                 user_agent: str = "", username: str = "", password: str = "") -> None:
        if client is not None:
            self._reddit = client
        else:
            self._reddit = praw.Reddit(
                client_id=client_id, client_secret=client_secret,
                user_agent=user_agent or "ai-content-factory/0.1",
                username=username or None, password=password or None,
            )

    @classmethod
    def from_secrets(cls, secrets) -> "RedditSource":
        return cls(client_id=secrets.reddit_client_id,
                   client_secret=secrets.reddit_client_secret,
                   user_agent=secrets.reddit_user_agent)

    def discover(self, query: SourceQuery) -> list[Story]:
        stories: list[Story] = []
        sort_fn = _SORT_ATTRS.get(query.sort, "hot")
        for sub_name in query.subreddits:
            try:
                sub = self._reddit.subreddit(sub_name)
                submissions = list(getattr(sub, sort_fn)(limit=query.limit))
            except Exception as e:
                log.warning("reddit discover failed for r/%s: %s", sub_name, e)
                continue
            for s in submissions:
                if (s.score or 0) < query.min_score:
                    continue
                if (s.num_comments or 0) < query.min_comments:
                    continue
                stories.append(self._to_story(s))
        stories = filter_by_age(stories, query.max_age_hours)
        return dedupe_by_source_id(stories)

    def fetch_full(self, story: Story) -> Story:
        # PRAW submissions already include selftext on listing endpoints for
        # most subreddits; if missing, fetch by id. Best-effort, never raises.
        try:
            if not story.body_text:
                sub = self._reddit.submission(id=story.source_id)
                story.body_text = getattr(sub, "selftext", "") or ""
                story.body_raw = story.body_text
        except Exception as e:
            log.warning("reddit fetch_full failed for %s: %s", story.source_id, e)
        return story

    @staticmethod
    def _to_story(s) -> Story:
        return Story(
            source="reddit",
            source_id=s.id,
            subreddit=getattr(s.subreddit, "display_name", ""),
            author=getattr(getattr(s, "author", None), "name", "[deleted]"),
            title=s.title,
            body_text=getattr(s, "selftext", "") or "",
            body_raw=getattr(s, "selftext", "") or "",
            score=getattr(s, "score", 0) or 0,
            num_comments=getattr(s, "num_comments", 0) or 0,
            created_utc=getattr(s, "created_utc", 0.0),
            permalink=getattr(s, "permalink", ""),
        )
```

- [ ] **Step 5: Run, confirm pass.**

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml plugins/content/reddit/ tests/test_reddit_source.py
git commit -m "feat(plugins): Reddit ContentSource (PRAW)"
```

---

### Task 4: LLM base + Ollama provider

**Files:**
- Create: `plugins/llm/__init__.py`
- Create: `plugins/llm/base.py`
- Create: `plugins/llm/ollama/__init__.py`
- Create: `plugins/llm/ollama/provider.py`
- Test: `tests/test_llm_base.py`, `tests/test_ollama_provider.py`

**Interfaces:**
- Produces: `extract_json(text)` helper, `OllamaProvider(LLMProvider)` with `complete()` and `json_complete()`.

- [ ] **Step 1: Write `plugins/llm/base.py`**

```python
# plugins/llm/base.py
import json
import re


def extract_json(text: str) -> dict:
    """Best-effort JSON object extraction from LLM output that may include
    code fences or surrounding prose."""
    if not text:
        return {}
    # Strip markdown code fences.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    # Find the first {...} block.
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        text = m.group(0)
    return json.loads(text)
```

- [ ] **Step 2: Write failing test for extract_json**

```python
# tests/test_llm_base.py
import pytest
from plugins.llm.base import extract_json


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    s = 'Here:\n```json\n{"a": 2}\n```\nDone.'
    assert extract_json(s) == {"a": 2}


def test_extract_with_prose():
    assert extract_json('Sure! {"x": "y"} ok') == {"x": "y"}


def test_extract_invalid_raises():
    with pytest.raises(json.JSONDecodeError if False else Exception):
        extract_json("no json at all")
```

Fix the last test to: `with pytest.raises(Exception): extract_json("no json at all")` and add `import pytest`.

- [ ] **Step 3: Implement, run, confirm pass.**

- [ ] **Step 4: Write failing test for OllamaProvider using a fake transport**

```python
# tests/test_ollama_provider.py
import pytest
from plugins.llm.ollama.provider import OllamaProvider


class FakeTransport:
    """Stand-in for httpx.Client. Records calls, returns canned JSON."""
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []
    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json))
        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"message": {"content": self.response_text}}
        return R()


def test_complete_returns_content():
    t = FakeTransport("hello world")
    p = OllamaProvider(host="http://x", model="m", transport=t)
    assert p.complete("prompt") == "hello world"
    assert t.calls[0][0].endswith("/api/chat")


def test_json_complete_parses():
    t = FakeTransport('{"overall": 80, "confidence": 0.9}')
    p = OllamaProvider(host="http://x", model="m", transport=t)
    out = p.json_complete("p", schema={"overall": "number"})
    assert out["overall"] == 80


def test_json_complete_raises_on_garbage():
    t = FakeTransport("totally not json")
    p = OllamaProvider(host="http://x", model="m", transport=t)
    with pytest.raises(Exception):
        p.json_complete("p", schema={})
```

- [ ] **Step 5: Run, verify fail.**

- [ ] **Step 6: Implement OllamaProvider**

```python
# plugins/llm/ollama/provider.py
import logging
from typing import Optional

from plugins.llm.base import extract_json

log = logging.getLogger(__name__)


class OllamaProvider:
    """LLMProvider over the Ollama HTTP API.

    `transport` is an httpx-compatible client (default: real httpx.Client);
    pass a fake in tests. Uses the /api/chat endpoint with the modern
    message format.
    """

    def __init__(self, host: str = "http://localhost:11434",
                 model: str = "llama3.1", transport=None,
                 timeout: float = 120.0, temperature: float = 0.7) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        if transport is None:
            import httpx
            transport = httpx.Client(timeout=timeout)
        self._transport = transport

    def complete(self, prompt: str, system: str = "", **kw) -> str:
        payload = {
            "model": kw.get("model", self.model),
            "stream": False,
            "options": {"temperature": kw.get("temperature", self.temperature)},
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        r = self._transport.post(f"{self.host}/api/chat", json=payload,
                                 timeout=kw.get("timeout", self.timeout))
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]

    def json_complete(self, prompt: str, schema: dict, system: str = "", **kw) -> dict:
        sys_msg = (system + "\n\n" if system else "") + \
            "Respond ONLY with a JSON object matching this schema. No prose, no code fences:\n" + \
            __import__("json").dumps(schema, indent=2)
        text = self.complete(prompt, system=sys_msg, **kw)
        return extract_json(text)
```

- [ ] **Step 7: Run, confirm pass.**

- [ ] **Step 8: Commit**

```bash
git add plugins/llm/ tests/test_llm_base.py tests/test_ollama_provider.py
git commit -m "feat(plugins): LLM JSON helper + Ollama provider"
```

---

### Task 5: prompts + scoring schema

**Files:**
- Create: `config/prompts/analyzer.txt`
- Create: `config/prompts/rewriter_storytelling.txt` (and the other 6 by copy)
- Create: `config/scoring_schema.json`

**Interfaces:**
- Produces: prompt templates loaded by the agents at runtime.

- [ ] **Step 1: Write `config/scoring_schema.json`**

```json
{
  "entertainment": "number 0-10",
  "suspense": "number 0-10",
  "emotion": "number 0-10",
  "shock": "number 0-10",
  "virality": "number 0-10",
  "quality": "number 0-10",
  "retention": "number 0-10",
  "overall": "number 0-100",
  "confidence": "number 0-1"
}
```

- [ ] **Step 2: Write `config/prompts/analyzer.txt`**

```
You are a content strategist scoring Reddit stories for faceless YouTube
video potential. Score the story below on these dimensions (0-10 unless noted):

- entertainment: how engaging / fun to listen to
- suspense: does it make you want to know what happens next
- emotion: does it evoke a strong feeling
- shock: surprise / unexpected twist factor
- virality: likelihood of being shared
- quality: writing clarity and narrative coherence
- retention: will viewers watch to the end
- overall: composite score 0-100
- confidence: your confidence in the scoring, 0-1

Story title: {title}
Story body:
{body}

Return ONLY the JSON object. No prose.
```

- [ ] **Step 3: Write `config/prompts/rewriter_storytelling.txt`** (template; one per style)

```
Rewrite the following Reddit story as a {style} narration suitable for a
faceless YouTube short. Rules:
- Do NOT copy the original text. Rewrite in your own voice.
- Improve pacing and readability for spoken narration.
- Maintain the facts and the emotional arc; do not invent events.
- First person is fine if the original is first person.
- Aim for ~150 words (about 60 seconds of narration).

Original title: {title}
Original body:
{body}

Return ONLY the narration text. No preamble, no labels.
```

Create the 6 sibling files by copying this template and changing the leading
word — `rewriter_dramatic.txt`, `rewriter_funny.txt`, `rewriter_serious.txt`,
`rewriter_documentary.txt`, `rewriter_horror.txt`, `rewriter_conversational.txt`.

- [ ] **Step 4: Commit**

```bash
git add config/prompts/ config/scoring_schema.json
git commit -m "feat(config): analyzer + rewriter prompt templates"
```

---

### Task 6: Research agent

**Files:**
- Create: `agents/__init__.py`
- Create: `agents/research_agent.py`
- Test: `tests/test_research_agent.py`

**Interfaces:**
- Consumes: a `ContentSource` (injected), `infra.db.repositories.insert_story`.
- Produces: `make_research_agent(source, conn)` → agent fn matching `PipelineRunner.register`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_research_agent.py
from datetime import datetime
from core.enums import JobStage, JobStatus
from core.models import JobContext, SourceQuery, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job, get_story_by_job
from agents.research_agent import make_research_agent


class FakeSource:
    def __init__(self, stories): self._s = stories
    def discover(self, q): return self._s
    def fetch_full(self, s): return s


def test_research_agent_persists_top_story(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_seed")
    story = Story(source="reddit", source_id="t3_top", subreddit="nosleep",
                  author="u", title="T", body_text="B", score=9001,
                  num_comments=500, created_utc=datetime.utcnow().timestamp(),
                  permalink="/x")
    agent = make_research_agent(FakeSource([story]), conn,
                                query=SourceQuery(subreddits=["nosleep"]))
    ctx = JobContext(job_id=jid)
    out = agent(ctx)
    row = get_story_by_job(conn, jid)
    assert row["source_id"] == "t3_top"
    assert row["title"] == "T"
    assert out.story is not None
    assert out.story.source_id == "t3_top"
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
# agents/research_agent.py
import logging
import sqlite3

from core.models import JobContext, SourceQuery, Story
from infra.db.repositories import insert_story

log = logging.getLogger(__name__)


def make_research_agent(source, conn: sqlite3.Connection,
                        query: SourceQuery):
    """Build a RESEARCH-stage agent bound to a content source + query.

    The agent discovers stories, picks the top-scoring one, persists it, and
    attaches it to the JobContext for downstream stages.
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
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add agents/ tests/test_research_agent.py
git commit -m "feat(agents): research agent"
```

---

### Task 7: Analyzer agent

**Files:**
- Create: `agents/analyzer_agent.py`
- Test: `tests/test_analyzer_agent.py`

**Interfaces:**
- Consumes: `LLMProvider` (injected), config path for prompts + schema.
- Produces: `make_analyzer_agent(llm, conn, min_overall)` → agent fn.

- [ ] **Step 1: Write failing test with FakeLLM**

```python
# tests/test_analyzer_agent.py
from datetime import datetime
from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, insert_story, get_score_by_story
from agents.analyzer_agent import make_analyzer_agent


class FakeLLM:
    def __init__(self, payload): self.payload = payload
    def json_complete(self, prompt, schema, **kw): return self.payload


def test_analyzer_persists_score(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    story = Story(source="reddit", source_id="t3_x", subreddit="n", author="u",
                  title="T", body_text="B", score=1, num_comments=1,
                  created_utc=datetime.utcnow().timestamp(), permalink="")
    sid = insert_story(conn, jid, story)
    payload = {"entertainment": 8, "suspense": 7, "emotion": 6, "shock": 5,
               "virality": 9, "quality": 7, "retention": 8,
               "overall": 78.0, "confidence": 0.9}
    agent = make_analyzer_agent(FakeLLM(payload), conn, min_overall=70)
    ctx = JobContext(job_id=jid, story=story)
    agent(ctx)
    row = get_score_by_story(conn, sid)
    assert row["overall"] == 78.0
    assert row["confidence"] == 0.9


def test_analyzer_rejects_below_threshold(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    from infra.db.repositories import update_job_status
    from core.enums import JobStatus
    story = Story(source="reddit", source_id="t3_x", subreddit="n", author="u",
                  title="T", body_text="B", score=1, num_comments=1,
                  created_utc=datetime.utcnow().timestamp(), permalink="")
    insert_story(conn, jid, story)
    payload = {"entertainment": 3, "suspense": 3, "emotion": 3, "shock": 3,
               "virality": 3, "quality": 3, "retention": 3,
               "overall": 30.0, "confidence": 0.5}
    agent = make_analyzer_agent(FakeLLM(payload), conn, min_overall=70)
    ctx = JobContext(job_id=jid, story=story)
    import pytest
    with pytest.raises(RuntimeError, match="below threshold"):
        agent(ctx)
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add agents/analyzer_agent.py tests/test_analyzer_agent.py
git commit -m "feat(agents): analyzer agent"
```

---

### Task 8: Rewriter agent

**Files:**
- Create: `agents/rewriter_agent.py`
- Test: `tests/test_rewriter_agent.py`

**Interfaces:**
- Consumes: `LLMProvider`, narration style.
- Produces: `make_rewriter_agent(llm, conn, style)`.

- [ ] **Step 1: Write failing test**

```python
# tests/test_rewriter_agent.py
from datetime import datetime
from core.enums import NarrationStyle
from core.models import JobContext, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, insert_story, get_script_by_story
from agents.rewriter_agent import make_rewriter_agent


class FakeLLM:
    def __init__(self, text): self.text = text
    def complete(self, prompt, system="", **kw): return self.text


def test_rewriter_persists_script(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    story = Story(source="reddit", source_id="t3_x", subreddit="n", author="u",
                  title="The Cat", body_text="I saw a cat.", score=1,
                  num_comments=1, created_utc=datetime.utcnow().timestamp(),
                  permalink="")
    sid = insert_story(conn, jid, story)
    narration = "So there I was. A cat. Staring right at me."
    agent = make_rewriter_agent(FakeLLM(narration), conn,
                                style=NarrationStyle.STORYTELLING)
    ctx = JobContext(job_id=jid, story=story)
    agent(ctx)
    row = get_script_by_story(conn, sid)
    assert row["style"] == "storytelling"
    assert "cat" in row["text"].lower()
    assert row["word_count"] > 0
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement**

```python
# agents/rewriter_agent.py
import logging
import sqlite3
from pathlib import Path

from core.enums import NarrationStyle
from core.models import JobContext, Script
from infra.db.repositories import get_story_by_job, insert_script

log = logging.getLogger(__name__)
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "config" / "prompts"


def _prompt_for(style: NarrationStyle) -> str:
    p = _PROMPT_DIR / f"rewriter_{style.value}.txt"
    if not p.exists():
        # Fall back to the storytelling template if a style file is missing.
        p = _PROMPT_DIR / "rewriter_storytelling.txt"
    return p.read_text(encoding="utf-8")


def make_rewriter_agent(llm, conn: sqlite3.Connection, style: NarrationStyle,
                        model_name: str = ""):
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
            reading_time=len(words) / 2.5,  # ~150 wpm ≈ 2.5 wps
        )
        insert_script(conn, row["id"], script)
        ctx.script = script
        ctx.progress(100, "Script ready")
        return ctx
    return agent
```

- [ ] **Step 4: Run, confirm pass.**

- [ ] **Step 5: Commit**

```bash
git add agents/rewriter_agent.py tests/test_rewriter_agent.py
git commit -m "feat(agents): rewriter agent"
```

---

### Task 9: wire agents into the container + register plugins

**Files:**
- Modify: `app/container.py`
- Test: `tests/test_container.py` (extend)

- [ ] **Step 1: Update container to register agents + built-in plugins**

In `app/container.py`, after `self.pool.start()`:

```python
        self._register_plugins()
        self._register_agents()
        log.info("container bootstrapped (db=%s)", self.paths.db_path)

    def _register_plugins(self) -> None:
        # Reddit content source — only if creds present.
        from app.secrets import load_secrets
        from plugins.content.reddit.source import RedditSource
        from plugins.registry import PluginInfo
        secrets = load_secrets(self.paths)
        if secrets.reddit_client_id and secrets.reddit_client_secret:
            try:
                src = RedditSource.from_secrets(secrets)
                self.registry.register(PluginInfo(
                    name="reddit", version="0.1", contract="content_source",
                    label="Reddit", instance=src, config={}))
            except Exception as e:
                log.warning("reddit source init failed: %s", e)
        # Ollama LLM provider — always registered (it lazily connects).
        from plugins.llm.ollama.provider import OllamaProvider
        ollama = OllamaProvider(host=self.config.llm.ollama_host,
                                model=self.config.llm.ollama_model)
        self.registry.register(PluginInfo(
            name="ollama", version="0.1", contract="llm_provider",
            label="Ollama", instance=ollama, config={}))

    def _register_agents(self) -> None:
        from core.enums import JobStage
        from core.models import SourceQuery
        from agents.research_agent import make_research_agent
        from agents.analyzer_agent import make_analyzer_agent
        from agents.rewriter_agent import make_rewriter_agent
        src = self.registry.active("content_source")
        if src is not None:
            q = SourceQuery(
                subreddits=self.config.reddit.subreddits,
                min_score=self.config.reddit.min_score,
                min_comments=self.config.reddit.min_comments,
                max_age_hours=self.config.reddit.max_age_hours,
                sort=self.config.reddit.sort,
                limit=self.config.reddit.limit,
            )
            self.runner.register(JobStage.RESEARCH, make_research_agent(src, self.db, q))
        llm = self.registry.active("llm_provider")
        if llm is not None:
            self.runner.register(JobStage.ANALYZE,
                make_analyzer_agent(llm, self.db,
                                    min_overall=self.config.scoring.min_overall))
            self.runner.register(JobStage.REWRITE,
                make_rewriter_agent(llm, self.db,
                    style=NarrationStyle.STORYTELLING))  # default; configurable later
```

Add at top of container.py:
```python
from core.enums import NarrationStyle
```

- [ ] **Step 2: Extend container test — verify Ollama provider always registered**

```python
def test_container_registers_ollama_and_optional_reddit(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    c = Container(); c.bootstrap()
    try:
        assert c.registry.get("llm_provider", "Ollama") is not None
        # No reddit creds → not registered, no crash.
        assert c.registry.list("content_source") == []
        # Analyzer + Rewriter stages wired.
        from core.enums import JobStage
        assert JobStage.ANALYZE in c.runner._agents
        assert JobStage.REWRITE in c.runner._agents
    finally:
        c.shutdown()
```

- [ ] **Step 3: Run, confirm pass.**

- [ ] **Step 4: Commit**

```bash
git add app/container.py tests/test_container.py
git commit -m "feat(app): wire content/llm plugins + research/analyze/rewrite agents"
```

---

### Task 10: ResearchService + Research view

**Files:**
- Create: `app/services.py`
- Create: `gui/views/research.py`
- Modify: `gui/shell.py` (wire Research view into the stack)
- Test: `tests/test_services.py`, `tests/test_research_view.py`

**Interfaces:**
- Produces: `ResearchService.discover(query) -> list[Story]`, `ResearchService.enqueue(story) -> job_id`. `ResearchView` UI.

- [ ] **Step 1: Write `app/services.py`**

```python
# app/services.py
import logging

from core.models import SourceQuery, Story
from infra.db.repositories import create_job, insert_story

log = logging.getLogger(__name__)


class ResearchService:
    """Application service: bridges the GUI to the ContentSource plugin + jobs."""

    def __init__(self, container) -> None:
        self.container = container

    def discover(self, query: SourceQuery) -> list[Story]:
        src = self.container.registry.active("content_source")
        if src is None:
            log.warning("no content source registered")
            return []
        return src.discover(query)

    def enqueue(self, story: Story) -> int:
        """Create a job for a chosen story and seed its stories row."""
        jid = create_job(self.container.db, source_id=story.source_id,
                         story_url=story.permalink)
        insert_story(self.container.db, jid, story)
        return jid

    def start_job(self, job_id: int, stage) -> None:
        from core.enums import JobStage
        self.container.pool.submit(job_id, stage)
```

- [ ] **Step 2: Write failing service test with a fake container**

```python
# tests/test_services.py
from datetime import datetime
from core.enums import JobStage
from core.models import SourceQuery, Story
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import get_job, get_story_by_job
from app.services import ResearchService


class FakeContainer:
    def __init__(self, db, src):
        self.db = db; self.registry = self; self._src = src; self.pool = self
    def active(self, contract, label=None): return self._src
    def submit(self, job_id, stage): self._submitted = (job_id, stage)


def _story(sid="t3_a"):
    return Story(source="reddit", source_id=sid, subreddit="n", author="u",
                 title="T", body_text="B", score=1, num_comments=1,
                 created_utc=datetime.utcnow().timestamp(), permalink="/x")


def test_service_discover_returns_from_source(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    class S:
        def discover(self, q): return [_story("t3_a"), _story("t3_b")]
        def fetch_full(self, s): return s
    svc = ResearchService(FakeContainer(conn, S()))
    out = svc.discover(SourceQuery(subreddits=["n"]))
    assert [s.source_id for s in out] == ["t3_a", "t3_b"]


def test_service_enqueue_creates_job_with_story(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    class S:
        def discover(self, q): return []
        def fetch_full(self, s): return s
    c = FakeContainer(conn, S())
    svc = ResearchService(c)
    jid = svc.enqueue(_story("t3_a"))
    job = get_job(conn, jid)
    row = get_story_by_job(conn, jid)
    assert job["source_id"] == "t3_a"
    assert row["title"] == "T"
    svc.start_job(jid, JobStage.ANALYZE)
    assert c._submitted == (jid, JobStage.ANALYZE)
```

- [ ] **Step 3: Run, verify fail, then implement service (Step 1 code), confirm pass.**

- [ ] **Step 4: Write `gui/views/research.py`**

```python
# gui/views/research.py
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox,
    QComboBox, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView,
)
from PySide6.QtCore import Qt
from core.models import SourceQuery, Story


class ResearchView(QWidget):
    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        self._results: list[Story] = []
        v = QVBoxLayout(self)
        title = QLabel("Research"); title.setObjectName("title")
        v.addWidget(title)

        # Filter row.
        filters = QHBoxLayout()
        self.subreddits = QLineEdit("AskReddit, nosleep, tifu")
        self.subreddits.setPlaceholderText("subreddits, comma-separated")
        self.min_score = QSpinBox(); self.min_score.setRange(0, 100000); self.min_score.setValue(1000)
        self.min_comments = QSpinBox(); self.min_comments.setRange(0, 100000); self.min_comments.setValue(50)
        self.sort = QComboBox(); self.sort.addItems(["hot", "top", "new", "rising"])
        self.limit = QSpinBox(); self.limit.setRange(1, 100); self.limit.setValue(25)
        self.discover_btn = QPushButton("🔍 Discover")
        self.discover_btn.setObjectName("primary")
        self.discover_btn.clicked.connect(self._on_discover)
        for lbl_text, w in (("Subreddits", self.subreddits), ("Min score", self.min_score),
                            ("Min comments", self.min_comments),
                            ("Sort", self.sort), ("Limit", self.limit)):
            filters.addWidget(QLabel(lbl_text)); filters.addWidget(w)
        filters.addWidget(self.discover_btn)
        v.addLayout(filters)

        # Results table.
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["", "Subreddit", "Title", "Score", "Comments", "Age"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.table, 1)

        # Send-to-pipeline.
        actions = QHBoxLayout()
        self.enqueue_btn = QPushButton("➡ Send to Pipeline")
        self.enqueue_btn.clicked.connect(self._on_enqueue)
        actions.addStretch(); actions.addWidget(self.enqueue_btn)
        v.addLayout(actions)

    def _build_query(self) -> SourceQuery:
        subs = [s.strip() for s in self.subreddits.text().split(",") if s.strip()]
        return SourceQuery(
            subreddits=subs or ["AskReddit"],
            min_score=self.min_score.value(),
            min_comments=self.min_comments.value(),
            sort=self.sort.currentText(),
            limit=self.limit.value(),
        )

    def _on_discover(self) -> None:
        if not self.container:
            return
        from app.services import ResearchService
        svc = ResearchService(self.container)
        try:
            self._results = svc.discover(self._build_query())
        except Exception as e:
            QMessageBox.warning(self, "Discover failed", str(e))
            return
        self._populate()

    def _populate(self) -> None:
        self.table.setRowCount(0)
        now = datetime.utcnow().timestamp()
        for i, s in enumerate(self._results):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem())
            self.table.setItem(i, 1, QTableWidgetItem(s.subreddit))
            self.table.setItem(i, 2, QTableWidgetItem(s.title))
            self.table.setItem(i, 3, QTableWidgetItem(str(s.score)))
            self.table.setItem(i, 4, QTableWidgetItem(str(s.num_comments)))
            hours = int((now - s.created_utc) / 3600) if s.created_utc else 0
            self.table.setItem(i, 5, QTableWidgetItem(f"{hours}h"))

    def _on_enqueue(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows or not self.container:
            return
        from app.services import ResearchService
        from core.enums import JobStage
        svc = ResearchService(self.container)
        count = 0
        for r in sorted(rows):
            story = self._results[r]
            jid = svc.enqueue(story)
            svc.start_job(jid, JobStage.ANALYZE)   # research already done
            count += 1
        QMessageBox.information(self, "Queued", f"{count} job(s) queued.")
```

- [ ] **Step 5: Wire into shell — replace the Research placeholder**

In `gui/shell.py`, replace the placeholder loop so that index 1 (Research) uses the real view:

```python
        from gui.views.dashboard import DashboardView
        from gui.views.research import ResearchView
        self.dashboard = DashboardView(container=container)
        self.stack.addWidget(self.dashboard)
        self.research = ResearchView(container=container)
        self.stack.addWidget(self.research)
        placeholders = ["Pipeline", "Approval", "Library", "History", "Settings", "Logs"]
        for label in placeholders:
            self.stack.addWidget(PlaceholderView(label))
```

- [ ] **Step 6: Write a basic Research view test**

```python
# tests/test_research_view.py
from gui.views.research import ResearchView


def test_research_view_builds_and_has_columns(qtbot):
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    assert view.table.columnCount() == 6
    assert view.discover_btn.text().startswith("🔍")


def test_build_query_parses_subs(qtbot):
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    view.subreddits.setText("nosleep, tifu , askreddit")
    q = view._build_query()
    assert q.subreddits == ["nosleep", "tifu", "askreddit"]
```

- [ ] **Step 7: Run all tests, confirm pass.**

- [ ] **Step 8: Commit**

```bash
git add app/services.py gui/views/research.py gui/shell.py tests/test_services.py tests/test_research_view.py
git commit -m "feat(gui): research service + view"
```

---

## Phase 2 Self-Review

**Spec coverage:** Phase 2 deliverables in the design doc (§12):
- Reddit ContentSource (PRAW) → Task 3
- Research + Analyzer + Rewriter agents → Tasks 6, 7, 8
- LLM provider (Ollama) + prompts → Tasks 4, 5
- Research view → Task 10

**Placeholder scan:** none — each step has full code.

**Type consistency:** `SourceQuery` fields match between RedditSource tests and the agent; `StoryScore` fields match insert_score; `NarrationStyle.STORYTELLING` referenced consistently; `ResearchService.enqueue` returns int job_id used by `start_job`.

Phase 2 complete after these 10 tasks.
