# app/approval_service.py
import logging

from core.enums import ApprovalState, JobStage, JobStatus
from infra.db.repositories import (
    get_job, get_seo_by_job, get_video_by_job, list_pending_approval,
    set_approval_state, update_job_stage, update_job_status,
)

log = logging.getLogger(__name__)


class ApprovalService:
    """The approval gate. Nothing advances past AWAITING_APPROVAL without it.

    Holds the pipeline at the gate after EDIT; `approve()` enqueues the job at
    THUMBNAIL, after which the worker pool chains through SEO and PUBLISH.
    """

    def __init__(self, container) -> None:
        self.container = container

    def list_pending(self) -> list:
        return list_pending_approval(self.container.db)

    def approve(self, job_id: int, privacy: str | None = None) -> bool:
        """Approve a pending job and enqueue it at the THUMBNAIL stage.

        Returns True if the job was approved, False if it wasn't in a state
        we could approve.
        """
        job = get_job(self.container.db, job_id)
        if job is None:
            return False
        if job["stage"] != JobStage.AWAITING_APPROVAL.value:
            log.warning("approve: job %s not at gate (stage=%s)",
                        job_id, job["stage"])
            return False
        set_approval_state(self.container.db, job_id, ApprovalState.APPROVED)
        update_job_status(self.container.db, job_id, JobStatus.QUEUED)
        if privacy:
            self.container.db.execute(
                "UPDATE jobs SET config_json=? WHERE id=?",
                (__import__("json").dumps({"privacy": privacy}), job_id))
            self.container.db.commit()
        # Enqueue at THUMBNAIL — the worker pool chains forward from there.
        self.container.pool.submit(job_id, JobStage.THUMBNAIL)
        log.info("approved job %s → enqueued at THUMBNAIL (privacy=%s)",
                 job_id, privacy)
        return True

    def reject(self, job_id: int) -> bool:
        job = get_job(self.container.db, job_id)
        if job is None:
            return False
        set_approval_state(self.container.db, job_id, ApprovalState.REJECTED)
        update_job_status(self.container.db, job_id, JobStatus.DONE)
        log.info("rejected job %s", job_id)
        return True

    def edit(self, job_id: int, title: str | None = None,
             description: str | None = None) -> bool:
        """Edit the SEO title/description for an awaiting job.

        If a SEO row doesn't exist yet, creates a placeholder; the SEO agent
        will overwrite it when it runs.
        """
        from infra.db.repositories import insert_seo
        job = get_job(self.container.db, job_id)
        if job is None:
            return False
        video = get_video_by_job(self.container.db, job_id)
        if video is None:
            return False
        existing = get_seo_by_job(self.container.db, job_id)
        if existing:
            self.container.db.execute(
                "UPDATE seo SET title=COALESCE(?, title), "
                "description=COALESCE(?, description) WHERE id=?",
                (title, description, existing["id"]))
            self.container.db.commit()
        else:
            insert_seo(self.container.db, video["id"],
                       title=title or "", description=description or "",
                       tags_json="[]", hashtags_json="[]",
                       pinned_comment="", community_post="",
                       ctr_score=0.0, seo_score=0.0, model="manual")
        set_approval_state(self.container.db, job_id, ApprovalState.EDITED)
        return True

    def regenerate(self, job_id: int, stage: JobStage) -> bool:
        """Reset and re-enqueue a job at a specific (pre-approval) stage."""
        job = get_job(self.container.db, job_id)
        if job is None:
            return False
        update_job_stage(self.container.db, job_id, stage)
        update_job_status(self.container.db, job_id, JobStatus.QUEUED)
        self.container.pool.submit(job_id, stage)
        log.info("regenerate: job %s → re-enqueued at %s", job_id, stage)
        return True
