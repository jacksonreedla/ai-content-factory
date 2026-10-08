"""AI story generator content source.

Uses the existing LLM router (whatever provider is configured) to write
original stories from a theme. No external service beyond the LLM the app
already depends on, so it is always available offline with Ollama and fully
within every platform's terms - the content is original.

Parsing of the model output is a pure function so it can be tested without
calling a model.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re

from api.llm.router import LLMRouter
from app.config import Config
from app.prompt_manager import PromptManager
from models.story import Story, StoryStatus

log = logging.getLogger("acf.aistory")

_FENCE_RE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


def _content_id(title: str, text: str) -> str:
    digest = hashlib.sha1(f"{title}\n{text}".encode("utf-8")).hexdigest()
    return f"ai-{digest[:16]}"


def parse_generated(raw: str) -> list[Story]:
    """Parse an LLM response into Story objects. Pure - no network.

    Tolerates code fences and leading/trailing prose around the JSON array.
    """
    if not raw:
        return []
    cleaned = _FENCE_RE.sub("", raw).strip()

    data = None
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to extracting the outermost [ ... ] block.
        start, end = cleaned.find("["), cleaned.rfind("]")
        if start != -1 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                data = None

    if isinstance(data, dict):
        data = data.get("stories", [data])
    if not isinstance(data, list):
        log.warning("Generated story output was not a JSON array")
        return []

    stories: list[Story] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        text = str(entry.get("text", "") or entry.get("story", "")).strip()
        if not text:
            continue
        stories.append(Story(
            id=None, source="ai", source_id=_content_id(title, text),
            title=title or "Untitled", text=text,
            author="AI", subreddit="ai_generated", url="",
            upvotes=0, num_comments=0, created_utc=0.0,
            nsfw=False, status=StoryStatus.NEW,
        ))
    return stories


class StoryGenerator:
    """Generates original stories via the LLM router."""

    def __init__(self, config: Config, llm: LLMRouter, prompts: PromptManager):
        self.config = config
        self.llm = llm
        self.prompts = prompts

    def generate(self, count: int | None = None) -> list[Story]:
        """Generate ``count`` unique stories.

        Smaller local models often ignore "write N stories" and return one.
        Rather than trust a single call, this asks for the number still
        missing and repeats until it has enough (or runs out of attempts),
        deduping by content so retries don't pile up copies.
        """
        cfg = self.config.get("ai_stories", {}) or {}
        count = int(count or cfg.get("count", 3))
        max_attempts = count + 4

        collected: dict[str, Story] = {}
        attempts = 0
        provider = model = ""
        while len(collected) < count and attempts < max_attempts:
            attempts += 1
            remaining = count - len(collected)
            batch, provider, model = self._request(remaining, cfg)
            for story in batch:
                collected.setdefault(story.source_id, story)
                if len(collected) >= count:
                    break

        stories = list(collected.values())[:count]
        log.info("Generated %d/%d stories via %s/%s in %d attempt(s)",
                 len(stories), count, provider or "?", model or "?", attempts)
        return stories

    def _request(self, count: int, cfg: dict) -> tuple[list[Story], str, str]:
        """One LLM call asking for ``count`` stories; returns (stories, provider, model)."""
        max_words = cfg.get("max_words", 700)
        prompt = self.prompts.render(
            "generate_story",
            count=count,
            theme=cfg.get("theme", "dramatic first-person stories with a twist ending"),
            style=cfg.get("style", "storytelling"),
            min_words=cfg.get("min_words", 150),
            max_words=max_words,
        )
        response = self.llm.complete(
            "generate_story", prompt,
            temperature=float(cfg.get("temperature", 1.0)),
            json_mode=True,
            max_tokens=max(1024, int(max_words * count * 2)),
        )
        return parse_generated(response.text), response.provider, response.model
