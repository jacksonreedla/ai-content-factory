# tests/test_theme.py
from gui.theme.tokens import COLORS
from gui.theme import load_theme


def test_tokens_have_required_keys():
    for key in ("bg", "surface", "accent", "text", "muted",
                "border", "danger", "success"):
        assert key in COLORS


def test_load_theme_returns_nonempty_qss():
    qss = load_theme()
    assert "QMainWindow" in qss
    assert "{{" not in qss   # tokens all substituted
    assert len(qss) > 200
