"""Notifications: Discord webhook + desktop (via a GUI-registered handler).

The GUI registers its tray-icon handler at startup; headless runs just log.
"""
from __future__ import annotations

import logging
from typing import Callable

import requests

from app.config import Config

log = logging.getLogger("acf.notify")

DesktopHandler = Callable[[str, str], None]  # (title, message)
_desktop_handler: DesktopHandler | None = None


def register_desktop_handler(handler: DesktopHandler | None) -> None:
    global _desktop_handler
    _desktop_handler = handler


def send_discord(webhook_url: str, title: str, message: str) -> bool:
    try:
        response = requests.post(
            webhook_url,
            json={"embeds": [{"title": title[:250],
                              "description": message[:3900]}]},
            timeout=10,
        )
        return response.status_code < 300
    except requests.RequestException as exc:
        log.warning("Discord notification failed: %s", exc)
        return False


def notify(config: Config, title: str, message: str,
           level: str = "info") -> None:
    """Fan out one notification to every enabled channel. Never raises."""
    getattr(log, level, log.info)("NOTIFY %s: %s", title, message)

    webhook = (config.get("notifications.discord_webhook", "") or "").strip()
    if webhook:
        send_discord(webhook, title, message)

    if config.get("notifications.desktop", True) and _desktop_handler:
        try:
            _desktop_handler(title, message)
        except Exception:
            log.exception("Desktop notification handler failed")
