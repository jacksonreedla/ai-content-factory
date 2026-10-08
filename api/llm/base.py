"""Base interface every LLM provider implements."""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(RuntimeError):
    """Raised when a provider call fails (network, auth, bad output...)."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    def parse_json(self) -> dict[str, Any]:
        """Extract a JSON object from the response, tolerating code fences
        and leading/trailing prose (common with local models)."""
        text = self.text.strip()
        # strip markdown fences
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # fall back: grab the outermost {...}
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise LLMError(f"Model did not return valid JSON. Output was:\n{self.text[:500]}")


class LLMProvider(ABC):
    """One backend (Ollama, Claude, OpenAI, or a plugin)."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Cheap check: is this provider usable right now (key set, server up)?"""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        model: str,
        system: str = "",
        json_mode: bool = False,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Run one completion. Raises LLMError on failure."""
