# tests/test_ollama_provider.py
import pytest

from plugins.llm.ollama.provider import OllamaProvider


class FakeTransport:
    """Stand-in for httpx.Client. Records calls, returns canned content."""
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append((url, json, timeout))
        content = self.response_text  # capture for the closure

        class R:
            status_code = 200
            def raise_for_status(self): pass
            def json(self_inner): return {"message": {"content": content}}
        return R()


def test_complete_returns_content():
    t = FakeTransport("hello world")
    p = OllamaProvider(host="http://x", model="m", transport=t)
    assert p.complete("prompt") == "hello world"
    assert t.calls[0][0].endswith("/api/chat")
    payload = t.calls[0][1]
    assert payload["model"] == "m"
    assert payload["messages"][1]["content"] == "prompt"


def test_complete_uses_custom_temperature():
    t = FakeTransport("ok")
    p = OllamaProvider(host="http://x", model="m", transport=t, temperature=0.2)
    p.complete("p", temperature=0.9)
    assert t.calls[0][1]["options"]["temperature"] == 0.9


def test_json_complete_parses():
    t = FakeTransport('{"overall": 80, "confidence": 0.9}')
    p = OllamaProvider(host="http://x", model="m", transport=t)
    out = p.json_complete("p", schema={"overall": "number"})
    assert out["overall"] == 80


def test_json_complete_raises_on_garbage():
    t = FakeTransport("totally not json")
    p = OllamaProvider(host="http://x", model="m", transport=t)
    with pytest.raises(Exception):
        p.json_complete("p", schema={})
