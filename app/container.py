# app/container.py
import logging
from pathlib import Path

from app.config import load_config
from app.paths import AppPaths
from core.enums import NarrationStyle
from infra.db.connection import connect
from infra.db.migrations import migrate
from infra.logging_setup import configure_logging
from pipeline.runner import PipelineRunner
from pipeline.worker_pool import WorkerPool
from plugins.registry import PluginRegistry

log = logging.getLogger(__name__)


class Container:
    """Composition root. Wires infra to domain and starts the worker pool."""

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.config = None
        self.db = None
        self.registry = PluginRegistry()
        self.runner = PipelineRunner()
        self.pool = None
        self._log_handler = None

    def bootstrap(self) -> None:
        self.paths.ensure()
        self._log_handler = configure_logging(self.paths.logs_dir)
        self.config = load_config(self.paths)
        self.db = connect(self.paths.db_path)
        migrate(self.db)
        self.pool = WorkerPool(
            self.paths.db_path, self.runner,
            max_workers=self.config.general.concurrent_jobs,
        )
        self.pool.start()
        self._register_plugins()
        self._register_agents()
        log.info("container bootstrapped (db=%s)", self.paths.db_path)

    def _register_plugins(self) -> None:
        from app.secrets import load_secrets
        from plugins.content.reddit.source import RedditSource
        from plugins.llm.ollama.provider import OllamaProvider
        from plugins.voice.piper.engine import PiperVoiceEngine
        from plugins.captions.ass_styler import ASSStyler
        from plugins.editor.ffmpeg_editor import FFmpegEditor
        from plugins.music.ducker import MusicDucker
        from plugins.registry import PluginInfo

        secrets = load_secrets(self.paths)
        if secrets.reddit_client_id and secrets.reddit_client_secret:
            try:
                src = RedditSource.from_secrets(secrets)
                self.registry.register(PluginInfo(
                    name="reddit", version="0.1", contract="content_source",
                    label="Reddit", instance=src, config={}))
            except Exception as e:
                log.warning("reddit source init failed: %s", e)
        # Ollama always registers; it connects lazily.
        ollama = OllamaProvider(host=self.config.llm.ollama_host,
                                model=self.config.llm.ollama_model)
        self.registry.register(PluginInfo(
            name="ollama", version="0.1", contract="llm_provider",
            label="Ollama", instance=ollama, config={}))
        # Voice / captions / editor / music — always registered (lazy).
        self.registry.register(PluginInfo(
            name="piper", version="0.1", contract="voice_engine",
            label="Piper", instance=PiperVoiceEngine(), config={}))
        caption_tpl = Path(__file__).resolve().parent.parent / "config" / "caption_templates.json"
        self.registry.register(PluginInfo(
            name="ass", version="0.1", contract="caption_styler",
            label="ASS", instance=ASSStyler(templates_path=caption_tpl),
            config={}))
        self.registry.register(PluginInfo(
            name="ffmpeg", version="0.1", contract="video_editor",
            label="FFmpeg", instance=FFmpegEditor(), config={}))
        self.registry.register(PluginInfo(
            name="ducker", version="0.1", contract="music_track",
            label="Ducker", instance=MusicDucker(), config={}))

    def _register_agents(self) -> None:
        from core.enums import JobStage
        from core.models import SourceQuery
        from agents.research_agent import make_research_agent
        from agents.analyzer_agent import make_analyzer_agent
        from agents.rewriter_agent import make_rewriter_agent

        src = self.registry.active("content_source")
        if src is not None:
            q = SourceQuery(
                subreddits=self.config.reddit.subreddits,
                min_score=self.config.reddit.min_score,
                min_comments=self.config.reddit.min_comments,
                max_age_hours=self.config.reddit.max_age_hours,
                sort=self.config.reddit.sort,
                limit=self.config.reddit.limit,
            )
            self.runner.register(JobStage.RESEARCH,
                                 make_research_agent(src, self.db, q))
        llm = self.registry.active("llm_provider")
        if llm is not None:
            self.runner.register(JobStage.ANALYZE,
                make_analyzer_agent(llm, self.db,
                                    min_overall=self.config.scoring.min_overall))
            self.runner.register(JobStage.REWRITE,
                make_rewriter_agent(llm, self.db,
                                    style=NarrationStyle.STORYTELLING))
        # Phase 3 media agents.
        from agents.voice_agent import make_voice_agent
        from agents.subtitle_agent import make_subtitle_agent
        from agents.editor_agent import make_editor_agent
        from plugins.voice.base import VoiceOpts
        voice = self.registry.active("voice_engine")
        if voice is not None:
            opts = VoiceOpts(
                speed=self.config.voice.speed,
                pitch=self.config.voice.pitch,
                volume=self.config.voice.volume,
            )
            self.runner.register(JobStage.VOICE,
                make_voice_agent(voice, self.db, opts, self.paths))
        styler = self.registry.active("caption_styler")
        if styler is not None:
            try:
                from infra.whisper.transcribe import transcribe_words
            except Exception:
                transcribe_words = None  # type: ignore
            if transcribe_words is not None:
                self.runner.register(JobStage.SUBTITLE,
                    make_subtitle_agent(self.db, styler, self.paths,
                                        transcribe_words))
        editor = self.registry.active("video_editor")
        if editor is not None:
            self.runner.register(JobStage.EDIT,
                make_editor_agent(editor, self.db, self.paths,
                                  default_format=self.config.editor.default_format,
                                  background_category=self.config.editor.background_category))

    def shutdown(self) -> None:
        if self.pool:
            self.pool.stop()
        if self.db:
            self.db.close()
