# Plugin Authoring Guide

AI Content Factory is built around **plugin contracts**. Reddit, YouTube,
Ollama, Piper, etc. are all just the *first* implementations of these
contracts — you can add new content sources, LLMs, voices, publishers, and
more without touching core.

## The contracts

All contracts are `Protocol` classes in `plugins/contracts.py`:

| Contract | Built-in | What it does |
|----------|----------|--------------|
| `ContentSource` | Reddit | `discover(query) -> [Story]`, `fetch_full(story)` |
| `LLMProvider` | Ollama | `complete(prompt)`, `json_complete(prompt, schema)` |
| `VoiceEngine` | Piper | `synthesize(text, opts) -> AudioClip` |
| `CaptionStyler` | ASS | `render(words, style) -> SubtitleArtifacts` |
| `VideoEditor` | FFmpeg | `compose(spec) -> VideoFile` |
| `MusicTrack` | Ducker | loop/fade/duck helpers |
| `ThumbnailRenderer` | Pillow | `render(template, lines) -> PNG path` |
| `SEOGenerator` | LLM | `generate(video, script) -> SEOResult` |
| `Publisher` | YouTube | `upload(video, seo, privacy) -> PublishResult` |
| `AnalyticsSource` | YouTube | `fetch(publish) -> AnalyticsPoint` |

## Writing a plugin

A plugin is a folder with a `plugin.toml` manifest + an implementation:

```
my_plugin/
  plugin.toml
  __init__.py
  source.py
```

### `plugin.toml`

```toml
name = "news-api"
version = "0.1.0"
contract = "content_source"   # must match a contract key
label = "NewsAPI"             # unique within this contract
module = "source"             # import path within the plugin folder
class = "NewsSource"          # the class to instantiate
```

### `source.py`

Implement the contract's methods:

```python
from core.models import SourceQuery, Story

class NewsSource:
    def discover(self, query: SourceQuery) -> list[Story]:
        # ... fetch from your API ...
        return [Story(source="news", source_id=..., ...)]

    def fetch_full(self, story: Story) -> Story:
        return story
```

### Install it

Copy your plugin folder into `~/.aicf/plugins/`. On next launch the registry
discovers it, validates it satisfies the declared contract, and registers it.
Pick it as the active source in **Settings → Content Sources**.

## Registration details

The registry (`plugins/registry.py`):

1. Scans `plugins/` (built-ins) and `~/.aicf/plugins/` (user) on startup.
2. For each `plugin.toml`, duck-types the instance against the contract
   `Protocol` — if it doesn't satisfy, the plugin is disabled (logged, no crash).
3. Duplicate labels under the same contract → the later one is disabled.

This is why Reddit isn't special-cased anywhere in core: it's registered
through the same path your plugin uses.

## Testing your plugin

Mirror the built-in tests (`tests/test_reddit_source.py` etc.): instantiate
your plugin with a fake transport/client, call the contract methods, and
assert on the return types. No network in unit tests.
