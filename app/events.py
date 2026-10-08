"""Tiny thread-safe pub/sub event bus used to decouple pipeline from GUI."""
from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger("acf.events")

Handler = Callable[[dict[str, Any]], None]

# Well-known event names
JOB_UPDATED = "job.updated"           # payload: {job_id, status, stage, progress}
STORY_UPDATED = "story.updated"       # payload: {story_id, status}
PIPELINE_FINISHED = "pipeline.finished"
LOG_MESSAGE = "log.message"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event: str, handler: Handler) -> None:
        with self._lock:
            self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Handler) -> None:
        with self._lock:
            if handler in self._handlers.get(event, []):
                self._handlers[event].remove(handler)

    def publish(self, event: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        with self._lock:
            handlers = list(self._handlers.get(event, []))
        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                log.exception("Event handler failed for %s", event)


bus = EventBus()
