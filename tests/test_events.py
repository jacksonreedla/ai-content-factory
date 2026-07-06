# tests/test_events.py
from app.events import bus


def test_job_updated_signal(qtbot):
    received = []
    bus.job_updated.connect(lambda jid: received.append(jid))
    qtbot.wait(10)
    bus.job_updated.emit(7)
    qtbot.wait(10)
    assert received == [7]
    bus.job_updated.disconnect()


def test_progress_signal(qtbot):
    received = []
    bus.progress.connect(lambda jid, pct, msg: received.append((jid, pct, msg)))
    qtbot.wait(10)
    bus.progress.emit(1, 50, "half")
    qtbot.wait(10)
    assert received == [(1, 50, "half")]
    bus.progress.disconnect()
