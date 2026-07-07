# Phase 5 — Hardening & Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Complete the application: analytics, the four remaining views (Library, Settings, Logs, History), a first-run setup wizard, and PyInstaller packaging — so the app is distributable and production-ready.

**Architecture:** Reuses all Phase 1-4 infrastructure. `AnalyticsAgent` runs on a schedule (background QTimer), pulling metrics via the `AnalyticsSource` contract. The first-run wizard is a `QDialog` shown when `secrets.json` is absent or incomplete. PyInstaller `--onedir` spec per platform.

**Tech Stack:** Everything from Phases 1-4 + pyinstaller (build).

## Global Constraints

- No new external runtime deps beyond pyinstaller (build-time only).
- All new views follow the established container-injection pattern.
- Wizard never blocks startup on missing optional components (Ollama, Piper) — only requires secrets when the user wants those features.
- Same TDD + layering rules.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `plugins/analytics/__init__.py` | package marker |
| `plugins/analytics/youtube/source.py` | `YouTubeAnalyticsSource` |
| `agents/analytics_agent.py` | scheduled analytics pull |
| `app/system_checks.py` | ffmpeg/Ollama/Piper/whisper availability |
| `infra/models.py` | model downloader stub (first-run) |
| `gui/views/library.py` | media library browser |
| `gui/views/settings.py` | tabbed settings (General, Sources, LLM, Voice, Editor, Publishing, Secrets, About) |
| `gui/views/logs.py` | live log tail |
| `gui/views/history.py` | all jobs/publishes/analytics table |
| `gui/wizard.py` | first-run setup wizard dialog |
| `aicf.spec` | PyInstaller spec |
| `docs/PLUGIN_AUTHORING.md` | plugin authoring guide |

---

### Task 1: analytics source + agent + schedule

- `plugins/analytics/youtube/source.py`: `YouTubeAnalyticsSource.fetch(publish) -> AnalyticsPoint` via the YouTube API (uses the same client as the publisher).
- `agents/analytics_agent.py`: `run_once(conn, source)` iterates all `publishes` with `status=done`, fetches fresh metrics, inserts `analytics` rows. Idempotent by `fetched_at`.
- Container: add a `QTimer`-driven scheduler that calls `run_once` hourly (configurable). Tests cover the agent with a fake source.

### Task 2: system checks + first-run wizard

- `app/system_checks.py`: `check_all()` → `{ffmpeg, ffprobe, ollama, piper, whisper, models_dir}` status dict. Pure checks, no side effects.
- `gui/wizard.py`: `FirstRunWizard(QDialog)` — multi-page: welcome → ffmpeg (offer download) → Ollama (host check) → Reddit creds → YouTube OAuth → done. Writes `secrets.json` on finish.
- `main.py`: show wizard on first run (when `secrets.json` missing).

### Task 3: Library view

- `gui/views/library.py`: browse backgrounds/music/logos/intros/outros; add (file picker) → inserts `media_library` row + copies into `library/`; remove. Categories map to the spec's named folders.

### Task 4: Settings view

- `gui/views/settings.py`: tabbed. Edits every config section via dataclass binding; Save writes `settings.json`. Separate "Secrets" tab for Reddit creds + YouTube client secrets file picker + "Run OAuth" button.

### Task 5: Logs + History views

- `gui/views/logs.py`: tail of the rotating log, fed by `GUILogHandler.set_sink`; filter by level.
- `gui/views/history.py`: table joining jobs → videos → publishes → latest analytics, filterable.

### Task 6: PyInstaller packaging + plugin docs

- `aicf.spec`: onedir, include `config/`, `assets/`, `gui/theme/`, hidden imports for faster-whisper/pillow.
- `docs/PLUGIN_AUTHORING.md`: how to write a plugin (plugin.toml + Protocol + registration).
- Build script `scripts/build.sh` (per-OS stubs).

### Self-review
After Task 6: app is feature-complete, distributable, and documented. All 8 sidebar views real. Final test pass green.

---

Phase 5 deliverable: production-ready, distributable application.
