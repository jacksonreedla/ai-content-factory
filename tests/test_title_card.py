"""Title-card generation, account resolution, and render-overlay tests."""
from pathlib import Path

import copy

from app.config import Config, DEFAULTS
from editor.ffmpeg_render import build_render_command
from editor.spec import RenderSpec, VideoFormat
from editor.title_card import generate_title_card, resolve_account


def _cfg(**overrides) -> Config:
    c = Config(copy.deepcopy(DEFAULTS))
    for path, value in overrides.items():
        c.set(path.replace("__", "."), value, persist=False)
    return c


def make_spec(tmp_path: Path, **overrides) -> RenderSpec:
    defaults = dict(
        audio_path=tmp_path / "voice.wav",
        background_path=tmp_path / "bg.mp4",
        output_path=tmp_path / "out.mp4",
        format=VideoFormat.SHORTS,
    )
    defaults.update(overrides)
    return RenderSpec(**defaults)


# ------------------------------------------------------------- resolve_account
def test_resolve_account_uses_first_by_default():
    c = _cfg(accounts=[{"name": "a", "verified": True},
                       {"name": "b", "verified": False}])
    assert resolve_account(c)["name"] == "a"


def test_resolve_account_explicit_name_wins():
    c = _cfg(accounts=[{"name": "a"}, {"name": "b"}])
    acct = resolve_account(c, "b")
    assert acct["name"] == "b"


def test_resolve_account_configured_default():
    c = _cfg(accounts=[{"name": "a"}, {"name": "b"}],
             video__title_card__account="b")
    assert resolve_account(c)["name"] == "b"


def test_resolve_account_placeholder_when_empty():
    c = _cfg(accounts=[])
    acct = resolve_account(c, "ghost")
    assert acct["name"] == "ghost" and acct["verified"] is False


# ------------------------------------------------------------- card generation
def test_generate_title_card_creates_png(tmp_path):
    from PIL import Image
    out = generate_title_card(
        "A dramatic reddit story title that wraps onto several lines here",
        {"name": "redditstories_doggo", "avatar": "", "verified": True},
        tmp_path / "card.png", width=800)
    assert out.exists()
    img = Image.open(out)
    assert img.mode == "RGBA"
    assert img.size[0] == 800


# ------------------------------------------------------------- render overlay
def test_render_overlay_present_with_card(tmp_path):
    spec = make_spec(tmp_path, title_card_path=tmp_path / "card.png",
                     intro_seconds=3.2, card_fade_seconds=0.5)
    joined = " ".join(build_render_command(spec, 61.0))
    assert "-loop 1 -i" in joined                       # card image input
    assert "overlay=x=(W-w)/2" in joined
    assert "fade=t=in" not in joined          # card is visible instantly
    assert "fade=t=out:st=3.20:d=0.50:alpha=1" in joined
    assert "enable='lte(t,3.70)'" in joined


def test_render_card_index_after_music(tmp_path):
    spec = make_spec(tmp_path, music_path=tmp_path / "m.mp3",
                     title_card_path=tmp_path / "card.png", intro_seconds=2.0)
    joined = " ".join(build_render_command(spec, 60))
    assert "[2:a]" in joined            # music stays input 2
    assert "[3:v]format=rgba" in joined  # card is input 3


def test_render_no_card_when_intro_zero(tmp_path):
    spec = make_spec(tmp_path, title_card_path=tmp_path / "card.png",
                     intro_seconds=0.0)
    joined = " ".join(build_render_command(spec, 60))
    assert "overlay" not in joined
    assert "[0:v]" in joined


def test_render_plain_when_no_card(tmp_path):
    joined = " ".join(build_render_command(make_spec(tmp_path), 60))
    assert "overlay" not in joined and "rgba" not in joined
