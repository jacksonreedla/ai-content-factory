# tests/test_state_machine.py
from core.enums import JobStage, JobStatus
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.db.repositories import create_job, get_job

from pipeline.state_machine import next_stage
from pipeline.runner import PipelineRunner


def test_next_stage_sequential():
    assert next_stage(JobStage.RESEARCH) == JobStage.ANALYZE
    assert next_stage(JobStage.EDIT) == JobStage.AWAITING_APPROVAL
    assert next_stage(JobStage.AWAITING_APPROVAL) is None   # manual gate
    assert next_stage(JobStage.SEO) == JobStage.PUBLISH
    assert next_stage(JobStage.PUBLISH) is None


def test_runner_advances_through_registered_stages(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    called = []
    runner = PipelineRunner()

    def agent_research(ctx):
        called.append("research")
        return ctx

    runner.register(JobStage.RESEARCH, agent_research)
    runner.advance(conn, jid, JobStage.RESEARCH)
    job = get_job(conn, jid)
    assert job["stage"] == "analyze"
    assert called == ["research"]


def test_runner_marks_failed_on_exception(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    runner = PipelineRunner()

    def boom(ctx):
        raise RuntimeError("nope")

    runner.register(JobStage.RESEARCH, boom)
    runner.advance(conn, jid, JobStage.RESEARCH)
    job = get_job(conn, jid)
    assert job["status"] == "failed"
    assert "nope" in (job["error"] or "")


def test_runner_holds_at_approval_gate(tmp_path):
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    jid = create_job(conn, source_id="t3_x")
    update_stage_via_runner = PipelineRunner()

    def edit_agent(ctx):
        return ctx

    update_stage_via_runner.register(JobStage.EDIT, edit_agent)
    update_stage_via_runner.advance(conn, jid, JobStage.EDIT)
    job = get_job(conn, jid)
    assert job["stage"] == "awaiting_approval"
