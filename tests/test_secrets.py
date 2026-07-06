# tests/test_secrets.py
import json

from app.secrets import Secrets, load_secrets, save_secrets


def test_secrets_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    s = Secrets(reddit_client_id="abc", reddit_client_secret="shh",
                llm_api_keys={"openai": "sk-x"})
    save_secrets(s)
    s2 = load_secrets()
    assert s2.reddit_client_id == "abc"
    assert s2.reddit_client_secret == "shh"
    assert s2.llm_api_keys["openai"] == "sk-x"


def test_secrets_unknown_keys_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    (tmp_path / "secrets.json").write_text(
        json.dumps({"bogus": 1, "reddit_client_id": "z"}))
    s = load_secrets()
    assert s.reddit_client_id == "z"


def test_secrets_missing_file_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    s = load_secrets()
    assert s.reddit_client_id == ""
