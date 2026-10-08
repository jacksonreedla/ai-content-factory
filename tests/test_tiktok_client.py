"""Unit tests for TikTokClient's pure logic (no network)."""
from __future__ import annotations

from api.tiktok_client import CHUNK_SIZE, TikTokClient


def _client(monkeypatch, creator_info):
    client = TikTokClient(config=None)
    monkeypatch.setattr(client, "creator_info", lambda force=False: creator_info)
    return client


def test_resolve_privacy_uses_requested_when_allowed(monkeypatch):
    client = _client(monkeypatch, {
        "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]})
    assert client.resolve_privacy("public") == "PUBLIC_TO_EVERYONE"
    assert client.resolve_privacy("private") == "SELF_ONLY"


def test_resolve_privacy_falls_back_to_self_only(monkeypatch):
    # Unaudited apps / private accounts commonly allow only SELF_ONLY.
    client = _client(monkeypatch, {"privacy_level_options": ["SELF_ONLY"]})
    assert client.resolve_privacy("public") == "SELF_ONLY"


def test_resolve_privacy_unknown_word_defaults_private(monkeypatch):
    client = _client(monkeypatch, {
        "privacy_level_options": ["PUBLIC_TO_EVERYONE", "SELF_ONLY"]})
    assert client.resolve_privacy("nonsense") == "SELF_ONLY"


def test_chunk_plan_small_file_is_single_chunk():
    size = 3 * 1024 * 1024
    chunk_size, total = TikTokClient._chunk_plan(size)
    assert total == 1
    assert chunk_size == size


def test_chunk_plan_large_file_last_chunk_absorbs_remainder():
    size = CHUNK_SIZE * 3 + 1234
    chunk_size, total = TikTokClient._chunk_plan(size)
    assert chunk_size == CHUNK_SIZE
    assert total == 3  # remainder folded into the final chunk


def test_is_configured_requires_key_and_secret():
    assert TikTokClient(config=None).is_configured() is False
