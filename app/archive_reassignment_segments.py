from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping
import json

from app.free_time import free_ranges


class ArchiveSegmentError(ValueError):
    pass


def _json_list(value: Any) -> list[dict[str, Any]]:
    if not value:
        return []
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [dict(item) for item in parsed if isinstance(item, Mapping)] if isinstance(parsed, list) else []


def _iso(day: str, hm: str, *, end: bool = False) -> str:
    suffix = ":59" if end else ":00"
    return f"{day}T{hm}{suffix}"


def proposed_ranges(change_request: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Return exact SOLL coverage stored in an open archive change request."""
    if change_request.get("delete_event"):
        return []
    kind = str(change_request.get("event_kind") or "event")
    start_day = str(change_request.get("start_date") or "")[:10]
    end_day = str(change_request.get("end_date") or start_day)[:10]

    if kind == "no_event":
        result: list[tuple[str, str]] = []
        for segment in _json_list(change_request.get("no_event_segments")):
            day = str(segment.get("day_key") or segment.get("date") or "")[:10]
            start = str(segment.get("start_time") or "00:00")[:5]
            end = str(segment.get("end_time") or "23:59")[:5]
            if day:
                result.append((_iso(day, start), _iso(day, end, end=True)))
        if result:
            return sorted(result)

    children = _json_list(change_request.get("child_segments_json"))
    if children and int(change_request.get('time_model_version',1)) < 2:
        result = []
        for segment in children:
            start = str(segment.get("start_time") or "")[:5]
            end = str(segment.get("end_time") or "")[:5]
            if start and end and start_day and end_day:
                result.append((_iso(start_day, start), _iso(end_day, end, end=True)))
        if result:
            return sorted(result)

    if not start_day or not end_day:
        return []
    if bool(change_request.get("uses_time_range")):
        start = str(change_request.get("start_time") or "00:00")[:5]
        end = str(change_request.get("end_time") or "23:59")[:5]
        return [(_iso(start_day, start), _iso(end_day, end, end=True))]
    return [(f"{start_day}T00:00:00", f"{end_day}T23:59:59")]


def _source_range(connection, change_request: Mapping[str, Any], family_id: int, capture: str) -> tuple[str, str]:
    event_id = str(change_request["event_id"])
    root = connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if root is None:
        raise ArchiveSegmentError("Das archivierte Quellereignis wurde nicht gefunden.")

    if str(root["event_kind"]) == "no_event":
        row = connection.execute(
            """SELECT start_datetime,end_datetime FROM event_time_segments
               WHERE event_id=? AND start_datetime<=? AND end_datetime>=?
               ORDER BY start_datetime,end_datetime LIMIT 1""",
            (event_id, capture, capture),
        ).fetchone()
        if row is not None:
            return str(row["start_datetime"]), str(row["end_datetime"])

    if str(root['event_kind']) == 'event' and int(dict(root).get('time_model_version',1)) >= 2:
        return str(root['start_datetime']), str(root['end_datetime'])
    row = connection.execute(
        """SELECT e.start_datetime,e.end_datetime
           FROM event_assignments ea
           JOIN events e ON e.id=ea.event_id
           WHERE ea.family_id=? AND (e.id=? OR e.parent_event_id=?)
           ORDER BY CASE WHEN e.parent_event_id IS NULL THEN 1 ELSE 0 END,
                    e.start_datetime,e.id
           LIMIT 1""",
        (family_id, event_id, event_id),
    ).fetchone()
    if row is not None:
        return str(row["start_datetime"]), str(row["end_datetime"])
    return str(root["start_datetime"]), str(root["end_datetime"])


def _split_released_range_by_day(item: Mapping[str, Any]) -> list[dict[str, str]]:
    """Split one exact released interval at calendar-day boundaries."""
    start = datetime.fromisoformat(str(item["start_datetime"]))
    end = datetime.fromisoformat(str(item["end_datetime"]))
    result: list[dict[str, str]] = []
    cursor = start
    while cursor.date() < end.date():
        piece_end = cursor.replace(hour=23, minute=59, second=59, microsecond=0)
        result.append({
            "day_key": cursor.date().isoformat(),
            "start_time": cursor.strftime("%H:%M"),
            "end_time": "23:59",
            "start_datetime": cursor.isoformat(timespec="seconds"),
            "end_datetime": piece_end.isoformat(timespec="seconds"),
        })
        cursor = (piece_end + timedelta(seconds=1)).replace(microsecond=0)
    result.append({
        "day_key": cursor.date().isoformat(),
        "start_time": cursor.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "start_datetime": cursor.isoformat(timespec="seconds"),
        "end_datetime": end.isoformat(timespec="seconds"),
    })
    return result


def build_archive_reassignment_segments(
    connection,
    change_request: Mapping[str, Any],
    pending_rows: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Group removed archive families by exact released time pieces.

    The archived source structure is still unchanged while a change request is
    open.  Therefore the released ranges can be derived exactly as IST minus
    SOLL, instead of reconstructing boundaries from capture min/max values.
    """
    occupied = proposed_ranges(change_request)
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for row in pending_rows:
        fid = int(row["family_id"])
        capture = str(row.get("selected_capture_time") or "")[:19]
        if not capture:
            raise ArchiveSegmentError(f"Familie {fid} besitzt keine belastbare Aufnahmezeit.")
        old_start, old_end = _source_range(connection, change_request, fid, capture)
        released = [
            piece
            for raw_range in free_ranges(old_start, old_end, occupied)
            for piece in _split_released_range_by_day(raw_range)
        ]
        matching = [r for r in released if r["start_datetime"] <= capture <= r["end_datetime"]]
        if len(matching) != 1:
            raise ArchiveSegmentError(
                "Eine herausfallende Archivfamilie lässt sich keinem exakt freigewordenen "
                "Tages-/Zeitsegment zuordnen. Einzelne Familien dürfen nicht ohne "
                "Zeit-/Strukturänderung herausgelöst werden."
            )
        segment = matching[0]
        key = (segment["start_datetime"], segment["end_datetime"])
        item = grouped.setdefault(key, {
            **segment,
            "family_ids": [],
            "family_count": 0,
            "file_count": 0,
        })
        item["family_ids"].append(fid)
        item["family_count"] += 1
        item["file_count"] += int(row.get("file_count") or 0)

    result = list(grouped.values())
    for item in result:
        item["family_ids"] = sorted(set(int(x) for x in item["family_ids"]))
    result.sort(key=lambda item: (item["start_datetime"], item["end_datetime"]))
    return result


def validate_atomic_segment_selection(
    segments: Iterable[Mapping[str, Any]],
    family_ids: Iterable[int],
) -> list[dict[str, Any]]:
    requested = {int(x) for x in family_ids}
    if not requested:
        raise ArchiveSegmentError("Keine Tages-/Zeitsegmente ausgewählt.")
    selected: list[dict[str, Any]] = []
    covered: set[int] = set()
    for raw in segments:
        item = dict(raw)
        members = {int(x) for x in item.get("family_ids", [])}
        overlap = members & requested
        if overlap:
            if overlap != members:
                raise ArchiveSegmentError(
                    "Archiv-Neu-Zuordnung ist nur für vollständige Tages-/Zeitsegmente erlaubt."
                )
            selected.append(item)
            covered |= members
    if covered != requested:
        raise ArchiveSegmentError("Die ausgewählten Archivsegmente sind nicht mehr aktuell.")
    return selected


def selected_bounds(segments: Iterable[Mapping[str, Any]]) -> tuple[str, str]:
    items = list(segments)
    if not items:
        raise ArchiveSegmentError("Keine Tages-/Zeitsegmente ausgewählt.")
    return (
        min(str(item["start_datetime"]) for item in items),
        max(str(item["end_datetime"]) for item in items),
    )
