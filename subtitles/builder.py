"""Caption file builders - pure functions, fully unit-testable.

Word mode  -> .ass (Advanced SubStation) with one styled event per word,
              the classic Shorts look (big bold centered word, pop-in).
Sentence mode -> .srt grouped into readable lines.
"""
from __future__ import annotations

from pathlib import Path

from subtitles.base import CaptionStyle

# Named presets selectable in Settings; values override CaptionStyle fields.
STYLE_PRESETS: dict[str, dict] = {
    # Thick black outline + slight shadow -> the "sticker / bubble" look used
    # by big story channels. This is the default.
    "bubble": {"font_size": 96, "outline": 9, "shadow": 4, "animation": "pop"},
    "bold_center": {},
    "yellow_pop": {"color": "#FFD400", "highlight_color": "#FFFFFF",
                   "outline": 9, "shadow": 4, "animation": "pop"},
    "minimal": {"font_size": 60, "outline": 2, "shadow": 0,
                "animation": "none", "position": "bottom"},
    "top_bar": {"position": "top", "font_size": 64},
    # Multi-word line with the spoken word highlighted + popping. Far less
    # "templated" than a single centered word -> passes originality checks.
    "karaoke": {"font_size": 78, "outline": 8, "shadow": 3,
                "highlight_color": "#39E639", "animation": "karaoke"},
}


def resolve_style(preset: str, base: CaptionStyle | None = None) -> CaptionStyle:
    style = base or CaptionStyle()
    for key, value in STYLE_PRESETS.get(preset, {}).items():
        setattr(style, key, value)
    return style


# ------------------------------------------------------------------ helpers
def _ass_color(hex_color: str) -> str:
    """'#RRGGBB' -> ASS '&H00BBGGRR' (BGR order)."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return "&H00FFFFFF"
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    ms = int(round((seconds % 1) * 1000))
    s = int(seconds)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d},{ms:03d}"


_ALIGN = {"top": 8, "center": 5, "bottom": 2}


# ------------------------------------------------------------ word-mode ASS
def build_word_ass(words: list[dict], style: CaptionStyle, output_path: Path,
                   play_res: tuple[int, int] = (1080, 1920)) -> Path:
    """One dialogue event per word - Shorts-style captions."""
    align = _ALIGN.get(style.position, 5)
    primary = _ass_color(style.color)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res[0]}
PlayResY: {play_res[1]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{style.font},{style.font_size},{primary},{primary},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{align},60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    pop = ""
    if style.animation == "pop":
        pop = r"{\fscx70\fscy70\t(0,90,\fscx105\fscy105)\t(90,160,\fscx100\fscy100)}"

    lines = []
    for i, w in enumerate(words):
        start = w["start"]
        # keep each word on screen until the next starts (no flicker gaps)
        end = words[i + 1]["start"] if i + 1 < len(words) else w["end"]
        end = max(end, w["end"], start + 0.06)
        text = w["word"].upper().replace("{", "").replace("}", "")
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
                     f"Word,,0,0,0,,{pop}{text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return output_path


# --------------------------------------------------- karaoke phrase-highlight
def _ass_header(style: CaptionStyle, play_res: tuple[int, int]) -> str:
    align = _ALIGN.get(style.position, 5)
    primary = _ass_color(style.color)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_res[0]}
PlayResY: {play_res[1]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Word,{style.font},{style.font_size},{primary},{primary},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},{align},60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _phrase_lines(words: list[dict], max_words: int = 3,
                  max_chars: int = 18, max_gap_s: float = 0.6) -> list[list[dict]]:
    """Group words into short on-screen lines (a few words each)."""
    lines: list[list[dict]] = []
    current: list[dict] = []
    for w in words:
        if current:
            gap = w["start"] - current[-1]["end"]
            chars = sum(len(x["word"]) for x in current) + len(current) + len(w["word"])
            if len(current) >= max_words or chars > max_chars or gap > max_gap_s:
                lines.append(current)
                current = []
        current.append(w)
        if w["word"] and w["word"][-1] in ".!?":
            lines.append(current)
            current = []
    if current:
        lines.append(current)
    return lines


def build_karaoke_ass(words: list[dict], style: CaptionStyle, output_path: Path,
                      play_res: tuple[int, int] = (1080, 1920),
                      max_words: int = 3) -> Path:
    """Whole short line stays on screen; the spoken word is highlighted and
    pops. Reads as genuinely edited content rather than the one-word template."""
    highlight = _ass_color(style.highlight_color)
    lines = []
    for group in _phrase_lines(words, max_words=max_words):
        tokens = [w["word"].upper().replace("{", "").replace("}", "") for w in group]
        for j, w in enumerate(group):
            start = w["start"]
            end = group[j + 1]["start"] if j + 1 < len(group) else w["end"]
            end = max(end, w["end"], start + 0.06)
            parts = []
            for k, tok in enumerate(tokens):
                if k == j:
                    parts.append(
                        rf"{{\c{highlight}\fscx100\fscy100"
                        rf"\t(0,90,\fscx118\fscy118)}}{tok}{{\r}}")
                else:
                    parts.append(tok)
            text = " ".join(parts)
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},"
                         f"Word,,0,0,0,,{text}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_ass_header(style, play_res) + "\n".join(lines) + "\n",
                           encoding="utf-8")
    return output_path


# -------------------------------------------------------- sentence-mode SRT
def group_words(words: list[dict], max_chars: int = 42,
                max_gap_s: float = 0.8) -> list[dict]:
    """Group word timings into readable subtitle lines.

    Breaks on sentence punctuation, long pauses, or line length.
    Returns [{text, start, end}, ...].
    """
    groups: list[dict] = []
    current: list[dict] = []

    def flush() -> None:
        if current:
            groups.append({
                "text": " ".join(w["word"] for w in current),
                "start": current[0]["start"],
                "end": current[-1]["end"],
            })
            current.clear()

    for word in words:
        if current:
            gap = word["start"] - current[-1]["end"]
            length = len(" ".join(w["word"] for w in current)) + 1 + len(word["word"])
            if gap > max_gap_s or length > max_chars:
                flush()
        current.append(word)
        if word["word"] and word["word"][-1] in ".!?":
            flush()
    flush()
    return groups


def build_sentence_srt(words: list[dict], output_path: Path,
                       max_chars: int = 42) -> Path:
    groups = group_words(words, max_chars=max_chars)
    blocks = []
    for i, g in enumerate(groups, start=1):
        blocks.append(f"{i}\n{_srt_time(g['start'])} --> {_srt_time(g['end'])}\n"
                      f"{g['text']}\n")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(blocks), encoding="utf-8")
    return output_path
