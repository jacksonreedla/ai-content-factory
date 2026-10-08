"""Reusable GUI building blocks."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

log = logging.getLogger("acf.gui")


def remove_files(paths: Iterable[str]) -> int:
    """Delete the given files from disk. Returns how many were removed.

    Missing paths and empty strings are ignored; errors are logged, not raised.
    """
    removed = 0
    for path in paths:
        if not path:
            continue
        try:
            p = Path(path)
            if p.exists():
                p.unlink()
                removed += 1
        except OSError as exc:
            log.warning("Could not delete %s: %s", path, exc)
    return removed


class StatCard(QFrame):
    """Dashboard metric card: big number + small label."""

    def __init__(self, title: str, value: str = "-"):
        super().__init__()
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        layout.addWidget(self.value_label)
        layout.addWidget(self.title_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class PageHeader(QLabel):
    def __init__(self, text: str):
        super().__init__(text)
        self.setObjectName("PageTitle")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft)
