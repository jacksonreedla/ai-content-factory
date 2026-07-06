# gui/views/placeholder.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlaceholderView(QWidget):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lbl = QLabel(f"{title}\n\nComing in a later phase.")
        lbl.setObjectName("muted")
        lay.addWidget(lbl)
        lay.addStretch()
