# Architecture

## Layers

```
GUI (PySide6)  ──────  main_window + pages, all work on QThreads
      │
Pipeline orchestrator (app/pipeline.py)  ──  jobs, progress, events
      │
Agents (agents/)  ──  one responsibility each, run in order (all live):
  research → score → rewrite → voice → captions → edit → thumbnail → seo → upload → analytics
Services
  ├─ LLM Router (api/llm/)      provider-per-task + fallback chain
  ├─ Content sources (api/)     reddit_client (PRAW/.json + filters + TTS
  │                             clean), reddit_archive (credential-free, REAL
  │                             upvotes), rss_client; pure-function filters
  ├─ TikTok client (api/)       Content Posting API: OAuth + chunked direct post
  ├─ Prompt manager (app/)      editable templates in prompts/
  └─ Repositories (database/)   typed SQL, SQLite/WAL, thread-local conns
```

## Key decisions

- **Agents are stateless**; all state lives in SQLite. Any stage can be re-run.
- **Reddit without an API key still gets real scores**: `reddit_archive.py`
  reads a public archive that re-scans posts for matured vote counts, so
  `min_upvotes` filtering works. `research_agent` dispatches archive→rss (auto)
  and tops thin runs up with AI stories (`_maybe_topup`).
- **Multi-account**: videos are assigned accounts round-robin in `voice_agent`
  (`app/accounts.py`), counter persisted in `app_settings`; one DB per install
  so stories never repeat across accounts.
- **AgentContext** carries config, db, llm router, prompts, and a progress
  callback through a run. Agents communicate only via the database and
  `ctx.data`.
- **StubAgent** placeholders return `skipped=True` so the full pipeline runs
  end-to-end before every phase is built.
- **LLMRouter**: `ai.tasks.<task>` in config maps each task to provider+model;
  unavailable providers are skipped down `ai.fallback_order`. A provider is
  "available" if its server responds (Ollama) or a key is set (Claude/OpenAI).
  Plugins can register extra providers.
- **Events** (`app/events.py`): worker threads publish, GUI pages poll/apply
  on timers — no cross-thread Qt calls.
- **Config**: `settings/config.json` (editable in GUI), deep-merged over
  defaults. Runtime KV state lives in the `app_settings` table.

## Database tables

`stories`, `narrations`, `videos`, `jobs`, `uploads`, `api_usage`,
`analytics`, `app_settings`, `schema_version`. Migrations are stepwise in
`database/db.py::migrate`.

## Adding things

- **New content source**: implement fetch → `Story` objects, wire into
  ResearchAgent (or ship as a plugin `content_sources()` hook).
- **New LLM provider**: subclass `LLMProvider`, register via plugin
  `llm_providers()` hook or add to `LLMRouter.providers`.
- **New pipeline stage**: subclass `Agent`, add to `agents/registry.py`.
- **New publisher**: plugin `publishers()` hook, or follow `api/tiktok_client.py`
  + `agents/publisher_agent.py` as a template (client does OAuth + transport,
  the agent maps SEO metadata → the platform's post fields).

## Publishing (TikTok)

The `upload` stage direct-posts to TikTok via `api/tiktok_client.py`:
OAuth (Login Kit, local-redirect flow, token in `data/tiktok_token.json`) →
`creator_info/query` (to learn allowed privacy levels) → `video/init/` →
chunked `PUT` upload → poll `status/fetch/` until published. `PublisherAgent`
builds the caption from the SEO title/description/hashtags, resolves the
configured visibility to a TikTok privacy level (falling back to `SELF_ONLY`
when the account/app doesn't allow the requested one), and labels posts as
AI-generated. Unaudited apps are forced to `SELF_ONLY` by TikTok. TikTok's
posting API returns no view/like stats, so the analytics stats pass is a no-op
unless a separate stats source is connected.

## Phase plan (all complete)

1. Foundation — DB, config, agents, LLM router, Reddit, GUI. ✔
2. Audio — `voices/` TTS engines, `subtitles/` Whisper captioner. ✔
3. Video — `editor/` FFmpeg renderer, thumbnails, media library. ✔
4. Publishing — TikTok Content Posting API (Direct Post), OAuth, notifications. ✔
5. Intelligence — `analytics/insights.py` learns best styles/times. ✔
