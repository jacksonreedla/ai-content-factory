"""Prompt template tests."""
import pytest

from app.prompt_manager import PromptError, PromptManager


def test_all_templates_exist():
    manager = PromptManager()
    templates = manager.list_templates()
    for required in ("score_story", "rewrite_story", "generate_metadata",
                     "thumbnail_text"):
        assert required in templates


def test_render_substitutes():
    manager = PromptManager()
    rendered = manager.render("rewrite_story", title="My Title", text="body",
                              style="dramatic", target_words=150,
                              target_seconds=60)
    assert "My Title" in rendered
    assert "dramatic" in rendered
    assert "150" in rendered
    assert "{title}" not in rendered


def test_score_template_keeps_json_braces():
    manager = PromptManager()
    rendered = manager.render("score_story", title="t", subreddit="s",
                              upvotes=1, num_comments=2, text="x")
    assert '{"entertainment"' in rendered  # {{ }} unescaped correctly


def test_missing_template_raises():
    manager = PromptManager()
    with pytest.raises(PromptError):
        manager.raw("does_not_exist")
