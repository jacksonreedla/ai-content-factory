# pipeline/state_machine.py
from core.enums import JobStage

# Pre-approval chain ends at the approval gate; post-approval resumes at THUMBNAIL.
_SEQUENCE = [
    JobStage.RESEARCH, JobStage.ANALYZE, JobStage.REWRITE,
    JobStage.VOICE, JobStage.SUBTITLE, JobStage.EDIT,
    JobStage.AWAITING_APPROVAL,
    JobStage.THUMBNAIL, JobStage.SEO, JobStage.PUBLISH,
]


def next_stage(current: JobStage) -> JobStage | None:
    """Return the next stage, or None if `current` is a terminal/gate."""
    try:
        i = _SEQUENCE.index(current)
    except ValueError:
        return None
    # AWAITING_APPROVAL is a manual gate — no automatic advance.
    if current == JobStage.AWAITING_APPROVAL:
        return None
    if i + 1 >= len(_SEQUENCE):
        return None
    return _SEQUENCE[i + 1]


def stage_index(stage: JobStage) -> int:
    try:
        return _SEQUENCE.index(stage)
    except ValueError:
        return -1
