"""Round-robin account rotation for multi-account posting."""
from __future__ import annotations

from app.accounts import account_names, rotate_account


class _Cfg:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


def test_account_names_skips_blanks_and_malformed():
    cfg = _Cfg({"accounts": [
        {"name": "a"}, {"name": ""}, {"nope": 1}, "x", {"name": "  b  "},
    ]})
    assert account_names(cfg) == ["a", "b"]


def test_rotate_cycles_in_order():
    names = ["a", "b", "c"]
    idx = 0
    picks = []
    for _ in range(7):
        name, idx = rotate_account(names, idx)
        picks.append(name)
    assert picks == ["a", "b", "c", "a", "b", "c", "a"]
    assert idx == 7


def test_rotate_resumes_from_persisted_index():
    # Simulates a fresh run continuing the cycle from where the last one left.
    names = ["a", "b", "c"]
    name, idx = rotate_account(names, 5)      # 5 % 3 == 2 -> "c"
    assert name == "c" and idx == 6


def test_rotate_no_accounts_returns_blank_and_holds_index():
    name, idx = rotate_account([], 4)
    assert name == "" and idx == 4


def test_rotate_single_account_always_same():
    names = ["solo"]
    n1, i1 = rotate_account(names, 0)
    n2, i2 = rotate_account(names, i1)
    assert n1 == n2 == "solo" and i2 == 2
