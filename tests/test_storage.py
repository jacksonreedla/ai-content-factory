# tests/test_storage.py
from app.paths import AppPaths
from infra.storage import job_dir, library_subdir


def test_job_dir_creates(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    paths = AppPaths(); paths.ensure()
    d = job_dir(paths, 42)
    assert d == paths.jobs_dir / "42"
    assert d.is_dir()


def test_library_subdir_creates(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    paths = AppPaths(); paths.ensure()
    d = library_subdir(paths, "backgrounds", "minecraft_parkour")
    assert d.is_dir()
    assert d == paths.library_dir / "backgrounds" / "minecraft_parkour"
