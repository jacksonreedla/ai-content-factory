# plugins/analytics/youtube/source.py
import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class AnalyticsPoint:
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    watch_time_min: float = 0.0
    ctr: float = 0.0
    retention_pct: float = 0.0


class YouTubeAnalyticsSource:
    """AnalyticsSource over the YouTube Analytics API.

    `client` is injected for tests (a fake exposing `.videos().getRating`/etc.).
    In production it's the same OAuth client as the publisher. Satisfies the
    AnalyticsSource protocol.
    """

    def __init__(self, client=None) -> None:
        self._client = client

    def set_client(self, client) -> None:
        self._client = client

    def fetch(self, publish) -> AnalyticsPoint:
        """Fetch current metrics for a published video.

        `publish` is a DB row (or dict) with `remote_id`.
        """
        if self._client is None:
            log.warning("analytics source has no client")
            return AnalyticsPoint()
        remote_id = publish["remote_id"] if hasattr(publish, "__getitem__") else \
            getattr(publish, "remote_id", "")
        if not remote_id:
            return AnalyticsPoint()
        try:
            # videos().list(part=statistics) gives the public counters.
            resp = self._client.videos().list(
                part="statistics", id=remote_id).execute()
            stats = (resp.get("items") or [{}])[0].get("statistics", {})
            return AnalyticsPoint(
                views=int(stats.get("viewCount", 0)),
                likes=int(stats.get("likeCount", 0)),
                comments=int(stats.get("commentCount", 0)),
            )
        except Exception as e:
            log.warning("analytics fetch failed for %s: %s", remote_id, e)
            return AnalyticsPoint()
