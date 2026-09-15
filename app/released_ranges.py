from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from app.free_time import free_ranges


def subtract_intervals(
    old_intervals: Iterable[tuple[str, str]],
    new_intervals: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Return exact pieces that belonged to old intervals but no longer to new ones."""
    new_values = [(str(a)[:19], str(b)[:19]) for a, b in new_intervals]
    released: list[tuple[str, str]] = []
    for old_start, old_end in old_intervals:
        for item in free_ranges(str(old_start)[:19], str(old_end)[:19], new_values):
            released.append((item["start_datetime"], item["end_datetime"]))
    return merge_intervals(released)


def split_intervals_by_day(intervals: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for raw_start, raw_end in intervals:
        start = datetime.fromisoformat(str(raw_start)[:19])
        end = datetime.fromisoformat(str(raw_end)[:19])
        cursor = start
        while cursor.date() < end.date():
            day_end = cursor.replace(hour=23, minute=59, second=59)
            result.append((cursor.isoformat(timespec="seconds"), day_end.isoformat(timespec="seconds")))
            cursor = day_end + timedelta(seconds=1)
        result.append((cursor.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")))
    return result


def merge_intervals(intervals: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    values = sorted((datetime.fromisoformat(str(a)[:19]), datetime.fromisoformat(str(b)[:19])) for a, b in intervals)
    merged: list[list[datetime]] = []
    for start, end in values:
        if not merged or start > merged[-1][1] + timedelta(seconds=1):
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(a.isoformat(timespec="seconds"), b.isoformat(timespec="seconds")) for a, b in merged]


def range_for_capture(capture_time: str, ranges: Iterable[tuple[str, str]]) -> tuple[str, str] | None:
    capture = str(capture_time or "")[:19]
    matches = [(a, b) for a, b in ranges if a <= capture <= b]
    if len(matches) == 1:
        return matches[0]
    return None
