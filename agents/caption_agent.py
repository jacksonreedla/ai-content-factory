"""Caption Agent: transcribes voiceovers and writes styled caption files."""
from __future__ import annotations

from pathlib import Path

from agents.base import Agent, AgentContext, AgentResult
from app.paths import CAPTIONS_DIR
from database.repositories import VideoRepo
from subtitles.base import CaptionStyle
from subtitles.builder import (build_karaoke_ass, build_sentence_srt,
                               build_word_ass, resolve_style)
from subtitles.whisper_transcriber import WhisperNotInstalledError, WhisperTranscriber


def _make_transcriber(ctx: AgentContext) -> WhisperTranscriber:
    """Factory - patchable in tests."""
    return WhisperTranscriber(
        model_size=ctx.config.get("subtitles.whisper_model", "base"),
        device=ctx.config.get("subtitles.device", "auto"),
        language=ctx.config.get("subtitles.language", "en"),
    )


class CaptionAgent(Agent):
    name = "captions"
    stage = "captions"

    def execute(self, ctx: AgentContext) -> AgentResult:
        video_repo = VideoRepo(ctx.db)
        videos = video_repo.needing_captions()
        if not videos:
            return AgentResult(ok=True, skipped=True,
                               message="no videos awaiting captions")

        try:
            transcriber = _make_transcriber(ctx)
        except WhisperNotInstalledError as exc:
            return AgentResult(ok=False, message=str(exc))

        mode = ctx.config.get("captions.mode", "word")
        style = resolve_style(
            ctx.config.get("captions.preset", "karaoke"),
            CaptionStyle(
                mode=mode,
                font=ctx.config.get("captions.font", "Montserrat ExtraBold"),
                highlight_color=ctx.config.get("captions.highlight_color", "#FFD400"),
            ),
        )

        done, failed = 0, 0
        for i, video in enumerate(videos):
            ctx.report(self.stage, i / len(videos))
            audio = Path(video["audio_path"])
            if not audio.exists():
                self.log.warning("Audio missing for video %s: %s",
                                 video["id"], audio)
                failed += 1
                continue
            try:
                words = transcriber.transcribe(audio)
                if not words:
                    raise ValueError("transcription produced no words")
                # The title is spoken over the title card at the start; drop
                # those words so body captions only appear after the card fades.
                intro = float(video.get("intro_seconds") or 0)
                if intro > 0:
                    words = [w for w in words if w["start"] >= intro - 0.15]
                    if not words:
                        raise ValueError("no body words after title intro")
                if mode == "word":
                    res = (1080, 1920) if video["format"] == "shorts" else (1920, 1080)
                    builder = (build_karaoke_ass if style.animation == "karaoke"
                               else build_word_ass)
                    out = builder(
                        words, style, CAPTIONS_DIR / f"video_{video['id']}.ass",
                        play_res=res)
                else:
                    out = build_sentence_srt(
                        words, CAPTIONS_DIR / f"video_{video['id']}.srt")
                video_repo.set_captions(video["id"], str(out))
                done += 1
            except WhisperNotInstalledError as exc:
                return AgentResult(ok=False, message=str(exc))
            except Exception as exc:
                self.log.warning("Captions failed for video %s: %s",
                                 video["id"], exc)
                failed += 1

        return AgentResult(ok=done > 0 or failed == 0,
                           message=f"{done} caption files written, {failed} failed",
                           data={"done": done, "failed": failed})
