"""LLM response parsing + router fallback tests."""
import pytest

from api.llm.base import LLMError, LLMResponse
from api.llm.router import LLMRouter
from tests.fakes import FakeProvider


def make_response(text: str) -> LLMResponse:
    return LLMResponse(text=text, provider="fake", model="m")


def test_parse_clean_json():
    assert make_response('{"a": 1}').parse_json() == {"a": 1}


def test_parse_fenced_json():
    text = "```json\n{\"a\": 1}\n```"
    assert make_response(text).parse_json() == {"a": 1}


def test_parse_json_with_prose():
    text = 'Here is your result:\n{"a": 1}\nHope that helps!'
    assert make_response(text).parse_json() == {"a": 1}


def test_parse_garbage_raises():
    with pytest.raises(LLMError):
        make_response("not json at all").parse_json()


def _router_with(config, providers):
    router = LLMRouter(config)
    router.providers = providers
    return router


def test_router_uses_preferred(config):
    fake = FakeProvider(['{"ok": true}'])
    config.set("ai.tasks.score.provider", "fake", persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    router = _router_with(config, {"fake": fake})
    response = router.complete("score", "prompt", json_mode=True)
    assert response.provider == "fake"
    assert len(fake.calls) == 1


def test_router_falls_back_when_preferred_down(config):
    down = FakeProvider(available=False)
    backup = FakeProvider(["backup response"])
    config.set("ai.tasks.score.provider", "down", persist=False)
    config.set("ai.fallback_order", ["down", "backup"], persist=False)
    router = _router_with(config, {"down": down, "backup": backup})
    response = router.complete("score", "prompt")
    assert response.text == "backup response"


def test_router_raises_when_all_down(config):
    config.set("ai.tasks.score.provider", "down", persist=False)
    config.set("ai.fallback_order", ["down"], persist=False)
    router = _router_with(config, {"down": FakeProvider(available=False)})
    with pytest.raises(LLMError):
        router.complete("score", "prompt")


def test_usage_callback_fires(config):
    recorded = []
    config.set("ai.tasks.score.provider", "fake", persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    router = LLMRouter(config, usage_callback=lambda *a: recorded.append(a))
    router.providers = {"fake": FakeProvider(["x"])}
    router.complete("score", "prompt")
    assert recorded and recorded[0][2] == "score"
