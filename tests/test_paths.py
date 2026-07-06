# tests/test_paths.py
from app.paths import AppPaths


def test_paths_under_user_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    p = AppPaths()
    assert p.data_dir == tmp_path
    assert p.db_path == tmp_path / "aicf.db"
    assert p.settings_path == tmp_path / "settings.json"
    assert p.secrets_path == tmp_path / "secrets.json"
    assert p.logs_dir == tmp_path / "logs"
    assert p.library_dir == tmp_path / "library"
    assert p.jobs_dir == tmp_path / "jobs"
    assert p.plugins_dir == tmp_path / "plugins"


def test_ensure_creates_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    p = AppPaths()
    p.ensure()
    for d in [p.logs_dir, p.library_dir, p.jobs_dir, p.plugins_dir]:
        assert d.is_dir()
