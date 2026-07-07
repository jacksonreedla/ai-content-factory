# agents/analytics_agent.py
import logging
import sqlite3

from infra.db.repositories import insert_media  # noqa: F401  (kept for symmetry)

log = logging.getLogger(__name__)


def run_once(conn: sqlite3.Connection, source) -> int:
    """Pull fresh metrics for every successful publish. Returns count inserted.

    Idempotent within a run: each call appends one analytics row per publish.
    The scheduler calls this hourly.
    """
    if source is None:
        return 0
    rows = conn.execute(
        "SELECT * FROM publishes WHERE status='done' AND remote_id != ''"
    ).fetchall()
    inserted = 0
    for p in rows:
        point = source.fetch(p)
        conn.execute(
            "INSERT INTO analytics (publish_id, views, likes, comments, shares, "
            "watch_time_min, ctr, retention_pct) VALUES (?,?,?,?,?,?,?,?)",
            (p["id"], point.views, point.likes, point.comments, point.shares,
             point.watch_time_min, point.ctr, point.retention_pct),
        )
        inserted += 1
    conn.commit()
    if inserted:
        log.info("analytics: inserted %d points", inserted)
    return inserted
