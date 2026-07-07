# gui/wizard.py
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)


class FirstRunWizard(QDialog):
    """Multi-page first-run setup. Shown when secrets.json is missing.

    Pages: welcome → system check → Reddit creds → YouTube → done. Each page
    is optional; the user can skip anything and configure later in Settings.
    """

    def __init__(self, container, parent=None):
        super().__init__(parent)
        self.container = container
        self.setWindowTitle("Welcome — First Run Setup")
        self.resize(640, 480)
        v = QVBoxLayout(self)
        self.stack = QStackedWidget()
        v.addWidget(self.stack, 1)

        self.stack.addWidget(self._welcome_page())
        self.stack.addWidget(self._checks_page())
        self.stack.addWidget(self._reddit_page())
        self.stack.addWidget(self._youtube_page())
        self.stack.addWidget(self._done_page())

        nav = QHBoxLayout()
        self.back_btn = QPushButton("◀  Back"); self.back_btn.clicked.connect(self._back)
        self.next_btn = QPushButton("Next  ▶"); self.next_btn.setObjectName("primary")
        self.next_btn.clicked.connect(self._next)
        self.finish_btn = QPushButton("✓  Finish"); self.finish_btn.clicked.connect(self.accept)
        self.finish_btn.hide()
        nav.addStretch(); nav.addWidget(self.back_btn)
        nav.addWidget(self.next_btn); nav.addWidget(self.finish_btn)
        v.addLayout(nav)
        self._update_nav()

    # --- pages -------------------------------------------------------------

    def _welcome_page(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Welcome to AI Content Factory</h2>"))
        v.addWidget(QLabel(
            "This wizard checks your system and sets up Reddit + YouTube.\n"
            "Everything runs locally. You can skip any step and configure later "
            "in Settings.\n\nAll data lives under ~/.aicf/."))
        v.addStretch()
        return w

    def _checks_page(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>System check</h2>"))
        self.checks_view = QTextEdit(); self.checks_view.setReadOnly(True)
        v.addWidget(self.checks_view)
        check_btn = QPushButton("🔍  Check now")
        check_btn.clicked.connect(self._run_checks)
        v.addWidget(check_btn)
        return w

    def _reddit_page(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Reddit</h2>"))
        v.addWidget(QLabel("Create a Reddit app at reddit.com/prefs/apps (script type)."))
        self.rid = QLineEdit(); self.rid.setPlaceholderText("client ID")
        self.rsec = QLineEdit(); self.rsec.setPlaceholderText("client secret")
        self.rsec.setEchoMode(QLineEdit.EchoMode.Password)
        self.rua = QLineEdit("ai-content-factory/0.1")
        for lbl, f in (("Client ID", self.rid), ("Client secret", self.rsec),
                       ("User agent", self.rua)):
            v.addWidget(QLabel(lbl)); v.addWidget(f)
        v.addStretch()
        return w

    def _youtube_page(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>YouTube</h2>"))
        v.addWidget(QLabel("Optional. Create OAuth credentials in Google Cloud Console, "
                           "download client_secrets.json."))
        self.yt_path = QLineEdit(); self.yt_path.setPlaceholderText("path to client_secrets.json")
        pick = QPushButton("Choose file..."); pick.clicked.connect(self._pick_yt)
        v.addWidget(self.yt_path); v.addWidget(pick)
        v.addStretch()
        return w

    def _done_page(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("<h2>Ready!</h2>"))
        v.addWidget(QLabel("You're set. Use the Research view to find stories, "
                           "the Pipeline to watch them process, and Approval to "
                           "publish. You can change anything in Settings later."))
        v.addStretch()
        return w

    # --- actions -----------------------------------------------------------

    def _run_checks(self):
        from app.system_checks import check_all
        s = check_all(ollama_host=self.container.config.llm.ollama_host)
        lines = ["System status:\n"]
        for k, ok in s.items():
            mark = "✅" if ok else "❌"
            lines.append(f"  {mark}  {k}: {'available' if ok else 'not found'}")
        lines.append("\n(ffmpeg is required to render video; Ollama/Piper are "
                     "recommended but the app runs without them.)")
        self.checks_view.setPlainText("\n".join(lines))

    def _pick_yt(self):
        path, _ = QFileDialog.getOpenFileName(self, "client_secrets.json", "",
                                              "JSON (*.json)")
        if path:
            self.yt_path.setText(path)

    def _back(self):
        i = self.stack.currentIndex()
        if i > 0:
            self.stack.setCurrentIndex(i - 1)
        self._update_nav()

    def _next(self):
        i = self.stack.currentIndex()
        if i < self.stack.count() - 1:
            self.stack.setCurrentIndex(i + 1)
        self._update_nav()

    def _update_nav(self):
        i = self.stack.currentIndex()
        self.back_btn.setEnabled(i > 0)
        last = i == self.stack.count() - 1
        self.next_btn.setVisible(not last)
        self.finish_btn.setVisible(last)

    def persist(self) -> None:
        """Save whatever the user filled in. Called on accept."""
        from app.secrets import Secrets, save_secrets
        s = Secrets(
            reddit_client_id=self.rid.text().strip(),
            reddit_client_secret=self.rsec.text().strip(),
            reddit_user_agent=self.rua.text().strip() or "ai-content-factory/0.1",
        )
        save_secrets(s, self.container.paths)
        # Stash the YouTube secrets path on the container so Settings can pick it up.
        if self.yt_path.text().strip():
            self.container._wizard_yt_secrets = self.yt_path.text().strip()
