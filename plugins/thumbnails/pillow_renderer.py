# plugins/thumbnails/pillow_renderer.py
import json
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Lazy import so the test suite doesn't require Pillow at import time.


_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "config" / "thumbnail_templates.json"
_THUMB_W, _THUMB_H = 1280, 720


def _load_template(name: str) -> dict:
    try:
        data = json.loads(_TEMPLATES.read_text(encoding="utf-8"))
        return data.get(name) or data.get("bold_lower") or {}
    except Exception as e:
        log.warning("thumbnail template load failed (%s); using default", e)
        return {"bg_color": "#0e0f13", "accent": "#ff2db7",
                "text_color": "#ffffff", "font_size": 96, "font_bold": True,
                "padding": 60, "accent_bar_height": 16, "two_lines": True}


def _load_font(size: int, bold: bool):
    from PIL import ImageFont
    candidates = (["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]
                  if bold else ["DejaVuSans.ttf"])
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


class PillowThumbnailRenderer:
    """ThumbnailRenderer over Pillow. Renders 1280×720 PNGs with big text."""

    def __init__(self, templates_path: Optional[Path] = None) -> None:
        global _TEMPLATES
        if templates_path:
            _TEMPLATES = Path(templates_path)

    def render(self, template: str, lines, out_path=None,
               bg_path: Optional[str] = None) -> str:
        """Render a thumbnail to `out_path`. Returns the path string.

        `lines` is a tuple/list of (line1, line2); line2 may be empty.
        """
        from PIL import Image, ImageDraw
        tpl = _load_template(template)
        if isinstance(lines, (tuple, list)):
            line1 = lines[0] if len(lines) > 0 else ""
            line2 = lines[1] if len(lines) > 1 else ""
        else:
            line1, line2 = str(lines), ""

        # Background.
        if bg_path and Path(bg_path).exists():
            img = Image.open(bg_path).convert("RGB").resize(
                (_THUMB_W, _THUMB_H), Image.LANCZOS)
            # Darken for text contrast.
            overlay = Image.new("RGB", (_THUMB_W, _THUMB_H),
                                _hex_to_rgb(tpl.get("bg_color", "#0e0f13")))
            img = Image.blend(img, overlay, 0.45)
        else:
            img = Image.new("RGB", (_THUMB_W, _THUMB_H),
                            _hex_to_rgb(tpl.get("bg_color", "#0e0f13")))
        draw = ImageDraw.Draw(img)

        # Accent bar (lower third).
        bar_h = int(tpl.get("accent_bar_height", 16))
        if bar_h > 0:
            draw.rectangle(
                [0, _THUMB_H - bar_h - int(_THUMB_H * 0.28),
                 _THUMB_W, _THUMB_H - int(_THUMB_H * 0.28) + bar_h],
                fill=_hex_to_rgb(tpl.get("accent", "#ff2db7")))

        # Text.
        font = _load_font(int(tpl.get("font_size", 96)),
                          bool(tpl.get("font_bold", True)))
        text_color = _hex_to_rgb(tpl.get("text_color", "#ffffff"))
        # Wrap line1 into at most 2 visual lines if it's long.
        wrapped = _wrap(line1, font, draw, _THUMB_W - 2 * int(tpl.get("padding", 60)))
        all_lines = wrapped + ([line2] if (tpl.get("two_lines", True) and line2) else [])
        # Vertically center the text block.
        line_spacing = 12
        line_h = (font.size if hasattr(font, "size") else 40) + line_spacing
        total_h = len(all_lines) * line_h
        y = (_THUMB_H - total_h) // 2
        pad = int(tpl.get("padding", 60))
        for ln in all_lines:
            w = _text_width(draw, ln, font)
            x = max(pad, (_THUMB_W - w) // 2)
            # Outline for readability.
            for ox, oy in ((-3, 0), (3, 0), (0, -3), (0, 3)):
                draw.text((x + ox, y + oy), ln, fill=(0, 0, 0), font=font)
            draw.text((x, y), ln, fill=text_color, font=font)
            y += line_h

        if out_path:
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            img.save(str(out_path), "PNG")
            return str(out_path)
        # No path: save to a temp.
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".png")
        Path(tmp).parent  # noop; satisfy type
        img.save(tmp, "PNG")
        return tmp


def _wrap(text: str, font, draw, max_w: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if _text_width(draw, trial, font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines[:2]   # cap at 2


def _text_width(draw, text: str, font) -> int:
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]
    except Exception:
        return len(text) * (getattr(font, "size", 40) // 2)
