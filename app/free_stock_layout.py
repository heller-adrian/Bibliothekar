"""Canonical physical layout for unassigned workspace families.

The current installation represents one logical camera library.  Occupancy is
therefore library-wide even though free families and files remain owned by
their import job.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, Iterable

from app.free_time import free_ranges_for_day


ACTIVE_EVENT_STATUSES = ("draft", "planned", "applied", "archived")
PHYSICAL_EVENT_STATUSES = ("applied", "archived")


class FreeStockLayoutError(ValueError):
    pass


def _days_between(start: str, end: str) -> set[str]:
    first = date.fromisoformat(str(start)[:10])
    last = date.fromisoformat(str(end)[:10])
    result: set[str] = set()
    current = first
    while current <= last:
        result.add(current.isoformat())
        current += timedelta(days=1)
    return result


def affected_days_for_event(connection: Any, event_id: str) -> set[str]:
    """Days whose physical free stock may change with one event mutation."""
    event = connection.execute(
        "SELECT start_datetime,end_datetime,event_kind FROM events WHERE id=?",
        (event_id,),
    ).fetchone()
    if event is None:
        return set()
    days = _days_between(str(event["start_datetime"]), str(event["end_datetime"]))
    if str(event["event_kind"] or "event") == "no_event":
        days.update(
            str(row["day_key"])
            for row in connection.execute(
                "SELECT day_key FROM event_time_segments WHERE event_id=?",
                (event_id,),
            ).fetchall()
        )
    for row in connection.execute(
        """SELECT released_start_datetime,released_end_datetime
           FROM event_reapply_removed_families WHERE event_id=?""",
        (event_id,),
    ).fetchall():
        if row["released_start_datetime"] and row["released_end_datetime"]:
            days.update(
                _days_between(
                    str(row["released_start_datetime"]),
                    str(row["released_end_datetime"]),
                )
            )
    return days


def occupied_ranges_for_day(
    connection: Any,
    day_key: str,
    *,
    physical: bool,
    include_event_ids: Iterable[str] = (),
    exclude_event_ids: Iterable[str] = (),
) -> list[tuple[str, str]]:
    """Return total library occupancy while preserving legacy disjoint ranges."""
    included = {str(value) for value in include_event_ids}
    excluded = {str(value) for value in exclude_event_ids}
    statuses = PHYSICAL_EVENT_STATUSES if physical else ACTIVE_EVENT_STATUSES
    placeholders = ",".join("?" for _ in statuses)
    rows = connection.execute(
        f"""SELECT * FROM events
            WHERE parent_event_id IS NULL AND pending_delete=0
              AND status IN ({placeholders})""",
        statuses,
    ).fetchall()
    # A planned event being applied belongs to the physical target state even
    # though its status changes only after the verified file operation.
    if included:
        extra_placeholders = ",".join("?" for _ in included)
        rows = list(rows) + list(
            connection.execute(
                f"""SELECT * FROM events WHERE parent_event_id IS NULL
                    AND pending_delete=0 AND id IN ({extra_placeholders})""",
                tuple(sorted(included)),
            ).fetchall()
        )

    result: list[tuple[str, str]] = []
    seen: set[str] = set()
    day_start = f"{day_key}T00:00:00"
    day_end = f"{day_key}T23:59:59"
    for raw in rows:
        event = dict(raw)
        event_id = str(event["id"])
        if event_id in seen or event_id in excluded:
            continue
        seen.add(event_id)
        if str(event.get("event_kind") or "event") == "no_event":
            intervals = connection.execute(
                """SELECT start_datetime,end_datetime FROM event_time_segments
                   WHERE event_id=? AND start_datetime<=? AND end_datetime>=?
                   ORDER BY start_datetime,id""",
                (event_id, day_end, day_start),
            ).fetchall()
        else:
            children = connection.execute(
                """SELECT start_datetime,end_datetime FROM events
                   WHERE parent_event_id=? ORDER BY start_datetime,id""",
                (event_id,),
            ).fetchall()
            intervals = (
                children
                if int(event.get("time_model_version") or 1) < 2 and children
                else [raw]
            )
        for interval in intervals:
            start = str(interval["start_datetime"])[:19]
            end = str(interval["end_datetime"])[:19]
            if start <= day_end and end >= day_start:
                result.append((max(start, day_start), min(end, day_end)))
    return sorted(set(result))


def _filesystem_time(value: str, *, end: bool) -> str:
    parsed = datetime.fromisoformat(value)
    # Minute-aligned ranges keep the concise product spelling.  Non-aligned
    # legacy ranges retain seconds so two distinct exact intervals cannot map
    # to the same folder name.
    if parsed.second == (59 if end else 0):
        return parsed.strftime("%H-%M")
    return parsed.strftime("%H-%M-%S")


def effective_released_range(
    connection: Any,
    family_id: int,
    capture_time: str,
    *,
    physical: bool,
) -> tuple[str, str] | None:
    marker = connection.execute(
        """SELECT released_start_datetime,released_end_datetime
           FROM released_free_families
           WHERE family_id=? AND archive_origin=1
           ORDER BY created_at DESC LIMIT 1""",
        (int(family_id),),
    ).fetchone()
    if marker is None:
        return None
    origin_start = str(marker["released_start_datetime"] or "")[:19]
    origin_end = str(marker["released_end_datetime"] or "")[:19]
    capture = str(capture_time or "")[:19]
    if not origin_start or not origin_end or not capture:
        return None
    day_key = capture[:10]
    from app.free_time import free_ranges_for_day
    free_ranges = free_ranges_for_day(
        day_key,
        occupied_ranges_for_day(connection, day_key, physical=physical),
    )
    for item in free_ranges:
        start = max(origin_start, str(item["start_datetime"])[:19])
        end = min(origin_end, str(item["end_datetime"])[:19])
        if start <= capture <= end:
            return start, end
    return None


def released_origin_directory(
    connection: Any,
    family_id: int,
    capture_time: str,
    *,
    physical: bool,
    release_name: str = "Released Archive Files",
) -> PurePosixPath | None:
    from app.managed_directory_names import NAME_PAIRS
    if release_name not in NAME_PAIRS["released_archive"]:
        raise FreeStockLayoutError("Unknown released archive directory name.")
    bounds = effective_released_range(
        connection, family_id, capture_time, physical=physical
    )
    if bounds is None:
        return None
    start, end = bounds
    day_key = start[:10]
    if start[11:16] == "00:00" and end[11:16] == "23:59":
        folder = day_key
    else:
        folder = (
            f"{day_key} · "
            f"{_filesystem_time(start, end=False)}–"
            f"{_filesystem_time(end, end=True)}"
        )
    return PurePosixPath(release_name, day_key[:4], folder)


def canonical_free_directory(
    connection: Any,
    capture_time: str,
    *,
    physical: bool = True,
    include_event_ids: Iterable[str] = (),
) -> PurePosixPath:
    capture = str(capture_time or "")[:19]
    try:
        parsed = datetime.fromisoformat(capture)
    except ValueError as exc:
        raise FreeStockLayoutError("Für freien Bestand fehlt eine gültige Aufnahmezeit.") from exc
    day_key = parsed.date().isoformat()
    occupied = occupied_ranges_for_day(
        connection,
        day_key,
        physical=physical,
        include_event_ids=include_event_ids,
    )
    free = free_ranges_for_day(day_key, occupied)
    if not occupied and len(free) == 1:
        folder = day_key
    else:
        segment = next(
            (
                item
                for item in free
                if item["start_datetime"] <= capture <= item["end_datetime"]
            ),
            None,
        )
        if segment is None:
            raise FreeStockLayoutError(
                "Die Familie liegt in einem belegten Zeitraum und ist kein freier Bestand."
            )
        folder = (
            f"{day_key} · "
            f"{_filesystem_time(segment['start_datetime'], end=False)}–"
            f"{_filesystem_time(segment['end_datetime'], end=True)}"
        )
    return PurePosixPath(day_key[:4], folder)


def free_file_rows(
    connection: Any,
    days: Iterable[str],
    *,
    job_id: str,
    shared_library: bool,
) -> list[dict[str, Any]]:
    day_values = sorted({str(day) for day in days if day})
    if not day_values:
        return []
    day_placeholders = ",".join("?" for _ in day_values)
    scope_sql = (
        "f.current_root_kind='shared_workspace'"
        if shared_library
        else "f.job_id=?"
    )
    params: list[Any] = list(day_values)
    if not shared_library:
        params.append(job_id)
    rows = connection.execute(
        f"""SELECT f.*,ff.family_key,ff.status AS family_status,
                   ff.selected_capture_time AS family_capture_time,
                   ff.capture_time_confidence AS family_confidence
            FROM files f JOIN file_families ff ON ff.id=f.family_id
            WHERE substr(ff.selected_capture_time,1,10) IN ({day_placeholders})
              AND {scope_sql}
              AND NOT EXISTS (
                  SELECT 1 FROM event_assignments ea
                  JOIN events e ON e.id=ea.event_id
                  WHERE ea.family_id=ff.id
                    AND e.status IN ('draft','planned','applied','archived')
              )
            ORDER BY ff.selected_capture_time,ff.id,f.original_relative_path""",
        tuple(params),
    ).fetchall()
    return [{**dict(row), "_free_stock": True} for row in rows]
