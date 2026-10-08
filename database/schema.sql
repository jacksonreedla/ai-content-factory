-- AI Content Factory schema (v1)

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,
    source_id       TEXT NOT NULL,
    subreddit       TEXT DEFAULT '',
    title           TEXT NOT NULL,
    author          TEXT DEFAULT '',
    url             TEXT DEFAULT '',
    text            TEXT NOT NULL,
    upvotes         INTEGER DEFAULT 0,
    num_comments    INTEGER DEFAULT 0,
    created_utc     REAL DEFAULT 0,
    nsfw            INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'new',
    scores_json     TEXT,
    overall_score   REAL DEFAULT 0,
    rejected_reason TEXT DEFAULT '',
    fetched_at      TEXT DEFAULT (datetime('now')),
    UNIQUE (source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_stories_status ON stories (status);
CREATE INDEX IF NOT EXISTS idx_stories_score  ON stories (overall_score DESC);

CREATE TABLE IF NOT EXISTS narrations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id       INTEGER NOT NULL REFERENCES stories (id) ON DELETE CASCADE,
    style          TEXT NOT NULL,
    target_seconds INTEGER NOT NULL,
    text           TEXT NOT NULL,
    provider       TEXT DEFAULT '',
    model          TEXT DEFAULT '',
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS videos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id       INTEGER REFERENCES stories (id) ON DELETE SET NULL,
    narration_id   INTEGER REFERENCES narrations (id) ON DELETE SET NULL,
    title          TEXT DEFAULT '',
    format         TEXT DEFAULT 'shorts',
    status         TEXT DEFAULT 'draft',
    file_path      TEXT DEFAULT '',
    audio_path     TEXT DEFAULT '',
    captions_path  TEXT DEFAULT '',
    thumbnail_path TEXT DEFAULT '',
    card_path      TEXT DEFAULT '',      -- generated Reddit-style title card image
    duration_s     REAL DEFAULT 0,
    intro_seconds  REAL DEFAULT 0,       -- length of the spoken title (card display time)
    account        TEXT DEFAULT '',      -- title-card account override ('' = config default)
    metadata_json  TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    type         TEXT NOT NULL,
    status       TEXT DEFAULT 'pending',
    priority     INTEGER DEFAULT 5,
    stage        TEXT DEFAULT '',
    progress     REAL DEFAULT 0,
    payload_json TEXT,
    error        TEXT DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now')),
    started_at   TEXT,
    finished_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status, priority);

CREATE TABLE IF NOT EXISTS uploads (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id     INTEGER NOT NULL REFERENCES videos (id) ON DELETE CASCADE,
    platform     TEXT DEFAULT 'youtube',
    remote_id    TEXT DEFAULT '',
    visibility   TEXT DEFAULT 'private',
    scheduled_at TEXT,
    uploaded_at  TEXT,
    status       TEXT DEFAULT 'pending',
    error        TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS api_usage (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    provider   TEXT NOT NULL,
    model      TEXT DEFAULT '',
    task       TEXT DEFAULT '',
    tokens_in  INTEGER DEFAULT 0,
    tokens_out INTEGER DEFAULT 0,
    cost_usd   REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analytics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id    INTEGER REFERENCES videos (id) ON DELETE CASCADE,
    metric      TEXT NOT NULL,          -- views | ctr | avg_watch_time | subs | revenue
    value       REAL NOT NULL,
    recorded_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
