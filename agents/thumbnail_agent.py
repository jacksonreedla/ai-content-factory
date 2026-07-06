# agents/thumbnail_agent.py
import logging
import sqlite3

from core.models import JobContext
from infra.db.repositories import (
    get_story_by_job, get_thumbnails_by_job, get_video_by_job,
    insert_thumbnail,
)
from infra.storage import job_dir

log = logging.getLogger(__name__)

# Templates to render variants for the approval/A-B screen.
_VARIANTS = [
    ("bold_lower", "THIS HAPPENED", ""),
    ("centered_pop", "YOU WON'T BELIEVE", "THIS"),
    ("minimal_top", "REAL STORY", ""),
]


def make_thumbnail_agent(renderer, conn: sqlite3.Connection, paths,
                         templates=None):
    """Build a THUMBNAIL-stage agent. Renders several variants."""
    variants = templates or _VARIANTS

    def agent(ctx: JobContext) -> JobContext:
        row = get_story_by_job(conn, ctx.job_id)
        if row is None:
            raise RuntimeError(f"no story for job {ctx.job_id}")
        video = get_video_by_job(conn, ctx.job_id)
        if video is None:
            raise RuntimeError(f"no video for job {ctx.job_id}")
        ctx.progress(20, "Rendering thumbnail variants")
        jd = job_dir(paths, ctx.job_id)
        # Derive short, punchy lines from the title.
        title = (row["title"] or "").upper()
        words = title.split()
        line1 = " ".join(words[:3]) if len(words) >= 3 else title
        line2 = " ".join(words[3:5]) if len(words) > 3 else ""
        for i, (tpl, l1, l2) in enumerate(variants):
            out = jd / f"thumb_{tpl}.png"
            try:
                renderer.render(tpl, (l1 or line1, l2 or line2),
                                out_path=str(out),
                                bg_path=video["video_path"] or None)
                insert_thumbnail(conn, video["id"], tpl,
                                 l1 or line1, l2 or line2, str(out), i)
            except Exception as e:
                log.warning("thumbnail variant %s failed: %s", tpl, e)
        # Point the video's thumbnail_path at the first variant.
        thumbs = get_thumbnails_by_job(conn, ctx.job_id)
        if thumbs:
            conn.execute("UPDATE videos SET thumbnail_path=? WHERE id=?",
                         (thumbs[0]["image_path"], video["id"]))
            conn.commit()
        ctx.progress(100, "Thumbnails ready")
        return ctx
    return agent
