# AI Content Factory — Architecture & Design

**Status:** Approved (design phase)
**Date:** 2026-07-06
**Location:** `/home/apollo/Downloads/RedditBot/`

## Purpose

A professional, cross-platform desktop application that automatically creates
high-quality faceless YouTube videos from Reddit stories. The full pipeline —
find stories, score with AI, rewrite for narration, generate voiceover and
subtitles, compose with background gameplay + music, render thumbnails and SEO
metadata, and upload to YouTube — runs locally, is configurable, and requires
human approval before anything publishes.

This is built like commercial software: modular, object-oriented,
dependency-injected, and independently testable. Reddit is simply the *first*
content source; everything swappable is behind a plugin contract.

## Decisions (locked during brainstorming)

| Area | Decision |
|------|----------|
| Target platform | Cross-platform distributable (Windows / macOS / Linux) |
| Architecture | Layered monolith (GUI → services → domain → infra) + plugin registry |
| Orchestration | Persisted state-machine pipeline + bounded worker pool |
| LLM | Pluggable provider; **Ollama is the default local backend**, optional OpenAI/DeepSeek/Groq |
| Content source | Pluggable; **PRAW/Reddit is the first implementation** |
| Packaging | PyInstaller `--onedir`; ffmpeg + models downloaded on first run |
| GUI toolkit | PySide6 QWidgets + QSS dark theme |
| Data store | SQLite (file under `~/.aicf/`) |
| Music | Module exists (loop/fade/duck/normalize); **ships empty — user supplies tracks** |

Standalone project. Does not integrate with the existing OmniChrome suite, but
reuses hard-won patterns from it (faster-whisper word timings, ASS captions over
`drawtext`, ffmpeg-v8-safe filter graphs) without copying code.

---

## 1. Architecture & layering

Four layers; dependencies point **downward only**. This is what makes modules
independently testable: agents and the pipeline never import GUI; infrastructure
never imports domain.

```
┌─────────────────────────────────────────────────────┐
│  GUI  (PySide6 QWidgets + QSS)                       │  Qt signals/slots
│  views, widgets, viewmodels, theming                 │
├─────────────────────────────────────────────────────┤
│  Application Services                                │  use-case orchestration
│  JobService, ApprovalService, SettingsService,       │  ─ thin, no business rules
│  LibraryService, AnalyticsService                    │
├─────────────────────────────────────────────────────┤
│  Domain                                              │  pure Python, no Qt
│  Pipeline (state machine) + Agents (run/ctx)         │  ← this is the heart
│  Plugin contracts: ContentSource, LLMProvider,       │
│  VoiceEngine, CaptionStyler, Editor, MusicTrack,     │
│  ThumbnailRenderer, SEOGenerator, Publisher,         │
│  AnalyticsSource                                     │
├─────────────────────────────────────────────────────┤
│  Infrastructure                                      │  side-effects live here
│  SQLite (sqlite3), FS store, ffmpeg/ffprobe,         │
│  Ollama/OpenAI adapters, PRAW adapter, Whisper,      │
│  Piper, yt uploads, model downloader                 │
└─────────────────────────────────────────────────────┘
```

A small **DI container** (`app/container.py`) wires interfaces → concrete
classes at startup (built-in implementations) and again after plugins load.
Agents receive their dependencies through constructor injection, never by
importing globals — this is what makes each one unit-testable with fakes.

## 2. Folder structure

