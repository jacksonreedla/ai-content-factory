"""Plugin contracts + discovery.

A plugin is a subfolder of ``plugins/`` containing ``plugin.py`` which
defines a ``Plugin`` class inheriting from :class:`FactoryPlugin`.
"""
from __future__ import annotations

import importlib.util
import logging
from abc import ABC
from pathlib import Path
from typing import Any

from app.paths import PLUGINS_DIR

log = logging.getLogger("acf.plugins")


class FactoryPlugin(ABC):
    """Base for all plugins. Override whichever hooks apply."""

    name: str = "unnamed"
    version: str = "0.1"

    def content_sources(self) -> dict[str, Any]:
        """Return {source_name: fetch_callable} for new content sources."""
        return {}

    def llm_providers(self) -> dict[str, Any]:
        """Return {provider_name: LLMProvider instance}."""
        return {}

    def publishers(self) -> dict[str, Any]:
        """Return {platform_name: publisher} (TikTok, Instagram, ...)."""
        return {}


def discover_plugins() -> list[FactoryPlugin]:
    """Import every plugins/<name>/plugin.py and instantiate its Plugin class."""
    found: list[FactoryPlugin] = []
    if not PLUGINS_DIR.exists():
        return found
    for entry in sorted(PLUGINS_DIR.iterdir()):
        plugin_file = entry / "plugin.py"
        if not (entry.is_dir() and plugin_file.exists()):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"acf_plugin_{entry.name}", plugin_file)
            module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
            spec.loader.exec_module(module)                 # type: ignore[union-attr]
            plugin_cls = getattr(module, "Plugin", None)
            if plugin_cls and issubclass(plugin_cls, FactoryPlugin):
                found.append(plugin_cls())
                log.info("Loaded plugin '%s'", entry.name)
            else:
                log.warning("plugins/%s/plugin.py has no Plugin(FactoryPlugin) class",
                            entry.name)
        except Exception:
            log.exception("Failed to load plugin '%s'", entry.name)
    return found
