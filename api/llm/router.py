"""Routes each AI task to its configured provider, with fallback.

Config decides everything (Settings -> AI):
    ai.tasks.score    -> {"provider": "ollama", "model": "llama3.1"}
    ai.fallback_order -> ["ollama", "claude", "openai"]

If the preferred provider is down/unconfigured, the router walks the
fallback order. Usage (tokens) is recorded for the dashboard.
"""
from __future__ import annotations

import logging
from typing import Callable

from api.llm.base import LLMError, LLMProvider, LLMResponse
from api.llm.claude_provider import ClaudeProvider
from api.llm.ollama_provider import OllamaProvider
from api.llm.openai_provider import OpenAIProvider
from app.config import Config

log = logging.getLogger("acf.llm.router")

UsageCallback = Callable[[str, str, str, int, int], None]
# (provider, model, task, tokens_in, tokens_out)


class LLMRouter:
    def __init__(self, config: Config, usage_callback: UsageCallback | None = None,
                 extra_providers: dict[str, LLMProvider] | None = None):
        self.config = config
        self.usage_callback = usage_callback
        self.providers: dict[str, LLMProvider] = {
            "ollama": OllamaProvider(
                base_url=config.get("ai.ollama.base_url", "http://localhost:11434"),
                timeout_s=config.get("ai.ollama.timeout_s", 300),
            ),
            "claude": ClaudeProvider(
                api_key=config.get("ai.claude.api_key", ""),
                default_model=config.get("ai.claude.model", "claude-sonnet-5"),
                timeout_s=config.get("ai.claude.timeout_s", 120),
            ),
            "openai": OpenAIProvider(
                api_key=config.get("ai.openai.api_key", ""),
                default_model=config.get("ai.openai.model", "gpt-4o-mini"),
                timeout_s=config.get("ai.openai.timeout_s", 120),
            ),
        }
        if extra_providers:  # plugins can register more backends
            self.providers.update(extra_providers)

    # ------------------------------------------------------------------ public
    def complete(self, task: str, prompt: str, *, system: str = "",
                 json_mode: bool = False, temperature: float = 0.7,
                 max_tokens: int = 4096) -> LLMResponse:
        """Run ``task`` using its configured provider, falling back if needed."""
        task_cfg = self.config.get(f"ai.tasks.{task}", {}) or {}
        preferred = task_cfg.get("provider", "ollama")
        model = task_cfg.get("model", "")

        order = [preferred] + [
            p for p in self.config.get("ai.fallback_order", ["ollama", "claude", "openai"])
            if p != preferred
        ]

        last_error: Exception | None = None
        for name in order:
            provider = self.providers.get(name)
            if provider is None or not provider.is_available():
                continue
            use_model = model if name == preferred else ""  # fallbacks use their default
            try:
                response = provider.generate(
                    prompt, model=use_model or getattr(provider, "default_model", model),
                    system=system, json_mode=json_mode,
                    temperature=temperature, max_tokens=max_tokens,
                )
                if self.usage_callback:
                    try:
                        self.usage_callback(response.provider, response.model, task,
                                            response.tokens_in, response.tokens_out)
                    except Exception:
                        log.exception("Usage callback failed")
                if name != preferred:
                    log.warning("Task '%s' fell back from %s to %s", task, preferred, name)
                return response
            except LLMError as exc:
                log.warning("Provider %s failed for task '%s': %s", name, task, exc)
                last_error = exc

        raise LLMError(
            f"No AI provider could handle task '{task}'. "
            f"Is Ollama running, or is an API key configured? "
            f"Last error: {last_error}"
        )

    def availability(self) -> dict[str, bool]:
        return {name: p.is_available() for name, p in self.providers.items()}
