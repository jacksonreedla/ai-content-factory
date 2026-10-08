# AI Content Factory

Desktop app that automates faceless short-form video production: fetch Reddit
stories → AI-score them → rewrite into narration → (voice → captions → video →
thumbnail) → SEO metadata → **post to TikTok**. Built modular so new content
sources, AI models, and platforms plug in without rewrites.

**Current status: v1.0 — all ten agents live.** The complete loop:
Reddit research → AI scoring → AI rewriting → voiceovers → Whisper captions →
rendered videos with music ducking and thumbnails → SEO metadata →
**TikTok direct-post upload** → analytics → revenue estimates.

Highlights added since v1.0:

- **Credential-free Reddit sourcing *with real upvote/comment counts*** via a
  public archive API — so `min_upvotes` filtering works without a Reddit API
  key (see *Content sources → reddit*).
- **Multi-account round-robin** — produced videos are spread evenly across your
  configured accounts so no two accounts ever post the same story.
- **AI top-up safety net** — thin research runs are automatically filled with
  original AI stories so no account runs dry.
- **Narration text cleaning** — Reddit markdown/links/zero-width junk is
  stripped before TTS.

## Setup (Windows)

1. **Python 3.11+** — check with `python --version`
2. **Install dependencies**
   ```
   cd Ai_Factory
   pip install -r requirements.txt
   ```
3. **Ollama** (the default free AI backend)
   - Install from https://ollama.com
   - Pull a model: `ollama pull llama3.1`
   - Ollama runs at `http://localhost:11434` automatically.
4. **Run it**
   ```
   python main.py
   ```
   Headless (no GUI): `python main.py --headless` or `python main.py --stage research`

> **Auto-uploading needs TikTok API credentials.** Everything up to a rendered,
> captioned video works with zero external accounts. Posting to TikTok requires
> a TikTok developer app (see *TikTok setup*). Until that's connected, finished
> videos simply wait in `data/output/`.

## Content sources

The Research stage pulls from any combination of sources set in
`sources.enabled` (Settings → `config.json`): `reddit`, `rss`, `ai`. Each source
runs independently — one failing is logged and skipped rather than killing the
run. After all sources run, the **AI top-up safety net** tops the batch up to a
minimum (see below).

- **`reddit`** — the primary source. With **approved Reddit API credentials**
  (`reddit.client_id`/`client_secret`) it uses PRAW (full data, high limits).
  **Without credentials it still gets real scores**, via `reddit.public_method`:

  | method    | data | notes |
  |-----------|------|-------|
  | `auto` *(default)* | real upvotes | **archive** first, per-sub **rss** fallback |
  | `archive` | real upvotes/comments | public archive API, no key |
  | `json`    | real upvotes/comments | Reddit `.json` — usually hard-blocked (403) now |
  | `rss`     | no scores | Reddit RSS — last resort, `min_upvotes` can't apply |

  The **archive** path (`api/reddit_archive.py`) reads a public Pushshift-style
  archive that re-scans posts after they collect votes, so older posts carry
  their *matured* score. It pulls posts from the last `archive_window_days` (45)
  but skips anything newer than `archive_min_maturity_hours` (24) so scores have
  settled. Busy subs that return HTTP 422 ("window too broad") auto-narrow their
  window down to `archive_min_window_days` (5) before falling back to RSS.
  Best for **text-story** subs (AITAH, TIFU, TrueOffMyChest, MaliciousCompliance,
  nosleep…); question/image subs (AskReddit, funny…) carry no body text and get
  filtered out — don't add them.

- **`rss`** — any RSS/Atom feeds in `rss.feeds`. No key, works immediately.
  Uses `feedparser` if installed, else a stdlib parser.

- **`ai`** — original stories written by your LLM from `ai_stories.theme`. Zero
  external dependency, fully original content. Edit `prompts/generate_story.txt`.

### Never run dry: AI top-up safety net

