# infra/db/migrations.py
import re
import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def _ensure_schema_version_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )


def current_version(conn: sqlite3.Connection) -> int:
    _ensure_schema_version_table(conn)
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    return row["v"] or 0


def _migration_files() -> list[tuple[int, Path]]:
    out = []
    for p in _MIGRATIONS_DIR.glob("*.sql"):
        m = re.match(r"(\d+)_", p.name)
        if m:
            out.append((int(m.group(1)), p))
    return sorted(out)


def migrate(conn: sqlite3.Connection) -> int:
    current = current_version(conn)
    for version, path in _migration_files():
        if version <= current:
            continue
        sql = path.read_text()
        conn.executescript(sql)
        # executescript may have already created schema_version; ensure our row.
        _ensure_schema_version_table(conn)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()
    return current_version(conn)
