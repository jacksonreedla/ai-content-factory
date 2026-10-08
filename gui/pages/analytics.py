"""Analytics page: per-video stats, totals, and learned recommendations."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QTextEdit,
                               QVBoxLayout, QWidget)

from agents.analytics_agent import INSIGHTS_KEY, REVENUE_KEY
from analytics.insights import duration_bucket
from app.config import Config
from database.db import Database
from database.repositories import AnalyticsRepo, SettingsRepo
from gui.widgets import PageHeader, StatCard


class AnalyticsPage(QWidget):
    def __init__(self, config: Config, db: Database, run_stage=None):
        super().__init__()
        self.config = config
        self.db = db
        self.run_stage = run_stage
        self.repo = AnalyticsRepo(db)
        self.settings = SettingsRepo(db)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Analytics"))

        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh stats from YouTube")
        self.refresh_btn.setObjectName("Primary")
        self.refresh_btn.clicked.connect(self._refresh_stats)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addStretch()
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        cards = QGridLayout()
        cards.setSpacing(12)
        self.views_card = StatCard("Total views")
        self.likes_card = StatCard("Total likes")
        self.comments_card = StatCard("Total comments")
        self.revenue_card = StatCard("Est. revenue (USD)")
        for i, card in enumerate([self.views_card, self.likes_card,
                                  self.comments_card, self.revenue_card]):
            cards.addWidget(card, 0, i)
        layout.addLayout(cards)

        insights_label = QLabel("Recommendations")
        insights_label.setObjectName("SectionTitle")
        layout.addWidget(insights_label)
        self.insights_view = QTextEdit()
        self.insights_view.setReadOnly(True)
        self.insights_view.setMaximumHeight(140)
        layout.addWidget(self.insights_view)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Video", "Title", "Source", "Style", "Length", "Views",
             "Likes", "Comments"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(1, 300)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, stretch=1)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        rows = self.repo.performance_rows()
        self.table.setRowCount(len(rows))
        views = likes = comments = 0.0
        for r, row in enumerate(rows):
            views += row["views"]
            likes += row["likes"]
            comments += row["comments"]
            values = [
                str(row["video_id"]), row["title"] or "",
                row["subreddit"] or "-", row["style"] or "-",
                duration_bucket(float(row["duration_s"] or 0)),
                f"{int(row['views']):,}", f"{int(row['likes']):,}",
                f"{int(row['comments']):,}",
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(value))

        self.views_card.set_value(f"{int(views):,}")
        self.likes_card.set_value(f"{int(likes):,}")
        self.comments_card.set_value(f"{int(comments):,}")
        self.revenue_card.set_value(
            f"${self.settings.get(REVENUE_KEY, '0.00')}")

        raw = self.settings.get(INSIGHTS_KEY)
        if raw:
            try:
                insights = json.loads(raw)
                lines = [f"- {r}" for r in insights.get("recommendations", [])]
                self.insights_view.setPlainText("\n".join(lines))
            except json.JSONDecodeError:
                self.insights_view.setPlainText("(could not read insights)")
        else:
            self.insights_view.setPlainText(
                "Run 'Refresh stats' after your first uploads to get "
                "recommendations.")

    def _refresh_stats(self) -> None:
        if not self.run_stage:
            return
        self.refresh_btn.setEnabled(False)
        self.status_label.setText("Fetching stats...")

        def done(result):
            self.refresh_btn.setEnabled(True)
            stage_result = result.stage_results.get("analytics")
            self.status_label.setText(
                stage_result.message if stage_result else "Done.")
            self.refresh()

        def error(message: str):
            self.refresh_btn.setEnabled(True)
            self.status_label.setText(f"Error: {message.splitlines()[0]}")

        self.run_stage("analytics", done, error)
