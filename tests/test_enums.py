# tests/test_enums.py
from core.enums import (
    JobStage, JobStatus, ExportFormat, NarrationStyle, ApprovalState,
)


def test_pipeline_stage_order():
    order = list(JobStage)
    assert order[0] == JobStage.RESEARCH
    assert order.index(JobStage.EDIT) < order.index(JobStage.AWAITING_APPROVAL)
    assert order.index(JobStage.AWAITING_APPROVAL) < order.index(JobStage.THUMBNAIL)
    assert order[-1] == JobStage.PUBLISH


def test_approval_pending_is_default():
    assert ApprovalState.PENDING.value == "pending"


def test_narration_styles_match_spec():
    styles = {s.value for s in NarrationStyle}
    assert styles == {"dramatic", "funny", "serious", "storytelling",
                      "documentary", "horror", "conversational"}


def test_export_formats():
    fmts = {f.value for f in ExportFormat}
    assert "shorts_vertical_9_16" in fmts
    assert "youtube_16_9" in fmts


def test_job_status_values():
    assert JobStatus.QUEUED.value == "queued"
