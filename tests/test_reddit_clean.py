"""clean_story_text: turn raw Reddit markdown into clean narration text."""
from __future__ import annotations

from api.reddit_client import clean_story_text


def test_strips_markdown_emphasis():
    out = clean_story_text("This was **so** *bad* and ~~worse~~.")
    assert out == "This was so bad and worse."


def test_markdown_link_keeps_text_drops_url():
    out = clean_story_text("See [my update](https://reddit.com/x) here.")
    assert out == "See my update here."
    assert "http" not in out


def test_bare_urls_removed():
    out = clean_story_text("Proof at https://imgur.com/abc and www.example.com ok")
    assert "http" not in out and "www." not in out
    assert "Proof at" in out and "ok" in out


def test_html_entities_unescaped():
    assert clean_story_text("me &amp; her &lt;3") == "me & her <3"


def test_zero_width_chars_removed():
    # Reddit sprinkles zero-width spaces (​) into posts.
    assert clean_story_text("hello​​world") == "helloworld"


def test_headings_quotes_and_bullets_stripped():
    raw = "# Title\n> a quote\n- point one\n1. numbered"
    out = clean_story_text(raw)
    assert "#" not in out and ">" not in out
    assert "Title" in out and "a quote" in out
    assert "point one" in out and "numbered" in out


def test_paragraph_breaks_preserved():
    out = clean_story_text("Para one.\n\n\n\nPara two.")
    assert out == "Para one.\n\nPara two."


def test_empty_input():
    assert clean_story_text("") == ""
    assert clean_story_text(None) == ""  # type: ignore[arg-type]
