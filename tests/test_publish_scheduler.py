"""Publish-slot scheduling tests (pure functions)."""
from datetime import datetime, time

from scheduler.publish_scheduler import (next_publish_time, parse_slots,
                                         to_rfc3339_utc)


def test_parse_slots():
    assert parse_slots(["19:30", "15:00"]) == [time(15, 0), time(19, 30)]
    assert parse_slots(["bad", "25:99", ""]) == []
    assert parse_slots(["07:05"]) == [time(7, 5)]


def test_next_slot_same_day():
    after = datetime(2026, 7, 4, 10, 0)
    result = next_publish_time(["15:00", "19:00"], after)
    assert result == datetime(2026, 7, 4, 15, 0)


def test_next_slot_second_of_day():
    after = datetime(2026, 7, 4, 16, 0)
    result = next_publish_time(["15:00", "19:00"], after)
    assert result == datetime(2026, 7, 4, 19, 0)


def test_next_slot_rolls_to_next_day():
    after = datetime(2026, 7, 4, 20, 0)
    result = next_publish_time(["15:00", "19:00"], after)
    assert result == datetime(2026, 7, 5, 15, 0)


def test_exact_slot_time_moves_forward():
    after = datetime(2026, 7, 4, 15, 0)
    result = next_publish_time(["15:00"], after)
    assert result == datetime(2026, 7, 5, 15, 0)   # strictly after


def test_empty_slots_default():
    after = datetime(2026, 7, 4, 10, 0)
    assert next_publish_time([], after) == datetime(2026, 7, 4, 15, 0)


def test_chained_slots_spread_across_days():
    slots = ["15:00", "19:00"]
    current = datetime(2026, 7, 4, 12, 0)
    picks = []
    for _ in range(4):
        current = next_publish_time(slots, current)
        picks.append(current)
    assert picks == [
        datetime(2026, 7, 4, 15, 0), datetime(2026, 7, 4, 19, 0),
        datetime(2026, 7, 5, 15, 0), datetime(2026, 7, 5, 19, 0),
    ]


def test_rfc3339_format():
    result = to_rfc3339_utc(datetime(2026, 7, 4, 15, 0))
    assert result.endswith("Z")
    assert "T" in result
    assert len(result) == 20
