# tests/test_shell.py
from gui.shell import MainWindow


def test_main_window_has_nav_and_stack(qtbot):
    win = MainWindow(container=None)
    qtbot.addWidget(win)
    assert win.nav.count() >= 7
    assert win.stack.count() >= 8


def test_switching_nav_changes_stack(qtbot):
    win = MainWindow(container=None)
    qtbot.addWidget(win)
    assert win.stack.currentIndex() == 0
    win.nav.setCurrentRow(2)
    assert win.stack.currentIndex() == 2


def test_window_title_set(qtbot):
    win = MainWindow(container=None)
    qtbot.addWidget(win)
    assert "AI Content Factory" in win.windowTitle()