After the sources run, if the number of **new** stories is below a target, the
Research agent generates original AI stories to fill the gap (`_maybe_topup` in
`agents/research_agent.py`). The target defaults to
`num_accounts × ai_stories.topup_per_account` (so 3 accounts → 9). It only fills
the shortfall, is capped by `ai_stories.topup_max`, and a failure (e.g. LLM
offline) is non-fatal. It even rescues a run where every content source failed.
Config: `ai_stories.topup_enabled`, `topup_target` (0 = auto), `topup_per_account`,
`topup_max`.

## Multi-account posting (round-robin)

Configure accounts in `accounts` (Settings → Accounts). When
`publish.rotate_accounts` is on (default), each produced video is stamped with
the **next account in rotation** (`app/accounts.py::rotate_account`, applied in
`agents/voice_agent.py`). The rotation counter is persisted in the
`app_settings` table (`account_rotation_index`), so the A→B→C cycle continues
across separate runs. Combined with de-duplication (each story is stored once by
`(source, source_id)` and produced once), **no two accounts ever post the same
story.**

> **Run ONE instance / ONE database for all accounts.** Running separate copies
> gives each its own DB, so they'd independently grab the same top stories and
> post duplicates. One app, one `data/factory.db`, accounts rotated inside it.

## Using it

1. **Settings → AI providers** — *Test provider availability* to confirm Ollama
   is online; set the model per task (e.g. `llama3.1`).
2. **Research** — subreddits + filters are pre-set; click *Save & fetch stories*.
3. **Stories** — with `scoring.auto_approve` on (default in this build), stories
   above `scoring.min_overall_score` flow straight to rewrite. Turn it off for
   manual review.
4. **Dashboard → Generate** runs the whole pipeline in one click.
5. Adding a **Claude API key** in Settings later instantly enables Claude as a
   provider/fallback — no code changes.

## Tests

```
pip install pytest feedparser
python -m pytest tests -q
```

220+ tests, no network required (all sources are monkeypatched).

## For future contributors — where things live

- **Pipeline / agents** (`agents/`): research → score → rewrite → voice →
  captions → editor → thumbnail → seo → publisher → analytics. Each subclasses
  `Agent` and is independently runnable via `python main.py --stage <name>`.
- **Reddit sourcing**:
  - `api/reddit_client.py` — PRAW client, pure-function filters
    (`passes_filters`), `clean_story_text` (TTS cleanup), the public `.json`
    client (`RedditJSONClient`), and `normalize_subreddit`.
  - `api/reddit_archive.py` — **the credential-free real-upvote source**
    (`RedditArchiveClient`, `parse_archive_json`, `reddit_archive_url`).
  - `api/rss_client.py` — RSS/Atom source + Reddit-RSS fallback.
  - `agents/research_agent.py` — orchestrates sources, the archive/json/rss
    dispatch (`_run_reddit_public`), and the AI top-up (`_maybe_topup`).
- **Accounts**: `app/accounts.py` (helpers), assignment in
  `agents/voice_agent.py`, rendering in `editor/title_card.py::resolve_account`,
  stored on `videos.account`.
- **Config**: defaults + deep-merge in `app/config.py` (`DEFAULTS`); live values
  in `settings/config.json`. Access via dot-paths: `config.get("reddit.min_upvotes")`.
- **Data**: SQLite via `database/db.py` (migrations in `migrate`) and typed
  `database/repositories.py`. Stories de-dupe on `(source, source_id)`.
- **LLM**: `api/llm/` router picks a provider per task with fallback; prompts are
  editable text in `prompts/`.

**Key config knobs** (all under `settings/config.json`, inherit from `DEFAULTS`):

| key | purpose |
|-----|---------|
| `reddit.public_method` | `auto` \| `archive` \| `json` \| `rss` |
| `reddit.min_upvotes` / `min_comments` / `min_words` | quality filters (need real scores) |
| `reddit.archive_window_days` / `archive_min_maturity_hours` / `archive_min_window_days` | archive window + 422 narrowing floor |
| `ai_stories.topup_*` | AI top-up safety net |
| `publish.rotate_accounts` | round-robin account assignment |
| `scoring.auto_approve` / `min_overall_score` | hands-off vs manual approval |

