"""AI Content Factory - application entry point.

Usage:
    python main.py              Launch the desktop GUI.
    python main.py --headless   Run the full pipeline once without a GUI.
    python main.py --stage X    Run a single pipeline stage (research, score,
                                rewrite, seo, ...) without a GUI.
"""
from __future__ import annotations

import argparse
import logging
import sys

from app.config import Config
from app.logging_setup import setup_logging
from app.paths import ensure_dirs
from database.db import Database

log = logging.getLogger("acf.main")


def build_services() -> tuple[Config, Database]:
    """Initialise shared services (config, logging, database)."""
    ensure_dirs()
    setup_logging()
    config = Config.load()
    db = Database.default()
    db.migrate()
    return config, db


def run_gui(config: Config, db: Database) -> int:
    from PySide6.QtWidgets import QApplication

    from gui.main_window import MainWindow

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("AI Content Factory")
    window = MainWindow(config, db)
    window.show()
    return qt_app.exec()


def run_headless(config: Config, db: Database, stage: str | None) -> int:
    from app.pipeline import Pipeline

    pipeline = Pipeline(config, db)
    if stage:
        result = pipeline.run_stage(stage)
    else:
        result = pipeline.run_all()
    log.info("Pipeline finished: %s", result.summary())
    return 0 if result.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Content Factory")
    parser.add_argument("--headless", action="store_true", help="run pipeline without GUI")
    parser.add_argument("--stage", type=str, default=None, help="run a single stage headless")
    args = parser.parse_args()

    config, db = build_services()
    log.info("AI Content Factory starting (headless=%s)", args.headless or bool(args.stage))

    if args.headless or args.stage:
        return run_headless(config, db, args.stage)
    return run_gui(config, db)


if __name__ == "__main__":
    sys.exit(main())
