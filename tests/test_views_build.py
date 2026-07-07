# tests/test_views_build.py
"""All 8 sidebar views must build without error."""
from gui.views.library import LibraryView
from gui.views.history import HistoryView
from gui.views.settings import SettingsView
from gui.views.logs import LogsView


def test_library_view_builds(qtbot):
    v = LibraryView(container=None)
    qtbot.addWidget(v)
    assert v.table.columnCount() == 4
    assert v.kind.count() >= 5  # background/music/logo/intro/outro


def test_history_view_builds(qtbot):
    v = HistoryView(container=None)
    qtbot.addWidget(v)
    assert v.table.columnCount() == 8


def test_settings_view_builds(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    from app.container import Container
    c = Container(); c.bootstrap()
    try:
        v = SettingsView(container=c)
        qtbot.addWidget(v)
        assert v.tabs.count() == 8  # general/sources/llm/voice/editor/pub/secrets/about
        assert v.concurrent.value() == 1
    finally:
        c.shutdown()


def test_logs_view_builds(qtbot):
    v = LogsView(container=None)
    qtbot.addWidget(v)
    v._append("2024-01-01 INFO app: hello")
    v._append("2024-01-01 ERROR app: oops")
    assert "hello" in v.view.toPlainText()
    # Filter out INFO.
    v.cb_info.setChecked(False)
    v._refilter()
    assert "hello" not in v.view.toPlainText()
    assert "oops" in v.view.toPlainText()
