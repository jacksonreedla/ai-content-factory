# gui/views/logs.py
from collections import deque

from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout,
    QWidget,
)


class LogsView(QWidget):
    """Live tail of the app log, fed by the GUILogHandler sink."""

    MAX_LINES = 2000

    def __init__(self, container=None, parent=None):
        super().__init__(parent)
        self.container = container
        v = QVBoxLayout(self)
        title = QLabel("Logs")
        title.setObjectName("title")
        v.addWidget(title)

        bar = QHBoxLayout()
        self.cb_info = QCheckBox("INFO"); self.cb_info.setChecked(True)
        self.cb_warn = QCheckBox("WARN"); self.cb_warn.setChecked(True)
        self.cb_error = QCheckBox("ERROR"); self.cb_error.setChecked(True)
        for cb in (self.cb_info, self.cb_warn, self.cb_error):
            cb.stateChanged.connect(self._refilter)
            bar.addWidget(cb)
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._on_clear)
        bar.addWidget(clear_btn); bar.addStretch()
        v.addLayout(bar)

        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setStyleSheet("QPlainTextEdit { font-family: 'Menlo','Consolas',monospace; font-size: 12px; }")
        v.addWidget(self.view, 1)

        self._lines = deque(maxlen=self.MAX_LINES)

    def attach(self) -> None:
        """Wire this view as the GUI log handler's sink."""
        if self.container and getattr(self.container, "_log_handler", None):
            self.container._log_handler.set_sink(self._append)

    def _append(self, line: str) -> None:
        self._lines.append(line)
        if self._visible(line):
            self.view.appendPlainText(line.rstrip())

    def _visible(self, line: str) -> bool:
        if " INFO " in line and not self.cb_info.isChecked(): return False
        if (" WARNING" in line or " WARN " in line) and not self.cb_warn.isChecked(): return False
        if " ERROR " in line and not self.cb_error.isChecked(): return False
        return True

    def _refilter(self):
        self.view.setPlainText("\n".join(l.rstrip() for l in self._lines if self._visible(l)))

    def _on_clear(self):
        self._lines.clear()
        self.view.clear()
