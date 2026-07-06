# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the application skeleton — layering, config, database, plugin registry, and a launching GUI shell with a working Dashboard — so the app runs, persists settings, and is ready for Phase 2 features.

**Architecture:** Layered monolith (GUI → services → domain → infra) with a DI container wiring plugin contracts to implementations. Pure-Python domain layer; side effects isolated to infra. PySide6 QWidgets + QSS for the GUI.

**Tech Stack:** Python 3.12+, PySide6, sqlite3 (stdlib), pytest, pytest-qt.

## Global Constraints

- Python 3.12+ required.
- Dependencies pinned in `pyproject.toml`.
- Layering rule: `gui` → `app` services → `core`/`pipeline`/`agents` domain → `infra`. Never import upward.
- User data lives under `~/.aicf/`; never write into the install dir at runtime.
- Secrets in `~/.aicf/secrets.json`, never logged.
- Every agent/contract testable with fakes — no network or ffmpeg in unit tests.
- Type hints + dataclasses everywhere in domain code.
- TDD: failing test first, then implementation.

---

## File Structure

Files created in Phase 1, by responsibility:

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | project metadata, deps, tool config |
| `main.py` | entry point: QApplication + container bootstrap |
| `app/paths.py` | cross-platform path resolution for `~/.aicf` |
| `app/config.py` | typed config tree (dataclasses) + load/save |
| `app/events.py` | Qt signal bus |
| `app/container.py` | DI wiring |
| `core/enums.py` | JobStage, JobStatus, ExportFormat, NarrationStyle, ApprovalState |
| `core/results.py` | Result[T] / error type |
| `core/models.py` | Story, ScoredStory, Script, Job, etc. dataclasses |
| `pipeline/state_machine.py` | stage transitions |
| `pipeline/runner.py` | drives a job through stages |
| `pipeline/worker_pool.py` | bounded thread pool + SQLite-backed queue |
| `plugins/registry.py` | plugin discovery + loading |
| `infra/db/connection.py` | sqlite connection factory |
| `infra/db/migrations.py` | applies numbered SQL migrations |
| `infra/db/migrations/0001_init.sql` | initial schema |
| `infra/db/repositories.py` | job/story repo functions |
| `infra/storage.py` | FS layout for library + jobs |
| `infra/logging_setup.py` | rotating file + GUI log handler |
| `gui/theme/dark.qss` | dark theme stylesheet + tokens |
| `gui/theme/tokens.py` | color tokens as Python constants |
| `gui/shell.py` | main window, sidebar, stacked views |
| `gui/views/dashboard.py` | Dashboard view |
| `gui/views/placeholder.py` | placeholder views for other nav entries |
| `gui/viewmodels.py` | DashboardViewModel |
| `tests/` | mirrors package tree, one test module per source module |

---

### Task 1: Project skeleton + pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `app/__init__.py` (empty)
- Create: `core/__init__.py` (empty)
- Create: `pipeline/__init__.py` (empty)
- Create: `plugins/__init__.py` (empty)
- Create: `infra/__init__.py` (empty)
- Create: `gui/__init__.py` (empty)
- Create: `gui/views/__init__.py` (empty)
- Create: `gui/theme/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

**Interfaces:**
- Produces: a pip-installable project with deps for the rest of Phase 1.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-content-factory"
version = "0.1.0"
description = "Automated faceless YouTube video creation from Reddit stories."
requires-python = ">=3.12"
dependencies = [
    "PySide6>=6.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-qt>=4.4",
    "pytest-cov>=5",
]

[project.scripts]
aicf = "main:main"

[tool.setuptools.packages.find]
include = ["app", "core", "pipeline", "plugins", "infra", "gui"]

[tool.pytest.ini_options]
testpaths = ["tests"]
qt_api = "pyside6"
addopts = "-ra"
```

- [ ] **Step 2: Create package `__init__.py` files**

Create the empty `__init__.py` files listed in the Files block so the packages resolve.

- [ ] **Step 3: Install dev deps into the venv**

Run: `.venv/bin/pip install -e ".[dev]"`
Expected: succeeds, PySide6 + pytest + pytest-qt installed.

- [ ] **Step 4: Smoke test the import graph**

Run: `.venv/bin/python -c "import app, core, pipeline, plugins, infra, gui; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git init && git add -A && git commit -m "chore: project skeleton + pyproject"
```

---

### Task 2: core/enums.py

**Files:**
- Create: `core/enums.py`
- Test: `tests/test_enums.py`

**Interfaces:**
- Produces: enums used throughout the codebase.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_enums.py
from core.enums import (
    JobStage, JobStatus, ExportFormat, NarrationStyle, ApprovalState,
)

def test_pipeline_stage_order():
    order = list(JobStage)
    assert order[0] == JobStage.RESEARCH
    assert order.index(JobStage.EDIT) < order.index(JobStage.AWAITING_APPROVAL)
    assert order.index(JobStage.AWAITING_APPROVAL) < order.index(JobStage.THUMBNAIL)
    assert order[-1] == JobStage.PUBLISH

def test_approval_pending_is_default():
    assert ApprovalState.PENDING.value == "pending"

