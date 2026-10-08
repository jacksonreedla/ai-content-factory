"""normalize_subreddit: strip r/ prefixes and URLs from user input."""
from __future__ import annotations

import pytest

from api.reddit_client import normalize_subreddit


@pytest.mark.parametrize("raw, expected", [
    ("r/funny", "funny"),
    ("/r/facepalm", "facepalm"),
    ("R/Unexpected", "Unexpected"),
    ("  r/Whatcouldgowrong  ", "Whatcouldgowrong"),
    ("https://www.reddit.com/r/Wellthatsucks/", "Wellthatsucks"),
    ("www.reddit.com/r/instantkarma", "instantkarma"),
    ("old.reddit.com/r/MildlyInfuriating", "MildlyInfuriating"),
    ("MildlyInfuriating", "MildlyInfuriating"),   # already bare
    ("therewasanattempt", "therewasanattempt"),
    ("r/funny,", "funny"),                        # trailing comma
    ("", ""),
    ("   ", ""),
])
def test_normalize_subreddit(raw, expected):
    assert normalize_subreddit(raw) == expected


def test_bare_name_starting_with_r_is_untouched():
    # "russia" starts with 'r' but has no "r/" prefix - must not be stripped.
    assert normalize_subreddit("russia") == "russia"


from api.reddit_client import reddit_rss_url


def test_reddit_rss_url_top_includes_time_filter():
    assert reddit_rss_url("r/funny", "top", "week") == \
        "https://www.reddit.com/r/funny/top.rss?t=week"


def test_reddit_rss_url_hot_has_no_time():
    assert reddit_rss_url("tifu", "hot") == "https://www.reddit.com/r/tifu/.rss"


def test_reddit_rss_url_best_maps_to_hot():
    assert reddit_rss_url("r/AITAH", "best") == \
        "https://www.reddit.com/r/AITAH/.rss"
