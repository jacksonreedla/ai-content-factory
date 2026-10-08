"""Logs page: live application log stream."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

from app.logging_setup import ring_buffer
from gui.widgets import PageHeader


class LogsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Logs"))

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(2000)
        layout.addWidget(self.view, stretch=1)

        self._pending: list[str] = list(ring_buffer.buffer)
        ring_buffer.subscribe(self._queue_line)

        # Flush from a timer: log lines can arrive from worker threads and
        # QPlainTextEdit must only be touched on the GUI thread.
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flush)
        self._timer.start(500)

    def _queue_line(self, line: str) -> None:
        self._pending.append(line)

    def _flush(self) -> None:
        if not self._pending:
            return
        lines, self._pending = self._pending, []
        self.view.appendPlainText("\n".join(lines))