def test_narration_styles_match_spec():
    styles = {s.value for s in NarrationStyle}
    assert styles == {"dramatic","funny","serious","storytelling","documentary","horror","conversational"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_enums.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write implementation**

```python
# core/enums.py
from enum import Enum

class JobStage(str, Enum):
    RESEARCH = "research"
    ANALYZE = "analyze"
    REWRITE = "rewrite"
    VOICE = "voice"
    SUBTITLE = "subtitle"
    EDIT = "edit"
    AWAITING_APPROVAL = "awaiting_approval"
    THUMBNAIL = "thumbnail"
    SEO = "seo"
    PUBLISH = "publish"

class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    DONE = "done"

class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"

class ExportFormat(str, Enum):
    SHORTS_VERTICAL = "shorts_vertical_9_16"   # YouTube Shorts
    TIKTOK = "tiktok_9_16"
    REELS = "reels_9_16"
    YOUTUBE = "youtube_16_9"

class NarrationStyle(str, Enum):
    DRAMATIC = "dramatic"
    FUNNY = "funny"
    SERIOUS = "serious"
    STORYTELLING = "storytelling"
    DOCUMENTARY = "documentary"
    HORROR = "horror"
    CONVERSATIONAL = "conversational"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_enums.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/enums.py tests/test_enums.py
git commit -m "feat(core): job/export/narration enums"
```

---

### Task 3: core/results.py — Result[T]

**Files:**
- Create: `core/results.py`
- Test: `tests/test_results.py`

**Interfaces:**
- Produces: `Result` (success/failure container) used by agents and services.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_results.py
import pytest
from core.results import Result, ResultError

def test_ok_carries_value():
    r = Result.ok(42)
    assert r.success and r.value == 42

def test_err_carries_message():
    r = Result.err("boom")
    assert not r.success and r.error == "boom"

def test_unwrap_ok():
    assert Result.ok("x").unwrap() == "x"

def test_unwrap_err_raises():
    with pytest.raises(ResultError):
        Result.err("nope").unwrap()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_results.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# core/results.py
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class ResultError(Exception):
    """Raised when unwrap() is called on a failed Result."""

@dataclass(frozen=True)
class Result(Generic[T]):
    success: bool
    value: Optional[T] = None
    error: Optional[str] = None

    @staticmethod
    def ok(value: T) -> "Result[T]":
        return Result(success=True, value=value)

    @staticmethod
    def err(error: str) -> "Result[T]":
        return Result(success=False, error=error)

    def unwrap(self) -> T:
        if not self.success:
            raise ResultError(self.error or "unknown error")
        return self.value  # type: ignore[return-value]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_results.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/results.py tests/test_results.py
git commit -m "feat(core): Result[T] type"
```

---

### Task 4: app/paths.py — cross-platform paths

**Files:**
- Create: `app/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces: `AppPaths` with attributes: `data_dir`, `db_path`, `settings_path`, `secrets_path`, `logs_dir`, `library_dir`, `jobs_dir`, `plugins_dir`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_paths.py
from pathlib import Path
from app.paths import AppPaths

def test_paths_under_user_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    p = AppPaths()
    assert p.data_dir == tmp_path
    assert p.db_path == tmp_path / "aicf.db"
    assert p.settings_path == tmp_path / "settings.json"
    assert p.secrets_path == tmp_path / "secrets.json"
    assert p.logs_dir == tmp_path / "logs"
    assert p.library_dir == tmp_path / "library"
    assert p.jobs_dir == tmp_path / "jobs"
    assert p.plugins_dir == tmp_path / "plugins"

def test_ensure_creates_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    p = AppPaths()
    p.ensure()
    for d in [p.logs_dir, p.library_dir, p.jobs_dir, p.plugins_dir]:
        assert d.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# app/paths.py
import os
from pathlib import Path

class AppPaths:
    """Cross-platform path resolution for user data. Override with $AICF_HOME for tests."""

    def __init__(self) -> None:
        home = os.environ.get("AICF_HOME")
        if home:
            self.data_dir = Path(home)
        else:
            self.data_dir = Path.home() / ".aicf"

    @property
    def db_path(self) -> Path: return self.data_dir / "aicf.db"
    @property
    def settings_path(self) -> Path: return self.data_dir / "settings.json"
    @property
    def secrets_path(self) -> Path: return self.data_dir / "secrets.json"
    @property
    def logs_dir(self) -> Path: return self.data_dir / "logs"
    @property
    def library_dir(self) -> Path: return self.data_dir / "library"
    @property
    def jobs_dir(self) -> Path: return self.data_dir / "jobs"
    @property
    def plugins_dir(self) -> Path: return self.data_dir / "plugins"

    def ensure(self) -> None:
        for d in (self.data_dir, self.logs_dir, self.library_dir,
                  self.jobs_dir, self.plugins_dir):
            d.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/paths.py tests/test_paths.py
git commit -m "feat(app): cross-platform AppPaths"
```

---

### Task 5: app/config.py — typed config tree

**Files:**
- Create: `app/config.py`
- Create: `config/default_settings.json`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass tree + `load_config()` / `save_config()`.

- [ ] **Step 1: Write default settings file**

```json
// config/default_settings.json
{
  "general": {
    "theme": "dark",
    "concurrent_jobs": 1
  },
  "scoring": {
    "min_overall": 70
  },
  "reddit": {
    "subreddits": ["AskReddit", "tifu", "nosleep"],
    "min_score": 1000,
    "min_comments": 50,
    "max_age_hours": 168,
    "sort": "hot",
    "limit": 25
  },
  "llm": {
    "active_provider": "ollama",
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3.1"
  },
  "voice": {
    "active_engine": "piper",
    "speed": 1.0,
    "pitch": 1.0,
    "volume": 1.0
  },
  "editor": {
    "default_format": "shorts_vertical_9_16",
    "background_category": "minecraft_parkour"
  },
  "publishing": {
    "default_privacy": "draft"
  }
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_config.py
from app.config import load_config, save_config, Config

def test_load_defaults_when_no_user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    cfg = load_config()
    assert cfg.scoring.min_overall == 70
    assert cfg.general.concurrent_jobs == 1
    assert cfg.llm.active_provider == "ollama"

def test_user_overrides_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    cfg = load_config()
    cfg.scoring.min_overall = 85
    save_config(cfg)
    cfg2 = load_config()
    assert cfg2.scoring.min_overall == 85
    # unchanged value still there
    assert cfg2.general.concurrent_jobs == 1

def test_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"general": {"theme": "light"}}')
    cfg = load_config()
    assert cfg.general.theme == "light"
    assert cfg.scoring.min_overall == 70
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: FAIL.

- [ ] **Step 4: Write implementation**

```python
# app/config.py
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from app.paths import AppPaths

@dataclass
class GeneralConfig: theme: str = "dark"; concurrent_jobs: int = 1

@dataclass
class ScoringConfig: min_overall: float = 70

@dataclass
class RedditConfig:
    subreddits: list = field(default_factory=lambda: ["AskReddit","tifu","nosleep"])
    min_score: int = 1000
    min_comments: int = 50
    max_age_hours: int = 168
    sort: str = "hot"
    limit: int = 25

@dataclass
class LLMConfig:
    active_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

@dataclass
class VoiceConfig:
    active_engine: str = "piper"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0

@dataclass
class EditorConfig:
    default_format: str = "shorts_vertical_9_16"
    background_category: str = "minecraft_parkour"

@dataclass
class PublishingConfig:
    default_privacy: str = "draft"

@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)

_SHIPPED_DEFAULTS = Path(__file__).resolve().parent.parent / "config" / "default_settings.json"

def _build(data: dict) -> Config:
    cfg = Config()
    cfg.general = GeneralConfig(**data.get("general", {}))
    cfg.scoring = ScoringConfig(**data.get("scoring", {}))
    cfg.reddit = RedditConfig(**data.get("reddit", {}))
    cfg.llm = LLMConfig(**data.get("llm", {}))
    cfg.voice = VoiceConfig(**data.get("voice", {}))
    cfg.editor = EditorConfig(**data.get("editor", {}))
    cfg.publishing = PublishingConfig(**data.get("publishing", {}))
    return cfg

def load_config(paths: AppPaths | None = None) -> Config:
    paths = paths or AppPaths()
    with _SHIPPED_DEFAULTS.open() as f:
        data = json.load(f)
    if paths.settings_path.exists():
        with paths.settings_path.open() as f:
            user = json.load(f)
        for section, vals in user.items():
            if isinstance(vals, dict) and section in data:
                data[section].update(vals)
    return _build(data)

def save_config(cfg: Config, paths: AppPaths | None = None) -> None:
    paths = paths or AppPaths()
    save_dict = asdict(cfg)
    with paths.settings_path.open("w") as f:
        json.dump(save_dict, f, indent=2)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/config.py config/default_settings.json tests/test_config.py
git commit -m "feat(app): typed config tree + defaults"
```

---

### Task 6: core/models.py — domain dataclasses

**Files:**
- Create: `core/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Story`, `StoryScore`, `Script`, `JobContext`, `SourceQuery`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
from datetime import datetime
from core.models import Story, StoryScore, SourceQuery, JobContext
from core.enums import JobStage, NarrationStyle

def test_source_query_defaults():
    q = SourceQuery(subreddits=["nosleep"])
    assert q.subreddits == ["nosleep"]
    assert q.sort == "hot"

def test_story_score_subscores():
    s = StoryScore(entertainment=8, suspense=7, emotion=6, shock=5,
                   virality=9, quality=7, retention=8, overall=7.8, confidence=0.9)
    assert s.overall == 7.8
    assert s.passes(7.0)

def test_job_context_progress_callback():
    ctx = JobContext(job_id=1)
    captured = []
    ctx.progress = lambda pct, msg="": captured.append((pct, msg))
    ctx.progress(50, "halfway")
    assert captured == [(50, "halfway")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# core/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional, Any
from core.enums import JobStage, NarrationStyle

ProgressFn = Callable[..., None]  # (pct: int, msg: str = "")

@dataclass
class SourceQuery:
    subreddits: list[str]
    min_score: int = 1000
    min_comments: int = 50
    max_age_hours: int = 168
    sort: str = "hot"            # hot | top | rising | new
    limit: int = 25

@dataclass
class Story:
    source: str                  # e.g. "reddit"
    source_id: str               # reddit fullname / id
    subreddit: str
    author: str
    title: str
    body_text: str
    score: int
    num_comments: int
    created_utc: float
    permalink: str
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    body_raw: Optional[str] = None

@dataclass
class StoryScore:
    entertainment: float
    suspense: float
    emotion: float
    shock: float
    virality: float
    quality: float
    retention: float
    overall: float
    confidence: float
    model: str = ""

    def passes(self, threshold: float) -> bool:
        return self.overall >= threshold

@dataclass
class Script:
    story_id: int
    style: NarrationStyle
    text: str
    model: str = ""
    word_count: int = 0
    reading_time: float = 0.0    # seconds

@dataclass
class JobContext:
    job_id: int
    story: Optional[Story] = None
    script: Optional[Script] = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    progress: ProgressFn = lambda pct, msg="": None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_models.py
git commit -m "feat(core): domain dataclasses"
```

---

### Task 7: infra/db — connection + migrations

**Files:**
- Create: `infra/db/__init__.py`
- Create: `infra/db/connection.py`
- Create: `infra/db/migrations.py`
- Create: `infra/db/migrations/0001_init.sql`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `connect(db_path) -> Connection`, `migrate(conn)`.

- [ ] **Step 1: Write the initial migration SQL**

```sql
-- infra/db/migrations/0001_init.sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    story_url TEXT,
    stage TEXT NOT NULL DEFAULT 'research',
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 0,
    approval_state TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER UNIQUE,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    subreddit TEXT,
    author TEXT,
    title TEXT,
    body_raw TEXT,
    body_text TEXT,
    score INTEGER,
    num_comments INTEGER,
    created_utc REAL,
    permalink TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS story_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    entertainment REAL, suspense REAL, emotion REAL, shock REAL,
    virality REAL, quality REAL, retention REAL,
    overall REAL, confidence REAL, model TEXT,
    scored_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (story_id) REFERENCES stories(id)
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id INTEGER NOT NULL,
    style TEXT, model TEXT, text TEXT,
    word_count INTEGER, reading_time REAL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (story_id) REFERENCES stories(id)
);

CREATE TABLE IF NOT EXISTS voice_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER NOT NULL,
    engine TEXT, voice TEXT, speed REAL, pitch REAL, emotion TEXT,
    duration_sec REAL, audio_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (script_id) REFERENCES scripts(id)
);

