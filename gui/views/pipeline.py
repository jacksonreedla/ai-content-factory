# gui/views/pipeline.py
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class PipelineView(QWidget):
    """Live view of all jobs: stage, status, approval, updated. Auto-refreshes."""

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Pipeline")
        title.setObjectName("title")
        v.addWidget(title)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Job", "Stage", "Status", "Approval", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.table, 1)

        bar = QHBoxLayout()
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.clicked.connect(self.refresh)
        bar.addWidget(refresh_btn)
        bar.addStretch()
        v.addLayout(bar)

        # Auto-refresh every 3s while visible.
        from PySide6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self.refresh)

    def showEvent(self, ev):
        super().showEvent(ev)
        self.refresh()
        self._timer.start()

    def hideEvent(self, ev):
        super().hideEvent(ev)
        self._timer.stop()

    def refresh(self) -> None:
        if not self.container or not self.container.db:
            return
        from infra.db.repositories import list_jobs
        rows = list_jobs(self.container.db, limit=200)
        self.table.setRowCount(0)
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(r["id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["stage"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["status"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(r["approval_state"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(r["updated_at"] or ""))
