# tests/test_config.py
from app.config import load_config, save_config


def test_load_defaults_when_no_user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    cfg = load_config()
    assert cfg.scoring.min_overall == 70
    assert cfg.general.concurrent_jobs == 1
    assert cfg.llm.active_provider == "ollama"


def test_user_overrides_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    cfg = load_config()
    cfg.scoring.min_overall = 85
    save_config(cfg)
    cfg2 = load_config()
    assert cfg2.scoring.min_overall == 85
    # Unchanged value still present.
    assert cfg2.general.concurrent_jobs == 1


def test_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    (tmp_path / "settings.json").write_text('{"general": {"theme": "light"}}')
    cfg = load_config()
    assert cfg.general.theme == "light"
    assert cfg.scoring.min_overall == 70
