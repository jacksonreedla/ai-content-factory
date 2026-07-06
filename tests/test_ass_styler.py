# tests/test_ass_styler.py
from pathlib import Path

from plugins.captions.ass_styler import ASSStyler
from plugins.captions.word_timing import WordTiming


def _words():
    return [
        WordTiming("Hello", 0.0, 0.4),
        WordTiming("world", 0.4, 0.8),
        WordTiming("this", 0.8, 1.0),
        WordTiming("is", 1.0, 1.1),
        WordTiming("a", 1.1, 1.15),
        WordTiming("test", 1.15, 1.5),
        WordTiming("caption", 1.5, 2.0),
        WordTiming("block", 2.0, 2.4),
    ]


def test_render_writes_ass_and_srt(tmp_path):
    styler = ASSStyler()
    ass = tmp_path / "c.ass"
    srt = tmp_path / "c.srt"
    arts = styler.render(_words(), ass_path=str(ass), srt_path=str(srt))
    assert Path(arts.ass_path).exists()
    assert Path(arts.srt_path).exists()
    ass_text = ass.read_text()
    assert "[Script Info]" in ass_text
    assert "Style: Default" in ass_text
    assert "Hello" in ass_text
    assert "\\k" in ass_text  # karaoke timing


def test_srt_is_numbered(tmp_path):
    styler = ASSStyler()
    srt = tmp_path / "c.srt"
    styler.render(_words(), srt_path=str(srt))
    text = srt.read_text()
    assert "1\n" in text
    assert "2\n" in text
    assert "-->" in text


def test_render_empty_words_returns_empty_paths(tmp_path):
    styler = ASSStyler()
    arts = styler.render([], ass_path=str(tmp_path / "x.ass"),
                         srt_path=str(tmp_path / "x.srt"))
    assert arts.ass_path  # returns the path string, no file written
    assert not (tmp_path / "x.ass").exists()


def test_format_times():
    from plugins.captions.ass_styler import _fmt_time, _srt_time
    assert _fmt_time(0) == "0:00:00.00"
    assert _fmt_time(61.5) == "0:01:01.50"
    assert _srt_time(0) == "0:00:00,000"
    assert _srt_time(61.5) == "0:01:01,500"