CREATE TABLE IF NOT EXISTS subtitles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_clip_id INTEGER NOT NULL,
    format TEXT, styler TEXT, ass_path TEXT, srt_path TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (voice_clip_id) REFERENCES voice_clips(id)
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    format TEXT, aspect TEXT, width INTEGER, height INTEGER,
    duration_sec REAL, background_id INTEGER, music_id INTEGER,
    video_path TEXT, thumbnail_path TEXT, size_bytes INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS thumbnails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    template TEXT, text_line1 TEXT, text_line2 TEXT,
    image_path TEXT, variant INTEGER,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS seo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    title TEXT, description TEXT, tags_json TEXT, hashtags_json TEXT,
    pinned_comment TEXT, community_post TEXT,
    ctr_score REAL, seo_score REAL, model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS publishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER NOT NULL,
    platform TEXT, remote_id TEXT, privacy TEXT, playlist_id TEXT,
    status TEXT, attempt_count INTEGER NOT NULL DEFAULT 0,
    published_at TEXT, response_json TEXT,
    FOREIGN KEY (video_id) REFERENCES videos(id)
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publish_id INTEGER NOT NULL,
    views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER,
    watch_time_min REAL, ctr REAL, retention_pct REAL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (publish_id) REFERENCES publishes(id)
);

