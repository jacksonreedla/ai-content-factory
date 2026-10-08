"""Voice Agent: turns narrations into voiceover audio + a video record."""
from __future__ import annotations

from app.paths import AUDIO_DIR
from agents.base import Agent, AgentContext, AgentResult
from app.accounts import account_names, rotate_account
from database.repositories import (NarrationRepo, SettingsRepo, StoryRepo,
                                   VideoRepo)
from models.story import StoryStatus
from voices.audio_post import audio_duration_s, concat_with_gap, post_process
from voices.base import TTSRequest
from voices.registry import TTSUnavailableError, build_engine


class VoiceAgent(Agent):
    name = "voice"
    stage = "voice"

    def execute(self, ctx: AgentContext) -> AgentResult:
        story_repo = StoryRepo(ctx.db)
        narration_repo = NarrationRepo(ctx.db)
        video_repo = VideoRepo(ctx.db)

        stories = [s for s in story_repo.by_status(StoryStatus.REWRITTEN)
                   if not video_repo.story_has_audio(s.id)]
        if not stories:
            return AgentResult(ok=True, skipped=True,
                               message="no narrations awaiting voiceover")

        try:
            engine = build_engine(ctx.config)
        except TTSUnavailableError as exc:
            return AgentResult(ok=False, message=str(exc))
        self.log.info("Using TTS engine: %s", engine.name)

        fmt = ctx.config.get("video.format", "shorts")
        speed = float(ctx.config.get("voice.speed", 1.0))
        voice_id = ctx.config.get("voice.voice_id", "")
        normalize = bool(ctx.config.get("voice.normalize", True))
        trim = bool(ctx.config.get("voice.trim_silence", True))
        title_card = bool(ctx.config.get("video.title_card.enabled", True))
        gap = float(ctx.config.get("video.title_card.gap_seconds", 0.4))

        # Round-robin account assignment across configured accounts. The
        # rotation counter is persisted in app_settings so the cycle continues
        # A -> B -> C across separate runs, not just within one batch. This is
        # what keeps 3+ accounts from ever posting the same story.
        settings = SettingsRepo(ctx.db)
        rotate = bool(ctx.config.get("publish.rotate_accounts", True))
        accounts = account_names(ctx.config) if rotate else []
        rot_index = int(settings.get("account_rotation_index", "0") or 0)

        done, failed = 0, 0
        for i, story in enumerate(stories):
            ctx.report(self.stage, i / len(stories))
            narration = narration_repo.latest_for_story(story.id)
            if not narration:
                continue
            try:
                def synth(text: str, path):
                    engine.synthesize(TTSRequest(
                        text=text, output_path=path,
                        voice_id=voice_id, speed=speed))
                    return post_process(path, normalize=normalize,
                                        trim_silence=trim)

                out_path = AUDIO_DIR / f"story_{story.id}.wav"
                intro_seconds = 0.0

                if title_card and story.title.strip():
                    # Read the title first, then the body, so the card can show
                    # while the title is spoken and fade out afterwards.
                    title_path = synth(story.title,
                                       AUDIO_DIR / f"story_{story.id}_title.wav")
                    body_path = synth(narration["text"],
                                      AUDIO_DIR / f"story_{story.id}_body.wav")
                    intro_seconds = audio_duration_s(title_path) + gap
                    concat_with_gap(title_path, body_path, out_path, gap)
                    title_path.unlink(missing_ok=True)
                    body_path.unlink(missing_ok=True)
                else:
                    synth(narration["text"], out_path)

                duration = audio_duration_s(out_path)
                video_id = video_repo.add(story.id, narration["id"], fmt,
                                          title=story.title)
                video_repo.set_audio(video_id, str(out_path), duration)
                video_repo.set_intro(video_id, intro_seconds)
                if accounts:
                    account, rot_index = rotate_account(accounts, rot_index)
                    video_repo.set_account(video_id, account)
                    self.log.info("Assigned story %s -> account '%s'",
                                  story.id, account)
                ctx.data.setdefault("video_ids", []).append(video_id)
                done += 1
                self.log.info("Voiceover for story %s: %.1fs (intro %.1fs) -> %s",
                              story.id, duration, intro_seconds, out_path.name)
            except Exception as exc:
                self.log.warning("Voiceover failed for story %s: %s", story.id, exc)
                failed += 1

        if accounts:
            settings.set("account_rotation_index", str(rot_index))

        return AgentResult(ok=done > 0 or failed == 0,
                           message=f"{done} voiceovers generated ({engine.name}), "
                                   f"{failed} failed",
                           data={"done": done, "failed": failed})
