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


def set_approval_state(conn: sqlite3.Connection, job_id: int, state) -> None:
    s = state.value if hasattr(state, "value") else str(state)
    conn.execute(
        "UPDATE jobs SET approval_state=?, updated_at=datetime('now') WHERE id=?",
        (s, job_id))
    conn.commit()


def count_jobs_by_status(conn: sqlite3.Connection, status: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM jobs WHERE status=?", (status,)).fetchone()
    return row["n"] if row else 0


# --- Stories ---------------------------------------------------------------

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


def list_stories(conn, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM stories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


# --- Scores ----------------------------------------------------------------

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


# --- Scripts ---------------------------------------------------------------

def insert_script(conn, story_id: int, script) -> int:
    cur = conn.execute(
        "INSERT INTO scripts (story_id, style, model, text, word_count, reading_time) "
        "VALUES (?,?,?,?,?,?)",
        (story_id,
         script.style.value if hasattr(script.style, "value") else str(script.style),
         script.model, script.text, script.word_count, script.reading_time),
    )
    conn.commit()
    return cur.lastrowid


def get_script_by_story(conn, story_id: int):
    return conn.execute(
        "SELECT * FROM scripts WHERE story_id=? ORDER BY id DESC LIMIT 1",
        (story_id,)).fetchone()


# --- Voice clips -----------------------------------------------------------

def insert_voice_clip(conn, script_id: int, engine: str, voice: str,
                      speed: float, pitch: float, emotion: str,
                      duration_sec: float, audio_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO voice_clips (script_id, engine, voice, speed, pitch, "
        "emotion, duration_sec, audio_path) VALUES (?,?,?,?,?,?,?,?)",
        (script_id, engine, voice, speed, pitch, emotion,
         duration_sec, audio_path),
    )
    conn.commit()
    return cur.lastrowid


def get_voice_clip_by_job(conn, job_id: int):
    return conn.execute(
        "SELECT vc.* FROM voice_clips vc "
        "JOIN scripts s ON vc.script_id=s.id "
        "JOIN stories st ON s.story_id=st.id "
        "WHERE st.job_id=?", (job_id,)).fetchone()


# --- Subtitles -------------------------------------------------------------

def insert_subtitle(conn, voice_clip_id: int, fmt: str, styler: str,
                    ass_path: str, srt_path: str) -> int:
    cur = conn.execute(
        "INSERT INTO subtitles (voice_clip_id, format, styler, ass_path, srt_path) "
        "VALUES (?,?,?,?,?)",
        (voice_clip_id, fmt, styler, ass_path, srt_path),
    )
    conn.commit()
    return cur.lastrowid


def get_subtitle_by_job(conn, job_id: int):
    return conn.execute(
        "SELECT sub.* FROM subtitles sub "
        "JOIN voice_clips vc ON sub.voice_clip_id=vc.id "
        "JOIN scripts s ON vc.script_id=s.id "
        "JOIN stories st ON s.story_id=st.id "
        "WHERE st.job_id=?", (job_id,)).fetchone()


# --- Videos ----------------------------------------------------------------

def insert_video(conn, job_id: int, format: str, aspect: str,
                 width: int, height: int, duration_sec: float,
                 background_id, music_id, video_path: str,
                 thumbnail_path: str, size_bytes: int) -> int:
    cur = conn.execute(
        "INSERT INTO videos (job_id, format, aspect, width, height, duration_sec, "
        "background_id, music_id, video_path, thumbnail_path, size_bytes) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (job_id, format, aspect, width, height, duration_sec,
         background_id, music_id, video_path, thumbnail_path, size_bytes),
    )
    conn.commit()
    return cur.lastrowid


def get_video_by_job(conn, job_id: int):
    return conn.execute(
        "SELECT * FROM videos WHERE job_id=? ORDER BY id DESC LIMIT 1",
        (job_id,)).fetchone()


# --- Media library ---------------------------------------------------------

def list_media(conn, kind: str = "", category: str = "") -> list:
    sql = "SELECT * FROM media_library WHERE 1=1"
    args: list = []
    if kind:
        sql += " AND kind=?"; args.append(kind)
    if category:
        sql += " AND category=?"; args.append(category)
    sql += " ORDER BY id DESC"
    return conn.execute(sql, args).fetchall()


def insert_media(conn, kind: str, category: str, name: str, path: str,
                 duration_sec: float = 0.0, resolution: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO media_library (kind, category, name, path, duration_sec, resolution) "
        "VALUES (?,?,?,?,?,?)",
        (kind, category, name, path, duration_sec, resolution),
    )
    conn.commit()
    return cur.lastrowid
