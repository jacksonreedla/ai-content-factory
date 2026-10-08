"""OpenAI provider - activates when an API key is configured."""
from __future__ import annotations

import logging

import requests

from api.llm.base import LLMError, LLMProvider, LLMResponse

log = logging.getLogger("acf.llm.openai")

API_URL = "https://api.openai.com/v1/chat/completions"


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, api_key: str = "", default_model: str = "gpt-4o-mini",
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
            raise LLMError("OpenAI API key not configured (Settings -> AI)")
        model = model or self.default_model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        try:
            r = requests.post(
                API_URL, json=body, timeout=self.timeout_s,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            raise LLMError(f"OpenAI request failed: {exc}") from exc

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected OpenAI response shape: {data}") from exc
        usage = data.get("usage", {})
        return LLMResponse(
            text=text, provider=self.name, model=model,
            tokens_in=int(usage.get("prompt_tokens", 0)),
            tokens_out=int(usage.get("completion_tokens", 0)),
            raw=data,
        )
