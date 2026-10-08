"""Rewrite Agent: turns approved stories into original spoken narration.

Every narration ends with a short question to the audience (e.g. "Am I in the
wrong?") to drive comments. The question is generated per-story by the LLM and
tailored to the video; if the LLM is unavailable it falls back to a random pick
from ``rewrite.engagement_fallbacks``. Toggle it with
``rewrite.engagement_question``.
"""
from __future__ import annotations

import random

from agents.base import Agent, AgentContext, AgentResult
from database.repositories import NarrationRepo, StoryRepo
from models.story import StoryStatus


class RewriteAgent(Agent):
    name = "rewrite"
    stage = "rewrite"

    @staticmethod
    def _clean_question(text: str) -> str:
        """Reduce model output to one tidy question ending in '?'."""
        if not text:
            return ""
        line = text.strip().splitlines()[0].strip()
        line = line.strip('"').strip("'").strip()
        # Drop a leading label like "Question:" if the model added one.
        if ":" in line[:12]:
            line = line.split(":", 1)[1].strip()
        if not line:
            return ""
        if not line.endswith("?"):
            line = line.rstrip(".!,;: ") + "?"
        return line

    def _closing_question(self, ctx: AgentContext, story,
                          narration_text: str) -> str:
        """A relevant audience question; LLM first, fallback pool if it fails."""
        fallbacks = list(ctx.config.get("rewrite.engagement_fallbacks", []) or [])
        try:
            prompt = ctx.prompts.render(
                "engagement_question",
                title=story.title, narration=narration_text[:4000])
            response = ctx.llm.complete("engagement", prompt, temperature=0.9,
                                        max_tokens=40)
            question = self._clean_question(response.text)
            if question:
                return question
        except Exception as exc:
            self.log.warning("Engagement question via AI failed for story %s "
                             "(%s); using a fallback", story.id, exc)
        return random.choice(fallbacks) if fallbacks else ""

    def _with_closing_question(self, ctx: AgentContext, story,
                               narration: str) -> str:
        """Append the closing question unless disabled."""
        if not ctx.config.get("rewrite.engagement_question", True):
            return narration
        question = self._closing_question(ctx, story, narration)
        if not question:
            return narration
        body = narration.rstrip()
        # Avoid an awkward double question if the body already ends in one.
        if body.endswith("?"):
            return body
        return body + "\n\n" + question

    def execute(self, ctx: AgentContext) -> AgentResult:
        story_repo = StoryRepo(ctx.db)
        narration_repo = NarrationRepo(ctx.db)

        # A specific story can be requested (from the GUI); otherwise take
        # everything approved.
        story_id = ctx.data.get("story_id")
        if story_id:
            story = story_repo.get(int(story_id))
            stories = [story] if story else []
        else:
            stories = story_repo.by_status(StoryStatus.APPROVED)

        if not stories:
            return AgentResult(ok=True, skipped=True,
                               message="no approved stories to rewrite")

        style = ctx.data.get("style", ctx.config.get("rewrite.style", "storytelling"))
        target_seconds = int(ctx.data.get(
            "target_seconds", ctx.config.get("rewrite.target_seconds", 60)))
        wpm = int(ctx.config.get("rewrite.words_per_minute", 155))
        target_words = max(50, int(target_seconds / 60 * wpm))

        done, failed = 0, 0
        for i, story in enumerate(stories):
            ctx.report(self.stage, i / len(stories))
            prompt = ctx.prompts.render(
                "rewrite_story",
                title=story.title, text=story.text[:12000],
                style=style, target_words=target_words,
                target_seconds=target_seconds,
            )
            try:
                response = ctx.llm.complete("rewrite", prompt, temperature=0.8,
                                            max_tokens=max(1024, target_words * 3))
                narration = response.text.strip()
                if len(narration.split()) < max(30, target_words // 4):
                    raise ValueError(
                        f"narration too short ({len(narration.split())} words)")
                narration = self._with_closing_question(ctx, story, narration)
                narration_id = narration_repo.add(
                    story.id, style, target_seconds, narration,
                    provider=response.provider, model=response.model,
                )
                story_repo.set_status(story.id, StoryStatus.REWRITTEN)
                ctx.data.setdefault("narration_ids", []).append(narration_id)
                done += 1
            except Exception as exc:
                self.log.warning("Rewrite failed for story %s: %s", story.id, exc)
                failed += 1

        return AgentResult(ok=failed < max(1, len(stories)),
                           message=f"{done} narrations written, {failed} failed",
                           data={"done": done, "failed": failed})
