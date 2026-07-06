# plugins/publishing/youtube/publisher.py
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class PublishResult:
    remote_id: str
    status: str        # done | failed
    response: dict


class YouTubePublisher:
    """Publisher over the YouTube Data API v3 with resumable upload + retries.

    `client` is injected for tests (a fake exposing `.videos().insert(...)`).
    In production it's built from OAuth credentials. Privacy is one of
    draft|private|unlisted|public|scheduled.
    """

    def __init__(self, client=None, max_retries: int = 5,
                 backoff_base: float = 2.0) -> None:
        self._client = client
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    def set_client(self, client) -> None:
        self._client = client

    def upload(self, video, seo, privacy: str,
               playlist_id: Optional[str] = None,
               scheduled_at: Optional[str] = None) -> PublishResult:
        if self._client is None:
            raise RuntimeError("YouTubePublisher has no client (run OAuth first)")
        from googleapiclient.http import MediaFileUpload  # type: ignore
        video_path = video if isinstance(video, str) else getattr(
            video, "path", video["video_path"] if isinstance(video, dict) else str(video))
        title = _get(seo, "title", "")
        description = _get(seo, "description", "")
        tags = _get(seo, "tags", []) or []
        # Map our privacy vocab to YouTube's.
        yt_privacy = {
            "draft": "private", "private": "private",
            "unlisted": "unlisted", "public": "public",
            "scheduled": "private",
        }.get(privacy, "private")
        body = {
            "snippet": {
                "title": title, "description": description,
                "tags": list(tags), "categoryId": "22",
            },
            "status": {
                "privacyStatus": yt_privacy,
                "selfDeclaredMadeForKids": False,
            },
        }
        if scheduled_at and privacy == "scheduled":
            body["status"]["publishAt"] = scheduled_at
        media = MediaFileUpload(video_path, resumable=True,
                                chunksize=10 * 1024 * 1024)
        request = self._client.videos().insert(
            part="snippet,status", body=body, media_body=media)

        response = None
        for attempt in range(1, self.max_retries + 1):
            try:
                status, response = request.next_chunk()
                if response and "id" in response:
                    return PublishResult(remote_id=response["id"],
                                         status="done", response=response)
            except Exception as e:
                log.warning("upload attempt %d/%d failed: %s",
                            attempt, self.max_retries, e)
                if attempt == self.max_retries:
                    return PublishResult(remote_id="", status="failed",
                                         response={"error": str(e)})
                time.sleep(self.backoff_base ** attempt)
        return PublishResult(remote_id="", status="failed",
                             response=response or {})


def _get(obj, key, default):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
