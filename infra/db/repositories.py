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
