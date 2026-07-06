# tests/test_worker_pool.py
import time

from core.enums import JobStage
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job

from pipeline.runner import PipelineRunner
from pipeline.worker_pool import WorkerPool


def test_pool_runs_submitted_job(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    runner = PipelineRunner()
    flag = {"ran": False}

    def agent(ctx):
        flag["ran"] = True
        return ctx

    runner.register(JobStage.RESEARCH, agent)
    pool = WorkerPool(tmp_path / "t.db", runner, max_workers=1)
    pool.start()
    try:
        pool.submit(jid, JobStage.RESEARCH)
        for _ in range(100):
            if flag["ran"]:
                break
            time.sleep(0.02)
        assert flag["ran"]
    finally:
        pool.stop()


def test_pool_chains_to_next_stage(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_y")
    runner = PipelineRunner()
    order = []

    def a_research(ctx):
        order.append("research")
        return ctx

    def a_analyze(ctx):
        order.append("analyze")
        return ctx

    runner.register(JobStage.RESEARCH, a_research)
    runner.register(JobStage.ANALYZE, a_analyze)
    pool = WorkerPool(tmp_path / "t.db", runner, max_workers=1)
    pool.start()
    try:
        pool.submit(jid, JobStage.RESEARCH)
        # The chain runs ahead through no-op stages (VOICE/SUBTITLE/EDIT have
        # no agents registered) until it hits the AWAITING_APPROVAL gate,
        # where it must stop. Both registered agents must have run.
        for _ in range(300):
            job = get_job(conn, jid)
            if job and job["stage"] == "awaiting_approval":
                break
            time.sleep(0.02)
        job = get_job(conn, jid)
        assert job["stage"] == "awaiting_approval"   # stopped at the gate
        assert order == ["research", "analyze"]      # both agents ran, in order
    finally:
        pool.stop()
