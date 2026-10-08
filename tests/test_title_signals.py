"""wild_title_score: rates how out-of-pocket a title is (pure heuristic)."""
from __future__ import annotations

from app.title_signals import wild_title_score


def test_examples_score_high():
    assert wild_title_score("I hate my disabled sister") >= 0.8
    assert wild_title_score("Playing the Spanking Game") >= 0.5
    assert wild_title_score("I caught my husband cheating with my mom") >= 0.7


def test_mundane_titles_score_low():
    assert wild_title_score("My trip to the grocery store") < 0.3
    assert wild_title_score("A nice walk in the park") < 0.2
    assert wild_title_score("My favourite cake recipe") < 0.2


def test_wild_beats_mundane():
    wild = wild_title_score("I hate my disabled sister")
    mild = wild_title_score("My trip to the grocery store")
    assert wild > mild


def test_bounded_0_to_1():
    for t in ["", "hate kill revenge cheating affair caught my sister disabled",
              "just a normal day"]:
        s = wild_title_score(t)
        assert 0.0 <= s <= 1.0


def test_empty_is_zero():
    assert wild_title_score("") == 0.0
