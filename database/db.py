"""SQLite connection management + migrations.

One ``Database`` object is shared app-wide; each thread gets its own
underlying sqlite3 connection (sqlite objects are not thread-portable).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterable

from app.paths import DB_PATH

log = logging.getLogger("acf.db")

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
SCHEMA_VERSION = 2


class Database:
    """Thread-safe-ish wrapper: one connection per thread, WAL mode."""

    def __init__(self, path: Path | str):
        self.path = str(path)
        self._local = threading.local()

    @classmethod
    def default(cls) -> "Database":
        return cls(DB_PATH)

    @classmethod
    def in_memory(cls) -> "Database":
        """A private in-memory DB for unit tests (single-thread)."""
        db = cls(":memory:")
        db.migrate()
        return db

    # ------------------------------------------------------------ connection
    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            if self.path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL")
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    # ------------------------------------------------------------ helpers
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        row = self.query_one(sql, params)
        return row[0] if row else None

    # ------------------------------------------------------------ migration
    def _column_exists(self, table: str, column: str) -> bool:
        rows = self.query(f"PRAGMA table_info({table})")
        return any(r["name"] == column for r in rows)

    def _add_column(self, table: str, column: str, ddl: str) -> None:
        if not self._column_exists(table, column):
            self.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            log.info("Added column %s.%s", table, column)

    def _migrate_v2(self) -> None:
        """Title-card support: extra columns on videos. Idempotent."""
        self._add_column("videos", "card_path", "TEXT DEFAULT ''")
        self._add_column("videos", "intro_seconds", "REAL DEFAULT 0")
        self._add_column("videos", "account", "TEXT DEFAULT ''")

    def migrate(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema)
        # Column additions are guarded/idempotent, so they are safe to run on
        # both fresh and existing databases.
        self._migrate_v2()
        row = self.query_one("SELECT version FROM schema_version")
        if row is None:
            self.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
            log.info("Database initialised at schema v%s (%s)", SCHEMA_VERSION, self.path)
        elif row["version"] < SCHEMA_VERSION:
            self.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
            log.info("Database migrated to schema v%s", SCHEMA_VERSION)
