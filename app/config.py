# app/config.py
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from app.paths import AppPaths


@dataclass
class GeneralConfig:
    theme: str = "dark"
    concurrent_jobs: int = 1


@dataclass
class ScoringConfig:
    min_overall: float = 70


@dataclass
class RedditConfig:
    subreddits: list = field(default_factory=lambda: ["AskReddit", "tifu", "nosleep"])
    min_score: int = 1000
    min_comments: int = 50
    max_age_hours: int = 168
    sort: str = "hot"
    limit: int = 25


@dataclass
class LLMConfig:
    active_provider: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"


@dataclass
class VoiceConfig:
    active_engine: str = "piper"
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0


@dataclass
class EditorConfig:
    default_format: str = "shorts_vertical_9_16"
    background_category: str = "minecraft_parkour"


@dataclass
class PublishingConfig:
    default_privacy: str = "draft"


@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    editor: EditorConfig = field(default_factory=EditorConfig)
    publishing: PublishingConfig = field(default_factory=PublishingConfig)


_SHIPPED_DEFAULTS = Path(__file__).resolve().parent.parent / "config" / "default_settings.json"


def _build(data: dict) -> Config:
    cfg = Config()
    cfg.general = GeneralConfig(**data.get("general", {}))
    cfg.scoring = ScoringConfig(**data.get("scoring", {}))
    cfg.reddit = RedditConfig(**data.get("reddit", {}))
    cfg.llm = LLMConfig(**data.get("llm", {}))
    cfg.voice = VoiceConfig(**data.get("voice", {}))
    cfg.editor = EditorConfig(**data.get("editor", {}))
    cfg.publishing = PublishingConfig(**data.get("publishing", {}))
    return cfg


def load_config(paths: Optional[AppPaths] = None) -> Config:
    paths = paths or AppPaths()
    with _SHIPPED_DEFAULTS.open() as f:
        data = json.load(f)
    if paths.settings_path.exists():
        with paths.settings_path.open() as f:
            user = json.load(f)
        for section, vals in user.items():
            if isinstance(vals, dict) and section in data:
                data[section].update(vals)
    return _build(data)


def save_config(cfg: Config, paths: Optional[AppPaths] = None) -> None:
    paths = paths or AppPaths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    save_dict = asdict(cfg)
    with paths.settings_path.open("w") as f:
        json.dump(save_dict, f, indent=2)
