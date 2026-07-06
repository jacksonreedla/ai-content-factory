# app/container.py
import logging

from app.config import load_config
from app.paths import AppPaths
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.logging_setup import configure_logging
from pipeline.runner import PipelineRunner
from pipeline.worker_pool import WorkerPool
from plugins.registry import PluginRegistry

log = logging.getLogger(__name__)


class Container:
    """Composition root. Wires infra to domain and starts the worker pool."""

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.config = None
        self.db = None
        self.registry = PluginRegistry()
        self.runner = PipelineRunner()
        self.pool = None
        self._log_handler = None

    def bootstrap(self) -> None:
        self.paths.ensure()
        self._log_handler = configure_logging(self.paths.logs_dir)
        self.config = load_config(self.paths)
        self.db = connect(self.paths.db_path)
        migrate(self.db)
        self.pool = WorkerPool(
            self.paths.db_path, self.runner,
            max_workers=self.config.general.concurrent_jobs,
        )
        self.pool.start()
        log.info("container bootstrapped (db=%s)", self.paths.db_path)

    def shutdown(self) -> None:
        if self.pool:
            self.pool.stop()
        if self.db:
            self.db.close()
