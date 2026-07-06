# app/events.py
from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """App-wide Qt signal bus. Worker threads emit; Qt marshals to the UI thread."""
    job_updated = Signal(int)              # job_id
    progress = Signal(int, int, str)       # job_id, pct, message
    job_failed = Signal(int, str)          # job_id, error
    notify = Signal(str, str)              # level, message


# Singleton imported across the GUI.
bus = SignalBus()