```
ai_content_factory/
├── main.py                      # entry: QApplication + container bootstrap
├── app/                         # composition root
│   ├── container.py             # DI wiring
│   ├── config.py                # typed config (dataclasses) + load/save
│   ├── paths.py                 # cross-platform path resolution
│   └── events.py                # app-wide signal bus (Qt-based)
├── core/                        # domain primitives
│   ├── models.py                # Story, ScoredStory, Script, Job, Video, ...
│   ├── enums.py                 # JobStage, JobStatus, ExportFormat, ...
│   └── results.py               # Result[T] / error types
├── pipeline/
│   ├── state_machine.py         # stage transitions, persistence hooks
│   ├── runner.py                # drives a job through stages
│   └── worker_pool.py           # bounded thread pool, queue, concurrency
├── agents/                      # one responsibility each
│   ├── base.py                  # Agent protocol: run(ctx) -> ctx
│   ├── research_agent.py
│   ├── analyzer_agent.py
│   ├── rewriter_agent.py
│   ├── voice_agent.py
│   ├── subtitle_agent.py
│   ├── editor_agent.py
│   ├── thumbnail_agent.py
│   ├── seo_agent.py
│   ├── publishing_agent.py
│   └── analytics_agent.py
├── plugins/                     # built-in implementations of contracts
│   ├── content/
│   │   └── reddit/              # ContentSource (PRAW)
│   ├── llm/
│   │   ├── ollama/              # LLMProvider (default)
│   │   └── openai/              # optional
│   ├── voice/
│   │   ├── piper/
│   │   ├── kokoro/
│   │   └── xtts/
│   ├── captions/                # CaptionStyler (word-by-word, animated)
│   ├── editor/                  # ffmpeg-based Editor
│   ├── music/                   # MusicTrack (royalty-free loops)
│   ├── thumbnails/              # ThumbnailRenderer (templates)
│   ├── seo/                     # SEOGenerator
│   ├── publishing/
│   │   └── youtube/             # Publisher
│   ├── analytics/
│   │   └── youtube/             # AnalyticsSource
│   └── registry.py              # discovery + loading of plugin packages
├── infra/
│   ├── db/                      # schema, migrations, repositories
│   ├── storage/                 # per-user FS layout, media library
│   ├── ffmpeg/                  # probe, render, filter_complex builder
│   ├── whisper/                 # faster-whisper wrapper + word timings
│   ├── models.py                # model downloader (first-run)
│   └── youtube/                 # OAuth + Data API v3 client
├── gui/
│   ├── theme/                   # dark.qss, tokens, icons
│   ├── shell.py                 # main window, sidebar, stacked views
│   ├── views/                   # dashboard, research, queue, approval,
│   │                            #   library, history, settings, logs
│   ├── widgets/                 # reusable: progress, status chip, etc.
│   └── viewmodels.py            # Qt models bridging services → views
├── config/                      # shipped defaults
│   ├── default_settings.json
│   ├── caption_templates.json
│   ├── thumbnail_templates.json
│   └── prompts/                 # per-agent prompt templates
├── tests/                       # unit + integration, mirrors package tree
└── assets/                      # logo, fonts (Inter/Josefin Sans), icons
```

The key bit: **Reddit lives under `plugins/content/`**, not at the top level —
it's just the first content source, as the spec demands.

## 3. The pipeline spine

Each video is a **Job** with a persisted state machine. Stages run left-to-
right; the **approval gate** splits the pipeline in two:

```
                   ┌────────── AWAITING_APPROVAL ──────────┐
RESEARCH → ANALYZE → REWRITE → VOICE → SUBTITLE → EDIT → THUMBNAIL → SEO → PUBLISH
   │          │         │        │         │         │         │         │       │
   └── each stage commits outputs + job.stage to SQLite, so a crash/restart resumes ─┘

   ┌─ pre-approval (auto) ─────────────────────────┐   ┌─ post-approval (manual trigger) ─┐
```

- **`JobStage`** is an enum; the runner advances one stage per step, calls the
  matching agent, writes artifacts + the new stage to the DB, then enqueues the
  next stage.
- **`AWAITING_APPROVAL`** is a terminal state of the *first* sub-pipeline. A
  human hits Approve/Reject/Edit/Regenerate in the UI; Approve enqueues the job
  at the `THUMBNAIL` stage.
- **Worker pool** is a bounded `ThreadPoolExecutor` (configurable concurrency,
  default **1** — video editing is heavy). Each worker pops staged jobs off a
  SQLite-backed queue (cheap, crash-safe, no extra deps).
- Every stage emits progress via a Qt signal bus → live progress bars in the GUI.
- A stage that throws is caught; the job goes to `FAILED(stage, error)` and the
  UI shows it for retry. No job silently dies.

### Agent contract

```python
class Agent(Protocol):
    name: str
    stage: JobStage
    def run(self, ctx: JobContext) -> JobContext: ...
```

