# gui/views/history.py
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


class HistoryView(QWidget):
    """All jobs joined with their video / publish / latest analytics."""

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("History")
        title.setObjectName("title")
        v.addWidget(title)

        bar = QHBoxLayout()
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.clicked.connect(self.refresh)
        bar.addWidget(refresh_btn); bar.addStretch()
        v.addLayout(bar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Job", "Stage", "Status", "Video", "Published", "Views", "Likes", "Updated"])
        self.table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.table, 1)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        if not self.container or not self.container.db:
            return
        rows = self.container.db.execute(
            "SELECT j.id AS job_id, j.stage, j.status, j.updated_at, "
            "v.video_path, p.status AS pub_status, "
            "(SELECT views FROM analytics a WHERE a.publish_id=p.id ORDER BY a.id DESC LIMIT 1) AS views, "
            "(SELECT likes FROM analytics a WHERE a.publish_id=p.id ORDER BY a.id DESC LIMIT 1) AS likes "
            "FROM jobs j "
            "LEFT JOIN videos v ON v.job_id=j.id "
            "LEFT JOIN publishes p ON p.video_id=v.id "
            "ORDER BY j.id DESC LIMIT 500"
        ).fetchall()
        for i, r in enumerate(rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(r["job_id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["stage"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["status"] or ""))
            self.table.setItem(i, 3, QTableWidgetItem(r["video_path"] or ""))
            self.table.setItem(i, 4, QTableWidgetItem(r["pub_status"] or ""))
            self.table.setItem(i, 5, QTableWidgetItem(str(r["views"] or "")))
            self.table.setItem(i, 6, QTableWidgetItem(str(r["likes"] or "")))
            self.table.setItem(i, 7, QTableWidgetItem(r["updated_at"] or ""))
