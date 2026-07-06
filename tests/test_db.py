# tests/test_db.py
from infra.db.connection import connect
from infra.db.migrations import migrate, current_version


def test_migrate_creates_tables(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    expected = {"jobs", "stories", "story_scores", "scripts", "voice_clips",
                "subtitles", "videos", "thumbnails", "seo", "publishes",
                "analytics", "media_library", "content_sources",
                "llm_providers", "voice_engines"}
    assert expected.issubset(tables)
    assert current_version(conn) >= 1


def test_migrate_is_idempotent(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    v1 = current_version(conn)
    migrate(conn)
    v2 = current_version(conn)
    assert v1 == v2


def test_foreign_keys_enforced(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    # Inserting a story referencing a non-existent job should fail.
    import sqlite3
    with __import__("pytest").raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO stories (job_id, source, source_id) VALUES (999, 'reddit', 'x')")
