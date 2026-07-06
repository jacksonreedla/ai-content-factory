# core/enums.py
from enum import Enum


class JobStage(str, Enum):
    RESEARCH = "research"
    ANALYZE = "analyze"
    REWRITE = "rewrite"
    VOICE = "voice"
    SUBTITLE = "subtitle"
    EDIT = "edit"
    AWAITING_APPROVAL = "awaiting_approval"
    THUMBNAIL = "thumbnail"
    SEO = "seo"
    PUBLISH = "publish"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    FAILED = "failed"
    DONE = "done"


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class ExportFormat(str, Enum):
    SHORTS_VERTICAL = "shorts_vertical_9_16"   # YouTube Shorts
    TIKTOK = "tiktok_9_16"
    REELS = "reels_9_16"
    YOUTUBE = "youtube_16_9"


class NarrationStyle(str, Enum):
    DRAMATIC = "dramatic"
    FUNNY = "funny"
    SERIOUS = "serious"
    STORYTELLING = "storytelling"
    DOCUMENTARY = "documentary"
    HORROR = "horror"
    CONVERSATIONAL = "conversational"
