"""Publish-slot scheduling - pure functions, fully unit-testable.

Users configure daily local-time slots like ["15:00", "19:00"]. Each
scheduled upload takes the next free slot after the previous one, so a
batch of renders spreads across days automatically.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone


def parse_slots(slot_strings: list[str]) -> list[time]:
    """['15:00', '19:30'] -> sorted [time(15,0), time(19,30)]. Bad entries skipped."""
    slots = []
    for raw in slot_strings:
        try:
            hour, minute = raw.strip().split(":")
            slots.append(time(int(hour), int(minute)))
        except (ValueError, AttributeError):
            continue
    return sorted(slots)


def next_publish_time(slot_strings: list[str], after: datetime) -> datetime:
    """First slot strictly after ``after`` (local naive datetimes)."""
    slots = parse_slots(slot_strings) or [time(15, 0)]
    for day_offset in range(0, 370):
        day = (after + timedelta(days=day_offset)).date()
        for slot in slots:
            candidate = datetime.combine(day, slot)
            if candidate > after:
                return candidate
    return after + timedelta(days=1)  # unreachable safety net


def to_rfc3339_utc(local_dt: datetime) -> str:
    """Naive local datetime -> RFC3339 UTC string for the YouTube API."""
    aware = local_dt.astimezone()  # attach the system timezone
    return aware.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
