# app/services.py
import logging

from core.models import SourceQuery, Story

log = logging.getLogger(__name__)


class ResearchService:
    """Application service: bridges the GUI to the ContentSource plugin + jobs."""

    def __init__(self, container) -> None:
        self.container = container

    def discover(self, query: SourceQuery) -> list[Story]:
        src = self.container.registry.active("content_source")
        if src is None:
            log.warning("no content source registered")
            return []
        return src.discover(query)

    def enqueue(self, story: Story) -> int:
        """Create a job for a chosen story and seed its stories row."""
        from infra.db.repositories import create_job, insert_story
        jid = create_job(self.container.db, source_id=story.source_id,
                         story_url=story.permalink)
        insert_story(self.container.db, jid, story)
        return jid

    def start_job(self, job_id: int, stage) -> None:
        self.container.pool.submit(job_id, stage)
