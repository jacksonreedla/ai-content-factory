"""Dashboard: today's numbers, AI provider status, recent activity."""
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QGridLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from app.config import Config
from database.db import Database
from database.repositories import JobRepo, StoryRepo, UsageRepo, VideoRepo
from gui.widgets import PageHeader, StatCard


class DashboardPage(QWidget):
    def __init__(self, config: Config, db: Database, on_generate=None):
        super().__init__()
        self.config = config
        self.db = db
        self.on_generate = on_generate

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Dashboard"))

        # one-click automation
        self.generate_btn = QPushButton("Generate  -  run full pipeline")
        self.generate_btn.setObjectName("Primary")
        self.generate_btn.setMinimumHeight(42)
        if on_generate:
            self.generate_btn.clicked.connect(on_generate)
        layout.addWidget(self.generate_btn)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cards = {
            "stories": StatCard("Stories in library"),
            "approved": StatCard("Awaiting review"),
            "narrations": StatCard("Narrations written"),
            "videos": StatCard("Videos generated"),
            "uploads": StatCard("Videos uploaded"),
            "ai_calls": StatCard("AI calls today"),
            "tokens": StatCard("Tokens today"),
            "providers": StatCard("AI providers online"),
            "views": StatCard("Total views"),
            "revenue": StatCard("Est. revenue (USD)"),
        }
        for i, card in enumerate(self.cards.values()):
            grid.addWidget(card, i // 4, i % 4)
        layout.addLayout(grid)

        section = QLabel("Recent jobs")
        section.setObjectName("SectionTitle")
        layout.addWidget(section)

        self.jobs_table = QTableWidget(0, 5)
        self.jobs_table.setHorizontalHeaderLabels(
            ["ID", "Type", "Stage", "Status", "Error"])
        self.jobs_table.horizontalHeader().setStretchLastSection(True)
        self.jobs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.jobs_table.setAlternatingRowColors(True)
        layout.addWidget(self.jobs_table, stretch=1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(5000)
        self.refresh()

    def refresh(self) -> None:
        story_repo = StoryRepo(self.db)
        counts = story_repo.count_by_status()
        total = sum(counts.values())
        self.cards["stories"].set_value(str(total))
        self.cards["approved"].set_value(str(counts.get("scored", 0)))
        narrations = self.db.scalar("SELECT COUNT(*) FROM narrations") or 0
        self.cards["narrations"].set_value(str(narrations))
        self.cards["videos"].set_value(str(VideoRepo(self.db).count()))
        uploads = self.db.scalar(
            "SELECT COUNT(*) FROM uploads WHERE status = 'uploaded'") or 0
        self.cards["uploads"].set_value(str(uploads))

        usage = UsageRepo(self.db).totals_today()
        self.cards["ai_calls"].set_value(str(usage["calls"]))
        self.cards["tokens"].set_value(
            f"{usage['tokens_in'] + usage['tokens_out']:,}")

        from database.repositories import AnalyticsRepo, SettingsRepo
        total_views = sum(
            metrics.get("views", 0)
            for metrics in AnalyticsRepo(self.db).latest_all().values())
        self.cards["views"].set_value(f"{int(total_views):,}")
        self.cards["revenue"].set_value(
            f"${SettingsRepo(self.db).get('analytics.revenue_estimate', '0.00')}")

        jobs = JobRepo(self.db).recent(15)
        self.jobs_table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            for col, value in enumerate([
                str(job.id), job.type, job.stage, job.status.value,
                (job.error or "")[:120],
            ]):
                self.jobs_table.setItem(row, col, QTableWidgetItem(value))

    def set_provider_status(self, availability: dict[str, bool]) -> None:
        online = [name for name, ok in availability.items() if ok]
        self.cards["providers"].set_value(", ".join(online) if online else "none")
