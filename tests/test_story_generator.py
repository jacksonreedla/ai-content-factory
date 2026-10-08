"""AI story generator: pure output parsing + generation via a fake LLM."""
from api.llm.router import LLMRouter
from api.story_generator import StoryGenerator, parse_generated
from app.prompt_manager import PromptManager
from tests.fakes import FakeProvider

ARRAY = '[{"title": "A Twist", "text": "It was a body of text."}, ' \
        '{"title": "Two", "text": "Second body here."}]'


def test_parse_plain_array():
    stories = parse_generated(ARRAY)
    assert len(stories) == 2
    assert stories[0].source == "ai"
    assert stories[0].title == "A Twist"
    assert stories[0].source_id.startswith("ai-")


def test_parse_code_fenced():
    stories = parse_generated("```json\n" + ARRAY + "\n```")
    assert len(stories) == 2


def test_parse_dict_wrapper():
    stories = parse_generated('{"stories": ' + ARRAY + '}')
    assert len(stories) == 2


def test_parse_with_surrounding_prose():
    raw = "Sure, here you go:\n" + ARRAY + "\nHope these help!"
    stories = parse_generated(raw)
    assert len(stories) == 2


def test_parse_skips_entry_without_text():
    stories = parse_generated('[{"title": "empty"}, {"title": "ok", "text": "hi"}]')
    assert len(stories) == 1
    assert stories[0].title == "ok"


def test_parse_invalid_returns_empty():
    assert parse_generated("total nonsense, no json") == []
    assert parse_generated("") == []


def test_content_id_is_stable_and_unique():
    a = parse_generated(ARRAY)
    b = parse_generated(ARRAY)
    assert a[0].source_id == b[0].source_id      # same content -> same id
    assert a[0].source_id != a[1].source_id      # different content -> different id


def _fake_router(config, responses):
    config.set("ai.tasks.generate_story", {"provider": "fake", "model": ""},
               persist=False)
    config.set("ai.fallback_order", ["fake"], persist=False)
    return LLMRouter(config, extra_providers={"fake": FakeProvider(responses)})


def test_generate_uses_router(config):
    router = _fake_router(config, [ARRAY])
    gen = StoryGenerator(config, router, PromptManager())
    stories = gen.generate(count=2)
    assert len(stories) == 2
    assert all(s.source == "ai" for s in stories)


def test_generate_loops_until_count(config):
    # Model returns one story per call - generator should keep asking.
    singles = [
        '[{"title": "S1", "text": "first tale, unique alpha content."}]',
        '[{"title": "S2", "text": "second tale, unique beta content."}]',
        '[{"title": "S3", "text": "third tale, unique gamma content."}]',
    ]
    gen = StoryGenerator(config, _fake_router(config, singles), PromptManager())
    stories = gen.generate(count=3)
    assert len(stories) == 3
    assert len({s.source_id for s in stories}) == 3


def test_generate_terminates_on_repeats(config):
    # Model keeps returning the same story - must dedupe and stop, not hang.
    dup = '[{"title": "Dup", "text": "the very same tale every time."}]'
    gen = StoryGenerator(config, _fake_router(config, [dup] * 20), PromptManager())
    stories = gen.generate(count=3)
    assert len(stories) == 1
