"""SEO Agent: generates titles, descriptions, tags and pinned comments.

On top of whatever the AI produces, this stage always applies the user's own
metadata from Settings -> Upload:
  * custom tags they typed once (merged into every video's tags, and optionally
    added as #hashtags in the TikTok caption), and
  * a short auto-summary description (handy for TikTok's short captions).

These user rules run even when the AI metadata step is unavailable, so tags and
a summary are guaranteed on every video via a lightweight, no-AI fallback.
"""
from __future__ import annotations

import json
import re

from agents.base import Agent, AgentContext, AgentResult
from database.repositories import NarrationRepo, SettingsRepo, StoryRepo
from models.story import StoryStatus

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _normalize_tag(tag: str) -> str:
    return re.sub(r"\s+", " ", str(tag).strip().lstrip("#")).strip()


def _merge_tags(existing: list, extra: list) -> list[str]:
    """Append ``extra`` after ``existing``, de-duplicated case-insensitively."""
    out: list[str] = []
    seen: set[str] = set()
    for tag in list(existing) + list(extra):
        clean = _normalize_tag(tag)
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def short_summary(text: str, max_chars: int = 200) -> str:
    """A concise summary: whole sentences up to ``max_chars`` (never mid-word)."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    summary = ""
    for sentence in _SENTENCE_SPLIT.split(text):
        candidate = (summary + " " + sentence).strip()
        if len(candidate) > max_chars:
            break
        summary = candidate
    if not summary:  # first sentence already too long -> hard trim on a word
        summary = text[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return summary


class SEOAgent(Agent):
    name = "seo"
    stage = "seo"

    def _apply_user_metadata(self, metadata: dict, story, narration_text: str,
                             ctx: AgentContext) -> dict:
        """Layer the user's custom tags + short summary onto AI metadata."""
        metadata = dict(metadata) if isinstance(metadata, dict) else {}
        metadata.setdefault("title", story.title or "Untitled")
        metadata.setdefault("description", "")
        metadata.setdefault("hashtags", [])
        metadata.setdefault("tags", [])
        metadata.setdefault("pinned_comment", "")

        custom_tags = [_normalize_tag(t)
                       for t in (ctx.config.get("seo.custom_tags", []) or [])
                       if _normalize_tag(t)]

        # Tags: AI tags first, then the user's, de-duplicated.
        metadata["tags"] = _merge_tags(metadata.get("tags", []), custom_tags)

        # Optionally surface the custom tags as #hashtags in the caption.
        if custom_tags and ctx.config.get("seo.custom_tags_as_hashtags", True):
            existing = [h.lstrip("#") for h in metadata.get("hashtags", [])]
            merged = _merge_tags(existing, custom_tags)
            metadata["hashtags"] = ["#" + t.replace(" ", "") for t in merged]

        # Short auto-summary description (guaranteed if enabled, or if the AI
        # left the description empty).
        want_summary = ctx.config.get("seo.short_summary", True)
        if want_summary or not str(metadata.get("description", "")).strip():
            metadata["description"] = short_summary(
                narration_text,
                int(ctx.config.get("seo.summary_max_chars", 200)))
        return metadata

    def execute(self, ctx: AgentContext) -> AgentResult:
        story_repo = StoryRepo(ctx.db)
        narration_repo = NarrationRepo(ctx.db)
        settings = SettingsRepo(ctx.db)
        stories = story_repo.by_status(StoryStatus.REWRITTEN)
        if not stories:
            return AgentResult(ok=True, skipped=True,
                               message="no rewritten stories needing metadata")

        style = ctx.config.get("rewrite.style", "storytelling")
        done, ai_failed = 0, 0
        for i, story in enumerate(stories):
            ctx.report(self.stage, i / len(stories))
            narration = narration_repo.latest_for_story(story.id)
            if not narration:
                continue
            narration_text = narration["text"]

            metadata: dict = {}
            prompt = ctx.prompts.render(
                "generate_metadata",
                title=story.title, narration=narration_text[:8000], style=style,
            )
            try:
                response = ctx.llm.complete("metadata", prompt, json_mode=True,
                                            temperature=0.7)
                parsed = response.parse_json()
                if isinstance(parsed, dict):
                    metadata = parsed
                else:
                    ai_failed += 1
            except Exception as exc:
                # No AI available/failed: fall back to user metadata only so
                # tags and a summary are still applied.
                self.log.warning("AI metadata failed for story %s (%s); "
                                 "using custom-tags/summary fallback",
                                 story.id, exc)
                ai_failed += 1

            metadata = self._apply_user_metadata(
                metadata, story, narration_text, ctx)
            settings.set(f"metadata.story.{story.id}",
                         json.dumps(metadata, ensure_ascii=False))
            done += 1

        message = f"{done} metadata sets ready"
        if ai_failed:
            message += f" ({ai_failed} used custom-tags/summary fallback)"
        return AgentResult(ok=True, message=message,
                           data={"done": done, "ai_failed": ai_failed})
