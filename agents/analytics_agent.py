"""Analytics Agent: pulls YouTube stats, stores snapshots, learns what works."""
from __future__ import annotations

import json

from agents.base import Agent, AgentContext, AgentResult
from analytics.insights import compute_insights, estimate_revenue
from api.youtube_client import YouTubeClient, YouTubeError
from database.repositories import AnalyticsRepo, SettingsRepo, UploadRepo

INSIGHTS_KEY = "analytics.insights"
REVENUE_KEY = "analytics.revenue_estimate"


def _make_client(ctx: AgentContext) -> YouTubeClient:
    """Factory - patchable in tests."""
    return YouTubeClient()


class AnalyticsAgent(Agent):
    name = "analytics"
    stage = "analytics"

    def execute(self, ctx: AgentContext) -> AgentResult:
        upload_repo = UploadRepo(ctx.db)
        analytics_repo = AnalyticsRepo(ctx.db)
        settings = SettingsRepo(ctx.db)

        uploads = [u for u in upload_repo.recent(500)
                   if u["status"] == "uploaded" and u["remote_id"]]
        if not uploads:
            return AgentResult(ok=True, skipped=True,
                               message="no uploaded videos to analyze")

        client = _make_client(ctx)
        if not client.is_configured() or not client.is_authorized():
            # TikTok's Content Posting API does not return view/like stats, so
            # this optional stats pass (YouTube Data API) simply skips unless a
            # YouTube client is also connected.
            return AgentResult(ok=True, skipped=True,
                               message="stats source not connected - skipping")

        ctx.report(self.stage, 0.2)
        try:
            stats = client.video_stats([u["remote_id"] for u in uploads])
        except YouTubeError as exc:
            return AgentResult(ok=False, message=str(exc))

        updated = 0
        for upload in uploads:
            metrics = stats.get(upload["remote_id"])
            if not metrics:
                continue
            for metric, value in metrics.items():
                analytics_repo.record(upload["video_id"], metric, float(value))
            updated += 1

        # ------------------------------------------------ learn + summarize
        ctx.report(self.stage, 0.7)
        rows = analytics_repo.performance_rows()
        insights = compute_insights(rows)
        settings.set(INSIGHTS_KEY, json.dumps(insights, ensure_ascii=False))

        revenue = estimate_revenue(
            rows,
            rpm_shorts=float(ctx.config.get("analytics.rpm_shorts", 0.15)),
            rpm_longform=float(ctx.config.get("analytics.rpm_longform", 3.0)))
        settings.set(REVENUE_KEY, f"{revenue:.2f}")

        total_views = int(sum(r["views"] for r in rows))
        return AgentResult(
            ok=True,
            message=(f"stats refreshed for {updated} videos - "
                     f"{total_views:,} total views, ~${revenue:.2f} est."),
            data={"updated": updated, "views": total_views,
                  "revenue": revenue})
