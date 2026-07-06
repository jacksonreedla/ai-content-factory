# tests/test_container.py
from app.container import Container


def test_container_wires_core_services(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    c = Container()
    c.bootstrap()
    try:
        assert c.paths.data_dir == tmp_path
        assert c.config.general.concurrent_jobs == 1
        assert c.db is not None
        assert c.registry is not None
        assert c.runner is not None
        assert c.pool is not None
    finally:
        c.shutdown()


def test_container_db_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    c = Container()
    c.bootstrap()
    try:
        tables = {r[0] for r in c.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "jobs" in tables
    finally:
        c.shutdown()
