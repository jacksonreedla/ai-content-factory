# Phase 4 — Publish & Approval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Build the approval gate that splits the pipeline, plus the post-approval stages: thumbnail generation, SEO generation, and YouTube upload — so the full pipeline runs story → uploaded video (private/draft by default) with a mandatory human approval click.

**Architecture:** `ApprovalService` exposes approve/reject/edit/regenerate against jobs in `AWAITING_APPROVAL`. Approving enqueues the job at THUMBNAIL; the worker pool then chains THUMBNAIL → SEO → PUBLISH automatically. `ThumbnailRenderer` and `SEOGenerator` are plugin contracts (Pillow + LLM built-ins); `Publisher` is a contract with the YouTube Data API v3 built-in (OAuth, resumable upload, retries).

**Tech Stack:** Pillow (thumbnails), LLM (SEO), google-api-python-client + google-auth-oauthlib (YouTube), PySide6.

## Global Constraints

- **Nothing publishes without an explicit human approve.** The pipeline holds at `AWAITING_APPROVAL`; only `ApprovalService.approve()` advances to THUMBNAIL.
- Default upload privacy = `draft` (configurable). Public/scheduled require explicit choice in the UI.
- OAuth tokens stored in `~/.aicf/secrets.json` (encrypted-at-rest is Phase 5; for now 0600 perms).
- All publisher/thumbnail/SEO tests use fakes; YouTube API tests skip without creds.
- TDD throughout.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `app/approval_service.py` | `ApprovalService` — approve/reject/edit/regenerate/list_pending |
| `plugins/thumbnails/__init__.py` | package marker |
| `plugins/thumbnails/pillow_renderer.py` | `PillowThumbnailRenderer(ThumbnailRenderer)` |
| `config/thumbnail_templates.json` | layout templates |
| `plugins/seo/__init__.py` | package marker |
| `plugins/seo/llm_seo.py` | `LLMSEOGenerator(SEOGenerator)` |
| `config/prompts/seo.txt` | SEO prompt template |
| `config/seo_schema.json` | JSON schema for SEO output |
| `plugins/publishing/__init__.py` | package marker |
| `plugins/publishing/youtube/__init__.py` | package marker |
| `plugins/publishing/youtube/publisher.py` | `YouTubePublisher(Publisher)` |
| `infra/youtube/oauth.py` | OAuth flow + token storage |
| `agents/thumbnail_agent.py` | THUMBNAIL stage |
| `agents/seo_agent.py` | SEO stage |
| `agents/publishing_agent.py` | PUBLISH stage |
| `gui/views/approval.py` | Approval view |
| `gui/views/pipeline.py` | Pipeline/queue view |

---

### Task 1: ApprovalService

- `app/approval_service.py`:
  - `list_pending()` → jobs at `AWAITING_APPROVAL` with their video + script.
  - `approve(job_id, privacy=None)` → set `approval_state=approved`, enqueue at THUMBNAIL.
  - `reject(job_id)` → set `approval_state=rejected`, status done.
  - `edit(job_id, title, description)` → patch the SEO row (created lazily) or store on job.
  - `regenerate(job_id, stage)` → reset and re-enqueue at the given stage.
- Tests with a real migrated DB + fake pool.

### Task 2: thumbnail renderer (Pillow)

- `config/thumbnail_templates.json`: e.g. `{"bold_lower": {"bg_color": "#0e0f13", "accent": "#ff2db7", "font_size": 96, ...}}`.
- `PillowThumbnailRenderer.render(template, lines, out_path, bg_path=None)` → PNG. Large readable text, accent bar, optional background image. Falls back to a system font if Josefin Sans isn't installed.
- Tests render a real PNG and assert size.

### Task 3: SEO generator (LLM)

- `config/prompts/seo.txt` + `config/seo_schema.json` (title, description, tags[], hashtags[], pinned_comment, community_post, ctr_score, seo_score).
- `LLMSEOGenerator.generate(video, script) -> SEOResult`.
- Tests with FakeLLM.

### Task 4: thumbnail + seo agents

- `agents/thumbnail_agent.py`: reads video, renders 2-3 thumbnail variants, persists.
- `agents/seo_agent.py`: reads video + script, generates SEO, persists `seo` row.

### Task 5: YouTube OAuth + publisher

- `infra/youtube/oauth.py`: `run_oauth_flow(client_secrets_path, token_path)` → saves token; `load_credentials(token_path)`.
- `plugins/publishing/youtube/publisher.py`: `YouTubePublisher.upload(video, seo, privacy)` — resumable upload via google-api-python-client, with exponential-backoff retries. Marked to skip in tests without creds.
- Tests: fake the google client; assert retry + persistence behavior.

### Task 6: publishing agent + wiring

- `agents/publishing_agent.py`: calls publisher, persists `publishes` row, handles retries by raising (runner marks failed).
- Container: register all Phase 4 plugins + agents. Approval service exposed on container.

### Task 7: Approval view

- `gui/views/approval.py`: list of pending jobs (left), preview pane (right) with thumbnail variants, editable title/description, Approve/Reject/Edit/Regenerate buttons. Privacy dropdown for approve.
- Tests: view builds, populates from a seeded DB, buttons wired.

### Task 8: Pipeline view (live queue)

- `gui/views/pipeline.py`: table of jobs with stage/status/progress, refresh on signal bus, right-click pause/retry/cancel.
- Tests: view builds, populates.

### Self-review
After Task 8: a story can flow through the entire pipeline to a (draft) YouTube upload, gated by human approval. Phase 4 deliverable met.

---

Phase 4 deliverable: full pipeline story→upload with human gate.
