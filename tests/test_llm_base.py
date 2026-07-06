# tests/test_llm_base.py
import pytest

from plugins.llm.base import extract_json


def test_extract_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json():
    s = "Here:\n```json\n{\"a\": 2}\n```\nDone."
    assert extract_json(s) == {"a": 2}


def test_extract_with_prose():
    assert extract_json('Sure! {"x": "y"} ok') == {"x": "y"}


def test_extract_invalid_raises():
    with pytest.raises(Exception):
        extract_json("no json at all")
