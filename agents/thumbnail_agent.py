"""Thumbnail Agent: frame + AI text overlay for each rendered video."""
from __future__ import annotations

from pathlib import Path

from agents.base import Agent, AgentContext, AgentResult
from app.paths import THUMBS_DIR
from database.repositories import StoryRepo, VideoRepo
from editor.ffmpeg_render import RenderError
from editor.thumbnail import ThumbnailError, extract_frame, generate_thumbnail


class ThumbnailAgent(Agent):
    name = "thumbnail"
    stage = "thumbnail"

    def _thumbnail_text(self, ctx: AgentContext, video: dict) -> str:
        """Ask the LLM for punchy text; fall back to the video title."""
        title = video.get("title") or "You won't believe this"
        try:
            story = (StoryRepo(ctx.db).get(video["story_id"])
                     if video.get("story_id") else None)
            prompt = ctx.prompts.render(
                "thumbnail_text", title=title,
                narration=(story.text[:2000] if story else title))
            data = ctx.llm.complete("thumbnail_text", prompt,
                                    json_mode=True, temperature=0.8).parse_json()
            options = [o for o in data.get("options", []) if o and o.strip()]
            if options:
                return options[0]
        except Exception as exc:
            self.log.warning("AI thumbnail text failed (%s); using title", exc)
        words = title.split()[:6]
        return " ".join(words)

    def execute(self, ctx: AgentContext) -> AgentResult:
        video_repo = VideoRepo(ctx.db)
        videos = video_repo.needing_thumbnail()
        if not videos:
            return AgentResult(ok=True, skipped=True,
                               message="no videos awaiting thumbnails")

        font_path = ctx.config.get("thumbnail.font_path", "")
        text_color = ctx.config.get("thumbnail.text_color", "#FFFFFF")
        stroke_color = ctx.config.get("thumbnail.stroke_color", "#000000")

        done, failed = 0, 0
        for i, video in enumerate(videos):
            ctx.report(self.stage, i / len(videos))
            try:
                frame = extract_frame(
                    Path(video["file_path"]),
                    THUMBS_DIR / f"frame_{video['id']}.jpg", at_s=1.0)
                text = self._thumbnail_text(ctx, video)
                thumb = generate_thumbnail(
                    frame, text, THUMBS_DIR / f"thumb_{video['id']}.jpg",
                    font_path=font_path, text_color=text_color,
                    stroke_color=stroke_color)
                video_repo.set_thumbnail(video["id"], str(thumb))
                done += 1
            except (RenderError, ThumbnailError) as exc:
                self.log.warning("Thumbnail failed for video %s: %s",
                                 video["id"], exc)
                failed += 1
            except Exception:
                self.log.exception("Unexpected thumbnail error for video %s",
                                   video["id"])
                failed += 1

        return AgentResult(ok=done > 0 or failed == 0,
                           message=f"{done} thumbnails created, {failed} failed",
                           data={"done": done, "failed": failed})
