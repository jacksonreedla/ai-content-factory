# gui/views/settings.py
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
    QMessageBox, QFileDialog,
)


class SettingsView(QWidget):
    """Tabbed settings editor bound to the config dataclasses."""

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("title")
        v.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._general_tab(), "General")
        self.tabs.addTab(self._content_tab(), "Content Sources")
        self.tabs.addTab(self._llm_tab(), "AI / LLM")
        self.tabs.addTab(self._voice_tab(), "Voice")
        self.tabs.addTab(self._editor_tab(), "Editor")
        self.tabs.addTab(self._publishing_tab(), "Publishing")
        self.tabs.addTab(self._secrets_tab(), "Secrets")
        self.tabs.addTab(self._about_tab(), "About")
        v.addWidget(self.tabs, 1)

        bar = QHBoxLayout()
        save_btn = QPushButton("💾  Save settings")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._on_save)
        bar.addStretch(); bar.addWidget(save_btn)
        v.addLayout(bar)

        self._load()

    # --- tabs --------------------------------------------------------------

    def _general_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.theme = QComboBox(); self.theme.addItems(["dark"])
        self.concurrent = QSpinBox(); self.concurrent.setRange(1, 8)
        self.scoring_min = QDoubleSpinBox(); self.scoring_min.setRange(0, 100)
        f.addRow("Theme", self.theme)
        f.addRow("Concurrent jobs", self.concurrent)
        f.addRow("Min story score (overall)", self.scoring_min)
        return w

    def _content_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.subreddits = QLineEdit()
        self.reddit_min_score = QSpinBox(); self.reddit_min_score.setRange(0, 1000000)
        self.reddit_min_comments = QSpinBox(); self.reddit_min_comments.setRange(0, 1000000)
        self.reddit_sort = QComboBox(); self.reddit_sort.addItems(["hot","top","new","rising"])
        self.reddit_limit = QSpinBox(); self.reddit_limit.setRange(1, 100)
        f.addRow("Subreddits (comma-sep)", self.subreddits)
        f.addRow("Min score", self.reddit_min_score)
        f.addRow("Min comments", self.reddit_min_comments)
        f.addRow("Sort", self.reddit_sort)
        f.addRow("Limit", self.reddit_limit)
        return w

    def _llm_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.llm_provider = QLineEdit()
        self.ollama_host = QLineEdit()
        self.ollama_model = QLineEdit()
        f.addRow("Active provider", self.llm_provider)
        f.addRow("Ollama host", self.ollama_host)
        f.addRow("Ollama model", self.ollama_model)
        return w

    def _voice_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.voice_engine = QLineEdit()
        self.voice_speed = QDoubleSpinBox(); self.voice_speed.setRange(0.25, 4.0); self.voice_speed.setSingleStep(0.05)
        self.voice_pitch = QDoubleSpinBox(); self.voice_pitch.setRange(0.25, 4.0); self.voice_pitch.setSingleStep(0.05)
        self.voice_volume = QDoubleSpinBox(); self.voice_volume.setRange(0.0, 2.0); self.voice_volume.setSingleStep(0.05)
        f.addRow("Active engine", self.voice_engine)
        f.addRow("Speed", self.voice_speed)
        f.addRow("Pitch", self.voice_pitch)
        f.addRow("Volume", self.voice_volume)
        return w

    def _editor_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.editor_format = QComboBox()
        self.editor_format.addItems(["shorts_vertical_9_16","tiktok_9_16","reels_9_16","youtube_16_9"])
        self.editor_bg = QLineEdit()
        f.addRow("Default format", self.editor_format)
        f.addRow("Background category", self.editor_bg)
        return w

    def _publishing_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.publish_privacy = QComboBox()
        self.publish_privacy.addItems(["draft","private","unlisted","public"])
        f.addRow("Default privacy", self.publish_privacy)
        return w

    def _secrets_tab(self):
        w = QWidget(); f = QFormLayout(w)
        self.secret_client_id = QLineEdit()
        self.secret_client_secret = QLineEdit()
        self.secret_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self.secret_user_agent = QLineEdit()
        self.yt_secrets_path = QLineEdit()
        pick_btn = QPushButton("Choose client_secrets.json...")
        pick_btn.clicked.connect(self._pick_yt_secrets)
        f.addRow("Reddit client ID", self.secret_client_id)
        f.addRow("Reddit client secret", self.secret_client_secret)
        f.addRow("Reddit user agent", self.secret_user_agent)
        f.addRow("YouTube client secrets", self.yt_secrets_path)
        f.addRow(pick_btn)
        oauth_btn = QPushButton("🔑  Run YouTube OAuth")
        oauth_btn.clicked.connect(self._run_oauth)
        f.addRow(oauth_btn)
        return w

    def _about_tab(self):
        w = QWidget(); v = QVBoxLayout(w)
        v.addWidget(QLabel("AI Content Factory"))
        lbl = QLabel("v0.1.0\n\nAutomated faceless YouTube video creation from Reddit stories.\n\n"
                     "User data: ~/.aicf/\nAll processing is local; nothing is uploaded without approval.")
        lbl.setObjectName("muted")
        v.addWidget(lbl); v.addStretch()
        return w

    # --- load / save -------------------------------------------------------

    def _load(self) -> None:
        if not self.container or not self.container.config:
            return
        cfg = self.container.config
        self.concurrent.setValue(cfg.general.concurrent_jobs)
        self.scoring_min.setValue(cfg.scoring.min_overall)
        self.subreddits.setText(", ".join(cfg.reddit.subreddits))
        self.reddit_min_score.setValue(cfg.reddit.min_score)
        self.reddit_min_comments.setValue(cfg.reddit.min_comments)
        self.reddit_sort.setCurrentText(cfg.reddit.sort)
        self.reddit_limit.setValue(cfg.reddit.limit)
        self.llm_provider.setText(cfg.llm.active_provider)
        self.ollama_host.setText(cfg.llm.ollama_host)
        self.ollama_model.setText(cfg.llm.ollama_model)
        self.voice_engine.setText(cfg.voice.active_engine)
        self.voice_speed.setValue(cfg.voice.speed)
        self.voice_pitch.setValue(cfg.voice.pitch)
        self.voice_volume.setValue(cfg.voice.volume)
        self.editor_format.setCurrentText(cfg.editor.default_format)
        self.editor_bg.setText(cfg.editor.background_category)
        self.publish_privacy.setCurrentText(cfg.publishing.default_privacy)
        # Secrets.
        from app.secrets import load_secrets
        s = load_secrets(self.container.paths)
        self.secret_client_id.setText(s.reddit_client_id)
        self.secret_client_secret.setText(s.reddit_client_secret)
        self.secret_user_agent.setText(s.reddit_user_agent)

    def _on_save(self) -> None:
        if not self.container or not self.container.config:
            return
        cfg = self.container.config
        cfg.general.concurrent_jobs = self.concurrent.value()
        cfg.scoring.min_overall = self.scoring_min.value()
        cfg.reddit.subreddits = [s.strip() for s in self.subreddits.text().split(",") if s.strip()]
        cfg.reddit.min_score = self.reddit_min_score.value()
        cfg.reddit.min_comments = self.reddit_min_comments.value()
        cfg.reddit.sort = self.reddit_sort.currentText()
        cfg.reddit.limit = self.reddit_limit.value()
        cfg.llm.active_provider = self.llm_provider.text()
        cfg.llm.ollama_host = self.ollama_host.text()
        cfg.llm.ollama_model = self.ollama_model.text()
        cfg.voice.active_engine = self.voice_engine.text()
        cfg.voice.speed = self.voice_speed.value()
        cfg.voice.pitch = self.voice_pitch.value()
        cfg.voice.volume = self.voice_volume.value()
        cfg.editor.default_format = self.editor_format.currentText()
        cfg.editor.background_category = self.editor_bg.text()
        cfg.publishing.default_privacy = self.publish_privacy.currentText()
        from app.config import save_config
        save_config(cfg, self.container.paths)
        # Secrets.
        from app.secrets import Secrets, save_secrets
        save_secrets(Secrets(
            reddit_client_id=self.secret_client_id.text(),
            reddit_client_secret=self.secret_client_secret.text(),
            reddit_user_agent=self.secret_user_agent.text() or "ai-content-factory/0.1",
        ), self.container.paths)
        QMessageBox.information(self, "Saved", "Settings saved. Restart to apply some changes.")

    def _pick_yt_secrets(self):
        path, _ = QFileDialog.getOpenFileName(self, "YouTube client_secrets.json", "",
                                              "JSON (*.json)")
        if path:
            self.yt_secrets_path.setText(path)

    def _run_oauth(self):
        from pathlib import Path
        cs = self.yt_secrets_path.text().strip()
        if not cs or not Path(cs).exists():
            QMessageBox.warning(self, "OAuth", "Pick a client_secrets.json first.")
            return
        try:
            from infra.youtube.oauth import run_oauth_flow, MissingYouTubeDeps
            token = self.container.paths.data_dir / "yt_token.json"
            run_oauth_flow(Path(cs), token)
            QMessageBox.information(self, "OAuth", "YouTube authorized.")
        except MissingYouTubeDeps as e:
            QMessageBox.warning(self, "OAuth", str(e))
        except Exception as e:
            QMessageBox.warning(self, "OAuth failed", str(e))
