# app/container.py
import logging

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

    def shutdown(self) -> None:
        if self.pool:
            self.pool.stop()
        if self.db:
            self.db.close()
