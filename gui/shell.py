# gui/shell.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame, QListWidget,
    QStackedWidget, QStatusBar, QLabel, QListWidgetItem,
)

from gui.theme import load_theme
from gui.views.placeholder import PlaceholderView

NAV = [
    ("Dashboard", "📊"),
    ("Research",  "🔍"),
    ("Pipeline",  "⚙️"),
    ("Approval",  "✅"),
    ("Library",   "📁"),
    ("History",   "🕐"),
    ("Settings",  "🔧"),
    ("Logs",      "📜"),
]


class MainWindow(QMainWindow):
    def __init__(self, container=None):
        super().__init__()
        self.container = container
        self.setWindowTitle("AI Content Factory")
        self.resize(1280, 800)

        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Sidebar.
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sb = QVBoxLayout(self.sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)
        brand = QLabel("✦ AI Content Factory")
        brand.setObjectName("brand")
        sb.addWidget(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for label, icon in NAV:
            QListWidgetItem(f"  {icon}   {label}", self.nav)
        self.nav.setCurrentRow(0)
        self.nav.currentRowChanged.connect(self._on_nav)
        sb.addWidget(self.nav, 1)
        lay.addWidget(self.sidebar)

        # Stack: Dashboard + Research + Pipeline + Approval are real.
        self.stack = QStackedWidget()
        from gui.views.dashboard import DashboardView
        from gui.views.research import ResearchView
        from gui.views.pipeline import PipelineView
        from gui.views.approval import ApprovalView
        self.dashboard = DashboardView(container=container)
        self.stack.addWidget(self.dashboard)
        self.research = ResearchView(container=container)
        self.stack.addWidget(self.research)
        self.pipeline = PipelineView(container=container)
        self.stack.addWidget(self.pipeline)
        self.approval = ApprovalView(container=container)
        self.stack.addWidget(self.approval)
        placeholders = ["Library", "History", "Settings", "Logs"]
        for label in placeholders:
            self.stack.addWidget(PlaceholderView(label))
        lay.addWidget(self.stack, 1)

        # Status bar.
        sb_bar = QStatusBar()
        sb_bar.showMessage("Ready")
        self.setStatusBar(sb_bar)

        self.setStyleSheet(load_theme())

    def _on_nav(self, row: int) -> None:
        self.stack.setCurrentIndex(row)

    def refresh_dashboard(self) -> None:
        if hasattr(self, "dashboard"):
            self.dashboard.refresh()
