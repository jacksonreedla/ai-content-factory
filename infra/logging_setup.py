# infra/logging_setup.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class GUILogHandler(logging.Handler):
    """Optional handler; the GUI attaches its emit to the Logs view."""
    def __init__(self) -> None:
        super().__init__()
        self._sink = None

    def set_sink(self, sink) -> None:
        self._sink = sink

    def emit(self, record) -> None:
        if self._sink:
            try:
                self._sink(self.format(record))
            except Exception:  # pragma: no cover
                pass


def configure_logging(logs_dir: Path) -> GUILogHandler:
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fmt = logging.Formatter(_LOG_FORMAT)

    # Avoid duplicate handlers on re-bootstrap.
    for h in list(root.handlers):
        if isinstance(h, (RotatingFileHandler, GUILogHandler)):
            root.removeHandler(h)

    fh = RotatingFileHandler(logs_dir / "aicf.log", maxBytes=1_000_000,
                             backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    gui_handler = GUILogHandler()
    gui_handler.setFormatter(fmt)
    root.addHandler(gui_handler)
    return gui_handler
