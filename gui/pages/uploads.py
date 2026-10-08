"""Uploads page: TikTok connection status + upload history."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from api.tiktok_client import TikTokClient
from app.config import Config
from database.db import Database
from database.repositories import UploadRepo
from gui.widgets import PageHeader


class UploadsPage(QWidget):
    def __init__(self, config: Config, db: Database, run_stage=None,
                 runner=None):
        super().__init__()
        self.config = config
        self.db = db
        self.run_stage = run_stage
        self.runner = runner
        self.repo = UploadRepo(db)
        self._profile_url = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Uploads - TikTok"))

        self.conn_label = QLabel("")
        self.conn_label.setObjectName("Hint")
        self.conn_label.setWordWrap(True)
        layout.addWidget(self.conn_label)

        toolbar = QHBoxLayout()
        self.connect_btn = QPushButton("Connect TikTok")
        self.connect_btn.clicked.connect(self._connect)
        toolbar.addWidget(self.connect_btn)

        self.upload_btn = QPushButton("Post rendered videos")
        self.upload_btn.setObjectName("Primary")
        self.upload_btn.clicked.connect(
            lambda: self._run("upload", self.upload_btn))
        toolbar.addWidget(self.upload_btn)

        toolbar.addStretch()
        self.status_label = QLabel("")
        self.status_label.setObjectName("Hint")
        toolbar.addWidget(self.status_label)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Video", "Privacy", "Uploaded", "Status",
             "Publish ID / error"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(1, 280)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, stretch=1)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        client = TikTokClient(config=self.config)
        if not client.is_configured():
            self.conn_label.setText(
                "Not configured: create a TikTok app (Login Kit + Content "
                "Posting API with Direct Post), then paste the Client Key and "
                "Client Secret into Settings -> config.json under 'tiktok'. "
                "See docs/tiktok_api_request.md, then click Connect TikTok.")
        else:
            try:
                authorized = client.is_authorized()
            except Exception:
                authorized = False
            self.conn_label.setText(
                "Connected - ready to post. Note: until your app passes "
                "TikTok's audit, posts are forced to private (SELF_ONLY)."
                if authorized
                else "Configured but not connected - click Connect TikTok.")

        self._uploads = self.repo.recent(100)
        self.table.setRowCount(len(self._uploads))
        for row, upload in enumerate(self._uploads):
            detail = upload["remote_id"] or (upload["error"] or "")
            values = [str(upload["id"]), upload.get("video_title") or "",
                      upload["visibility"], upload["uploaded_at"] or "-",
                      upload["status"], detail[:160]]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))

    def _open_selected(self, _item) -> None:
        # TikTok doesn't expose a public watch URL by publish_id; open the
        # connected creator's profile if we know it.
        if self._profile_url:
            QDesktopServices.openUrl(QUrl(self._profile_url))

    def _connect(self) -> None:
        """Run the OAuth flow on a worker thread (it blocks on the browser)."""
        if not self.runner:
            return
        self.connect_btn.setEnabled(False)
        self.status_label.setText("A browser window should open - sign in "
                                  "and allow access...")

        def do_auth():
            client = TikTokClient(config=self.config)
            client.authorize()
            return client.username()

        def done(username):
            self.connect_btn.setEnabled(True)
            if username:
                self._profile_url = f"https://www.tiktok.com/@{username}"
                self.status_label.setText(f"Connected as @{username}")
            else:
                self.status_label.setText("Connected to TikTok.")
            self.refresh()

        def error(message: str):
            self.connect_btn.setEnabled(True)
            self.status_label.setText(f"Error: {message.splitlines()[0][:160]}")

        self.runner.submit(do_auth, done, error)

    def _run(self, stage: str, button: QPushButton) -> None:
        if not self.run_stage:
            return
        button.setEnabled(False)
        self.status_label.setText("Posting... (see Logs)")

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