`JobContext` is a dataclass carrying the `Job`, the in-memory
`Story`/`Script`/asset paths, and a `progress(pct, message)` callback. Agents
are pure-ish: they read from `ctx`, do their one job via injected infra, write
results back into `ctx` + the DB.

## 4. Database schema (SQLite)

Relational, normalized; every row knows its `job_id` so the whole pipeline is
reconstructable.

```sql
-- the spine
jobs(id, source_id, story_url, stage, status, priority, created_at,
     updated_at, error, retry_count, config_json, approval_state)
    -- approval_state ∈ {pending, approved, rejected, edited}
    -- status         ∈ {queued, running, paused, failed, done}

stories(id, job_id UNIQUE, source, source_id, subreddit, author,
        title, body_raw, body_text, score, num_comments, created_utc,
        permalink, fetched_at)

story_scores(id, story_id, entertainment, suspense, emotion, shock,
             virality, quality, retention, overall, confidence, model, scored_at)

scripts(id, story_id, style, model, text, word_count, reading_time, created_at)
    -- style ∈ dramatic|funny|serious|storytelling|documentary|horror|conversational

voice_clips(id, script_id, engine, voice, speed, pitch, emotion,
            duration_sec, audio_path, created_at)

subtitles(id, voice_clip_id, format, styler, ass_path, srt_path, created_at)

videos(id, job_id, format, aspect, width, height, duration_sec,
       background_id, music_id, video_path, thumbnail_path, size_bytes, created_at)

thumbnails(id, video_id, template, text_line1, text_line2, image_path, variant)

seo(id, video_id, title, description, tags_json, hashtags_json,
    pinned_comment, community_post, ctr_score, seo_score, model, created_at)

publishes(id, video_id, platform, remote_id, privacy, playlist_id,
          status, attempt_count, published_at, response_json)

analytics(id, publish_id, views, likes, comments, shares, watch_time_min,
          ctr, retention_pct, fetched_at)

-- library + plugin registry
media_library(id, kind, category, name, path, duration_sec, resolution, added_at)
    -- kind ∈ background|music|logo|intro|outro

content_sources(id, plugin, label, config_json, enabled, added_at)
llm_providers(id, plugin, label, config_json, enabled)
voice_engines(id, plugin, label, config_json, enabled)
```

Migrations are plain numbered `.sql` files applied at startup
(`infra/db/migrations/0001_init.sql`, …) with a `schema_version` table — no ORM
needed, keeps it lightweight and inspectable.

## 5. Plugin contracts (the extensibility surface)

These are the interfaces the whole "make Reddit/YouTube non-special, plugins can
swap anything" goal hangs on. Each is a `Protocol` with at least one built-in
implementation and room for plugins:

```python
class ContentSource(Protocol):     # Reddit is plugin #1; News/AI/History later
    def discover(self, q: SourceQuery) -> list[Story]: ...
    def fetch_full(self, story: Story) -> Story: ...

class LLMProvider(Protocol):       # Ollama default; OpenAI/DeepSeek/Groq optional
    def complete(self, prompt, **kw) -> str: ...
    def json_complete(self, prompt, schema) -> dict: ...

class VoiceEngine(Protocol):       # Piper default; Kokoro/XTTS optional
    def synthesize(self, text, opts: VoiceOpts) -> AudioClip: ...

class CaptionStyler(Protocol):     # word-by-word, animated variants
    def render(self, words: list[WordTiming], style) -> SubtitleArtifacts: ...

class VideoEditor(Protocol):       # ffmpeg-based built-in
    def compose(self, spec: EditSpec) -> VideoFile: ...

class MusicTrack(Protocol): ...    # loop, fade, duck under narration
class ThumbnailRenderer(Protocol): ...
class SEOGenerator(Protocol): ...
class Publisher(Protocol):         # YouTube built-in; TikTok/IG via plugin
    def upload(self, video, seo, privacy) -> PublishResult: ...
class AnalyticsSource(Protocol): ...
```

**Plugin discovery:** the registry scans a `plugins/` package dir + an external
`~/.aicf/plugins/` dir on startup, loads entry-point-style metadata
(`plugin.toml`: name, version, contract implemented, class path), validates it
against the contract, and registers it. Built-ins register the same way.

