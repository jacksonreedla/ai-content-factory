"""Notification dispatch tests."""
from __future__ import annotations

import app.notifications as notifications_module
from app.notifications import notify, register_desktop_handler, send_discord


class FakeResponse:
    status_code = 204


def test_send_discord_posts_embed(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append({"url": url, "json": json})
        return FakeResponse()

    monkeypatch.setattr(notifications_module.requests, "post", fake_post)
    ok = send_discord("https://discord/webhook", "Title", "Message")
    assert ok
    assert calls[0]["json"]["embeds"][0]["title"] == "Title"


def test_notify_uses_discord_and_desktop(config, monkeypatch):
    discord_calls = []
    monkeypatch.setattr(notifications_module, "send_discord",
                        lambda url, t, m: discord_calls.append((url, t, m)))
    desktop_calls = []
    register_desktop_handler(lambda t, m: desktop_calls.append((t, m)))
    try:
        config.set("notifications.discord_webhook", "https://d/w", persist=False)
        notify(config, "Done", "All good")
        assert discord_calls == [("https://d/w", "Done", "All good")]
        assert desktop_calls == [("Done", "All good")]
    finally:
        register_desktop_handler(None)


def test_notify_never_raises(config):
    register_desktop_handler(lambda t, m: 1 / 0)
    try:
        notify(config, "T", "M")  # handler explodes; notify must swallow it
    finally:
        register_desktop_handler(None)