CREATE TABLE IF NOT EXISTS media_library (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,        -- background|music|logo|intro|outro
    category TEXT, name TEXT, path TEXT,
    duration_sec REAL, resolution TEXT,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS content_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin TEXT, label TEXT, config_json TEXT, enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llm_providers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin TEXT, label TEXT, config_json TEXT, enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS voice_engines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plugin TEXT, label TEXT, config_json TEXT, enabled INTEGER NOT NULL DEFAULT 1,
    added_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_stage ON jobs(stage);
CREATE INDEX IF NOT EXISTS idx_jobs_approval ON jobs(approval_state);
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_db.py
from infra.db.connection import connect
from infra.db.migrations import migrate, current_version

def test_migrate_creates_tables(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "jobs" in tables and "stories" in tables and "videos" in tables
    assert current_version(conn) >= 1

def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn); v1 = current_version(conn)
    migrate(conn); v2 = current_version(conn)
    assert v1 == v2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db.py -v`
Expected: FAIL.

- [ ] **Step 4: Write connection.py**

```python
# infra/db/connection.py
import sqlite3
from pathlib import Path

def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn
```

- [ ] **Step 5: Write migrations.py**

```python
# infra/db/migrations.py
import re
import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

def current_version(conn: sqlite3.Connection) -> int:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0

def _migration_files() -> list[tuple[int, Path]]:
    out = []
    for p in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        m = re.match(r"(\d+)_", p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)

def migrate(conn: sqlite3.Connection) -> int:
    current = current_version(conn)
    for version, path in _migration_files():
        if version <= current:
            continue
        sql = path.read_text()
        conn.executescript(sql)
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()
    return current_version(conn)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add infra/db/ tests/test_db.py
git commit -m "feat(infra): sqlite connection + migrations + initial schema"
```

---

### Task 8: infra/db/repositories.py — jobs repo

**Files:**
- Create: `infra/db/repositories.py`
- Test: `tests/test_repositories.py`

**Interfaces:**
- Produces: `create_job`, `get_job`, `list_jobs`, `update_job_stage`, `update_job_status`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repositories.py
import pytest
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job, update_job_stage, update_job_status
from core.enums import JobStage, JobStatus

@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "t.db"); migrate(c); return c

def test_create_and_get_job(conn):
    jid = create_job(conn, source_id="t3_abc", story_url="https://reddit/x")
    job = get_job(conn, jid)
    assert job["source_id"] == "t3_abc"
    assert job["stage"] == JobStage.RESEARCH.value

def test_update_stage_and_status(conn):
    jid = create_job(conn, source_id="t3_abc")
    update_job_stage(conn, jid, JobStage.REWRITE)
    update_job_status(conn, jid, JobStatus.RUNNING)
    job = get_job(conn, jid)
    assert job["stage"] == "rewrite"
    assert job["status"] == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_repositories.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# infra/db/repositories.py
import sqlite3
from typing import Optional

def create_job(conn: sqlite3.Connection, source_id: str,
               story_url: str = "", config_json: str = "",
               priority: int = 0) -> int:
    cur = conn.execute(
        "INSERT INTO jobs (source_id, story_url, config_json, priority) "
        "VALUES (?,?,?,?)",
        (source_id, story_url, config_json, priority),
    )
    conn.commit()
    return cur.lastrowid

def get_job(conn: sqlite3.Connection, job_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()

def list_jobs(conn: sqlite3.Connection, status: Optional[str] = None,
              limit: int = 100) -> list[sqlite3.Row]:
    if status:
        return conn.execute(
            "SELECT * FROM jobs WHERE status=? ORDER BY id DESC LIMIT ?",
            (status, limit)).fetchall()
    return conn.execute(
        "SELECT * FROM jobs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

def update_job_stage(conn: sqlite3.Connection, job_id: int, stage) -> None:
    s = stage.value if hasattr(stage, "value") else str(stage)
    conn.execute(
        "UPDATE jobs SET stage=?, updated_at=datetime('now') WHERE id=?",
        (s, job_id))
    conn.commit()

def update_job_status(conn: sqlite3.Connection, job_id: int, status,
                      error: str = "") -> None:
    s = status.value if hasattr(status, "value") else str(status)
    conn.execute(
        "UPDATE jobs SET status=?, error=?, updated_at=datetime('now') WHERE id=?",
        (s, error, job_id))
    conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_repositories.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add infra/db/repositories.py tests/test_repositories.py
git commit -m "feat(infra): jobs repository"
```

---

### Task 9: plugin contract Protocols + registry

**Files:**
- Create: `plugins/contracts.py`
- Create: `plugins/registry.py`
- Create: `plugins/plugin.toml` (manifest spec example)
- Test: `tests/test_registry.py`

**Interfaces:**
- Produces: the 10 contract Protocols, `PluginInfo`, `PluginRegistry`.

- [ ] **Step 1: Write contracts**

```python
# plugins/contracts.py
from typing import Protocol, runtime_checkable, Any

@runtime_checkable
class ContentSource(Protocol):
    def discover(self, query): ...
    def fetch_full(self, story): ...

@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, **kw) -> str: ...
    def json_complete(self, prompt: str, schema: dict) -> dict: ...

@runtime_checkable
class VoiceEngine(Protocol):
    def synthesize(self, text: str, opts) -> Any: ...

@runtime_checkable
class CaptionStyler(Protocol):
    def render(self, words, style) -> Any: ...

@runtime_checkable
class VideoEditor(Protocol):
    def compose(self, spec) -> Any: ...

@runtime_checkable
class MusicTrack(Protocol): ...

@runtime_checkable
class ThumbnailRenderer(Protocol):
    def render(self, template, lines) -> Any: ...

@runtime_checkable
class SEOGenerator(Protocol):
    def generate(self, video, script) -> Any: ...

@runtime_checkable
class Publisher(Protocol):
    def upload(self, video, seo, privacy) -> Any: ...

@runtime_checkable
class AnalyticsSource(Protocol): ...

CONTRACTS = {
    "content_source": ContentSource,
    "llm_provider": LLMProvider,
    "voice_engine": VoiceEngine,
    "caption_styler": CaptionStyler,
    "video_editor": VideoEditor,
    "music_track": MusicTrack,
    "thumbnail_renderer": ThumbnailRenderer,
    "seo_generator": SEOGenerator,
    "publisher": Publisher,
    "analytics_source": AnalyticsSource,
}
```

- [ ] **Step 2: Write the failing test**

```python
# tests/test_registry.py
from plugins.registry import PluginRegistry, PluginInfo

class FakeSource:
    def discover(self, query): return []
    def fetch_full(self, story): return story

def test_register_and_lookup():
    reg = PluginRegistry()
    info = PluginInfo(name="fake", version="0.1", contract="content_source",
                      label="Fake", instance=FakeSource(), config={})
    reg.register(info)
    assert reg.get("content_source", "fake") is info.instance

def test_unknown_contract_rejected():
    reg = PluginRegistry()
    class X: pass
    info = PluginInfo(name="x", version="0.1", contract="llm_provider",
                      label="X", instance=X(), config={})
    # X doesn't satisfy LLMProvider methods → not registered, no crash
    reg.register(info)
    assert reg.get("llm_provider", "x") is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_registry.py -v`
Expected: FAIL.

- [ ] **Step 4: Write registry.py**

```python
# plugins/registry.py
import logging
from dataclasses import dataclass, field
from typing import Any
from plugins.contracts import CONTRACTS

log = logging.getLogger(__name__)

@dataclass
class PluginInfo:
    name: str
    version: str
    contract: str
    label: str
    instance: Any
    config: dict = field(default_factory=dict)

class PluginRegistry:
    """Registers plugin instances under their contract, validating duck-typing."""

    def __init__(self) -> None:
        self._by_contract: dict[str, dict[str, PluginInfo]] = {}

    def register(self, info: PluginInfo) -> bool:
        contract_cls = CONTRACTS.get(info.contract)
        if contract_cls is None:
            log.warning("unknown contract %r for plugin %r", info.contract, info.name)
            return False
        try:
            ok = isinstance(info.instance, contract_cls)
        except Exception as e:  # runtime_checkable isinstance may raise on bad sigs
            log.warning("plugin %r contract check failed: %s", info.name, e)
            return False
        if not ok:
            log.warning("plugin %r does not satisfy contract %r", info.name, info.contract)
            return False
        bucket = self._by_contract.setdefault(info.contract, {})
        if info.label in bucket:
            log.warning("duplicate plugin %r under %r — disabling", info.name, info.contract)
            return False
        bucket[info.label] = info
        log.info("registered plugin %r (%s %s)", info.name, info.contract, info.version)
        return True

    def get(self, contract: str, label: str) -> Any | None:
        return self._by_contract.get(contract, {}).get(label, None) \
            and self._by_contract[contract][label].instance

    def list(self, contract: str) -> list[PluginInfo]:
        return list(self._by_contract.get(contract, {}).values())

    def active(self, contract: str, label: str | None = None) -> Any | None:
        bucket = self._by_contract.get(contract, {})
        if label:
            info = bucket.get(label)
            return info.instance if info else None
        if bucket:
            return next(iter(bucket.values())).instance
        return None
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_registry.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/ tests/test_registry.py
git commit -m "feat(plugins): contract Protocols + registry"
```

---

### Task 10: pipeline state machine + runner skeleton

**Files:**
- Create: `pipeline/state_machine.py`
- Create: `pipeline/runner.py`
- Test: `tests/test_state_machine.py`

**Interfaces:**
- Produces: `next_stage(stage)`, `PipelineRunner` with `register(stage, agent)` and `advance(conn, job_id)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_state_machine.py
import pytest
from core.enums import JobStage, JobStatus
from core.models import JobContext
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job, update_job_stage
from pipeline.state_machine import next_stage
from pipeline.runner import PipelineRunner

def test_next_stage_sequential():
    assert next_stage(JobStage.RESEARCH) == JobStage.ANALYZE
    assert next_stage(JobStage.EDIT) == JobStage.AWAITING_APPROVAL
    assert next_stage(JobStage.AWAITING_APPROVAL) is None  # gate
    assert next_stage(JobStage.SEO) == JobStage.PUBLISH
    assert next_stage(JobStage.PUBLISH) is None

def test_runner_advances_through_registered_stages(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    called = []
    runner = PipelineRunner()
    def agent_research(ctx): called.append("research"); return ctx
    def agent_analyze(ctx): called.append("analyze"); return ctx
    runner.register(JobStage.RESEARCH, agent_research)
    runner.register(JobStage.ANALYZE, agent_analyze)
    # advance one stage
    runner.advance(conn, jid, JobStage.RESEARCH)
    job = get_job(conn, jid)
    assert job["stage"] == "analyze"
    assert called == ["research"]

def test_runner_marks_failed_on_exception(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    runner = PipelineRunner()
    def boom(ctx): raise RuntimeError("nope")
    runner.register(JobStage.RESEARCH, boom)
    runner.advance(conn, jid, JobStage.RESEARCH)
    job = get_job(conn, jid)
    assert job["status"] == "failed"
    assert "nope" in (job["error"] or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_state_machine.py -v`
Expected: FAIL.

- [ ] **Step 3: Write state_machine.py**

```python
# pipeline/state_machine.py
from core.enums import JobStage

# Pre-approval chain ends at the gate; post-approval resumes at THUMBNAIL.
_SEQUENCE = [
    JobStage.RESEARCH, JobStage.ANALYZE, JobStage.REWRITE,
    JobStage.VOICE, JobStage.SUBTITLE, JobStage.EDIT,
    JobStage.AWAITING_APPROVAL,
    JobStage.THUMBNAIL, JobStage.SEO, JobStage.PUBLISH,
]

def next_stage(current: JobStage) -> JobStage | None:
    """Return the next stage, or None if `current` is a terminal/gate."""
    try:
        i = _SEQUENCE.index(current)
    except ValueError:
        return None
    # AWAITING_APPROVAL is a manual gate — no automatic advance.
    if current == JobStage.AWAITING_APPROVAL:
        return None
    if i + 1 >= len(_SEQUENCE):
        return None
    return _SEQUENCE[i + 1]
```

- [ ] **Step 4: Write runner.py**

```python
# pipeline/runner.py
import logging
import sqlite3
from core.enums import JobStage, JobStatus
from core.models import JobContext
from infra.db.repositories import get_job, update_job_stage, update_job_status

log = logging.getLogger(__name__)

class PipelineRunner:
    """Runs a single stage of a job, persists state, captures failures."""

    def __init__(self) -> None:
        self._agents: dict[JobStage, callable] = {}

    def register(self, stage: JobStage, agent) -> None:
        self._agents[stage] = agent

    def advance(self, conn: sqlite3.Connection, job_id: int,
                stage: JobStage) -> JobContext:
        job = get_job(conn, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        update_job_status(conn, job_id, JobStatus.RUNNING)
        ctx = JobContext(job_id=job_id)
        agent = self._agents.get(stage)
        try:
            if agent is not None:
                ctx = agent(ctx) or ctx
            nxt = next_stage(stage)
            if nxt is not None:
                update_job_stage(conn, job_id, nxt)
                update_job_status(conn, job_id, JobStatus.QUEUED)
            else:
                # terminal or gate
                update_job_status(conn, job_id, JobStatus.QUEUED)
        except Exception as e:
            log.exception("stage %s failed for job %s", stage, job_id)
            update_job_status(conn, job_id, JobStatus.FAILED, error=str(e))
        return ctx
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_state_machine.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add pipeline/ tests/test_state_machine.py
git commit -m "feat(pipeline): state machine + runner skeleton"
```

---

### Task 11: worker pool (SQLite-backed queue)

**Files:**
- Create: `pipeline/worker_pool.py`
- Test: `tests/test_worker_pool.py`

**Interfaces:**
- Produces: `WorkerPool` with `.start()`, `.submit(job_id, stage)`, `.stop()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_worker_pool.py
import time, threading
import pytest
from core.enums import JobStage, JobStatus
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job
from pipeline.runner import PipelineRunner
from pipeline.worker_pool import WorkerPool

def test_pool_runs_submitted_job(tmp_path):
    conn = connect(tmp_path / "t.db"); migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    runner = PipelineRunner()
    flag = {"ran": False}
    def agent(ctx):
        flag["ran"] = True
        return ctx
    runner.register(JobStage.RESEARCH, agent)
    pool = WorkerPool(conn, runner, max_workers=1)
    pool.start()
    try:
        pool.submit(jid, JobStage.RESEARCH)
        for _ in range(100):
            if flag["ran"]: break
            time.sleep(0.02)
        assert flag["ran"]
    finally:
        pool.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_worker_pool.py -v`
Expected: FAIL.

- [ ] **Step 3: Write worker_pool.py**

```python
# pipeline/worker_pool.py
import logging
import queue
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from core.enums import JobStage
from pipeline.runner import PipelineRunner

log = logging.getLogger(__name__)

class WorkerPool:
    """Bounded thread pool that drains a queue of (job_id, stage) tasks.

    Uses an in-process queue; SQLite persistence of job state is handled by
    the runner. A submitted task runs one stage; if the stage has a successor,
    the successor is re-enqueued so a job advances until it hits a gate or
    terminal.
    """

    def __init__(self, conn: sqlite3.Connection, runner: PipelineRunner,
                 max_workers: int = 1) -> None:
        self._conn = conn
        self._runner = runner
        self._max_workers = max_workers
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        # SQLite connections can't cross threads; open a per-worker conn instead.

    def start(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        for _ in range(self._max_workers):
            self._executor.submit(self._loop)

    def submit(self, job_id: int, stage: JobStage) -> None:
        self._queue.put((job_id, stage))

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                job_id, stage = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                from pipeline.state_machine import next_stage
                self._runner.advance(self._conn, job_id, stage)
                # check resulting stage to chain
                from infra.db.repositories import get_job
                job = get_job(self._conn, job_id)
                if job and job["status"] != "failed":
                    cur_stage = JobStage(job["stage"])
                    nxt = next_stage(cur_stage) if cur_stage != stage else next_stage(cur_stage)
                    # Only chain if the runner advanced the stage.
                    if job["stage"] != stage.value and nxt is not None:
                        self.submit(job_id, nxt)
            except Exception:
                log.exception("worker error on job %s stage %s", job_id, stage)

    def stop(self) -> None:
        self._stop.set()
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_worker_pool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/worker_pool.py tests/test_worker_pool.py
git commit -m "feat(pipeline): bounded worker pool"
```

---

### Task 12: app/events.py — Qt signal bus

**Files:**
- Create: `app/events.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Produces: `SignalBus` singleton with signals for job updates, progress, and notifications.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py
import pytest
from app.events import bus

def test_job_updated_signal(qtbot):
    received = []
    bus.job_updated.connect(lambda jid: received.append(jid))
    bus.job_updated.emit(7)
    assert received == [7]

def test_progress_signal(qtbot):
    received = []
    bus.progress.connect(lambda jid, pct, msg: received.append((jid, pct, msg)))
    bus.progress.emit(1, 50, "half")
    assert received == [(1, 50, "half")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_events.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# app/events.py
from PySide6.QtCore import QObject, Signal

class SignalBus(QObject):
    """App-wide Qt signal bus. Threads may emit; Qt marshals to the UI thread."""
    job_updated = Signal(int)              # job_id
    progress = Signal(int, int, str)       # job_id, pct, message
    job_failed = Signal(int, str)          # job_id, error
    notify = Signal(str, str)              # level, message

# Singleton — imported across the GUI.
bus = SignalBus()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/events.py tests/test_events.py
git commit -m "feat(app): Qt signal bus"
```

---

### Task 13: app/container.py — DI wiring

**Files:**
- Create: `app/container.py`
- Test: `tests/test_container.py`

**Interfaces:**
- Produces: `Container` exposing `paths`, `config`, `db`, `registry`, `runner`, `pool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_container.py
import pytest
from app.container import Container

def test_container_wires_core_services(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    c = Container()
    c.bootstrap()
    assert c.paths.data_dir == tmp_path
    assert c.config.general.concurrent_jobs == 1
    assert c.db is not None
    assert c.registry is not None
    assert c.runner is not None
    assert c.pool is not None
    c.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_container.py -v`
Expected: FAIL.

- [ ] **Step 3: Write implementation**

```python
# app/container.py
import logging
from app.config import load_config
from app.paths import AppPaths
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.logging_setup import configure_logging
from pipeline.runner import PipelineRunner
from pipeline.worker_pool import WorkerPool
from plugins.registry import PluginRegistry

log = logging.getLogger(__name__)

class Container:
    """Composition root. Wires infra to domain and starts the worker pool."""

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.config = None
        self.db = None
        self.registry = PluginRegistry()
        self.runner = PipelineRunner()
        self.pool = None
        self._log_handler = None

    def bootstrap(self) -> None:
        self.paths.ensure()
        self._log_handler = configure_logging(self.paths.logs_dir)
        self.config = load_config(self.paths)
        self.db = connect(self.paths.db_path)
        migrate(self.db)
        self.pool = WorkerPool(self.db, self.runner,
                               max_workers=self.config.general.concurrent_jobs)
        self.pool.start()
        log.info("container bootstrapped (db=%s)", self.paths.db_path)

    def shutdown(self) -> None:
        if self.pool:
            self.pool.stop()
        if self.db:
            self.db.close()
```

- [ ] **Step 4: Write infra/logging_setup.py (dependency of container)**

```python
# infra/logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

class GUILogHandler(logging.Handler):
    """Optional handler; the GUI attaches its emit to the Logs view."""
    def __init__(self) -> None:
        super().__init__()
        self._sink = None
    def set_sink(self, sink) -> None:
        self._sink = sink
    def emit(self, record) -> None:
        if self._sink:
            try:
                self._sink(self.format(record))
            except Exception:
                pass

def configure_logging(logs_dir: Path) -> GUILogHandler:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(_LOG_FORMAT)

    fh = RotatingFileHandler(logs_dir / "aicf.log", maxBytes=1_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    gui_handler = GUILogHandler()
    gui_handler.setFormatter(fmt)
    root.addHandler(gui_handler)
    return gui_handler
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_container.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/container.py infra/logging_setup.py tests/test_container.py
git commit -m "feat(app): DI container + logging setup"
```

---

### Task 14: GUI theme (QSS + tokens)

**Files:**
- Create: `gui/theme/tokens.py`
- Create: `gui/theme/dark.qss`
- Test: `tests/test_theme.py`

**Interfaces:**
- Produces: `COLORS` dict, `load_theme()` returning the QSS string.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_theme.py
from gui.theme.tokens import COLORS
from gui.theme import load_theme

def test_tokens_have_required_keys():
    for key in ("bg", "surface", "accent", "text", "muted", "border", "danger", "success"):
        assert key in COLORS

def test_load_theme_returns_nonempty_qss():
    qss = load_theme()
    assert "QMainWindow" in qss
    assert len(qss) > 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_theme.py -v`
Expected: FAIL.

- [ ] **Step 3: Write tokens.py**

```python
# gui/theme/tokens.py
COLORS = {
    "bg":      "#0e0f13",
    "surface": "#171a21",
    "surface2":"#1f232c",
    "accent":  "#ff2db7",   # magenta end of the OmniChrome gradient
    "accent2": "#2e93f0",   # blue end
    "text":    "#e6e9ef",
    "muted":   "#8b93a7",
    "border":  "#2a2f3a",
    "danger":  "#ff5470",
    "success": "#3ddc97",
    "warning": "#ffb454",
}
```

- [ ] **Step 4: Write dark.qss**

```css
/* gui/theme/dark.qss — tokens are substituted at load time. */
* { font-family: "Inter", "Segoe UI", "Sans Serif"; }

QMainWindow, QWidget#root {
    background-color: {{bg}};
    color: {{text}};
}

