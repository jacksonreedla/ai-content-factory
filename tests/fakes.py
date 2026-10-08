"""Test doubles."""
from __future__ import annotations

from api.llm.base import LLMProvider, LLMResponse


class FakeProvider(LLMProvider):
    """Scriptable provider: returns queued responses in order."""

    name = "fake"
    default_model = "fake-model"

    def __init__(self, responses: list[str] | None = None, available: bool = True):
        self.responses = list(responses or [])
        self.available = available
        self.calls: list[dict] = []

    def is_available(self) -> bool:
        return self.available

    def generate(self, prompt: str, *, model: str = "", system: str = "",
                 json_mode: bool = False, temperature: float = 0.7,
                 max_tokens: int = 4096) -> LLMResponse:
        self.calls.append({"prompt": prompt, "model": model, "json": json_mode})
        text = self.responses.pop(0) if self.responses else "fake output"
        return LLMResponse(text=text, provider=self.name,
                           model=model or self.default_model,
                           tokens_in=10, tokens_out=20)