## 6. Module breakdown

Every module is a thin Application Service over domain agents + plugin
contracts. The GUI never calls agents directly — it goes through a service.

| Module | Service | Agent(s) | Plugin contract used |
|--------|---------|----------|----------------------|
| Dashboard | `DashboardService` | — | — |
| Reddit Research | `ResearchService` | `ResearchAgent` | `ContentSource` |
| Story Analyzer | (via `JobService`) | `AnalyzerAgent` | `LLMProvider` |
| Story Rewriter | (via `JobService`) | `RewriterAgent` | `LLMProvider` |
| Voice Generation | (via `JobService`) | `VoiceAgent` | `VoiceEngine` |
| Subtitle Generator | (via `JobService`) | `SubtitleAgent` | `CaptionStyler` + faster-whisper |
| Video Library | `LibraryService` | — | — |
| Video Editor | (via `JobService`) | `EditorAgent` | `VideoEditor` |
| Music | (via `EditorAgent`) | — | `MusicTrack` |
| Thumbnail | (via `JobService`) | `ThumbnailAgent` | `ThumbnailRenderer` |
| SEO | (via `JobService`) | `SEOAgent` | `SEOGenerator` |
| Upload | (via `JobService`) | `PublishingAgent` | `Publisher` |
| Approval Queue | `ApprovalService` | — | — |
| Analytics | `AnalyticsService` | `AnalyticsAgent` | `AnalyticsSource` |

Module details:

- **Dashboard** — cheap aggregate `SELECT`s (counts by status/stage, last-24h
  throughput, next scheduled upload) pushed to a `DashboardViewModel`. No heavy
  work on the UI thread.
- **Reddit Research** — `ResearchService.discover(query)` → `ResearchAgent` →
  `ContentSource.discover()`. `SourceQuery` carries `subreddits: list[str]`,
  `min_score`, `min_comments`, `max_age_hours`,
  `sort ∈ {hot, top, rising, new}`, `limit`. Multiple subreddits run in parallel
  under the worker pool. Discovered stories are de-duplicated by `source_id` and
  written to `stories` before scoring.
- **AI Story Analyzer** — `AnalyzerAgent` calls `LLMProvider.json_complete()`
  with a strict JSON schema (seven sub-scores + `overall` + `confidence`),
  validates it, persists a `story_scores` row. Stories below
  `config.scoring.min_overall` are marked `rejected` and stop. The LLM is the
  only moving part — fake it in tests.
- **Story Rewriter** — `RewriterAgent` takes a scored story + a `NarrationStyle`
  enum and produces a `scripts` row. Prompt templates live in
  `config/prompts/rewriter/*.txt` so styles are editable without code. Never
  copies the raw post — the prompt enforces rewrite-for-narration.
- **Voice Generation** — `VoiceAgent` wraps `VoiceEngine`. `VoiceOpts` carries
  `voice, speed, pitch, emotion, volume`. Built-ins: **Piper** (default, fast on
  CPU), **Kokoro** (higher quality), **XTTS** (voice cloning, optional). Output
  is a wav under `storage/jobs/<id>/voice.wav` + a `voice_clips` row.
- **Subtitle Generator** — `SubtitleAgent` runs **faster-whisper** on the
  generated voice clip for word-level timings (word timings are what enable
  animated word-by-word captions and later restyling), then a `CaptionStyler`
  emits `.srt` + `.ass`. Styles are JSON templates in
  `config/caption_templates.json`, overridable per-job. ASS burn-in happens in
  the editor, not here.
- **Video Library** — `LibraryService` manages `media_library` + on-disk layout:
  ```
  <userData>/library/
    backgrounds/{minecraft_parkour,subway_surfers,gta,satisfying,nature,space,custom}/
    music/
    logos/   intros/   outros/
  ```
  Categories map to the spec's named folders. The editor is responsible for
  loop / crop / blur / resize / fit-to-narration-length.