QToolBar, QFrame#sidebar {
    background-color: {{surface}};
    border: none;
    border-right: 1px solid {{border}};
}

QPushButton {
    background-color: {{surface2}};
    color: {{text}};
    border: 1px solid {{border}};
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { border-color: {{accent}}; }
QPushButton:pressed { background-color: {{accent}}; }
QPushButton#primary {
    background-color: {{accent}};
    color: #fff;
    border: none;
}
QPushButton#danger { border-color: {{danger}}; color: {{danger}}; }

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: {{surface2}};
    color: {{text}};
    border: 1px solid {{border}};
    border-radius: 6px;
    padding: 5px 8px;
}
QLineEdit:focus { border-color: {{accent}}; }

QTableView, QTreeView, QListView {
    background-color: {{surface}};
    alternate-background-color: {{surface2}};
    border: 1px solid {{border}};
    gridline-color: {{border}};
    selection-background-color: {{accent}};
    selection-color: #fff;
}
QHeaderView::section {
    background-color: {{surface2}};
    color: {{muted}};
    padding: 6px;
    border: none;
    border-right: 1px solid {{border}};
}

QProgressBar {
    background-color: {{surface2}};
    border: 1px solid {{border}};
    border-radius: 4px;
    text-align: center;
    color: {{text}};
    height: 14px;
}
QProgressBar::chunk { background-color: {{accent}}; border-radius: 3px; }

