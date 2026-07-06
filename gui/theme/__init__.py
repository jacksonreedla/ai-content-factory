# gui/theme/__init__.py
from pathlib import Path

from gui.theme.tokens import COLORS

_QSS = Path(__file__).resolve().parent / "dark.qss"


def load_theme() -> str:
    qss = _QSS.read_text(encoding="utf-8")
    for key, val in COLORS.items():
        qss = qss.replace("{{" + key + "}}", val)
    return qss
