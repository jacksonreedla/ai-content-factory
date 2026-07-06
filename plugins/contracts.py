# plugins/contracts.py
from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class ContentSource(Protocol):
    def discover(self, query): ...
    def fetch_full(self, story): ...


@runtime_checkable
class LLMProvider(Protocol):
    def complete(self, prompt: str, **kw) -> str: ...
    def json_complete(self, prompt: str, schema: dict) -> dict: ...


@runtime_checkable
class VoiceEngine(Protocol):
    def synthesize(self, text: str, opts) -> Any: ...


@runtime_checkable
class CaptionStyler(Protocol):
    def render(self, words, style) -> Any: ...


@runtime_checkable
class VideoEditor(Protocol):
    def compose(self, spec) -> Any: ...


@runtime_checkable
class MusicTrack(Protocol): ...


@runtime_checkable
class ThumbnailRenderer(Protocol):
    def render(self, template, lines) -> Any: ...


@runtime_checkable
class SEOGenerator(Protocol):
    def generate(self, video, script) -> Any: ...


@runtime_checkable
class Publisher(Protocol):
    def upload(self, video, seo, privacy) -> Any: ...


@runtime_checkable
class AnalyticsSource(Protocol): ...


CONTRACTS = {
    "content_source": ContentSource,
    "llm_provider": LLMProvider,
    "voice_engine": VoiceEngine,
    "caption_styler": CaptionStyler,
    "video_editor": VideoEditor,
    "music_track": MusicTrack,
    "thumbnail_renderer": ThumbnailRenderer,
    "seo_generator": SEOGenerator,
    "publisher": Publisher,
    "analytics_source": AnalyticsSource,
}
