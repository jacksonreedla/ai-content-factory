# tests/test_research_view.py
from gui.views.research import ResearchView


def test_research_view_builds_and_has_columns(qtbot):
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    assert view.table.columnCount() == 6
    assert view.discover_btn.text().startswith("🔍")


def test_build_query_parses_subs(qtbot):
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    view.subreddits.setText("nosleep, tifu , askreddit")
    q = view._build_query()
    assert q.subreddits == ["nosleep", "tifu", "askreddit"]


def test_build_query_defaults_when_empty(qtbot):
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    view.subreddits.setText("")
    q = view._build_query()
    assert q.subreddits == ["AskReddit"]


def test_populate_shows_rows(qtbot):
    from datetime import datetime
    from core.models import Story
    view = ResearchView(container=None)
    qtbot.addWidget(view)
    view._results = [
        Story(source="reddit", source_id="a", subreddit="nosleep", author="u",
              title="Hello", body_text="b", score=42, num_comments=7,
              created_utc=datetime.utcnow().timestamp(), permalink="")
    ]
    view._populate()
    assert view.table.rowCount() == 1
    assert view.table.item(0, 2).text() == "Hello"
