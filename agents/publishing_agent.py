# agents/publishing_agent.py
import json
import logging
import sqlite3

from core.models import JobContext
from infra.db.repositories import (
    get_publish_by_job, get_seo_by_job, get_video_by_job, insert_publish,
)

log = logging.getLogger(__name__)


def make_publishing_agent(publisher, conn: sqlite3.Connection,
                          default_privacy: str = "draft",
                          playlist_id: str | None = None):
    """Build a PUBLISH-stage agent that uploads via the Publisher contract."""

    def agent(ctx: JobContext) -> JobContext:
        video = get_video_by_job(conn, ctx.job_id)
        if video is None:
            raise RuntimeError(f"no video for job {ctx.job_id}")
        seo = get_seo_by_job(conn, ctx.job_id)
        if seo is None:
            raise RuntimeError(f"no SEO for job {ctx.job_id}")
        # Resolve privacy from the job config (set at approval) or default.
        job = conn.execute("SELECT config_json FROM jobs WHERE id=?",
                           (ctx.job_id,)).fetchone()
        privacy = default_privacy
        if job and job["config_json"]:
            try:
                privacy = json.loads(job["config_json"]).get(
                    "privacy", default_privacy)
            except Exception:
                pass
        ctx.progress(20, f"Uploading to YouTube (privacy={privacy})")
        attempt = 1
        existing = get_publish_by_job(conn, ctx.job_id)
        if existing:
            attempt = int(existing["attempt_count"]) + 1
        try:
            result = publisher.upload(video, seo, privacy,
                                      playlist_id=playlist_id)
        except Exception as e:
            insert_publish(conn, video["id"], "youtube", "", privacy,
                           playlist_id or "", "failed", attempt,
                           response_json=json.dumps({"error": str(e)}))
            raise
        status = "done" if result.status == "done" else "failed"
        insert_publish(conn, video["id"], "youtube", result.remote_id,
                       privacy, playlist_id or "", status, attempt,
                       response_json=json.dumps(result.response))
        if status != "done":
            raise RuntimeError(
                f"upload finished with status {status}: {result.response}")
        ctx.progress(100, f"Published (id={result.remote_id})")
        return ctx
    return agent
