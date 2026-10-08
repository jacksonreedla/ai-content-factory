"""Thumbnail generation: video frame + big outlined text (Pillow).

``wrap_text`` and colors are pure/testable; frame extraction uses ffmpeg.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from editor.ffmpeg_render import RenderError, ffmpeg_available

log = logging.getLogger("acf.thumb")

FALLBACK_FONTS = ["arialbd.ttf", "arial.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf"]


class ThumbnailError(RuntimeError):
    pass


def wrap_text(text: str, max_chars_per_line: int = 12,
              max_lines: int = 3) -> list[str]:
    """Greedy word wrap for big thumbnail text."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars_per_line or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    return lines


def extract_frame(video_path: Path, output_path: Path, at_s: float = 1.0) -> Path:
    if not ffmpeg_available():
        raise RenderError("FFmpeg not found - cannot extract thumbnail frame")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-ss", f"{at_s:.2f}", "-i", str(video_path),
           "-frames:v", "1", "-q:v", "2", str(output_path)]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0 or not output_path.exists():
        raise RenderError("Frame extraction failed")
    return output_path


def _load_font(size: int, font_path: str = ""):
    from PIL import ImageFont
    candidates = ([font_path] if font_path else []) + FALLBACK_FONTS
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def generate_thumbnail(frame_path: Path, text: str, output_path: Path, *,
                       font_path: str = "", text_color: str = "#FFFFFF",
                       stroke_color: str = "#000000",
                       darken: float = 0.35) -> Path:
    """Compose the final thumbnail: darkened frame + centered outlined text."""
    try:
        from PIL import Image, ImageDraw, ImageEnhance
    except ImportError as exc:
        raise ThumbnailError(
            "Pillow is not installed. Run: pip install pillow") from exc

    image = Image.open(frame_path).convert("RGB")
    if darken:
        image = ImageEnhance.Brightness(image).enhance(1.0 - darken)

    draw = ImageDraw.Draw(image)
    width, height = image.size
    lines = wrap_text(text.upper())
    if not lines:
        lines = ["..."]

    # Font size scaled to fit the longest line inside ~90% of the width.
    longest = max(len(line) for line in lines)
    font_size = max(40, int(width * 0.9 / max(longest, 1) * 1.6))
    font = _load_font(font_size, font_path)
    stroke = max(2, font_size // 14)

    line_heights = []
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        line_heights.append(box[3] - box[1])
    total = sum(line_heights) + (len(lines) - 1) * int(font_size * 0.2)
    y = (height - total) // 2
    for line, line_height in zip(lines, line_heights):
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        x = (width - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=text_color,
                  stroke_width=stroke, stroke_fill=stroke_color)
        y += line_height + int(font_size * 0.2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=90)
    return output_path
