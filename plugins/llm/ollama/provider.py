# plugins/llm/ollama/provider.py
import json
import logging

from plugins.llm.base import extract_json

log = logging.getLogger(__name__)


class OllamaProvider:
    """LLMProvider over the Ollama HTTP /api/chat endpoint.

    `transport` is an httpx-like client (real httpx.Client by default; a fake
    in tests). Satisfies the LLMProvider protocol.
    """

    def __init__(self, host: str = "http://localhost:11434",
                 model: str = "llama3.1", transport=None,
                 timeout: float = 120.0, temperature: float = 0.7) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        if transport is None:
            import httpx
            transport = httpx.Client(timeout=timeout)
        self._transport = transport

    def complete(self, prompt: str, system: str = "", **kw) -> str:
        payload = {
            "model": kw.get("model", self.model),
            "stream": False,
            "options": {"temperature": kw.get("temperature", self.temperature)},
            "messages": [
                {"role": "system",
                 "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        r = self._transport.post(
            f"{self.host}/api/chat", json=payload,
            timeout=kw.get("timeout", self.timeout),
        )
        r.raise_for_status()
        data = r.json()
        return data["message"]["content"]

    def json_complete(self, prompt: str, schema: dict,
                      system: str = "", **kw) -> dict:
        sys_msg = (system + "\n\n" if system else "") + (
            "Respond ONLY with a JSON object matching this schema. "
            "No prose, no code fences:\n" + json.dumps(schema, indent=2)
        )
        text = self.complete(prompt, system=sys_msg, **kw)
        return extract_json(text)
