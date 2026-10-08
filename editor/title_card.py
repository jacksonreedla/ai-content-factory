"""Reddit-style title card generator (Pillow).

Produces a transparent PNG of a white rounded "post" card: avatar + username
(+ optional verified check) on top, the post title as the body, and a faux
upvote/comment row at the bottom. The renderer overlays this at the start of a
video and fades it out once the title has been read aloud.

``resolve_account`` is pure/testable; ``generate_title_card`` needs Pillow.
"""
from __future__ import annotations

import hashlib
import math
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("acf.card")

# Colours (RGBA)
CARD_BG = (255, 255, 255, 255)
TEXT_DARK = (26, 26, 27, 255)
META_GRAY = (135, 138, 140, 255)
VERIFIED_BLUE = (29, 155, 240, 255)
HEART_RED = (255, 69, 0, 255)          # reddit orange-red
COMMENT_GRAY = (135, 138, 140, 255)

_FALLBACK_FONTS_BOLD = ["arialbd.ttf", "seguisb.ttf", "DejaVuSans-Bold.ttf",
                        "Arial Bold.ttf"]
_FALLBACK_FONTS_REG = ["arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"]

_AVATAR_COLORS = [
    (255, 69, 0, 255), (0, 121, 211, 255), (0, 168, 107, 255),
    (146, 43, 33, 255), (123, 31, 162, 255), (230, 126, 34, 255),
]


class TitleCardError(RuntimeError):
    pass


# ------------------------------------------------------------- account resolve
def _normalize_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(account.get("name", "") or "reddit_user"),
        "avatar": str(account.get("avatar", "") or ""),
        "verified": bool(account.get("verified", False)),
    }


def resolve_account(config, name: str = "") -> dict[str, Any]:
    """Return the account dict to use for a card.

    Priority: explicit ``name`` -> configured default -> first account -> a
    generic placeholder. Never raises.
    """
    accounts = config.get("accounts", []) or []
    lookup = {a.get("name"): a for a in accounts if isinstance(a, dict)}

    if name and name in lookup:
        return _normalize_account(lookup[name])

    default = config.get("video.title_card.account", "") or ""
    if default and default in lookup:
        return _normalize_account(lookup[default])

    if accounts:
        return _normalize_account(accounts[0])
    return _normalize_account({"name": name})