- **Video Editor** — `EditorAgent` → `VideoEditor.compose(EditSpec)`. `EditSpec`
  names voice, background, music, captions, intro/outro/logo/watermark, and an
  `ExportFormat ∈ {shorts_vertical_9_16, tiktok_9_16, reels_9_16,
  youtube_16_9}`. Implementation in `infra/ffmpeg/` as a `filter_complex`
  builder, ffmpeg-v8-safe. Audio side chain (`sidechaincompress`) ducks music
  under narration.
- **Music** — `MusicTrack.apply(track, narration)` → loops to length, fades
  in/out, normalizes, ducks. **Ships with no tracks** — user supplies their own
  into `library/music/`.
- **Thumbnail Generator** — `ThumbnailRenderer.render(template, lines)` → PNG.
  Templates (`config/thumbnail_templates.json`) define layout zones (big text
  top/bottom, subject area, accent color). Emits multiple variants for A/B in
  the approval screen.
- **SEO** — `SEOGenerator.generate(video, script)` → title, description, tags,
  hashtags, pinned comment, community post, plus a self-scored `ctr_score` and
  `seo_score` (LLM-as-judge). Prompts under `config/prompts/seo/`.
- **Upload** — `PublishingAgent` → `Publisher.upload(video, seo, privacy)`,
  `privacy ∈ {draft, private, scheduled, public}`. YouTube built-in uses OAuth +
  Data API v3 with resumable upload + automatic retry (exponential backoff).
  Supports playlist selection. Each attempt is a `publishes` row with
  `attempt_count` + `response_json`.
- **Approval Queue** — *the load-bearing feature.* A job reaches
  `AWAITING_APPROVAL` after EDIT and stays there. `ApprovalService` exposes
  `approve(job_id)`, `reject(job_id)`, `edit(job_id, patch)`,
  `regenerate(job_id, stage)`. The approval view shows video preview, thumbnail
  variants, title, description, story score, AI confidence, and the four
  buttons. Only `approve` advances to THUMBNAIL → SEO → PUBLISH. **Nothing is
  published without a human click.**
- **Analytics** — `AnalyticsAgent` runs on a schedule (configurable, default
  hourly), pulls metrics per `publishes` row via `AnalyticsSource`, appends
  `analytics` rows. Dashboard surfaces trends.

## 7. Configuration system

Typed, layered, editable from the GUI:

```
config/default_settings.json    # shipped defaults (read-only)
~/.aicf/settings.json           # user overrides (GUI writes here)
~/.aicf/secrets.json            # Reddit creds, YouTube OAuth, LLM API keys (gitignored)
```

`app/config.py` loads defaults, deep-merges user overrides, and exposes a typed
tree of dataclasses (`GeneralConfig`, `RedditConfig`, `ScoringConfig`,
`VoiceConfig`, `EditorConfig`, `PublishingConfig`, `PathsConfig`, …). The
Settings view edits these and writes back to `settings.json`. Secrets are never
logged.

## 8. GUI design

**Shell** — `QMainWindow` with a fixed-width left sidebar (icon + label nav, VS
Code style) and a `QStackedWidget` content area. Custom dark QSS theme in
`gui/theme/dark.qss`, driven by a token block (`--bg`, `--surface`, `--accent`,
…). Inter for UI, Josefin Sans for the wordmark. Status bar at the bottom shows
worker-pool state, DB path, and a global progress indicator.

**Views:**

| View | Purpose |
|------|---------|
| Dashboard | stat cards (created/uploaded/pending/current), throughput, next-up schedule, system status (Ollama reachable? ffmpeg? models downloaded?) |
| Research | subreddit multi-select, score/comment/age filters, sort dropdown, "Discover now" button, results table with quick-preview, "Send N to pipeline" |
| Pipeline / Queue | live job table: stage, progress bar, status chip, ETA; right-click → pause/retry/cancel |
| Approval | carousel of awaiting videos: preview player, thumbnail variants, editable title/description, Approve/Reject/Edit/Regenerate |
| Library | backgrounds/music/logos/intros/outros browser, add/remove, categorize |
| History | filterable table of all jobs/publishes with analytics |
| Settings | tabbed: General, Content Sources, AI/LLM, Voice, Editor, Publishing, Paths, About |
| Logs | tail of the rotating log, filter by level/agent |

