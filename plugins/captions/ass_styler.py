# plugins/captions/ass_styler.py
import json
import logging
from pathlib import Path

from plugins.captions.word_timing import WordTiming, SubtitleArtifacts

log = logging.getLogger(__name__)

# Default style if no template is loaded.
_DEFAULT_STYLE = {
    "font": "Arial",
    "size": 48,
    "primary_color": "&H00FFFFFF",   # white
    "outline_color": "&H00000000",   # black
    "outline": 3,
    "bold": True,
    "margin_v": 80,
}


def _load_style(template_path: Path, style_name: str = "default") -> dict:
    if not template_path.exists():
        return dict(_DEFAULT_STYLE)
    try:
        data = json.loads(template_path.read_text(encoding="utf-8"))
        return data.get(style_name, _DEFAULT_STYLE)
    except Exception as e:
        log.warning("caption template load failed (%s); using default", e)
        return dict(_DEFAULT_STYLE)


def _fmt_time(t: float) -> str:
    """ASS timestamp: H:MM:SS.cs"""
    if t < 0:
        t = 0.0
    cs = int(round(t * 100)) % 100
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _srt_time(t: float) -> str:
    """SRT timestamp: H:MM:SS,mmm"""
    if t < 0:
        t = 0.0
    ms = int(round(t * 1000)) % 1000
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h}:{m:02d}:{s:02d},{ms:03d}"


class ASSStyler:
    """CaptionStyler that emits ASS (word-by-word karaoke) + plain SRT.

    Loads style templates from `caption_templates.json` if present, else uses
    the built-in default. Satisfies the CaptionStyler protocol.
    """

    def __init__(self, templates_path: Path | None = None,
                 style_name: str = "default") -> None:
        self.templates_path = Path(templates_path) if templates_path else None
        self.style_name = style_name

    def render(self, words: list[WordTiming],
               style=None, ass_path=None, srt_path=None) -> SubtitleArtifacts:
        s = style or self._style()
        ass_path = str(ass_path) if ass_path else None
        srt_path = str(srt_path) if srt_path else None
        if not words:
            return SubtitleArtifacts(ass_path=ass_path or "", srt_path=srt_path or "")
        if ass_path:
            Path(ass_path).parent.mkdir(parents=True, exist_ok=True)
            Path(ass_path).write_text(self._build_ass(words, s),
                                      encoding="utf-8")
        if srt_path:
            Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
            Path(srt_path).write_text(self._build_srt(words),
                                      encoding="utf-8")
        return SubtitleArtifacts(ass_path=ass_path or "", srt_path=srt_path or "")

    def _style(self) -> dict:
        if self.templates_path:
            return _load_style(self.templates_path, self.style_name)
        return dict(_DEFAULT_STYLE)

    def _build_ass(self, words: list[WordTiming], style: dict) -> str:
        bold = -1 if style.get("bold") else 0
        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, "
            "Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{style.get('font','Arial')},"
            f"{style.get('size',48)},"
            f"{style.get('primary_color','&H00FFFFFF')},"
            f"{style.get('outline_color','&H00000000')},&H80000000,"
            f"{bold},0,0,0,100,100,0,0,1,"
            f"{style.get('outline',3)},1,2,40,40,"
            f"{style.get('margin_v',80)},1\n"
            "\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
            "Effect, Text\n"
        )
        lines = []
        # Group words into ~7-word caption blocks for readability.
        block_size = 7
        for i in range(0, len(words), block_size):
            block = words[i:i + block_size]
            start = block[0].start
            end = block[-1].end
            # Karaoke timing: {\k<N>} per word (centiseconds).
            karaoke = []
            for w in block:
                dur = max(1, int(round((w.end - w.start) * 100)))
                karaoke.append(rf"\k{dur}" + w.word)
            text = "".join(karaoke)
            lines.append(
                f"Dialogue: 0,{_fmt_time(start)},{_fmt_time(end)},"
                f"Default,,0,0,0,,{text}"
            )
        return header + "\n".join(lines) + "\n"

    def _build_srt(self, words: list[WordTiming]) -> str:
        block_size = 7
        out = []
        for i in range(0, len(words), block_size):
            block = words[i:i + block_size]
            start = block[0].start
            end = block[-1].end
            text = " ".join(w.word for w in block)
            out.append(f"{i // block_size + 1}\n"
                       f"{_srt_time(start)} --> {_srt_time(end)}\n"
                       f"{text}\n")
        return "\n".join(out) + ("\n" if out else "")