When adding a **new content source**: implement fetch → `Story` objects, wire
into `ResearchAgent` (or ship a plugin `content_sources()` hook). Keep network
(fetch) separate from parsing/filtering (pure functions) so it's unit-testable
without network, matching the existing sources. See `docs/ARCHITECTURE.md`.

## Voice setup

The default engine is **Kokoro** — free, local, high-quality neural voices —
using the **ONNX** build. Default voice **`am_adam`**. Enable with:

```
pip install kokoro-onnx onnxruntime
```

On first render the model files (~90 MB) download into `data/models/`. Pick a
different voice in **Settings → Voice** (`am_michael`, `af_heart`, …). If Kokoro
isn't installed, the pipeline falls back to Windows SAPI so it still makes audio.

> Do **not** `pip install kokoro` (PyTorch build) on Python 3.13 — it pins
> `numpy==1.26.4` which has no 3.13 wheel. Use `kokoro-onnx` above.

Other engines (Settings → Voice): Windows **SAPI** (zero setup), **Piper**
(set exe + `.onnx` model paths), **ElevenLabs** (paste key). Install FFmpeg
(`winget install ffmpeg`) for normalization/trim — skipped gracefully if missing.

Captions: first run downloads the Whisper model (~74 MB for `base`). Word mode →
`.ass` (big-bold-word Shorts look); sentence mode → `.srt`.

## Video setup

1. **FFmpeg required**: `winget install ffmpeg`, then restart.
2. **Background clips**: drop gameplay `.mp4`s into
   `data/media_library/minecraft/` (or any category folder; pick it in
   Settings → Pipeline). Clips loop and auto-crop to format.
3. **Music (optional)**: drop tracks into `data/music/`; auto-ducks under
   narration.
4. Videos page → **Render videos**, then **Generate thumbnails**. Output lands
   in `data/output/`.

## TikTok setup (one time, free — needs TikTok app approval)

**Auto-uploading does not work until this is connected.** TikTok is the sole
publisher, using the official **Content Posting API** (Direct Post). Full
step-by-step in `docs/tiktok_api_request.md`. Short version:

1. At https://developers.tiktok.com create an app; add **Login Kit** and
   **Content Posting API**; enable **Direct Post**.
2. Request scopes `user.info.basic` and `video.publish`; register redirect URI
   `http://localhost:53682/callback`.
3. Paste the **Client Key** and **Client Secret** into **Settings → Upload**
   (or `settings/config.json` under `tiktok`).
4. In the app: **Uploads → Connect TikTok** → sign in.
5. **Uploads → Post rendered videos**, or run the whole pipeline.

Notes: **until your app passes TikTok's audit, every post is forced to private
(`SELF_ONLY`)** regardless of the visibility you pick — videos still upload to
your own profile privately. `upload.default_visibility` stays `private` until
you've passed the audit, then set it to `public`. `video.publish` allows ~6
upload initiations/min per user plus a daily cap.

### Closing engagement question

Every narration ends with a short audience question (e.g. "Am I in the wrong?")
to drive comments — generated per-story, spoken and captioned at the end, with a
fallback from `rewrite.engagement_fallbacks` if the AI is offline. Toggle in
Settings → Pipeline; edit `prompts/engagement_question.txt`.

### Tags & auto-summary

In **Settings → Upload**, set tags you always want added plus an optional short
auto-summary. The SEO stage merges your tags into every video (optionally as
`#hashtags`) and writes a concise description from the narration, even if the AI
metadata step is skipped.

## Roadmap

- ~~Phase 2 — Audio~~ ✔ · ~~Phase 3 — Video~~ ✔ · ~~Phase 4 — Publishing~~ ✔ ·
  ~~Phase 5 — Intelligence~~ ✔
- **Future ideas**: Instagram Reels / YouTube Shorts publishers and extra LLM
  backends via the plugin system (`plugins/`); a proper TikTok analytics source
  (Display/Research API) for true views/watch-time; A/B thumbnail testing;
  archive-source backfill to pre-build a large story backlog.
