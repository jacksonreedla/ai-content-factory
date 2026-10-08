"""Caption builder tests - pure functions, no whisper needed."""
from subtitles.base import CaptionStyle
from subtitles.builder import (build_karaoke_ass, build_sentence_srt,
                               build_word_ass, group_words, resolve_style,
                               _ass_color, _phrase_lines)

WORDS = [
    {"word": "So", "start": 0.0, "end": 0.2},
    {"word": "there", "start": 0.2, "end": 0.4},
    {"word": "I", "start": 0.4, "end": 0.5},
    {"word": "was.", "start": 0.5, "end": 0.9},
    {"word": "Everything", "start": 2.0, "end": 2.5},
    {"word": "changed!", "start": 2.5, "end": 3.0},
]


def test_word_ass_structure(tmp_path):
    out = build_word_ass(WORDS, CaptionStyle(), tmp_path / "test.ass")
    content = out.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in content
    assert "PlayResY: 1920" in content
    assert content.count("Dialogue:") == len(WORDS)
    assert "EVERYTHING" in content        # uppercased
    assert "\\fscx" in content            # pop animation present by default


def test_word_ass_no_gaps(tmp_path):
    out = build_word_ass(WORDS[:2], CaptionStyle(animation="none"),
                         tmp_path / "t.ass")
    content = out.read_text(encoding="utf-8")
    # first word should stay on screen until second starts (0.2s)
    assert "0:00:00.00,0:00:00.20" in content


def test_ass_color_conversion():
    assert _ass_color("#FF0000") == "&H000000FF"   # red -> BGR
    assert _ass_color("#FFD400") == "&H0000D4FF"


def test_group_words_breaks_on_sentence():
    groups = group_words(WORDS)
    assert len(groups) == 2
    assert groups[0]["text"] == "So there I was."
    assert groups[1]["text"] == "Everything changed!"


def test_group_words_breaks_on_length():
    long_words = [{"word": "word" + str(i), "start": i * 0.3,
                   "end": i * 0.3 + 0.25} for i in range(30)]
    groups = group_words(long_words, max_chars=30)
    assert all(len(g["text"]) <= 37 for g in groups)
    assert len(groups) > 1


def test_sentence_srt(tmp_path):
    out = build_sentence_srt(WORDS, tmp_path / "test.srt")
    content = out.read_text(encoding="utf-8")
    assert "1\n00:00:00,000 --> 00:00:00,900" in content
    assert "So there I was." in content
    assert "Everything changed!" in content


def test_resolve_style_presets():
    style = resolve_style("yellow_pop")
    assert style.color == "#FFD400"
    minimal = resolve_style("minimal")
    assert minimal.position == "bottom"
    assert minimal.animation == "none"


def test_karaoke_preset():
    style = resolve_style("karaoke")
    assert style.animation == "karaoke"
    assert style.highlight_color == "#39E639"


def test_phrase_lines_group_short():
    lines = _phrase_lines(WORDS, max_words=3)
    # every on-screen line holds at most 3 words -> not a lonely single word
    assert all(len(line) <= 3 for line in lines)
    assert len(lines) >= 2


def test_karaoke_ass_shows_full_line_with_highlight(tmp_path):
    out = build_karaoke_ass(WORDS, resolve_style("karaoke"), tmp_path / "k.ass")
    content = out.read_text(encoding="utf-8")
    # one event per word (each word gets its turn as the highlighted one)
    assert content.count("Dialogue:") == len(WORDS)
    # the highlight color + pop transform must appear on active words
    assert _ass_color("#39E639") in content
    assert "\\t(0,90," in content
    # a line with multiple words visible at once (siblings alongside active word)
    assert any("SO" in ln and "THERE" in ln for ln in content.splitlines())
