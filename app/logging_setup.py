"""Logging: rotating file + console + in-memory ring buffer for the GUI."""
from __future__ import annotations

import logging
import logging.handlers
from collections import deque
from typing import Callable

from app.paths import LOGS_DIR

_FORMAT = "%(asctime)s  %(levelname)-8s %(name)s: %(message)s"


class RingBufferHandler(logging.Handler):
    """Keeps the last N log lines in memory and notifies GUI subscribers."""

    def __init__(self, capacity: int = 2000):
        super().__init__()
        self.buffer: deque[str] = deque(maxlen=capacity)
        self._subscribers: list[Callable[[str], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        self.buffer.append(line)
        for callback in list(self._subscribers):
            try:
                callback(line)
            except Exception:
                pass

    def subscribe(self, callback: Callable[[str], None]) -> None:
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[str], None]) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)


ring_buffer = RingBufferHandler()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logging once. Safe to call repeatedly."""
    root = logging.getLogger()
    if getattr(root, "_acf_configured", False):
        return

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.handlers.RotatingFileHandler(
        LOGS_DIR / "app.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    ring_buffer.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(console)
    root.addHandler(file_handler)
    root.addHandler(ring_buffer)
    root._acf_configured = True  # type: ignore[attr-defined]
