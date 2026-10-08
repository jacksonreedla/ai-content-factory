"""Multi-account helpers: which accounts exist, and round-robin selection.

Kept dependency-free and pure so the rotation logic is unit-testable without a
database or config object.
"""
from __future__ import annotations

from typing import Any


def account_names(config: Any) -> list[str]:
    """Ordered list of configured account names (skips blanks/malformed)."""
    accounts = config.get("accounts", []) or []
    names: list[str] = []
    for a in accounts:
        if isinstance(a, dict):
            name = (a.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def rotate_account(names: list[str], index: int) -> tuple[str, int]:
    """Round-robin pick: return (account_name, next_index).

    ``index`` is a monotonically increasing counter persisted across runs; the
    chosen account is ``names[index % len(names)]``. With no accounts we return
    ("", index) so callers fall back to their default account and don't advance
    the counter.
    """
    if not names:
        return "", index
    return names[index % len(names)], index + 1
