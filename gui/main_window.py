"""Main window: sidebar navigation + stacked pages."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QStackedWidget, QVBoxLayout,
                               QWidget, QMainWindow)

from app.config import Config
from app.pipeline import Pipeline
from database.db import Database
from gui.pages.analytics import AnalyticsPage
from gui.pages.dashboard import DashboardPage
from gui.pages.logs import LogsPage
from gui.pages.queue import QueuePage
from gui.pages.research import ResearchPage
from gui.pages.settings_page import SettingsPage
from gui.pages.stories import StoriesPage
from gui.pages.uploads import UploadsPage
from gui.pages.videos import VideosPage
from gui.theme import STYLESHEET
from gui.workers import TaskRunner

log = logging.getLogger("acf.gui")

NAV_ITEMS = [
    ("Dashboard", "dashboard"),
    ("Research", "research"),
    ("Stories", "stories"),
    ("Videos", "videos"),
    ("Uploads", "uploads"),
    ("Analytics", "analytics"),
    ("Queue", "queue"),
    ("Logs", "logs"),
    ("Settings", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self, config: Config, db: Database):
        super().__init__()
        self.config = config
        self.db = db
        self.runner = TaskRunner()
        self._pipeline_busy = False

        self.setWindowTitle("AI Content Factory")
        self.resize(1280, 800)
        self.setStyleSheet(STYLESHEET)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------------- sidebar
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(0, 0, 0, 12)
        side_layout.setSpacing(0)

        title = QLabel("AI Content Factory")
        title.setObjectName("AppTitle")
        subtitle = QLabel("v1.0 - all agents live")
        subtitle.setObjectName("AppSubtitle")
        side_layout.addWidget(title)
        side_layout.addWidget(subtitle)

        self.stack = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        # ---------------- pages
        self.dashboard = DashboardPage(config, db, on_generate=self.run_full_pipeline)
        self.research = ResearchPage(config, db, run_stage=self.run_stage)
        self.stories = StoriesPage(config, db, run_stage=self.run_stage)
        self.videos = VideosPage(config, db, run_stage=self.run_stage)
        self.uploads = UploadsPage(config, db, run_stage=self.run_stage,
                                   runner=self.runner)
        self.analytics = AnalyticsPage(config, db, run_stage=self.run_stage)
        self.queue = QueuePage(db)
        self.logs = LogsPage()
        self.settings = SettingsPage(config, check_providers=self.check_providers)

        pages = {
            "dashboard": self.dashboard, "research": self.research,
            "stories": self.stories, "videos": self.videos,
            "uploads": self.uploads, "analytics": self.analytics,
            "queue": self.queue, "logs": self.logs, "settings": self.settings,
        }

        for index, (label, key) in enumerate(NAV_ITEMS):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(button, index)
            side_layout.addWidget(button)
            self.stack.addWidget(pages[key])
            button.clicked.connect(
                lambda _=False, i=index: self._switch_page(i))

        side_layout.addStretch()
        self.nav_group.button(0).setChecked(True)

        root.addWidget(sidebar)
        root.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)

        self._setup_tray()
        log.info("GUI ready")

    def _setup_tray(self) -> None:
        """System tray icon used for desktop notifications."""
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication, QStyle, QSystemTrayIcon

        from app.notifications import register_desktop_handler

        icon: QIcon = QApplication.instance().style().standardIcon(
            QStyle.StandardPixmap.SP_MediaPlay)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("AI Content Factory")
        self.tray.show()

        def show_message(title: str, message: str) -> None:
            self.tray.showMessage(title, message,
                                  QSystemTrayIcon.MessageIcon.Information,
                                  8000)

        register_desktop_handler(show_message)

    # ------------------------------------------------------------------
    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

    def _new_pipeline(self) -> Pipeline:
        # Fresh Pipeline per run so config edits apply immediately.
        return Pipeline(self.config, self.db)

    # ------------------------------------------------------------------ actions
    def run_full_pipeline(self) -> None:
        if self._pipeline_busy:
            QMessageBox.information(self, "Busy", "A pipeline run is already active.")
            return
        self._pipeline_busy = True
        self.dashboard.generate_btn.setEnabled(False)
        self.dashboard.generate_btn.setText("Running pipeline...")
        pipeline = self._new_pipeline()

        def done(result):
            self._pipeline_finished(f"Pipeline finished: {result.summary()}")

        def error(message: str):
            self._pipeline_finished(f"Pipeline error: {message.splitlines()[0]}")

        self.runner.submit(pipeline.run_all, done, error)

    def _pipeline_finished(self, message: str) -> None:
        self._pipeline_busy = False
        self.dashboard.generate_btn.setEnabled(True)
        self.dashboard.generate_btn.setText("Generate  -  run full pipeline")
        self.dashboard.refresh()
        self.stories.refresh()
        log.info(message)

    def run_stage(self, stage: str, on_done, on_error) -> None:
        """Pages call this to execute one stage on a worker thread."""
        pipeline = self._new_pipeline()
        self.runner.submit(lambda: pipeline.run_stage(stage), on_done, on_error)

    def check_providers(self, callback) -> None:
        pipeline = self._new_pipeline()

        def done(availability):
            callback(availability)
            self.dashboard.set_provider_status(availability)

        self.runner.submit(pipeline.llm.availability, done,
                           lambda msg: callback({}))
