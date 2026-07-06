# pipeline/worker_pool.py
import logging
import queue
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from core.enums import JobStage
from infra.db.connection import connect
from pipeline.runner import PipelineRunner
from pipeline.state_machine import next_stage
from infra.db.repositories import get_job

log = logging.getLogger(__name__)


class WorkerPool:
    """Bounded thread pool that drains a queue of (job_id, stage) tasks.

    SQLite connections are thread-bound, so each worker opens its own
    connection to the same db file via `threading.local`. The pool takes the
    db_path (not a connection) for that reason. A submitted task runs one
    stage; if the runner advanced the job to a successor stage (and that
    successor is not a manual gate), the successor is re-enqueued so a job
    advances until it hits a gate or terminal.
    """

    def __init__(self, db_path: Path, runner: PipelineRunner,
                 max_workers: int = 1) -> None:
        self._db_path = Path(db_path)
        self._runner = runner
        self._max_workers = max(1, max_workers)
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._executor: ThreadPoolExecutor | None = None
        self._tls = threading.local()  # holds a per-thread conn

    def _thread_conn(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = connect(self._db_path)
            self._tls.conn = conn
        return conn

    def start(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="aicf-worker",
        )
        for _ in range(self._max_workers):
            self._executor.submit(self._loop)

    def submit(self, job_id: int, stage: JobStage) -> None:
        self._queue.put((job_id, stage))

    def _loop(self) -> None:
        conn = self._thread_conn()
        while not self._stop.is_set():
            try:
                job_id, stage = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._runner.advance(conn, job_id, stage)
                # Chain forward: the runner advanced the job to `cur` (the next
                # pending stage). Re-enqueue `cur` so it runs next, unless the
                # runner was unable to advance (manual gate or terminal).
                job = get_job(conn, job_id)
                if job and job["status"] != "failed":
                    cur = JobStage(job["stage"])
                    if cur != stage and cur != JobStage.AWAITING_APPROVAL:
                        self.submit(job_id, cur)
            except Exception:
                log.exception("worker error on job %s stage %s", job_id, stage)

    def stop(self) -> None:
        self._stop.set()
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=True)
            self._executor = None
        # Close any per-thread connection this thread happens to own.
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:  # pragma: no cover
                pass
