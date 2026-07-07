# AI Content Factory

Automated faceless YouTube video creation from Reddit stories. Cross-platform
PySide6 desktop application.

Finds high-performing Reddit stories → ranks/scores them with AI → rewrites for
narration → generates voiceover + subtitles → composes with background gameplay
+ music → renders thumbnails + SEO metadata → and uploads to YouTube — **gated
by a mandatory human approval click**. Everything runs locally; nothing is
published without approval.

## Status

All five phases complete:

- ✅ **Phase 1 — Foundation:** layered skeleton, config, SQLite + migrations,
  plugin registry, pipeline state machine + worker pool, GUI shell + Dashboard
- ✅ **Phase 2 — Content & Intelligence:** Reddit ContentSource (PRAW),
  Ollama LLM provider, Research/Analyzer/Rewriter agents, Research view
- ✅ **Phase 3 — Media Generation:** Piper TTS (with silent fallback),
  faster-whisper subtitles, ASS caption styler, FFmpeg editor, Music ducker
- ✅ **Phase 4 — Publish & Approval:** ApprovalService gate, Pillow thumbnails,
  LLM SEO, YouTube publisher (resumable + retries), Approval + Pipeline views
- ✅ **Phase 5 — Hardening:** analytics, first-run wizard, Library/Settings/
  Logs/History views, PyInstaller spec, plugin docs

**119 tests passing**, including real ffmpeg rendering and YouTube retry logic.

See `docs/superpowers/specs/2026-07-06-ai-content-factory-design.md` for the
full architecture and `docs/superpowers/plans/` for per-phase plans.

## Architecture

Layered monolith (GUI → services → domain → infra) with dependency injection
and a plugin registry. Every swappable capability is behind a Protocol
contract (`ContentSource`, `LLMProvider`, `VoiceEngine`, `CaptionStyler`,
`VideoEditor`, `MusicTrack`, `ThumbnailRenderer`, `SEOGenerator`, `Publisher`,
`AnalyticsSource`). Reddit is *just the first content source*; YouTube is
*just the first publisher*. Add new ones without touching core — see
`docs/PLUGIN_AUTHORING.md`.

The pipeline is a persisted state machine with a worker pool:

```
RESEARCH → ANALYZE → REWRITE → VOICE → SUBTITLE → EDIT
    → [AWAITING_APPROVAL gate] → THUMBNAIL → SEO → PUBLISH
```

Each stage commits to SQLite, so jobs survive crashes and resume. The approval
gate is the load-bearing feature: **nothing passes it without a human click**.

## Quick start (development)

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Run the test suite (offscreen Qt; no display needed)
QT_QPA_PLATFORM=offscreen .venv/bin/pytest

# Launch the app (needs a display; on first run it shows a setup wizard)
.venv/bin/python main.py
```

User data lives under `~/.aicf/` (override with `$AICF_HOME` for tests):
`aicf.db`, `settings.json`, `secrets.json` (chmod 0600), `logs/`, `library/`,
`jobs/`, `plugins/`.

## External dependencies (detected at runtime)

| Tool | Required for | If missing |
|------|--------------|------------|
| `ffmpeg` / `ffprobe` | rendering video | required — install via your package manager |
| [Ollama](https://ollama.com) | LLM scoring/rewriting/SEO | agents that need an LLM will fail; use the OpenAI plugin instead |
| `piper` binary | TTS voiceover | falls back to a silent wav so the pipeline still runs |
| `faster-whisper` | subtitle word timings | SUBTITLE stage skipped |

Reddit API credentials and YouTube OAuth are configured in Settings or via the
first-run wizard.

## Building a distributable

```bash
./scripts/build.sh   # runs tests, then pyinstaller aicf.spec
# → dist/AIContentFactory/
```

Wrap the resulting folder with an OS installer (NSIS / dmgbuild / AppImage) —
ffmpeg and AI models are downloaded on first run to keep the installer small.

## Tech stack

Python 3.12+ · PySide6 (QWidgets + QSS) · SQLite · FFmpeg · faster-whisper ·
PRAW · httpx (Ollama) · Pillow · google-api-python-client (YouTube) · pytest /
pytest-qt.
