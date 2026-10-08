"""Stories page: review, approve/reject, score & rewrite stories."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSplitter, QTableWidget,
                               QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from app.config import Config
from database.db import Database
from database.repositories import NarrationRepo, StoryRepo
from gui.widgets import PageHeader, remove_files
from models.story import StoryStatus


class StoriesPage(QWidget):
    def __init__(self, config: Config, db: Database, run_stage=None):
        super().__init__()
        self.config = config
        self.db = db
        self.run_stage = run_stage
        self.repo = StoryRepo(db)
        self._stories = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Stories"))

        toolbar = QHBoxLayout()
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            ["all", "new", "scored", "approved", "rejected", "rewritten"])
        self.filter_combo.currentTextChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(QLabel("Show:"))
        toolbar.addWidget(self.filter_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            ["Upvotes (high→low)", "Score (high→low)", "Newest first"])
        self.sort_combo.currentTextChanged.connect(lambda _: self.refresh())
        toolbar.addWidget(QLabel("Sort:"))
        toolbar.addWidget(self.sort_combo)

        self.score_btn = QPushButton("Score new stories")
        self.score_btn.clicked.connect(lambda: self._run("score", self.score_btn))
        toolbar.addWidget(self.score_btn)

        self.rewrite_btn = QPushButton("Rewrite approved")
        self.rewrite_btn.clicked.connect(lambda: self._run("rewrite", self.rewrite_btn))
        toolbar.addWidget(self.rewrite_btn)

        self.voice_btn = QPushButton("Generate voiceovers")
        self.voice_btn.clicked.connect(lambda: self._run("voice", self.voice_btn))
        toolbar.addWidget(self.voice_btn)

        self.captions_btn = QPushButton("Generate captions")
        self.captions_btn.clicked.connect(
            lambda: self._run("captions", self.captions_btn))
        toolbar.addWidget(self.captions_btn)

        self.all_btn = QPushButton("All")
        self.all_btn.setObjectName("Primary")
        self.all_btn.setToolTip(
            "Rewrite, generate voiceovers, and generate captions for every "
            "approved story - one stage after another.")
        self.all_btn.clicked.connect(self._run_all)
        toolbar.addWidget(self.all_btn)

        toolbar.addStretch()
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Subreddit", "Title", "Upvotes", "Score", "Words", "Status"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._show_selected)
        self.table.setColumnWidth(2, 340)
        # Press Delete to remove all highlighted stories.
        delete_sc = QShortcut(QKeySequence.StandardKey.Delete, self.table)
        delete_sc.activated.connect(self._delete_selected)
        splitter.addWidget(self.table)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 0, 0, 0)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        right_layout.addWidget(self.detail, stretch=1)

        actions = QHBoxLayout()
        self.approve_btn = QPushButton("Approve")
        self.approve_btn.setObjectName("Success")
        self.approve_btn.clicked.connect(lambda: self._set_status(StoryStatus.APPROVED))
        self.reject_btn = QPushButton("Reject")
        self.reject_btn.setObjectName("Danger")
        self.reject_btn.clicked.connect(
            lambda: self._set_status(StoryStatus.REJECTED, "rejected by user"))
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.clicked.connect(self._delete_selected)
        actions.addWidget(self.approve_btn)
        actions.addWidget(self.reject_btn)
        actions.addStretch()
        actions.addWidget(self.delete_btn)
        right_layout.addLayout(actions)
        splitter.addWidget(right)
        splitter.setSizes([620, 420])

        layout.addWidget(splitter, stretch=1)
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        selected = self.filter_combo.currentText()
        if selected == "all":
            self._stories = self.repo.recent(300)
        else:
            self._stories = self.repo.by_status(StoryStatus(selected), 300)
        self._sort_stories()
        self.table.setRowCount(len(self._stories))
        numeric_cols = {0, 3, 4, 5}  # ID, Upvotes, Score, Words -> right-align
        for row, story in enumerate(self._stories):
            score = f"{story.scores.overall:.1f}" if story.scores else "-"
            for col, value in enumerate([
                str(story.id), story.subreddit, story.title,
                str(story.upvotes), score, str(story.word_count),
                story.status.value,
            ]):
                item = QTableWidgetItem(value)
                if col in numeric_cols:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight
                                          | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

    def _sort_stories(self) -> None:
        """Order the loaded stories per the Sort dropdown (in-place, so table
        rows stay aligned with self._stories)."""
        mode = self.sort_combo.currentText()
        if mode.startswith("Upvotes"):
            self._stories.sort(key=lambda s: s.upvotes or 0, reverse=True)
        elif mode.startswith("Score"):
            self._stories.sort(
                key=lambda s: s.scores.overall if s.scores else -1.0,
                reverse=True)
        # "Newest first" keeps the repository order (already newest-first).

    def _selected_story(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return self._stories[rows[0].row()]

    def _selected_stories(self) -> list:
        rows = sorted(r.row() for r in self.table.selectionModel().selectedRows())
        return [self._stories[r] for r in rows]

    def _show_selected(self) -> None:
        story = self._selected_story()
        if not story:
            return
        parts = [f"# {story.title}",
                 f"r/{story.subreddit} | {story.upvotes} upvotes | "
                 f"{story.num_comments} comments | {story.word_count} words", ""]
        if story.scores:
            parts.append(f"**Overall score: {story.scores.overall:.1f}/10** - "
                         f"{story.scores.reasoning}")
            axis = ", ".join(f"{k}: {v:.0f}" for k, v in story.scores.values.items())
            parts.append(axis)
            parts.append("")
        narration = NarrationRepo(self.db).latest_for_story(story.id)
        if narration:
            parts += ["## Narration", narration["text"], "", "## Original story", ""]
        parts.append(story.text)
        self.detail.setMarkdown("\n".join(parts))

    def _set_status(self, status: StoryStatus, reason: str = "") -> None:
        story = self._selected_story()
        if story:
            self.repo.set_status(story.id, status, reason)
            self.refresh()

    def _delete_selected(self) -> None:
        stories = self._selected_stories()
        if not stories:
            return
        if len(stories) == 1:
            prompt = (f"Permanently delete story #{stories[0].id} "
                      f"“{stories[0].title}”, ")
        else:
            prompt = f"Permanently delete these {len(stories)} stories, "
        reply = QMessageBox.question(
            self, "Delete stories",
            prompt + "along with any generated videos, audio and captions, "
            "from the app and your computer?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        removed = 0
        for story in stories:
            removed += remove_files(self.repo.delete(story.id))
        self.detail.clear()
        self.refresh()
        self.status_label.setText(
            f"Deleted {len(stories)} stor{'y' if len(stories) == 1 else 'ies'} "
            f"({removed} file(s) removed).")

    def _run(self, stage: str, button: QPushButton) -> None:
        if not self.run_stage:
            return
        button.setEnabled(False)
        self.status_label.setText(f"Running {stage}...")

        def done(result):
            button.setEnabled(True)
            stage_result = result.stage_results.get(stage)
            self.status_label.setText(stage_result.message if stage_result else "Done.")
            self.refresh()

        def error(message: str):
            button.setEnabled(True)
            self.status_label.setText(f"Error: {message.splitlines()[0]}")

        self.run_stage(stage, done, error)

    def _run_all(self) -> None:
        """Rewrite -> voice -> captions across all approved stories, in order.

        Each stage already processes every eligible item one by one; we chain
        the three stages so the whole approved queue goes from approved to
        captioned in a single click. Stops early on a hard failure.
        """
        if not self.run_stage:
            return
        stages = ["rewrite", "voice", "captions"]
        buttons = [self.score_btn, self.rewrite_btn, self.voice_btn,
                   self.captions_btn, self.all_btn]

        def set_enabled(on: bool) -> None:
            for b in buttons:
                b.setEnabled(on)

        def finish(message: str) -> None:
            set_enabled(True)
            self.status_label.setText(message)
            self.refresh()

        def run_next(index: int) -> None:
            if index >= len(stages):
                finish("All done - rewrite, voiceovers and captions complete.")
                return
            stage = stages[index]
            self.status_label.setText(
                f"Running {stage} ({index + 1}/{len(stages)})...")

            def done(result) -> None:
                sr = result.stage_results.get(stage)
                if sr and not sr.ok and not sr.skipped:
                    finish(f"Stopped at {stage}: {sr.message}")
                    return
                run_next(index + 1)

            def error(message: str) -> None:
                finish(f"Error during {stage}: {message.splitlines()[0]}")

            self.run_stage(stage, done, error)

        set_enabled(False)
        run_next(0)