QLabel#title { font-size: 16px; font-weight: 600; }
QLabel#stat-value { font-size: 22px; font-weight: 700; color: {{accent}}; }
QLabel#stat-label { color: {{muted}}; }
QLabel#muted { color: {{muted}}; }

QStatusBar { background-color: {{surface}}; color: {{muted}}; }

QListWidget#nav {
    background-color: {{surface}};
    border: none;
    outline: none;
}
QListWidget#nav::item { padding: 10px 14px; border-left: 3px solid transparent; }
QListWidget#nav::item:selected {
    background-color: {{surface2}};
    border-left: 3px solid {{accent}};
    color: {{text}};
}
```

- [ ] **Step 5: Write `gui/theme/__init__.py`**

```python
# gui/theme/__init__.py
from pathlib import Path
from gui.theme.tokens import COLORS

_QSS = Path(__file__).resolve().parent / "dark.qss"

def load_theme() -> str:
    qss = _QSS.read_text(encoding="utf-8")
    for key, val in COLORS.items():
        qss = qss.replace("{{" + key + "}}", val)
    return qss
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_theme.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add gui/theme/ tests/test_theme.py
git commit -m "feat(gui): dark theme tokens + QSS"
```

---

### Task 15: GUI shell (main window + sidebar)

**Files:**
- Create: `gui/shell.py`
- Create: `gui/views/placeholder.py`
- Test: `tests/test_shell.py`

**Interfaces:**
- Produces: `MainWindow` with sidebar nav switching a `QStackedWidget`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_shell.py
import pytest
from PySide6.QtWidgets import QApplication
from gui.shell import MainWindow

def test_main_window_has_sidebar_and_stack(qtbot):
    win = MainWindow(container=None)
    qtbot.addWidget(win)
    assert win.findChild(type(win), "sidebar") or win.sidebar is not None
    assert win.stack.count() >= 7   # 7 nav entries

def test_switching_nav_changes_stack(qtbot):
    win = MainWindow(container=None)
    qtbot.addWidget(win)
    initial = win.stack.currentIndex()
    win.nav.setCurrentRow(2)
    assert win.stack.currentIndex() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_shell.py -v`
