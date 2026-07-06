# gui/views/dashboard.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QLabel, QFrame,
)

from gui.viewmodels import compute_dashboard_stats, DashboardStats


class _StatCard(QFrame):
    def __init__(self, label: str, value: str = "0"):
        super().__init__()
        self.setObjectName("stat")
        lay = QVBoxLayout(self)
        self.value_lbl = QLabel(value)
        self.value_lbl.setObjectName("stat-value")
        self.label_lbl = QLabel(label)
        self.label_lbl.setObjectName("stat-label")
        lay.addWidget(self.value_lbl)
        lay.addWidget(self.label_lbl)
        self.setStyleSheet(
            "QFrame#stat { background-color: #171a21;"
            " border: 1px solid #2a2f3a; border-radius: 8px; padding: 16px; }")


class DashboardView(QWidget):
    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Dashboard")
        title.setObjectName("title")
        v.addWidget(title)

        self.grid = QGridLayout()
        self.grid.setSpacing(12)
        v.addLayout(self.grid)
        self.stat_values = []
        self.cards: list[_StatCard] = []
        for i, label in enumerate(("Videos Created", "Videos Uploaded",
                                   "Pending Approval", "Current Jobs")):
            card = _StatCard(label)
            self.grid.addWidget(card, 0, i)
            self.cards.append(card)
            self.stat_values.append(card.value_lbl)

        # System status section.
        v.addSpacing(16)
        status_title = QLabel("System Status")
        status_title.setObjectName("title")
        v.addWidget(status_title)
        self.status_frame = QFrame()
        sf = QVBoxLayout(self.status_frame)
        self.lbl_ffmpeg = QLabel("ffmpeg: —")
        self.lbl_db = QLabel("DB: —")
        self.lbl_ollama = QLabel("Ollama: —")
        self.lbl_models = QLabel("Models: —")
        for lbl in (self.lbl_ffmpeg, self.lbl_db,
                    self.lbl_ollama, self.lbl_models):
            lbl.setObjectName("muted")
            sf.addWidget(lbl)
        v.addWidget(self.status_frame)
        v.addStretch()

    def refresh(self) -> None:
        stats = DashboardStats()
        if self.container and self.container.db:
            stats = compute_dashboard_stats(self.container.db)
        self.stat_values[0].setText(str(stats.videos_created))
        self.stat_values[1].setText(str(stats.videos_uploaded))
        self.stat_values[2].setText(str(stats.videos_pending))
        self.stat_values[3].setText(str(stats.current_jobs))
        if self.container:
            self.lbl_db.setText(f"DB: {self.container.paths.db_path}")
