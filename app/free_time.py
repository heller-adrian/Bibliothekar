from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable


class FreeTimeError(ValueError):
    pass


def _second(value: Any, field_name: str) -> datetime:
    raw = str(value or "").strip()
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise FreeTimeError(f"{field_name} ist ungültig: {raw or '—'}.") from exc


def free_ranges(
    start_datetime: str,
    end_datetime: str,
    occupied_ranges: Iterable[tuple[str, str]],
) -> list[dict[str, str]]:
    """Return the unoccupied pieces inside one closed datetime interval.

    Bibliothekar uses second precision and inclusive event boundaries.  Occupied
    ranges are therefore subtracted with a one-second step so adjacent events do
    not create artificial free gaps.
    """
    start = _second(start_datetime, "Beginn")
    end = _second(end_datetime, "Ende")
    if end < start:
        raise FreeTimeError("Das Ende liegt vor dem Beginn.")

    clipped: list[tuple[datetime, datetime]] = []
    for raw_start, raw_end in occupied_ranges:
        occ_start = _second(raw_start, "Belegter Beginn")
        occ_end = _second(raw_end, "Belegtes Ende")
        if occ_end < occ_start:
            raise FreeTimeError("Ein belegter Zeitraum besitzt ein Ende vor dem Beginn.")
        if occ_end < start or occ_start > end:
            continue
        clipped.append((max(start, occ_start), min(end, occ_end)))

    clipped.sort(key=lambda item: (item[0], item[1]))
    merged: list[list[datetime]] = []
    for occ_start, occ_end in clipped:
        if not merged or occ_start > merged[-1][1] + timedelta(seconds=1):
            merged.append([occ_start, occ_end])
        else:
            merged[-1][1] = max(merged[-1][1], occ_end)

    result: list[dict[str, str]] = []
    cursor = start
    for occ_start, occ_end in merged:
        if cursor < occ_start:
            free_end = occ_start - timedelta(seconds=1)
            if cursor <= free_end:
                result.append(_range_dict(cursor, free_end))
        cursor = max(cursor, occ_end + timedelta(seconds=1))
        if cursor > end:
            break

    if cursor <= end:
        result.append(_range_dict(cursor, end))
    return result


def free_ranges_for_day(
    day_key: str,
    occupied_ranges: Iterable[tuple[str, str]],
) -> list[dict[str, str]]:
    """Return the exact free time pieces of one calendar day."""
    day = str(day_key or "").strip()
    try:
        datetime.strptime(day, "%Y-%m-%d")
    except ValueError as exc:
        raise FreeTimeError(f"Tag ist ungültig: {day or '—'}.") from exc
    return free_ranges(
        f"{day}T00:00:00",
        f"{day}T23:59:59",
        occupied_ranges,
    )


def _range_dict(start: datetime, end: datetime) -> dict[str, str]:
    start_iso = start.isoformat(timespec="seconds")
    end_iso = end.isoformat(timespec="seconds")
    return {
        "day_key": start_iso[:10],
        "start_time": start_iso[11:16],
        "end_time": end_iso[11:16],
        "start_datetime": start_iso,
        "end_datetime": end_iso,
    }
