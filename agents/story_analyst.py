"""Story Analyst Agent: scores unscored stories with the configured LLM."""
from __future__ import annotations

from agents.base import Agent, AgentContext, AgentResult
from app.title_signals import wild_title_score
from database.repositories import StoryRepo
from models.story import StoryScores, StoryStatus


class StoryAnalystAgent(Agent):
    name = "story_analyst"
    stage = "score"

    def execute(self, ctx: AgentContext) -> AgentResult:
        repo = StoryRepo(ctx.db)
        stories = repo.by_status(StoryStatus.NEW)
        if not stories:
            return AgentResult(ok=True, skipped=True, message="no new stories to score")

        threshold = float(ctx.config.get("scoring.min_overall_score", 6.5))
        auto_approve = bool(ctx.config.get("scoring.auto_approve", False))
        prioritize_wild = bool(
            ctx.config.get("scoring.prioritize_wild_titles", False))
        wild_boost = float(ctx.config.get("scoring.wild_title_boost", 2.5))
        scored, rejected, failed = 0, 0, 0

        for i, story in enumerate(stories):
            ctx.report(self.stage, i / len(stories))
            prompt = ctx.prompts.render(
                "score_story",
                title=story.title, subreddit=story.subreddit,
                upvotes=story.upvotes, num_comments=story.num_comments,
                text=story.text[:8000],
            )
            try:
                response = ctx.llm.complete("score", prompt, json_mode=True,
                                            temperature=0.3)
                scores = StoryScores.from_llm_json(response.parse_json())
            except Exception as exc:
                self.log.warning("Scoring failed for story %s: %s", story.id, exc)
                failed += 1
                continue

            # Optionally push wild / out-of-pocket titles up the ranking so they
            # clear the threshold and sort first.
            if prioritize_wild:
                wild = wild_title_score(story.title)
                if wild > 0:
                    scores.values["wild_title"] = wild
                    scores.overall = round(
                        min(10.0, scores.overall + wild_boost * wild), 2)

            if scores.overall < threshold:
                repo.set_scores(story.id, scores, StoryStatus.REJECTED)
                repo.set_status(story.id, StoryStatus.REJECTED,
                                f"score {scores.overall:.1f} < threshold {threshold}")
                rejected += 1
            else:
                status = StoryStatus.APPROVED if auto_approve else StoryStatus.SCORED
                repo.set_scores(story.id, scores, status)
                scored += 1

        return AgentResult(
            ok=True,
            message=f"{scored} passed, {rejected} below threshold, {failed} failed",
            data={"scored": scored, "rejected": rejected, "failed": failed},
        )
