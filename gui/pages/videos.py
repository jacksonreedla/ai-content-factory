"""Videos page: rendered output tracker + render/thumbnail actions."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from app.config import Config
from app.paths import MEDIA_LIBRARY_DIR, OUTPUT_DIR
from database.db import Database
from database.repositories import VideoRepo
from editor.media_library import list_categories
from gui.widgets import PageHeader, remove_files


class VideosPage(QWidget):
    def __init__(self, config: Config, db: Database, run_stage=None):
        super().__init__()
        self.config = config
        self.db = db
        self.run_stage = run_stage
        self.repo = VideoRepo(db)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Videos"))

        hint = QLabel(
            f"Backgrounds come from {MEDIA_LIBRARY_DIR} - drop gameplay .mp4 "
            f"files into a category folder. Finished videos land in {OUTPUT_DIR}.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Background:"))
        self.bg_combo = QComboBox()
        self.bg_combo.setToolTip(
            "Which media-library folder new renders pull background clips "
            "from. Saved to settings and used by Render / Re-render.")
        self._reload_categories()
        self.bg_combo.currentTextChanged.connect(self._set_background_category)
        toolbar.addWidget(self.bg_combo)

        self.render_btn = QPushButton("Render videos")
        self.render_btn.setObjectName("Primary")
        self.render_btn.clicked.connect(lambda: self._run("edit", self.render_btn))
        toolbar.addWidget(self.render_btn)

        self.rerender_btn = QPushButton("Re-render (apply new settings)")
        self.rerender_btn.clicked.connect(self._rerender)
        toolbar.addWidget(self.rerender_btn)

        self.thumb_btn = QPushButton("Generate thumbnails")
        self.thumb_btn.clicked.connect(
            lambda: self._run("thumbnail", self.thumb_btn))
        toolbar.addWidget(self.thumb_btn)

        self.open_btn = QPushButton("Open output folder")
        self.open_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(OUTPUT_DIR))))
        toolbar.addWidget(self.open_btn)

        self.media_btn = QPushButton("Open media library")
        self.media_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(MEDIA_LIBRARY_DIR))))
        toolbar.addWidget(self.media_btn)

        self.delete_btn = QPushButton("Delete videos")
        self.delete_btn.setObjectName("Danger")
        self.delete_btn.clicked.connect(self._delete_selected)
        toolbar.addWidget(self.delete_btn)

        toolbar.addStretch()

        toolbar.addWidget(QLabel("Title-card account:"))
        self.account_combo = QComboBox()
        self._reload_accounts()
        toolbar.addWidget(self.account_combo)
        self.set_account_btn = QPushButton("Set for selected")
        self.set_account_btn.clicked.connect(self._set_account)
        toolbar.addWidget(self.set_account_btn)
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Title", "Format", "Duration", "Audio", "Captions",
             "Account", "File"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(1, 320)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._open_selected)
        # Press Delete to remove all highlighted videos.
        delete_sc = QShortcut(QKeySequence.StandardKey.Delete, self.table)
        delete_sc.activated.connect(self._delete_selected)
        layout.addWidget(self.table, stretch=1)
        self.refresh()

    def refresh(self) -> None:
        self._reload_accounts()   # pick up accounts added/renamed in Settings
        self._reload_categories()  # pick up folders added to the media library
        self._videos = self.repo.recent(200)
        self.table.setRowCount(len(self._videos))
        for row, video in enumerate(self._videos):
            values = [
                str(video["id"]), video["title"] or "", video["format"],
                f"{video['duration_s']:.0f}s" if video["duration_s"] else "-",
                "yes" if video["audio_path"] else "-",
                "yes" if video["captions_path"] else "-",
                (video["account"] if video.get("account") else "(default)"),
                Path(video["file_path"]).name if video["file_path"] else "-",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _reload_categories(self) -> None:
        """Fill the Background dropdown from the media-library folders, keeping
        the currently configured category selected (even if its folder is
        empty or not yet created)."""
        current = self.config.get("video.background_category", "minecraft")
        cats = list_categories()
        if current and current not in cats:
            cats = [current] + cats
        self.bg_combo.blockSignals(True)
        self.bg_combo.clear()
        self.bg_combo.addItems(cats or [current])
        idx = self.bg_combo.findText(current)
        self.bg_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.bg_combo.blockSignals(False)

    def _set_background_category(self, name: str) -> None:
        name = (name or "").strip()
        if not name:
            return
        self.config.set("video.background_category", name)
        self.status_label.setText(f"Background folder set to “{name}”.")

    def _reload_accounts(self) -> None:
        # Re-read accounts from config so ones added in Settings show up here.
        current = (self.account_combo.currentText()
                   if self.account_combo.count() else "")
        self.account_combo.blockSignals(True)
        self.account_combo.clear()
        self.account_combo.addItem("(default)")
        self.account_combo.addItems(
            [a.get("name", "") for a in (self.config.get("accounts", []) or [])
             if a.get("name")])
        idx = self.account_combo.findText(current)
        self.account_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.account_combo.blockSignals(False)

    def _set_account(self) -> None:
        rows = sorted({r.row() for r in self.table.selectionModel().selectedRows()})
        if not rows:
            self.status_label.setText("Select one or more video rows first.")
            return
        choice = self.account_combo.currentText()
        account = "" if choice.startswith("(") else choice
        for r in rows:
            self.repo.set_account(int(self._videos[r]["id"]), account)
        self.refresh()
        label = account or "default"
        self.status_label.setText(f"Account set to {label} for {len(rows)} video(s).")

    def _open_selected(self, _item) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        video = self._videos[rows[0].row()]
        if video["file_path"] and Path(video["file_path"]).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(video["file_path"]))

    def _delete_selected(self) -> None:
        rows = sorted(r.row() for r in self.table.selectionModel().selectedRows())
        if not rows:
            self.status_label.setText("Select one or more video rows first.")
            return
        videos = [self._videos[r] for r in rows]
        if len(videos) == 1:
            title = videos[0]["title"] or f"video #{videos[0]['id']}"
            prompt = f"Permanently delete “{title}” and its "
        else:
            prompt = f"Permanently delete these {len(videos)} videos and their "
        reply = QMessageBox.question(
            self, "Delete videos",
            prompt + "video, audio, caption and thumbnail files from the app "
            "and your computer?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        removed = 0
        for video in videos:
            removed += remove_files(self.repo.delete(int(video["id"])))
        self.refresh()
        self.status_label.setText(
            f"Deleted {len(videos)} video(s) ({removed} file(s) removed).")

    def _rerender(self) -> None:
        """Clear the finished file(s) and re-run the edit stage so current
        settings (title card, background, music, effects) are applied.

        Operates on the selected rows, or on all rendered videos if none are
        selected. Voice and captions are not regenerated - only the video is
        rebuilt; change those on the Stories page if their settings changed.
        """
        rows = sorted({r.row() for r in self.table.selectionModel().selectedRows()})
        targets = ([self._videos[r] for r in rows] if rows
                   else list(self._videos))
        targets = [v for v in targets if v["audio_path"]]   # must have audio
        if not targets:
            self.status_label.setText("No rendered videos to re-render.")
            return
        if not rows:
            reply = QMessageBox.question(
                self, "Re-render all",
                f"Re-render all {len(targets)} videos with the current "
                "settings?\n\n(The title card, background, music and effects "
                "are rebuilt; voiceover and captions are kept.)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        for video in targets:
            self.repo.mark_for_rerender(int(video["id"]))
        self.refresh()
        self._run("edit", self.rerender_btn)

    def _run(self, stage: str, button: QPushButton) -> None:
        if not self.run_stage:
            return
        button.setEnabled(False)
        self.status_label.setText(f"Running {stage}... (see Logs for progress)")

        def done(result):
            button.setEnabled(True)
            stage_result = result.stage_results.get(stage)
            self.status_label.setText(
                stage_result.message if stage_result else "Done.")
            self.refresh()

        def error(message: str):
            button.setEnabled(True)
            self.status_label.setText(f"Error: {message.splitlines()[0]}")

        self.run_stage(stage, done, error)
