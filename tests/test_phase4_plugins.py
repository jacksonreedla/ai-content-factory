# tests/test_phase4_plugins.py
"""Thumbnail renderer, SEO generator, and publisher (with fake client)."""
import json
import shutil

from plugins.thumbnails.pillow_renderer import PillowThumbnailRenderer
from plugins.seo.llm_seo import LLMSEOGenerator, SEOResult
from plugins.publishing.youtube.publisher import YouTubePublisher, PublishResult


def test_thumbnail_renders_png(tmp_path):
    r = PillowThumbnailRenderer()
    out = tmp_path / "thumb.png"
    path = r.render("bold_lower", ("BIG TITLE", "second line"), out_path=str(out))
    assert out.exists()
    from PIL import Image
    img = Image.open(out)
    assert img.size == (1280, 720)


def test_thumbnail_handles_missing_template(tmp_path):
    r = PillowThumbnailRenderer()
    out = tmp_path / "t.png"
    path = r.render("nonexistent_template", ("HI",), out_path=str(out))
    assert out.exists()


def test_seo_generator_uses_llm():
    class FakeLLM:
        def json_complete(self, prompt, schema, **kw):
            return {"title": "T", "description": "D", "tags": ["a", "b"],
                    "hashtags": ["#x"], "pinned_comment": "pc",
                    "community_post": "cp", "ctr_score": 75, "seo_score": 80}
    gen = LLMSEOGenerator()
    class V: pass
    v = V(); v.llm = FakeLLM()
    result = gen.generate(v, "the script text")
    assert result.title == "T"
    assert result.tags == ["a", "b"]
    assert result.ctr_score == 75


class FakeChunk:
    def __init__(self, succeed_on=1):
        self.calls = 0
        self.succeed_on = succeed_on
    def next_chunk(self):
        self.calls += 1
        if self.calls < self.succeed_on:
            raise Exception("transient")
        return None, {"id": "yt123", "snippet": {"title": "T"}}


class FakeVideos:
    def __init__(self, succeed_on=1):
        self._chunk = FakeChunk(succeed_on)
    def insert(self, **kw):
        return self._chunk


class FakeYT:
    def __init__(self, succeed_on=1):
        self._v = FakeVideos(succeed_on)
    def videos(self):
        return self._v


def test_publisher_succeeds_first_try(tmp_path):
    # Patch MediaFileUpload import inside publisher.upload via monkey.
    import sys, types
    fake_http = types.ModuleType("googleapiclient.http")
    fake_http.MediaFileUpload = lambda *a, **k: object()
    sys.modules["googleapiclient.http"] = fake_http
    try:
        p = YouTubePublisher(client=FakeYT(succeed_on=1), backoff_base=0.01)
        video = str(tmp_path / "v.mp4")
        result = p.upload(video, {"title": "T"}, privacy="private")
        assert result.status == "done"
        assert result.remote_id == "yt123"
    finally:
        del sys.modules["googleapiclient.http"]


def test_publisher_retries_then_succeeds(tmp_path):
    import sys, types
    fake_http = types.ModuleType("googleapiclient.http")
    fake_http.MediaFileUpload = lambda *a, **k: object()
    sys.modules["googleapiclient.http"] = fake_http
    try:
        p = YouTubePublisher(client=FakeYT(succeed_on=3), max_retries=5,
                             backoff_base=0.01)
        result = p.upload(str(tmp_path / "v.mp4"), {"title": "T"}, "private")
        assert result.status == "done"
    finally:
        del sys.modules["googleapiclient.http"]


def test_publisher_fails_after_max_retries(tmp_path):
    import sys, types
    fake_http = types.ModuleType("googleapiclient.http")
    fake_http.MediaFileUpload = lambda *a, **k: object()
    sys.modules["googleapiclient.http"] = fake_http
    try:
        # Always fails.
        class AlwaysFailChunk:
            def next_chunk(self): raise Exception("permanent")
        class V:
            def insert(self, **k): return AlwaysFailChunk()
        class Y:
            def videos(self): return V()
        p = YouTubePublisher(client=Y(), max_retries=2, backoff_base=0.01)
        result = p.upload(str(tmp_path / "v.mp4"), {"title": "T"}, "private")
        assert result.status == "failed"
    finally:
        del sys.modules["googleapiclient.http"]
