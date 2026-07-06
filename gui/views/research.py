# gui/views/research.py
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from core.models import SourceQuery, Story


class ResearchView(QWidget):
    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        self._results: list[Story] = []
        v = QVBoxLayout(self)
        title = QLabel("Research")
        title.setObjectName("title")
        v.addWidget(title)

        # Filter row.
        filters = QHBoxLayout()
        self.subreddits = QLineEdit("AskReddit, nosleep, tifu")
        self.subreddits.setPlaceholderText("subreddits, comma-separated")
        self.min_score = QSpinBox()
        self.min_score.setRange(0, 100000)
        self.min_score.setValue(1000)
        self.min_comments = QSpinBox()
        self.min_comments.setRange(0, 100000)
        self.min_comments.setValue(50)
        self.sort = QComboBox()
        self.sort.addItems(["hot", "top", "new", "rising"])
        self.limit = QSpinBox()
        self.limit.setRange(1, 100)
        self.limit.setValue(25)
        self.discover_btn = QPushButton("🔍  Discover")
        self.discover_btn.setObjectName("primary")
        self.discover_btn.clicked.connect(self._on_discover)
        for lbl_text, w in (
            ("Subreddits", self.subreddits),
            ("Min score", self.min_score),
            ("Min comments", self.min_comments),
            ("Sort", self.sort),
            ("Limit", self.limit),
        ):
            filters.addWidget(QLabel(lbl_text))
            filters.addWidget(w)
        filters.addWidget(self.discover_btn)
        v.addLayout(filters)

        # Results table.
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["", "Subreddit", "Title", "Score", "Comments", "Age"])
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        v.addWidget(self.table, 1)

        # Send-to-pipeline.
        actions = QHBoxLayout()
        self.enqueue_btn = QPushButton("➡  Send to Pipeline")
        self.enqueue_btn.clicked.connect(self._on_enqueue)
        actions.addStretch()
        actions.addWidget(self.enqueue_btn)
        v.addLayout(actions)

    def _build_query(self) -> SourceQuery:
        subs = [s.strip() for s in self.subreddits.text().split(",") if s.strip()]
        return SourceQuery(
            subreddits=subs or ["AskReddit"],
            min_score=self.min_score.value(),
            min_comments=self.min_comments.value(),
            sort=self.sort.currentText(),
            limit=self.limit.value(),
        )

    def _on_discover(self) -> None:
        if not self.container:
            return
        from app.services import ResearchService
        svc = ResearchService(self.container)
        try:
            self._results = svc.discover(self._build_query())
        except Exception as e:
            QMessageBox.warning(self, "Discover failed", str(e))
            return
        self._populate()

    def _populate(self) -> None:
        self.table.setRowCount(0)
        now = datetime.now(timezone.utc).timestamp()
        for i, s in enumerate(self._results):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(""))
            self.table.setItem(i, 1, QTableWidgetItem(s.subreddit))
            self.table.setItem(i, 2, QTableWidgetItem(s.title))
            self.table.setItem(i, 3, QTableWidgetItem(str(s.score)))
            self.table.setItem(i, 4, QTableWidgetItem(str(s.num_comments)))
            hours = int((now - s.created_utc) / 3600) if s.created_utc else 0
            self.table.setItem(i, 5, QTableWidgetItem(f"{hours}h"))

    def _on_enqueue(self) -> None:
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        if not rows or not self.container:
            return
        from app.services import ResearchService
        from core.enums import JobStage
        svc = ResearchService(self.container)
        count = 0
        for r in sorted(rows):
            story = self._results[r]
            jid = svc.enqueue(story)
            svc.start_job(jid, JobStage.ANALYZE)   # research already done
            count += 1
        QMessageBox.information(self, "Queued", f"{count} job(s) queued.")
