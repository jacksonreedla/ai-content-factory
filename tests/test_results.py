# tests/test_results.py
import pytest

from core.results import Result, ResultError


def test_ok_carries_value():
    r = Result.ok(42)
    assert r.success
    assert r.value == 42


def test_err_carries_message():
    r = Result.err("boom")
    assert not r.success
    assert r.error == "boom"


def test_unwrap_ok():
    assert Result.ok("x").unwrap() == "x"


def test_unwrap_err_raises():
    with pytest.raises(ResultError):
        Result.err("nope").unwrap()
