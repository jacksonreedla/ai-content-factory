# pipeline/runner.py
import logging
import sqlite3
from typing import Callable

from core.enums import JobStage, JobStatus
from core.models import JobContext
from infra.db.repositories import get_job, update_job_stage, update_job_status
from pipeline.state_machine import next_stage

log = logging.getLogger(__name__)

AgentFn = Callable[[JobContext], JobContext]


class PipelineRunner:
    """Runs a single stage of a job, persists state, captures failures.

    Each agent is a function (stage, ctx) -> ctx. The runner:
      1. marks the job RUNNING,
      2. calls the agent (if registered),
      3. advances the job stage (or holds at a gate), and
      4. emits app events for the UI.
    """

    def __init__(self) -> None:
        self._agents: dict[JobStage, AgentFn] = {}
        self._on_progress = None  # set by container to forward to signal bus

    def register(self, stage: JobStage, agent: AgentFn) -> None:
        self._agents[stage] = agent

    def set_progress_forwarder(self, fn) -> None:
        self._on_progress = fn

    def advance(self, conn: sqlite3.Connection, job_id: int,
                stage: JobStage) -> JobContext:
        job = get_job(conn, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")

        update_job_status(conn, job_id, JobStatus.RUNNING)
        ctx = JobContext(job_id=job_id)
        # Wire up progress callback to forward to the signal bus (if attached).
        def _progress(pct: int, msg: str = "") -> None:
            if self._on_progress:
                try:
                    self._on_progress(job_id, pct, msg)
                except Exception:  # pragma: no cover
                    pass
        ctx.progress = _progress  # type: ignore[method-assign]

        agent = self._agents.get(stage)
        try:
            if agent is not None:
                ctx = agent(ctx) or ctx
            nxt = next_stage(stage)
            # The stage has completed; advance unless at a gate.
            if nxt is not None:
                update_job_stage(conn, job_id, nxt)
                update_job_status(conn, job_id, JobStatus.QUEUED)
            else:
                # Reached AWAITING_APPROVAL gate or PUBLISH terminal.
                update_job_status(conn, job_id, JobStatus.QUEUED)
        except Exception as e:
            log.exception("stage %s failed for job %s", stage, job_id)
            update_job_status(conn, job_id, JobStatus.FAILED, error=str(e))
        return ctx
