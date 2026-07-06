# tests/test_dashboard.py
from app.container import Container
from gui.views.dashboard import DashboardView


def test_dashboard_renders_stat_cards(qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("AICF_HOME", str(tmp_path))
    c = Container()
    c.bootstrap()
    try:
        view = DashboardView(container=c)
        qtbot.addWidget(view)
        view.refresh()
        # Four stat cards.
        assert len(view.stat_values) == 4
        # Values come from empty db → all "0".
        assert view.stat_values[0].text() == "0"
        assert view.stat_values[1].text() == "0"
        assert view.stat_values[2].text() == "0"
        assert view.stat_values[3].text() == "0"
        # DB path label is populated.
        assert str(tmp_path) in view.lbl_db.text()
    finally:
        c.shutdown()