Expected: FAIL.

- [ ] **Step 3: Write placeholder view**

```python
# gui/views/placeholder.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class PlaceholderView(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lbl = QLabel(f"{title}\n\nComing in a later phase.")
        lbl.setObjectName("muted")
        lay.addWidget(lbl)
        lay.addStretch()
```

- [ ] **Step 4: Write shell.py**

```python
# gui/shell.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QFrame, QListWidget,
    QStackedWidget, QStatusBar, QLabel, QListWidgetItem,
)
from PySide6.QtCore import Qt
from gui.theme import load_theme
from gui.views.placeholder import PlaceholderView

NAV = [
    ("Dashboard", "📊"),
    ("Research",  "🔍"),
    ("Pipeline",  "⚙️"),
    ("Approval",  "✅"),
    ("Library",   "📁"),
    ("History",   "🕐"),
    ("Settings",  "🔧"),
    ("Logs",      "📜"),
]

class MainWindow(QMainWindow):
    def __init__(self, container=None):
        super().__init__()
        self.container = container
        self.setWindowTitle("AI Content Factory")
        self.resize(1280, 800)

        central = QWidget(); central.setObjectName("root")
        self.setCentralWidget(central)
        lay = QHBoxLayout(central); lay.setContentsMargins(0,0,0,0); lay.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sb = QVBoxLayout(self.sidebar); sb.setContentsMargins(0,0,0,0); sb.setSpacing(0)
        brand = QLabel("✦ AI Content Factory"); brand.setStyleSheet("padding: 18px 16px; font-weight:700; font-size: 15px;")
        sb.addWidget(brand)
        self.nav = QListWidget(); self.nav.setObjectName("nav")
        for label, icon in NAV:
            QListWidgetItem(f"  {icon}   {label}", self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav)
        sb.addWidget(self.nav, 1)
        lay.addWidget(self.sidebar)

        # Stack
        self.stack = QStackedWidget()
        # index 0 = dashboard (real); rest placeholders for now
        from gui.views.dashboard import DashboardView
        self.dashboard = DashboardView(container=container)
        self.stack.addWidget(self.dashboard)
        for label, _ in NAV[1:]:
            self.stack.addWidget(PlaceholderView(label))
        lay.addWidget(self.stack, 1)

        # Status bar
        sb_bar = QStatusBar()
        sb_bar.showMessage("Ready")
        self.setStatusBar(sb_bar)

        self.setStyleSheet(load_theme())

    def _on_nav(self, row: int) -> None:
        self.stack.setCurrentIndex(row)

    def refresh_dashboard(self) -> None:
        if hasattr(self, "dashboard"):
            self.dashboard.refresh()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_shell.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gui/shell.py gui/views/placeholder.py tests/test_shell.py
git commit -m "feat(gui): main window + sidebar nav"
```

---

### Task 16: Dashboard view + viewmodel

