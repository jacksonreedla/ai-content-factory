"""Agent base class and shared context passed between pipeline stages."""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from api.llm.router import LLMRouter
from app.config import Config
from app.prompt_manager import PromptManager
from database.db import Database


@dataclass
class AgentContext:
    """Mutable bag of state flowing through the pipeline for one job."""

    config: Config
    db: Database
    llm: LLMRouter
    prompts: PromptManager
    data: dict[str, Any] = field(default_factory=dict)
    progress_callback: Callable[[str, float], None] | None = None

    def report(self, stage: str, progress: float) -> None:
        if self.progress_callback:
            self.progress_callback(stage, progress)


@dataclass
class AgentResult:
    ok: bool
    skipped: bool = False
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    duration_s: float = 0.0


class Agent(ABC):
    """One pipeline stage. Subclasses implement ``execute``."""

    name: str = "agent"
    stage: str = ""

    def __init__(self) -> None:
        self.log = logging.getLogger(f"acf.agent.{self.name}")

    def run(self, ctx: AgentContext) -> AgentResult:
        start = time.monotonic()
        self.log.info("--- %s starting", self.name)
        try:
            result = self.execute(ctx)
        except Exception as exc:
            self.log.exception("%s failed", self.name)
            result = AgentResult(ok=False, message=f"{type(exc).__name__}: {exc}")
        result.duration_s = time.monotonic() - start
        level = logging.INFO if result.ok else logging.ERROR
        self.log.log(level, "--- %s finished in %.1fs: %s",
                     self.name, result.duration_s,
                     result.message or ("skipped" if result.skipped else "ok"))
        return result

    @abstractmethod
    def execute(self, ctx: AgentContext) -> AgentResult:
        """Do the work. Raise or return ok=False on failure."""


class StubAgent(Agent):
    """Placeholder for stages that arrive in a later phase.

    Returns skipped=True so the pipeline can run end-to-end today.
    """

    def __init__(self, name: str, stage: str, phase: str) -> None:
        self.name = name
        self.stage = stage
        self.phase = phase
        super().__init__()

    def execute(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(ok=True, skipped=True,
                           message=f"{self.name} arrives in {self.phase} - skipped")
