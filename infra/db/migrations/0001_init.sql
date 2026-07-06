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
