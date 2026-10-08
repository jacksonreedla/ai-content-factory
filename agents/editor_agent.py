"""Editor Agent: assembles finished videos from audio + captions + background."""
from __future__ import annotations

from pathlib import Path

from agents.base import Agent, AgentContext, AgentResult
from app.paths import CARDS_DIR, MUSIC_DIR, OUTPUT_DIR
from database.repositories import SettingsRepo, StoryRepo, VideoRepo
from editor.ffmpeg_render import RenderError, ffmpeg_available, render
from editor.media_library import MediaLibraryError, pick_clip, pick_music
from editor.spec import RenderSpec, VideoFormat
from editor.title_card import TitleCardError, generate_title_card, resolve_account
from models.story import StoryStatus


class EditorAgent(Agent):
    name = "editor"
    stage = "edit"

    def execute(self, ctx: AgentContext) -> AgentResult:
        video_repo = VideoRepo(ctx.db)
        videos = video_repo.needing_render()
        if not videos:
            return AgentResult(ok=True, skipped=True,
                               message="no videos awaiting render")
        if not ffmpeg_available():
            return AgentResult(ok=False, message=(
                "FFmpeg not found. Install it (winget install ffmpeg), "
                "restart the app, and re-run the edit stage."))

        settings = SettingsRepo(ctx.db)
        story_repo = StoryRepo(ctx.db)
        category = ctx.config.get("video.background_category", "minecraft")
        selection = ctx.config.get("video.background_selection", "random")
        effects = ctx.config.get("video.effects", {}) or {}
        music_enabled = bool(ctx.config.get("video.music_enabled", True))
        music_volume = float(ctx.config.get("video.music_volume_db", -18))
        tail = float(ctx.config.get("video.tail_seconds", 0.5))
        card_enabled = bool(ctx.config.get("video.title_card.enabled", True))
        card_fade = float(ctx.config.get("video.title_card.fade_seconds", 0.5))
        card_font = ctx.config.get("thumbnail.font_path", "") or ""

        done, failed = 0, 0
        errors: list[str] = []
        for i, video in enumerate(videos):
            ctx.report(self.stage, i / len(videos))
            try:
                background = pick_clip(category, selection,
                                       state_get=settings.get,
                                       state_set=settings.set)
                music = pick_music(MUSIC_DIR) if music_enabled else None
                fmt = (VideoFormat.SHORTS if video["format"] == "shorts"
                       else VideoFormat.LANDSCAPE)
                duration = float(video["duration_s"] or 0) + tail
                if duration <= tail:
                    raise RenderError(
                        f"video {video['id']} has unknown audio duration")

                intro = float(video["intro_seconds"] or 0)
                card_path = self._make_card(
                    ctx, video, fmt, card_enabled, intro, card_font, video_repo)

                spec = RenderSpec(
                    audio_path=Path(video["audio_path"]),
                    background_path=background,
                    output_path=OUTPUT_DIR / f"video_{video['id']}.mp4",
                    format=fmt,
                    captions_path=(Path(video["captions_path"])
                                   if video["captions_path"] else None),
                    music_path=music,
                    music_volume_db=music_volume,
                    background_effects=effects,
                    title_card_path=card_path,
                    intro_seconds=intro if card_path else 0.0,
                    card_fade_seconds=card_fade,
                )
                output = render(spec, duration)
                video_repo.set_file(video["id"], str(output), duration)
                if video["story_id"]:
                    story_repo.set_status(video["story_id"], StoryStatus.PRODUCED)
                done += 1
                self.log.info("Rendered %s", output.name)
            except (MediaLibraryError, RenderError) as exc:
                self.log.warning("Render failed for video %s: %s",
                                 video["id"], exc)
                errors.append(str(exc))
                failed += 1
                if isinstance(exc, MediaLibraryError):
                    break  # same error would repeat for every video
            except Exception as exc:
                self.log.exception("Unexpected render error for video %s",
                                   video["id"])
                errors.append(f"{type(exc).__name__}: {exc}")
                failed += 1

        message = f"{done} videos rendered, {failed} failed"
        if errors:
            message += f" - first error: {errors[0][:200]}"
        return AgentResult(ok=done > 0 or failed == 0, message=message,
                           data={"done": done, "failed": failed})

    # ------------------------------------------------------------------
    def _make_card(self, ctx, video, fmt, enabled, intro, font_path, video_repo):
        """Generate the title-card image for a video, or return None.

        Returns the card path when a card should be overlaid, else None. Never
        raises - a card failure must not block the render.
        """
        if not enabled or intro <= 0:
            return None
        title = (video["title"] or "").strip()
        if not title:
            return None
        try:
            account = resolve_account(ctx.config, video.get("account") or "")
            width = int(min(fmt.resolution[0], 1080) * 0.9)
            card_path = CARDS_DIR / f"video_{video['id']}.png"
            generate_title_card(
                title, account, card_path, width=width,
                upvotes=str(ctx.config.get("video.title_card.upvotes", "99+")),
                comments=str(ctx.config.get("video.title_card.comments", "99+")),
                font_path=font_path)
            video_repo.set_card(video["id"], str(card_path))
            return card_path
        except (TitleCardError, OSError, ValueError) as exc:
            self.log.warning("Title card failed for video %s: %s",
                             video["id"], exc)
            return None
