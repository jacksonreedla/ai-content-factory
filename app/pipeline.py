"""Pipeline orchestrator: runs agents in order, tracks jobs, emits events."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from agents.base import AgentContext, AgentResult
from agents.registry import agent_for_stage, build_agents
from api.llm.router import LLMRouter
from app import events
from app.config import Config
from app.prompt_manager import PromptManager
from database.db import Database
from database.repositories import JobRepo, UsageRepo
from models.job import Job, JobStatus

log = logging.getLogger("acf.pipeline")


@dataclass
class PipelineResult:
    ok: bool
    stage_results: dict[str, AgentResult] = field(default_factory=dict)

    def summary(self) -> str:
        parts = []
        for stage, result in self.stage_results.items():
            mark = "SKIP" if result.skipped else ("OK" if result.ok else "FAIL")
            parts.append(f"{stage}={mark}")
        return ", ".join(parts) or "nothing ran"


class Pipeline:
    """Executes the ordered agent chain, or a single stage.

    Thread-safe enough for one worker at a time; the GUI runs it inside a
    QThread, headless mode runs it on the main thread.
    """

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db
        self.jobs = JobRepo(db)
        usage = UsageRepo(db)
        self.llm = LLMRouter(
            config,
            usage_callback=lambda p, m, t, ti, to: usage.record(p, m, t, ti, to),
        )
        self.prompts = PromptManager()
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    # ------------------------------------------------------------------ runs
    def _make_context(self, job_id: int | None, data: dict | None = None) -> AgentContext:
        def progress(stage: str, fraction: float) -> None:
            if job_id is not None:
                self.jobs.update(job_id, stage=stage, progress=fraction)
            events.bus.publish(events.JOB_UPDATED, {
                "job_id": job_id, "stage": stage, "progress": fraction,
            })

        return AgentContext(
            config=self.config, db=self.db, llm=self.llm,
            prompts=self.prompts, data=data or {},
            progress_callback=progress,
        )

    def run_all(self, data: dict | None = None) -> PipelineResult:
        """Run the full chain as one tracked job."""
        self._cancel.clear()
        job = Job(id=None, type="full_pipeline", payload=data or {})
        job_id = self.jobs.add(job)
        self.jobs.update(job_id, status=JobStatus.RUNNING)
        ctx = self._make_context(job_id, data)

        result = PipelineResult(ok=True)
        agents = build_agents()
        for index, agent in enumerate(agents):
            if self._cancel.is_set():
                self.jobs.update(job_id, status=JobStatus.CANCELLED)
                events.bus.publish(events.PIPELINE_FINISHED, {"job_id": job_id,
                                                              "status": "cancelled"})
                result.ok = False
                return result

            self.jobs.update(job_id, stage=agent.stage,
                             progress=index / len(agents))
            agent_result = agent.run(ctx)
            result.stage_results[agent.stage] = agent_result

            if not agent_result.ok:
                # Research failing (e.g. missing credentials) is fatal;
                # later-stage soft failures stop the run too, with the error
                # kept on the job for the GUI.
                self.jobs.update(job_id, status=JobStatus.FAILED,
                                 error=f"{agent.name}: {agent_result.message}")
                events.bus.publish(events.PIPELINE_FINISHED, {"job_id": job_id,
                                                              "status": "failed"})
                result.ok = False
                return result

        self.jobs.update(job_id, status=JobStatus.COMPLETED, progress=1.0)
        events.bus.publish(events.PIPELINE_FINISHED, {"job_id": job_id,
                                                      "status": "completed"})
        try:
            from app.notifications import notify
            notify(self.config, "Pipeline finished", result.summary())
        except Exception:
            log.exception("Completion notification failed")
        return result

    def run_stage(self, stage: str, data: dict | None = None) -> PipelineResult:
        """Run one stage as its own tracked job."""
        agent = agent_for_stage(stage)
        if agent is None:
            log.error("Unknown stage '%s'", stage)
            return PipelineResult(ok=False)

        job_id = self.jobs.add(Job(id=None, type=stage, payload=data or {}))
        self.jobs.update(job_id, status=JobStatus.RUNNING, stage=stage)
        ctx = self._make_context(job_id, data)

        agent_result = agent.run(ctx)
        status = JobStatus.COMPLETED if agent_result.ok else JobStatus.FAILED
        self.jobs.update(job_id, status=status, progress=1.0,
                         error="" if agent_result.ok else agent_result.message)
        events.bus.publish(events.PIPELINE_FINISHED, {
            "job_id": job_id,
            "status": status.value,
        })
        return PipelineResult(ok=agent_result.ok,
                              stage_results={stage: agent_result})
