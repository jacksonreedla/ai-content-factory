"""Ollama provider - local models, free, the default backend."""
from __future__ import annotations

import logging

import requests

from api.llm.base import LLMError, LLMProvider, LLMResponse

log = logging.getLogger("acf.llm.ollama")


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", timeout_s: int = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def is_available(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except requests.RequestException as exc:
            log.warning("Could not list Ollama models: %s", exc)
            return []

    def generate(self, prompt: str, *, model: str, system: str = "",
                 json_mode: bool = False, temperature: float = 0.7,
                 max_tokens: int = 4096) -> LLMResponse:
        payload: dict = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        try:
            r = requests.post(f"{self.base_url}/api/generate",
                              json=payload, timeout=self.timeout_s)
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            raise LLMError(f"Ollama request failed: {exc}") from exc

        text = data.get("response", "")
        if not text:
            raise LLMError(f"Ollama returned an empty response for model '{model}'")
        return LLMResponse(
            text=text, provider=self.name, model=model,
            tokens_in=int(data.get("prompt_eval_count", 0)),
            tokens_out=int(data.get("eval_count", 0)),
            raw=data,
        )
