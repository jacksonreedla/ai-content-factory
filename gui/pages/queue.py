"""Queue page: job history with live progress."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QProgressBar, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app import events
from database.db import Database
from database.repositories import JobRepo
from gui.widgets import PageHeader


class QueuePage(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.repo = JobRepo(db)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Job queue"))

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Type", "Status", "Stage", "Progress", "Created", "Error"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        # Events arrive from worker threads; Qt widgets must only be touched
        # on the GUI thread, so the callback just stores the value and the
        # timer applies it.
        self._latest_progress: float | None = None
        events.bus.subscribe(events.JOB_UPDATED, self._on_job_event)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1500)
        self.refresh()

    def _on_job_event(self, payload: dict) -> None:
        progress = payload.get("progress")
        if progress is not None:
            self._latest_progress = float(progress)

    def refresh(self) -> None:
        if self._latest_progress is not None:
            self.progress.setValue(int(self._latest_progress * 100))
            self._latest_progress = None
        rows = self.db.query(
            "SELECT id, type, status, stage, progress, created_at, error "
            "FROM jobs ORDER BY id DESC LIMIT 100")
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            values = [str(row["id"]), row["type"], row["status"], row["stage"],
                      f"{row['progress'] * 100:.0f}%", row["created_at"],
                      (row["error"] or "")[:200]]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))
