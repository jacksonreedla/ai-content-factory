"""Job domain model: one unit of pipeline work tracked in the queue."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class PipelineStage(str, Enum):
    """Ordered stages of the full automation pipeline."""

    RESEARCH = "research"
    SCORE = "score"
    REWRITE = "rewrite"
    VOICE = "voice"
    CAPTIONS = "captions"
    EDIT = "edit"
    THUMBNAIL = "thumbnail"
    SEO = "seo"
    UPLOAD = "upload"

    @classmethod
    def ordered(cls) -> list["PipelineStage"]:
        return list(cls)


@dataclass
class Job:
    id: int | None
    type: str                              # "full_pipeline" | single stage name
    status: JobStatus = JobStatus.PENDING
    priority: int = 5                      # 1 (highest) .. 9 (lowest)
    stage: str = ""
    progress: float = 0.0                  # 0..1
    payload: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def payload_json(self) -> str:
        return json.dumps(self.payload)

    @staticmethod
    def payload_from_json(raw: str | None) -> dict[str, Any]:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
