"""Research page: pick subreddits/filters and fetch stories."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QHBoxLayout,
                               QLabel, QPlainTextEdit, QPushButton, QSpinBox,
                               QVBoxLayout, QWidget)

from api.reddit_client import normalize_subreddit
from app.config import Config
from database.db import Database
from gui.widgets import PageHeader


class ResearchPage(QWidget):
    """Edits reddit config and triggers the research stage."""

    def __init__(self, config: Config, db: Database, run_stage=None):
        super().__init__()
        self.config = config
        self.db = db
        self.run_stage = run_stage

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Research - Reddit"))

        form = QFormLayout()
        form.setSpacing(10)

        self.subreddits_edit = QPlainTextEdit()
        self.subreddits_edit.setPlaceholderText("One subreddit per line - r/ prefix and full URLs are fine")
        self.subreddits_edit.setPlainText(
            "\n".join(config.get("reddit.subreddits", [])))
        self.subreddits_edit.setMaximumHeight(140)
        form.addRow("Subreddits", self.subreddits_edit)

        self.listing_combo = QComboBox()
        self.listing_combo.addItems(["top", "hot", "rising", "best"])
        self.listing_combo.setCurrentText(config.get("reddit.listing", "top"))
        form.addRow("Listing", self.listing_combo)

        self.time_combo = QComboBox()
        self.time_combo.addItems(["hour", "day", "week", "month", "year", "all"])
        self.time_combo.setCurrentText(config.get("reddit.time_filter", "day"))
        form.addRow("Time range (top)", self.time_combo)

        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 100)
        self.limit_spin.setValue(config.get("reddit.limit_per_subreddit", 25))
        form.addRow("Posts per subreddit", self.limit_spin)

        self.upvotes_spin = QSpinBox()
        self.upvotes_spin.setRange(0, 1_000_000)
        self.upvotes_spin.setValue(config.get("reddit.min_upvotes", 500))
        form.addRow("Minimum upvotes", self.upvotes_spin)

        self.comments_spin = QSpinBox()
        self.comments_spin.setRange(0, 100_000)
        self.comments_spin.setValue(config.get("reddit.min_comments", 20))
        form.addRow("Minimum comments", self.comments_spin)

        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 8760)
        self.age_spin.setSuffix(" h")
        self.age_spin.setValue(config.get("reddit.max_age_hours", 168))
        form.addRow("Maximum age", self.age_spin)

        self.min_words_spin = QSpinBox()
        self.min_words_spin.setRange(0, 100_000)
        self.min_words_spin.setValue(config.get("reddit.min_words", 80))
        form.addRow("Minimum words", self.min_words_spin)

        self.nsfw_check = QCheckBox("Allow NSFW stories")
        self.nsfw_check.setChecked(config.get("reddit.allow_nsfw", False))
        form.addRow("", self.nsfw_check)

        self.links_check = QCheckBox("Skip stories containing external links")
        self.links_check.setChecked(config.get("reddit.skip_external_links", True))
        form.addRow("", self.links_check)

        self.wild_check = QCheckBox(
            "Prioritize wild / out-of-pocket titles (boosts them when scoring)")
        self.wild_check.setChecked(
            config.get("scoring.prioritize_wild_titles", False))
        form.addRow("", self.wild_check)

        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.fetch_btn = QPushButton("Save && fetch stories")
        self.fetch_btn.setObjectName("Primary")
        self.fetch_btn.clicked.connect(self._on_fetch)
        buttons.addWidget(self.fetch_btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        layout.addWidget(self.status_label)
        layout.addStretch()

    # ------------------------------------------------------------------
    def save_to_config(self) -> None:
        seen: set[str] = set()
        subs: list[str] = []
        for line in self.subreddits_edit.toPlainText().splitlines():
            name = normalize_subreddit(line)
            key = name.lower()
            if name and key not in seen:
                seen.add(key)
                subs.append(name)
        c = self.config
        c.set("reddit.subreddits", subs, persist=False)
        c.set("reddit.listing", self.listing_combo.currentText(), persist=False)
        c.set("reddit.time_filter", self.time_combo.currentText(), persist=False)
        c.set("reddit.limit_per_subreddit", self.limit_spin.value(), persist=False)
        c.set("reddit.min_upvotes", self.upvotes_spin.value(), persist=False)
        c.set("reddit.min_comments", self.comments_spin.value(), persist=False)
        c.set("reddit.max_age_hours", self.age_spin.value(), persist=False)
        c.set("reddit.min_words", self.min_words_spin.value(), persist=False)
        c.set("reddit.allow_nsfw", self.nsfw_check.isChecked(), persist=False)
        c.set("scoring.prioritize_wild_titles", self.wild_check.isChecked(),
              persist=False)
        c.set("reddit.skip_external_links", self.links_check.isChecked(), persist=True)

    def _on_fetch(self) -> None:
        self.save_to_config()
        if self.run_stage:
            self.status_label.setText("Fetching stories...")
            self.fetch_btn.setEnabled(False)
            self.run_stage("research", self._on_done, self._on_error)

    def _on_done(self, result) -> None:
        self.fetch_btn.setEnabled(True)
        stage = result.stage_results.get("research")
        self.status_label.setText(stage.message if stage else "Done.")

    def _on_error(self, message: str) -> None:
        self.fetch_btn.setEnabled(True)
        self.status_label.setText(f"Error: {message.splitlines()[0]}")
