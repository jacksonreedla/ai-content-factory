"""Settings page: Reddit credentials, AI providers, pipeline defaults."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from app.config import Config
from gui.widgets import PageHeader

STYLES = ["storytelling", "dramatic", "calm", "funny", "serious",
          "horror", "true_crime", "documentary", "conversational"]
LENGTHS = [30, 60, 180, 300, 600]
TASKS = ["score", "rewrite", "metadata", "thumbnail_text"]


class SettingsPage(QWidget):
    def __init__(self, config: Config, check_providers=None):
        super().__init__()
        self.config = config
        self.check_providers = check_providers

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addWidget(PageHeader("Settings"))

        tabs = QTabWidget()
        tabs.addTab(self._reddit_tab(), "Reddit")
        tabs.addTab(self._ai_tab(), "AI providers")
        tabs.addTab(self._pipeline_tab(), "Pipeline")
        tabs.addTab(self._voice_tab(), "Voice && captions")
        tabs.addTab(self._title_card_tab(), "Title card")
        tabs.addTab(self._upload_tab(), "Upload")
        layout.addWidget(tabs, stretch=1)

        bottom = QHBoxLayout()
        self.save_btn = QPushButton("Save settings")
        self.save_btn.setObjectName("Primary")
        self.save_btn.clicked.connect(self._save)
        bottom.addWidget(self.save_btn)
        self.status = QLabel("")
        self.status.setObjectName("Hint")
        bottom.addWidget(self.status)
        bottom.addStretch()
        layout.addLayout(bottom)

    # ------------------------------------------------------------ tabs
    def _reddit_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        hint = QLabel(
            "Create a free 'script' app at reddit.com/prefs/apps and paste the "
            "id/secret here. The app only reads public posts.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow(hint)

        self.reddit_id = QLineEdit(self.config.get("reddit.client_id", ""))
        form.addRow("Client ID", self.reddit_id)
        self.reddit_secret = QLineEdit(self.config.get("reddit.client_secret", ""))
        self.reddit_secret.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Client secret", self.reddit_secret)
        self.reddit_agent = QLineEdit(self.config.get("reddit.user_agent", ""))
        form.addRow("User agent", self.reddit_agent)
        return w

    def _ai_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.ollama_url = QLineEdit(
            self.config.get("ai.ollama.base_url", "http://localhost:11434"))
        form.addRow("Ollama URL", self.ollama_url)

        self.claude_key = QLineEdit(self.config.get("ai.claude.api_key", ""))
        self.claude_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.claude_key.setPlaceholderText("optional - enables Claude fallback")
        form.addRow("Claude API key", self.claude_key)

        self.openai_key = QLineEdit(self.config.get("ai.openai.api_key", ""))
        self.openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key.setPlaceholderText("optional - enables OpenAI fallback")
        form.addRow("OpenAI API key", self.openai_key)

        form.addRow(QLabel(""))
        form.addRow(QLabel("Model per task (provider:model)"))
        self.task_edits: dict[str, tuple[QComboBox, QLineEdit]] = {}
        for task in TASKS:
            row = QHBoxLayout()
            provider = QComboBox()
            provider.addItems(["ollama", "claude", "openai"])
            provider.setCurrentText(
                self.config.get(f"ai.tasks.{task}.provider", "ollama"))
            model = QLineEdit(self.config.get(f"ai.tasks.{task}.model", "llama3.1"))
            row.addWidget(provider)
            row.addWidget(model)
            container = QWidget()
            container.setLayout(row)
            form.addRow(task, container)
            self.task_edits[task] = (provider, model)

        self.test_btn = QPushButton("Test provider availability")
        self.test_btn.clicked.connect(self._test_providers)
        form.addRow("", self.test_btn)
        self.provider_status = QLabel("")
        self.provider_status.setObjectName("Hint")
        form.addRow("", self.provider_status)
        return w

    def _pipeline_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0, 10)
        self.threshold_spin.setSingleStep(0.5)
        self.threshold_spin.setValue(
            float(self.config.get("scoring.min_overall_score", 6.5)))
        form.addRow("Minimum story score (0-10)", self.threshold_spin)

        self.auto_approve = QCheckBox(
            "Auto-approve stories above threshold (skip manual review)")
        self.auto_approve.setChecked(self.config.get("scoring.auto_approve", False))
        form.addRow("", self.auto_approve)

        self.style_combo = QComboBox()
        self.style_combo.addItems(STYLES)
        self.style_combo.setCurrentText(
            self.config.get("rewrite.style", "storytelling"))
        form.addRow("Narration style", self.style_combo)

        self.length_combo = QComboBox()
        self.length_combo.addItems([f"{s} seconds" for s in LENGTHS])
        current = int(self.config.get("rewrite.target_seconds", 60))
        if current in LENGTHS:
            self.length_combo.setCurrentIndex(LENGTHS.index(current))
        form.addRow("Target length", self.length_combo)

        self.wpm_spin = QSpinBox()
        self.wpm_spin.setRange(100, 220)
        self.wpm_spin.setValue(int(self.config.get("rewrite.words_per_minute", 155)))
        form.addRow("Narration words per minute", self.wpm_spin)

        self.engagement_check = QCheckBox(
            "End each narration with a question to the audience (drives comments)")
        self.engagement_check.setChecked(
            self.config.get("rewrite.engagement_question", True))
        form.addRow("", self.engagement_check)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["shorts", "landscape"])
        self.format_combo.setCurrentText(self.config.get("video.format", "shorts"))
        form.addRow("Video format", self.format_combo)

        self.bg_category = QLineEdit(
            self.config.get("video.background_category", "minecraft"))
        form.addRow("Background category", self.bg_category)

        self.bg_selection = QComboBox()
        self.bg_selection.addItems(["random", "sequential"])
        self.bg_selection.setCurrentText(
            self.config.get("video.background_selection", "random"))
        form.addRow("Background selection", self.bg_selection)

        self.music_check = QCheckBox("Mix background music (data/music folder)")
        self.music_check.setChecked(self.config.get("video.music_enabled", True))
        form.addRow("", self.music_check)

        self.music_volume = QSpinBox()
        self.music_volume.setRange(-40, 0)
        self.music_volume.setSuffix(" dB")
        self.music_volume.setValue(int(self.config.get("video.music_volume_db", -18)))
        form.addRow("Music volume", self.music_volume)
        return w

    def _voice_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        hint = QLabel(
            "Kokoro = free local neural voices (pip install kokoro soundfile; "
            "first run downloads the model). Use Voice ID am_adam for US male. "
            "Piper needs piper.exe + a .onnx model. SAPI = built-in Windows "
            "voices. ElevenLabs/OpenAI activate when a key is present.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow(hint)

        self.voice_engine = QComboBox()
        self.voice_engine.addItems(["kokoro", "piper", "sapi", "elevenlabs", "openai"])
        self.voice_engine.setCurrentText(self.config.get("voice.engine", "piper"))
        form.addRow("TTS engine", self.voice_engine)

        self.voice_id_edit = QLineEdit(self.config.get("voice.voice_id", ""))
        self.voice_id_edit.setPlaceholderText("e.g. am_adam (Kokoro US male)")
        form.addRow("Voice ID", self.voice_id_edit)

        self.voice_speed = QDoubleSpinBox()
        self.voice_speed.setRange(0.5, 2.0)
        self.voice_speed.setSingleStep(0.05)
        self.voice_speed.setValue(float(self.config.get("voice.speed", 1.0)))
        form.addRow("Speaking speed", self.voice_speed)

        self.piper_exe = QLineEdit(self.config.get("voice.piper_exe", "piper"))
        form.addRow("Piper executable", self.piper_exe)
        self.piper_model = QLineEdit(self.config.get("voice.piper_model", ""))
        self.piper_model.setPlaceholderText(r"C:\path\to\en_US-voice.onnx")
        form.addRow("Piper voice model", self.piper_model)

        self.eleven_key = QLineEdit(self.config.get("voice.elevenlabs_api_key", ""))
        self.eleven_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.eleven_key.setPlaceholderText("optional")
        form.addRow("ElevenLabs API key", self.eleven_key)

        form.addRow(QLabel(""))
        self.caption_mode = QComboBox()
        self.caption_mode.addItems(["word", "sentence"])
        self.caption_mode.setCurrentText(self.config.get("captions.mode", "word"))
        form.addRow("Caption mode", self.caption_mode)

        self.caption_preset = QComboBox()
        self.caption_preset.addItems(["bubble", "bold_center", "yellow_pop",
                                      "minimal", "top_bar"])
        self.caption_preset.setCurrentText(
            self.config.get("captions.preset", "bubble"))
        form.addRow("Caption preset", self.caption_preset)

        self.whisper_model = QComboBox()
        self.whisper_model.addItems(["tiny", "base", "small", "medium", "large-v3"])
        self.whisper_model.setCurrentText(
            self.config.get("subtitles.whisper_model", "base"))
        form.addRow("Whisper model", self.whisper_model)
        return w

    def _title_card_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        form = QFormLayout()

        hint = QLabel(
            "Each video opens with a Reddit-style title card. The post title is "
            "read aloud over the card, which then fades out as the captions "
            "begin. Manage the poster accounts shown on the card below.")
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        form.addRow(hint)

        self.card_enabled = QCheckBox("Show a title card at the start of each video")
        self.card_enabled.setChecked(
            bool(self.config.get("video.title_card.enabled", True)))
        form.addRow("", self.card_enabled)

        self.card_fade = QDoubleSpinBox()
        self.card_fade.setRange(0.0, 3.0)
        self.card_fade.setSingleStep(0.1)
        self.card_fade.setSuffix(" s")
        self.card_fade.setValue(
            float(self.config.get("video.title_card.fade_seconds", 0.5)))
        form.addRow("Fade-out duration", self.card_fade)

        self.card_upvotes = QLineEdit(
            str(self.config.get("video.title_card.upvotes", "99+")))
        form.addRow("Upvotes label", self.card_upvotes)
        self.card_comments = QLineEdit(
            str(self.config.get("video.title_card.comments", "99+")))
        form.addRow("Comments label", self.card_comments)

        self.card_default_account = QComboBox()
        form.addRow("Default account", self.card_default_account)
        layout.addLayout(form)

        layout.addWidget(QLabel(
            "Accounts - username, optional avatar image path, and verified badge:"))
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Username", "Avatar image path (optional)", "Verified"])
        self.accounts_table.setColumnWidth(0, 200)
        self.accounts_table.setColumnWidth(1, 320)
        layout.addWidget(self.accounts_table, stretch=1)

        for acct in (self.config.get("accounts", []) or []):
            self._add_account_row(acct.get("name", ""), acct.get("avatar", ""),
                                  bool(acct.get("verified", False)))

        row = QHBoxLayout()
        add_btn = QPushButton("Add account")
        add_btn.clicked.connect(lambda: self._add_account_row("", "", False))
        del_btn = QPushButton("Remove selected")
        del_btn.clicked.connect(self._remove_account_row)
        row.addWidget(add_btn)
        row.addWidget(del_btn)
        row.addStretch()
        layout.addLayout(row)

        self._refresh_default_accounts()
        return w

    def _add_account_row(self, name: str, avatar: str, verified: bool) -> None:
        table = self.accounts_table
        r = table.rowCount()
        table.insertRow(r)
        table.setItem(r, 0, QTableWidgetItem(name))
        table.setItem(r, 1, QTableWidgetItem(avatar))
        check = QTableWidgetItem()
        check.setFlags(Qt.ItemFlag.ItemIsUserCheckable
                       | Qt.ItemFlag.ItemIsEnabled
                       | Qt.ItemFlag.ItemIsSelectable)
        check.setCheckState(Qt.CheckState.Checked if verified
                            else Qt.CheckState.Unchecked)
        table.setItem(r, 2, check)
        self._refresh_default_accounts()

    def _remove_account_row(self) -> None:
        rows = sorted({i.row() for i in self.accounts_table.selectedIndexes()},
                      reverse=True)
        for r in rows:
            self.accounts_table.removeRow(r)
        self._refresh_default_accounts()

    def _refresh_default_accounts(self) -> None:
        combo = self.card_default_account
        current = (combo.currentText() if combo.count()
                   else self.config.get("video.title_card.account", ""))
        names = []
        for r in range(self.accounts_table.rowCount()):
            item = self.accounts_table.item(r, 0)
            if item and item.text().strip():
                names.append(item.text().strip())
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("(first in list)")
        combo.addItems(names)
        idx = combo.findText(current)
        combo.setCurrentIndex(idx if idx >= 0 else 0)
        combo.blockSignals(False)

    def _upload_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self.visibility_combo = QComboBox()
        self.visibility_combo.addItems(["public", "friends", "followers",
                                        "private"])
        self.visibility_combo.setCurrentText(
            self.config.get("upload.default_visibility", "public"))
        form.addRow("Default visibility", self.visibility_combo)

        self.tiktok_key_edit = QLineEdit(self.config.get("tiktok.client_key", ""))
        self.tiktok_key_edit.setPlaceholderText("TikTok app Client Key")
        form.addRow("TikTok Client Key", self.tiktok_key_edit)

        self.tiktok_secret_edit = QLineEdit(
            self.config.get("tiktok.client_secret", ""))
        self.tiktok_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.tiktok_secret_edit.setPlaceholderText("TikTok app Client Secret")
        form.addRow("TikTok Client Secret", self.tiktok_secret_edit)

        self.tiktok_aigc_check = QCheckBox("Label posts as AI-generated")
        self.tiktok_aigc_check.setChecked(
            self.config.get("tiktok.label_ai_generated", True))
        form.addRow("", self.tiktok_aigc_check)

        self.tiktok_comment_check = QCheckBox("Disable comments on posts")
        self.tiktok_comment_check.setChecked(
            self.config.get("tiktok.disable_comment", False))
        form.addRow("", self.tiktok_comment_check)

        tags_hint = QLabel(
            "Tags & description are added to every video automatically.")
        tags_hint.setObjectName("Hint")
        tags_hint.setWordWrap(True)
        form.addRow(tags_hint)

        self.custom_tags_edit = QLineEdit(
            ", ".join(self.config.get("seo.custom_tags", [])))
        self.custom_tags_edit.setPlaceholderText(
            "reddit stories, storytime, aita  (comma separated)")
        form.addRow("Your tags", self.custom_tags_edit)

        self.tags_as_hashtags_check = QCheckBox(
            "Also add my tags as #hashtags in the caption")
        self.tags_as_hashtags_check.setChecked(
            self.config.get("seo.custom_tags_as_hashtags", True))
        form.addRow("", self.tags_as_hashtags_check)

        self.short_summary_check = QCheckBox(
            "Auto-add a short summary description")
        self.short_summary_check.setChecked(
            self.config.get("seo.short_summary", True))
        form.addRow("", self.short_summary_check)

        self.discord_edit = QLineEdit(
            self.config.get("notifications.discord_webhook", ""))
        self.discord_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.discord_edit.setPlaceholderText("optional Discord webhook URL")
        form.addRow("Discord webhook", self.discord_edit)

        self.desktop_notify_check = QCheckBox("Desktop notifications")
        self.desktop_notify_check.setChecked(
            self.config.get("notifications.desktop", True))
        form.addRow("", self.desktop_notify_check)
        return w

    # ------------------------------------------------------------ actions
    def _save(self) -> None:
        c = self.config
        c.set("reddit.client_id", self.reddit_id.text().strip(), persist=False)
        c.set("reddit.client_secret", self.reddit_secret.text().strip(), persist=False)
        c.set("reddit.user_agent", self.reddit_agent.text().strip(), persist=False)
        c.set("ai.ollama.base_url", self.ollama_url.text().strip(), persist=False)
        c.set("ai.claude.api_key", self.claude_key.text().strip(), persist=False)
        c.set("ai.openai.api_key", self.openai_key.text().strip(), persist=False)
        for task, (provider, model) in self.task_edits.items():
            c.set(f"ai.tasks.{task}.provider", provider.currentText(), persist=False)
            c.set(f"ai.tasks.{task}.model", model.text().strip(), persist=False)
        c.set("scoring.min_overall_score", self.threshold_spin.value(), persist=False)
        c.set("scoring.auto_approve", self.auto_approve.isChecked(), persist=False)
        c.set("rewrite.style", self.style_combo.currentText(), persist=False)
        c.set("rewrite.target_seconds",
              LENGTHS[self.length_combo.currentIndex()], persist=False)
        c.set("rewrite.words_per_minute", self.wpm_spin.value(), persist=False)
        c.set("rewrite.engagement_question",
              self.engagement_check.isChecked(), persist=False)
        c.set("video.format", self.format_combo.currentText(), persist=False)
        c.set("video.background_category", self.bg_category.text().strip(),
              persist=False)
        c.set("video.background_selection", self.bg_selection.currentText(),
              persist=False)
        c.set("video.music_enabled", self.music_check.isChecked(), persist=False)
        c.set("video.music_volume_db", self.music_volume.value(), persist=False)
        c.set("voice.engine", self.voice_engine.currentText(), persist=False)
        c.set("voice.voice_id", self.voice_id_edit.text().strip(), persist=False)
        c.set("voice.speed", self.voice_speed.value(), persist=False)
        c.set("voice.piper_exe", self.piper_exe.text().strip(), persist=False)
        c.set("voice.piper_model", self.piper_model.text().strip(), persist=False)
        c.set("voice.elevenlabs_api_key", self.eleven_key.text().strip(), persist=False)
        c.set("captions.mode", self.caption_mode.currentText(), persist=False)
        c.set("captions.preset", self.caption_preset.currentText(), persist=False)
        c.set("subtitles.whisper_model", self.whisper_model.currentText(),
              persist=False)
        c.set("video.title_card.enabled", self.card_enabled.isChecked(),
              persist=False)
        c.set("video.title_card.fade_seconds", self.card_fade.value(),
              persist=False)
        c.set("video.title_card.upvotes",
              self.card_upvotes.text().strip() or "99+", persist=False)
        c.set("video.title_card.comments",
              self.card_comments.text().strip() or "99+", persist=False)
        accounts = []
        for r in range(self.accounts_table.rowCount()):
            name_item = self.accounts_table.item(r, 0)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue
            avatar_item = self.accounts_table.item(r, 1)
            verified_item = self.accounts_table.item(r, 2)
            accounts.append({
                "name": name,
                "avatar": avatar_item.text().strip() if avatar_item else "",
                "verified": bool(verified_item and verified_item.checkState()
                                 == Qt.CheckState.Checked),
            })
        c.set("accounts", accounts, persist=False)
        default = self.card_default_account.currentText()
        c.set("video.title_card.account",
              "" if default.startswith("(") else default, persist=False)
        c.set("upload.default_visibility", self.visibility_combo.currentText(),
              persist=False)
        c.set("tiktok.client_key", self.tiktok_key_edit.text().strip(),
              persist=False)
        c.set("tiktok.client_secret", self.tiktok_secret_edit.text().strip(),
              persist=False)
        c.set("tiktok.label_ai_generated", self.tiktok_aigc_check.isChecked(),
              persist=False)
        c.set("tiktok.disable_comment", self.tiktok_comment_check.isChecked(),
              persist=False)
        custom_tags = [t.strip() for t in self.custom_tags_edit.text().split(",")
                       if t.strip()]
        c.set("seo.custom_tags", custom_tags, persist=False)
        c.set("seo.custom_tags_as_hashtags",
              self.tags_as_hashtags_check.isChecked(), persist=False)
        c.set("seo.short_summary", self.short_summary_check.isChecked(),
              persist=False)
        c.set("notifications.discord_webhook", self.discord_edit.text().strip(),
              persist=False)
        c.set("notifications.desktop", self.desktop_notify_check.isChecked(),
              persist=True)
        self.status.setText("Saved. New settings apply to the next run.")

    def _test_providers(self) -> None:
        if not self.check_providers:
            return
        self._save()
        self.provider_status.setText("Checking...")
        self.check_providers(self._show_provider_status)

    def _show_provider_status(self, availability: dict[str, bool]) -> None:
        parts = [f"{name}: {'online' if ok else 'offline / no key'}"
                 for name, ok in availability.items()]
        self.provider_status.setText(" | ".join(parts))
