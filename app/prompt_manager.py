"""Loads editable AI prompt templates from the ``prompts/`` folder.

Users customise AI behaviour by editing the .txt files - no code changes.
Templates use ``{placeholder}`` substitution.
"""
from __future__ import annotations

import logging
import string
from pathlib import Path

from app.paths import PROMPTS_DIR

log = logging.getLogger("acf.prompts")


class PromptError(RuntimeError):
    pass


class _SafeFormatter(string.Formatter):
    """Leaves unknown placeholders intact instead of raising."""

    def get_value(self, key, args, kwargs):  # type: ignore[override]
        if isinstance(key, str) and key not in kwargs:
            return "{" + key + "}"
        return super().get_value(key, args, kwargs)


_formatter = _SafeFormatter()


class PromptManager:
    def __init__(self, prompts_dir: Path = PROMPTS_DIR):
        self.prompts_dir = prompts_dir

    def list_templates(self) -> list[str]:
        return sorted(p.stem for p in self.prompts_dir.glob("*.txt"))

    def raw(self, name: str) -> str:
        path = self.prompts_dir / f"{name}.txt"
        if not path.exists():
            raise PromptError(
                f"Prompt template '{name}' not found at {path}. "
                f"Available: {', '.join(self.list_templates()) or 'none'}"
            )
        return path.read_text(encoding="utf-8")

    def render(self, name: str, **kwargs: object) -> str:
        return _formatter.format(self.raw(name), **kwargs)
