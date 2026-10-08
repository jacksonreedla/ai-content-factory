"""Background execution for the GUI - never block the UI thread."""
from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QObject):
    """Runs a callable on a QThread; emits finished(result) or failed(msg)."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")


class TaskRunner:
    """Owns worker threads so they are not garbage collected mid-run."""

    def __init__(self) -> None:
        self._threads: list[tuple[QThread, Worker]] = []

    def submit(self, fn: Callable[..., Any],
               on_done: Callable[[Any], None] | None = None,
               on_error: Callable[[str], None] | None = None,
               *args: Any, **kwargs: Any) -> None:
        thread = QThread()
        worker = Worker(fn, *args, **kwargs)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _cleanup(*_a: Any) -> None:
            thread.quit()

        worker.finished.connect(_cleanup)
        worker.failed.connect(_cleanup)
        if on_done:
            worker.finished.connect(on_done)
        if on_error:
            worker.failed.connect(on_error)
        thread.finished.connect(lambda: self._release(thread))
        self._threads.append((thread, worker))
        thread.start()

    def _release(self, thread: QThread) -> None:
        self._threads = [(t, w) for (t, w) in self._threads if t is not thread]
        thread.deleteLater()
