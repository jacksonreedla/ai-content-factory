"""Anthropic Claude provider - activates when an API key is configured."""
from __future__ import annotations

import logging

import requests

from api.llm.base import LLMError, LLMProvider, LLMResponse

log = logging.getLogger("acf.llm.claude")

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self, api_key: str = "", default_model: str = "claude-sonnet-5",
                 timeout_s: int = 120):
        self.api_key = api_key
        self.default_model = default_model
        self.timeout_s = timeout_s

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate(self, prompt: str, *, model: str = "", system: str = "",
                 json_mode: bool = False, temperature: float = 0.7,
                 max_tokens: int = 4096) -> LLMResponse:
        if not self.api_key:
            raise LLMError("Claude API key not configured (Settings -> AI)")
        model = model or self.default_model
        if json_mode:
            system = (system + "\n\nRespond with a single valid JSON object "
                               "and nothing else.").strip()
        body: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        try:
            r = requests.post(
                API_URL, json=body, timeout=self.timeout_s,
                headers={"x-api-key": self.api_key,
                         "anthropic-version": API_VERSION,
                         "content-type": "application/json"},
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            raise LLMError(f"Claude request failed: {exc}") from exc

        parts = data.get("content", [])
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        if not text:
            raise LLMError("Claude returned an empty response")
        usage = data.get("usage", {})
        return LLMResponse(
            text=text, provider=self.name, model=model,
            tokens_in=int(usage.get("input_tokens", 0)),
            tokens_out=int(usage.get("output_tokens", 0)),
            raw=data,
        )