**Files:**
- Create: `gui/views/dashboard.py`
- Create: `gui/viewmodels.py`
- Test: `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `Container` (for `db` and `config`) — nullable in tests.
- Produces: `DashboardView` showing stat cards + system status.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dashboard.py
import pytest
from gui.views.dashboard import DashboardView

def test_dashboard_renders_stat_cards(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    from app.container import Container
    c = Container(); c.bootstrap()
    try:
        view = DashboardView(container=c)
        qtbot.addWidget(view)
        view.refresh()
        # four stat cards
        assert len(view.stat_values) == 4
        # values come from empty db → all "0"
        assert view.stat_values[0].text() == "0"
    finally:
        c.shutdown()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_dashboard.py -v`
Expected: FAIL.

- [ ] **Step 3: Write viewmodels.py**

```python
# gui/viewmodels.py
import sqlite3
from dataclasses import dataclass

@dataclass
class DashboardStats:
    videos_created: int = 0
    videos_uploaded: int = 0
    videos_pending: int = 0
    current_jobs: int = 0

def compute_dashboard_stats(conn: sqlite3.Connection) -> DashboardStats:
    def count(sql, *args):
        return conn.execute(sql, args).fetchone()[0] or 0
    return DashboardStats(
        videos_created=count("SELECT COUNT(*) FROM videos"),
        videos_uploaded=count("SELECT COUNT(*) FROM publishes WHERE status='done'"),
        videos_pending=count("SELECT COUNT(*) FROM jobs WHERE approval_state='pending'"),
        current_jobs=count("SELECT COUNT(*) FROM jobs WHERE status='running'"),
    )
```

- [ ] **Step 4: Write dashboard.py**

```python
# gui/views/dashboard.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame, QHBoxLayout,
)
from gui.viewmodels import compute_dashboard_stats, DashboardStats

class _StatCard(QFrame):
    def __init__(self, label: str, value: str = "0"):
        super().__init__()
        self.setObjectName("stat")
        lay = QVBoxLayout(self)
        self.value_lbl = QLabel(value); self.value_lbl.setObjectName("stat-value")
        self.label_lbl = QLabel(label); self.label_lbl.setObjectName("stat-label")
        lay.addWidget(self.value_lbl); lay.addWidget(self.label_lbl)
        self.setStyleSheet(
            "QFrame#stat { background-color: #171a21; border: 1px solid #2a2f3a;"
            " border-radius: 8px; padding: 16px; }")

class DashboardView(QWidget):
    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Dashboard"); title.setObjectName("title")
        v.addWidget(title)

        self.grid = QGridLayout(); self.grid.setSpacing(12)
        v.addLayout(self.grid)
        self.stat_values = []
        self.cards: list[_StatCard] = []
        for i, label in enumerate(("Videos Created", "Videos Uploaded",
                                   "Pending Approval", "Current Jobs")):
            card = _StatCard(label)
            self.grid.addWidget(card, 0, i)
            self.cards.append(card)
            self.stat_values.append(card.value_lbl)

        # System status section
        v.addSpacing(16)
        status_title = QLabel("System Status"); status_title.setObjectName("title")
        v.addWidget(status_title)
        self.status_frame = QFrame()
        sf = QVBoxLayout(self.status_frame)
        self.lbl_ffmpeg = QLabel("ffmpeg: —"); self.lbl_db = QLabel("DB: —")
        self.lbl_ollama = QLabel("Ollama: —"); self.lbl_models = QLabel("Models: —")
        for lbl in (self.lbl_ffmpeg, self.lbl_db, self.lbl_ollama, self.lbl_models):
            lbl.setObjectName("muted"); sf.addWidget(lbl)
        v.addWidget(self.status_frame)
        v.addStretch()

    def refresh(self) -> None:
        stats = DashboardStats()
        if self.container and self.container.db:
            stats = compute_dashboard_stats(self.container.db)
        self.stat_values[0].setText(str(stats.videos_created))
        self.stat_values[1].setText(str(stats.videos_uploaded))
        self.stat_values[2].setText(str(stats.videos_pending))
        self.stat_values[3].setText(str(stats.current_jobs))
        if self.container:
            self.lbl_db.setText(f"DB: {self.container.paths.db_path}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_dashboard.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gui/views/dashboard.py gui/viewmodels.py tests/test_dashboard.py
git commit -m "feat(gui): dashboard view + viewmodel"
```

---

### Task 17: main.py entry point + README

**Files:**
- Create: `main.py`
- Create: `README.md`
- Create: `.gitignore`
- Test: manual launch smoke test

**Interfaces:**
- Produces: a runnable `python main.py` launching the app.

- [ ] **Step 1: Write main.py**

```python
# main.py
import sys
from PySide6.QtWidgets import QApplication
from app.container import Container
from gui.shell import MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("AI Content Factory")
    container = Container()
    container.bootstrap()
    win = MainWindow(container=container)
    win.show()
    code = app.exec()
    container.shutdown()
    return code

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Write .gitignore**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.coverage
*.egg-info/
build/
dist/
.env
secrets.json
~/.aicf/
```

- [ ] **Step 3: Write README.md**

```markdown
# AI Content Factory

Automated faceless YouTube video creation from Reddit stories. Cross-platform
PySide6 desktop application.

## Status

Phase 1 (Foundation) — application skeleton, config, database, plugin registry,
GUI shell with Dashboard.

See `docs/superpowers/specs/2026-07-06-ai-content-factory-design.md` for the
full architecture and `docs/superpowers/plans/` for per-phase plans.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest             # run tests
.venv/bin/python main.py     # launch the app
```

User data lives under `~/.aicf/` (override with `$AICF_HOME` for tests).
```

- [ ] **Step 4: Smoke test — run the full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass.

- [ ] **Step 5: Launch smoke (optional, GUI may not show in headless)**

Run: `QT_QPA_PLATFORM=offscreen .venv/bin/python -c "from app.container import Container; from gui.shell import MainWindow; from PySide6.QtWidgets import QApplication; app=QApplication([]); c=Container(); c.bootstrap(); w=MainWindow(c); w.show(); print('launched ok'); c.shutdown()"`
Expected: prints `launched ok`.

- [ ] **Step 6: Commit**

```bash
git add main.py README.md .gitignore
git commit -m "feat: main entry point + docs"
```

---

## Phase 1 Self-Review

**Spec coverage:** every Phase 1 deliverable in the roadmap (§12) maps to a task:
- DI container → Task 13
- config system → Task 5
- SQLite + migrations → Tasks 7, 8
- paths/logging/errors → Tasks 3, 4, 13 (logging)
- plugin registry → Task 9
- GUI shell + Dashboard → Tasks 14, 15, 16

**Placeholder scan:** none — every code step has actual code.

**Type consistency:** `JobStage` / `JobStatus` used consistently; `PipelineRunner.advance(conn, job_id, stage)` signature consistent across tasks 10, 11, 13; `Container.bootstrap()` consistent in 13, 16, 17.

Phase 1 complete after these 17 tasks. Phases 2–5 get their own plan docs.