**Threading rule** — no agent, service, or infra call runs on the GUI thread.
Services hand work to the worker pool and report back via Qt signals.
Progress bars, status chips, and the job table are model-backed
(`QAbstractTableModel`) so they update reactively.

## 9. Cross-cutting concerns

- **Logging** — stdlib `logging`, rotating file handler under `~/.aicf/logs/` +
  a GUI handler that feeds the Logs view. Per-agent logger names.
- **Error handling** — `Result[T]` in domain code (no exceptions across agent
  boundaries); agents return failures, the runner records them. Infrastructure
  may raise, caught at the agent boundary.
- **First-run setup wizard** — checks/installs: ffmpeg on PATH (offer download),
  Ollama reachable (offer to start/point at host), model downloads (Whisper
  base, a Piper voice), Reddit creds entry, YouTube OAuth. Drives
  `models.py` downloader with progress.
- **Packaging** — PyInstaller `--onedir` per platform; ffmpeg + models
  downloaded on first run; NSIS (Win), dmgbuild (Mac), AppImage (Linux).
  `app/paths.py` resolves the right `~/.aicf` per OS.

## 10. Plugin system (concrete)

A plugin is a folder (built-in under `plugins/`, external under
`~/.aicf/plugins/`) containing:

```
my_plugin/
  plugin.toml     # name, version, contract (e.g. "voice"), class path
  __init__.py
  ...implementation...
```

`plugins/registry.py` at startup:

1. Scans both dirs, parses each `plugin.toml`.
2. Validates the class implements the declared `contract` (duck-typed against the
   `Protocol`).
3. Instantiates, injects any config the plugin declares it needs, registers it
   under its contract.
4. Conflicts (two plugins for the same contract with the same label) → log +
   disable the later one, never crash.

Built-ins register through the same path — so "Reddit is just the first content
source" is literally true in code. The Settings → Content Sources / AI / Voice
tabs list registered plugins and let the user pick the active one per contract.
Future TikTok/Instagram/Facebook/News/History/podcast/multi-channel plugins slot
in with zero core changes.

## 11. Testing strategy

- **Unit tests** per agent, faking the contracts (`FakeLLM`, `FakeVoice`,
  `FakeContentSource`) — fast, no network, no ffmpeg.
- **Integration tests** for the pipeline runner using a fake-stack config
  end-to-end (story in → awaiting-approval job out), asserting state transitions
  and DB rows.
- **ffmpeg tests** guarded behind a `@needs_ffmpeg` marker, real renders against
  a tiny sample asset.
- **GUI tests** with `pytest-qt` for viewmodels and signal wiring; visual layout
  left to manual review.
- Target: agents and pipeline at high coverage; infra adapters at "smoke + happy
  path."

## 12. Development roadmap

Each phase is independently shippable; the app is never left half-built.

- **Phase 1 — Foundation.** Repo skeleton, DI container, config system, SQLite +
  migrations, paths/logging/errors, plugin registry, GUI shell with sidebar +
  Dashboard + empty views. *Shippable: app launches, shows dashboard, persists
  config.*
- **Phase 2 — Content & intelligence.** Reddit `ContentSource` (PRAW), Research
  + Analyzer + Rewriter agents, LLM provider (Ollama), prompts. *Shippable:
  discover → score → rewrite, results in DB and a Research view.*
- **Phase 3 — Media generation.** Voice (Piper), Subtitle (faster-whisper word
  timings + ASS styler), Editor (ffmpeg compose), Music, Video Library.
  *Shippable: script → rendered video file on disk, no approval UI yet.*
- **Phase 4 — Publish & approval.** Approval queue + view, Thumbnail, SEO,
  YouTube Publisher (OAuth + resumable upload + retries), scheduling.
  *Shippable: full pipeline story→upload with human gate.*
- **Phase 5 — Hardening.** Analytics agent + view, first-run wizard + model
  downloader, PyInstaller packaging for all 3 OSes, plugin authoring docs, full
  test pass, performance pass.

## 13. Non-goals (explicit, for now)

- No cloud sync / multi-device.
- No multi-user / team collaboration.
- No mobile app.
- No transcription of arbitrary uploaded media (this is a creator, not an
  editor — OmniCut already owns that space).
- No bundled music (user supplies tracks).
