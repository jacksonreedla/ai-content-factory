# gui/viewmodels.py
import sqlite3
from dataclasses import dataclass


@dataclass
class DashboardStats:
    videos_created: int = 0
    videos_uploaded: int = 0
    videos_pending: int = 0
    current_jobs: int = 0


def compute_dashboard_stats(conn: sqlite3.Connection) -> DashboardStats:
    def count(sql, *args):
        row = conn.execute(sql, args).fetchone()
        return row[0] if row else 0
    return DashboardStats(
        videos_created=count("SELECT COUNT(*) FROM videos"),
        videos_uploaded=count(
            "SELECT COUNT(*) FROM publishes WHERE status='done'"),
        videos_pending=count(
            "SELECT COUNT(*) FROM jobs WHERE approval_state='pending'"),
        current_jobs=count("SELECT COUNT(*) FROM jobs WHERE status='running'"),
    )
