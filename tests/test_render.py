"""FFmpeg command builder + media library tests (no ffmpeg needed)."""
from pathlib import Path

import pytest

from editor.ffmpeg_render import build_render_command, escape_filter_path
from editor.media_library import (MediaLibraryError, list_clips, pick_clip,
                                  pick_music)
from editor.spec import RenderSpec, VideoFormat


def make_spec(tmp_path: Path, **overrides) -> RenderSpec:
    defaults = dict(
        audio_path=tmp_path / "voice.wav",
        background_path=tmp_path / "bg.mp4",
        output_path=tmp_path / "out.mp4",
        format=VideoFormat.SHORTS,
    )
    defaults.update(overrides)
    return RenderSpec(**defaults)


def test_basic_command_structure(tmp_path):
    cmd = build_render_command(make_spec(tmp_path), duration_s=61.5)
    assert cmd[0] == "ffmpeg"
    assert "-stream_loop" in cmd
    joined = " ".join(cmd)
    assert "scale=1080:1920" in joined
    assert "crop=1080:1920" in joined
    assert "-t 61.50" in joined
    assert "[1:a]anull[aout]" in joined       # no music -> plain voice
    assert "libx264" in cmd


def test_landscape_resolution(tmp_path):
    cmd = build_render_command(
        make_spec(tmp_path, format=VideoFormat.LANDSCAPE), duration_s=60)
    assert "scale=1920:1080" in " ".join(cmd)


def test_captions_burned_in(tmp_path):
    spec = make_spec(tmp_path, captions_path=tmp_path / "caps.ass")
    joined = " ".join(build_render_command(spec, 60))
    assert "ass=" in joined


def test_music_ducking_chain(tmp_path):
    spec = make_spec(tmp_path, music_path=tmp_path / "music.mp3",
                     music_volume_db=-20.0)
    joined = " ".join(build_render_command(spec, 60))
    assert "volume=-20.0dB" in joined
    assert "sidechaincompress" in joined
    assert "amix=inputs=2" in joined


def test_music_no_duck(tmp_path):
    spec = make_spec(tmp_path, music_path=tmp_path / "m.mp3", duck_music=False)
    joined = " ".join(build_render_command(spec, 60))
    assert "sidechaincompress" not in joined
    assert "amix" in joined


def test_effects(tmp_path):
    spec = make_spec(tmp_path,
                     background_effects={"blur": True, "speed": 1.5,
                                         "brightness": -0.1})
    joined = " ".join(build_render_command(spec, 60))
    assert "boxblur=8" in joined
    assert "setpts=PTS/1.500" in joined
    assert "eq=brightness=-0.10" in joined


def test_escape_filter_path_windows():
    escaped = escape_filter_path(Path(r"C:\data\caps.ass"))
    assert escaped == "C\\:/data/caps.ass"


# ------------------------------------------------------------- media library
def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


def test_list_clips_filters_extensions(tmp_path):
    _touch(tmp_path / "minecraft" / "a.mp4")
    _touch(tmp_path / "minecraft" / "b.webm")
    _touch(tmp_path / "minecraft" / "notes.txt")
    clips = list_clips("minecraft", root=tmp_path)
    assert [c.name for c in clips] == ["a.mp4", "b.webm"]


def test_pick_clip_random(tmp_path):
    _touch(tmp_path / "gta" / "a.mp4")
    _touch(tmp_path / "gta" / "b.mp4")
    picks = {pick_clip("gta", "random", root=tmp_path).name for _ in range(30)}
    assert picks <= {"a.mp4", "b.mp4"} and picks


def test_pick_clip_sequential_cycles(tmp_path):
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        _touch(tmp_path / "rain" / name)
    state: dict[str, str] = {}
    order = [pick_clip("rain", "sequential", state.get, state.__setitem__,
                       root=tmp_path).name for _ in range(6)]
    assert order == ["a.mp4", "b.mp4", "c.mp4", "a.mp4", "b.mp4", "c.mp4"]


def test_pick_clip_empty_raises(tmp_path):
    with pytest.raises(MediaLibraryError):
        pick_clip("nothing_here", root=tmp_path)


def test_pick_music(tmp_path):
    assert pick_music(tmp_path / "missing") is None
    _touch(tmp_path / "music" / "track.mp3")
    assert pick_music(tmp_path / "music").name == "track.mp3"
