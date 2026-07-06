# gui/views/approval.py
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QMessageBox,
)
from PySide6.QtCore import Qt


class ApprovalView(QWidget):
    """The approval gate UI. Lists pending jobs; lets you approve/reject/edit."""

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        self._rows = []
        v = QVBoxLayout(self)
        title = QLabel("Approval Queue")
        title.setObjectName("title")
        subtitle = QLabel("Nothing is published until you approve it.")
        subtitle.setObjectName("muted")
        v.addWidget(title); v.addWidget(subtitle)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: pending jobs table.
        left = QWidget()
        ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Job", "Title", "Created"])
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.currentCellChanged.connect(self._on_select)
        ll.addWidget(self.table)

        # Right: detail + actions.
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.addWidget(QLabel("Preview & details"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Title (editable)")
        self.desc_edit = QTextEdit()
        self.desc_edit.setPlaceholderText("Description (editable)")
        self.desc_edit.setMaximumHeight(100)
        rl.addWidget(QLabel("Title")); rl.addWidget(self.title_edit)
        rl.addWidget(QLabel("Description")); rl.addWidget(self.desc_edit)

        self.privacy = QComboBox()
        self.privacy.addItems(["draft", "private", "unlisted", "public"])
        rl.addWidget(QLabel("Upload privacy"))
        rl.addWidget(self.privacy)

        actions = QHBoxLayout()
        self.approve_btn = QPushButton("✅ Approve")
        self.approve_btn.setObjectName("primary")
        self.approve_btn.clicked.connect(self._on_approve)
        self.reject_btn = QPushButton("✖ Reject")
        self.reject_btn.setObjectName("danger")
        self.reject_btn.clicked.connect(self._on_reject)
        self.save_btn = QPushButton("💾 Save edits")
        self.save_btn.clicked.connect(self._on_save)
        for b in (self.approve_btn, self.save_btn, self.reject_btn):
            actions.addWidget(b)
        rl.addLayout(actions)
        rl.addStretch()

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 500])
        v.addWidget(splitter, 1)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh)
        v.addWidget(refresh_btn)

    def refresh(self) -> None:
        self.table.setRowCount(0)
        self._rows = []
        if not self.container or not getattr(self.container, "approval", None):
            return
        self._rows = list(self.container.approval.list_pending())
        for i, r in enumerate(self._rows):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(r["job_id"])))
            self.table.setItem(i, 1, QTableWidgetItem(r["title"] or ""))
            self.table.setItem(i, 2, QTableWidgetItem(r["created_at"] or ""))

    def _selected_job_id(self):
        row = self.table.currentRow()
        if 0 <= row < len(self._rows):
            return int(self._rows[row]["job_id"])
        return None

    def _on_select(self, row, *_):
        if 0 <= row < len(self._rows):
            r = self._rows[row]
            self.title_edit.setText(r["title"] or "")
            self.desc_edit.setPlainText(r["body_text"] or "")

    def _on_approve(self) -> None:
        jid = self._selected_job_id()
        if jid is None:
            return
        privacy = self.privacy.currentText()
        if self.container.approval.approve(jid, privacy=privacy):
            QMessageBox.information(self, "Approved", f"Job {jid} queued for upload.")
            self.refresh()

    def _on_reject(self) -> None:
        jid = self._selected_job_id()
        if jid is None:
            return
        if self.container.approval.reject(jid):
            self.refresh()

    def _on_save(self) -> None:
        jid = self._selected_job_id()
        if jid is None:
            return
        self.container.approval.edit(
            jid, title=self.title_edit.text(),
            description=self.desc_edit.toPlainText())
        QMessageBox.information(self, "Saved", "Edits saved.")