# ------------------------------------------------------------------ font utils
def _load_font(size: int, *, bold: bool = True, font_path: str = ""):
    from PIL import ImageFont
    candidates = ([font_path] if font_path else [])
    candidates += _FALLBACK_FONTS_BOLD if bold else _FALLBACK_FONTS_REG
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, font, max_width: int, draw) -> list[str]:
    """Greedy pixel-width word wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        width = draw.textlength(candidate, font=font)
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# -------------------------------------------------------------- avatar drawing
def _avatar(size: int, account: dict, font_path: str):
    """Circular avatar image: profile picture if available, else initial."""
    from PIL import Image, ImageDraw

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)

    avatar_path = account.get("avatar", "")
    if avatar_path and Path(avatar_path).exists():
        try:
            src = Image.open(avatar_path).convert("RGBA")
            # center-crop to square then resize
            w, h = src.size
            side = min(w, h)
            src = src.crop(((w - side) // 2, (h - side) // 2,
                            (w - side) // 2 + side, (h - side) // 2 + side))
            src = src.resize((size, size), Image.LANCZOS)
            src.putalpha(mask)
            return src
        except (OSError, ValueError) as exc:
            log.warning("Could not load avatar %s: %s", avatar_path, exc)

    # Fallback: solid colored circle with the first letter.
    name = account.get("name", "?")
    color = _AVATAR_COLORS[int(hashlib.md5(name.encode()).hexdigest(), 16)
                           % len(_AVATAR_COLORS)]
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size - 1, size - 1), fill=color)
    letter = (name.lstrip("uU/").lstrip("_") or name or "?")[0].upper()
    font = _load_font(int(size * 0.55), bold=True, font_path=font_path)
    box = draw.textbbox((0, 0), letter, font=font)
    draw.text(((size - (box[2] - box[0])) / 2 - box[0],
               (size - (box[3] - box[1])) / 2 - box[1]),
              letter, font=font, fill=(255, 255, 255, 255))
    img.putalpha(mask)
    return img


def _draw_verified(draw, x: int, y: int, size: int) -> None:
    """Blue verified badge with a white check."""
    draw.ellipse((x, y, x + size, y + size), fill=VERIFIED_BLUE)
    # white check mark
    w = max(2, size // 8)
    draw.line([(x + size * 0.27, y + size * 0.52),
               (x + size * 0.44, y + size * 0.68),
               (x + size * 0.74, y + size * 0.34)],
              fill=(255, 255, 255, 255), width=w, joint="curve")


def _draw_heart(draw, x: int, y: int, size: int) -> None:
    """A smooth, round heart via the classic heart parametric curve.

    Rendered as a filled many-point polygon so the lower sides curve outward
    to the point (like an emoji heart) instead of straight triangle edges.
    """
    pts = []
    deg = 0
    while deg < 360:
        t = math.radians(deg)
        hx = 16 * math.sin(t) ** 3
        hy = (13 * math.cos(t) - 5 * math.cos(2 * t)
              - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((hx, -hy))          # negate: point ends up at the bottom
        deg += 3
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y)
    sc = size / span
    off_x = x + (size - (max_x - min_x) * sc) / 2 - min_x * sc
    off_y = y + (size - (max_y - min_y) * sc) / 2 - min_y * sc
    draw.polygon([(off_x + px * sc, off_y + py * sc) for px, py in pts],
                 fill=HEART_RED)


def _draw_comment(draw, x: int, y: int, size: int) -> None:
    """Simple speech-bubble outline."""
    w = max(2, size // 10)
    draw.rounded_rectangle((x, y, x + size, y + size * 0.72),
                           radius=size // 5, outline=COMMENT_GRAY, width=w)
    draw.polygon([(x + size * 0.25, y + size * 0.72),
                  (x + size * 0.45, y + size * 0.72),
                  (x + size * 0.22, y + size)], fill=COMMENT_GRAY)


# ------------------------------------------------------------------- main entry
def _compose_card(title: str, account: dict[str, Any], width: int,
                  upvotes: str, comments: str, font_path: str):
    """Draw the white rounded card at ``width`` px; returns an RGBA image."""
    from PIL import Image, ImageDraw

    account = _normalize_account(account)
    pad = int(width * 0.05)
    radius = int(width * 0.03)
    avatar_d = int(width * 0.11)

    name_font = _load_font(int(width * 0.042), bold=True, font_path=font_path)
    title_font = _load_font(int(width * 0.064), bold=True, font_path=font_path)
    meta_font = _load_font(int(width * 0.040), bold=True, font_path=font_path)

    # Measure on a scratch canvas.
    scratch = ImageDraw.Draw(Image.new("RGBA", (width, 10)))
    inner_w = width - 2 * pad
    title_lines = _wrap(title.strip() or "…", title_font, inner_w, scratch)

    line_h = int(title_font.size * 1.28)
    title_block_h = line_h * len(title_lines)
    top_row_h = avatar_d
    meta_h = int(width * 0.07)
    gap1 = int(width * 0.045)   # between header and title
    gap2 = int(width * 0.05)    # between title and meta row
    height = pad + top_row_h + gap1 + title_block_h + gap2 + meta_h + pad

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius,
                           fill=CARD_BG)

    # ---- header: avatar + username (+ verified)
    avatar = _avatar(avatar_d, account, font_path)
    img.paste(avatar, (pad, pad), avatar)
    name_x = pad + avatar_d + int(width * 0.03)
    name_y = pad + (avatar_d - name_font.size) // 2 - int(width * 0.005)
    name = account["name"]
    draw.text((name_x, name_y), name, font=name_font, fill=TEXT_DARK)
    if account["verified"]:
        name_w = draw.textlength(name, font=name_font)
        badge = int(name_font.size * 0.95)
        _draw_verified(draw, int(name_x + name_w + width * 0.015),
                       name_y + int(name_font.size * 0.05), badge)

    # ---- title body
    y = pad + top_row_h + gap1
    for line in title_lines:
        draw.text((pad, y), line, font=title_font, fill=TEXT_DARK)
        y += line_h

    # ---- meta row: heart + count, comment + count
    y = height - pad - meta_h
    icon = int(meta_h * 0.7)
    icon_y = y + (meta_h - icon) // 2
    _draw_heart(draw, pad, icon_y, icon)
    hx = pad + icon + int(width * 0.02)
    draw.text((hx, y + (meta_h - meta_font.size) // 2), upvotes,
              font=meta_font, fill=META_GRAY)
    cx = hx + int(draw.textlength(upvotes, font=meta_font)) + int(width * 0.06)
    _draw_comment(draw, cx, icon_y, icon)
    ccx = cx + icon + int(width * 0.02)
    draw.text((ccx, y + (meta_h - meta_font.size) // 2), comments,
              font=meta_font, fill=META_GRAY)

    return img


def generate_title_card(title: str, account: dict[str, Any], output_path: Path,
                        *, width: int = 972, upvotes: str = "99+",
                        comments: str = "99+", font_path: str = "") -> Path:
    """Compose the card PNG with a soft drop shadow, rendered crisply.

    The card is drawn at 3x resolution and downscaled (anti-aliasing), and a
    blurred drop shadow is fitted *inside* the target ``width`` so the output
    size stays exactly ``width`` px wide.
    """
    try:
        from PIL import Image, ImageFilter
    except ImportError as exc:
        raise TitleCardError(
            "Pillow is not installed. Run: pip install pillow") from exc

    scale = 3
    pad_final = max(8, int(width * 0.05))          # shadow breathing room
    card_hi = _compose_card(title, account, (width - 2 * pad_final) * scale,
                            upvotes, comments, font_path)
    pad_hi = pad_final * scale
    canvas_w = width * scale                         # == card_hi.width + 2*pad_hi
    canvas_h = card_hi.height + 2 * pad_hi

    # Drop shadow: a blurred, offset black silhouette of the card.
    silhouette = Image.new("RGBA", card_hi.size, (0, 0, 0, 0))
    silhouette.paste(Image.new("RGBA", card_hi.size, (0, 0, 0, 165)),
                     (0, 0), card_hi.split()[3])
    shadow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    offset = int(pad_hi * 0.35)
    shadow.paste(silhouette, (pad_hi + offset, pad_hi + int(offset * 1.7)),
                 silhouette)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=pad_hi * 0.5))

    canvas = Image.alpha_composite(
        Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0)), shadow)
    canvas.alpha_composite(card_hi, (pad_hi, pad_hi))

    final = canvas.resize((width, round(canvas_h / scale)), Image.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, "PNG")
    return output_path
