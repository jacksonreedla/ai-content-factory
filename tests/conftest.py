"""Shared test fixtures. Run from the project root: python -m pytest tests"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import DEFAULTS, Config          # noqa: E402
from database.db import Database                 # noqa: E402


@pytest.fixture()
def db() -> Database:
    return Database.in_memory()


@pytest.fixture()
def config() -> Config:
    """In-memory config that never writes to disk."""
    cfg = Config.__new__(Config)
    import copy
    import threading
    cfg._data = copy.deepcopy(DEFAULTS)
    cfg._lock = threading.RLock()
    cfg.save = lambda: None  # type: ignore[method-assign]
    return cfg
