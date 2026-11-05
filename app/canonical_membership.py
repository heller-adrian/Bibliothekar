"""Library-wide time membership for Bibliothekar 0.28.2.

A backup/job is provenance only.  Event membership is determined by the
canonical event/no-event time definition across the active SSD workspace.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Iterable

from app.event_timeline import normalize_no_event_segments


class CanonicalMembershipError(ValueError):
    pass


def _clean_interval(start: Any, end: Any) -> tuple[str, str]:
    a = str(start or "")[:19]
    b = str(end or "")[:19]
    if len(a) != 19 or len(b) != 19 or a > b:
        raise CanonicalMembershipError("Der gewählte Zeitraum ist ungültig.")
    return a, b


def intervals_for_event_payload(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """Return the time intervals that define *new* membership for a save.

    New normal events use their final event interval.  Extensions of an
    existing normal event use only the selected extension intervals, otherwise
    already occupied historic time would incorrectly pull unrelated free stock.
    No-event collections use their explicit per-day segments.
    """
    event_kind = str(payload.get("event_kind") or "event")
    if event_kind == "no_event":
        segments = normalize_no_event_segments(payload.get("no_event_segments") or [])
        return [
            (str(item["start_datetime"])[:19], str(item["end_datetime"])[:19])
            for item in segments
        ]

    existing_parent = str(payload.get("existing_parent_event_id") or "").strip()
    selected = [
        item for item in (payload.get("selected_intervals") or [])
        if isinstance(item, dict)
        and item.get("start_datetime")
        and item.get("end_datetime")
    ]
    if existing_parent and selected:
        return [
            _clean_interval(item["start_datetime"], item["end_datetime"])
            for item in selected
        ]

    start_date = str(payload.get("start_date") or "")
    end_date = str(payload.get("end_date") or start_date)
    uses_time = bool(payload.get("uses_time_range"))
    start_time = str(payload.get("start_time") or ("00:00" if not uses_time else "00:00"))
    end_time = str(payload.get("end_time") or ("23:59" if not uses_time else "23:59"))
    if not uses_time:
        start_time, end_time = "00:00", "23:59"
    return [_clean_interval(
        f"{start_date}T{start_time}:00",
        f"{end_date}T{end_time}:59",
    )]


def _in_intervals(capture: str, intervals: Iterable[tuple[str, str]]) -> bool:
    value = str(capture or "")[:19]
    return bool(value) and any(start <= value <= end for start, end in intervals)


def global_free_families(
    connection: Any,
    intervals: Iterable[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Free families physically present in the active shared SSD workspace."""
    normalized = list(intervals)
    if not normalized:
        return []

    rows = connection.execute(
        """
        SELECT ff.id AS family_id, ff.job_id, ff.family_key, ff.original_stem,
               ff.selected_capture_time, ff.capture_time_confidence,
               j.source_volume_label, j.created_at AS source_created_at,
               COUNT(f.id) AS file_count,
               COALESCE(SUM(f.size_bytes),0) AS total_size_bytes,
               COALESCE(SUM(CASE WHEN f.review_status='required' THEN 1 ELSE 0 END),0)
                 AS review_required_count
        FROM file_families ff
        JOIN jobs j ON j.id=ff.job_id
        JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
        WHERE ff.selected_capture_time IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM files active
              WHERE active.family_id=ff.id
                AND active.job_id=ff.job_id
                AND active.current_root_kind='shared_workspace'
                AND COALESCE(active.current_relative_path,'')
                    NOT LIKE 'Freigewordene Archivdateien/%'
          )
          AND NOT EXISTS (
              SELECT 1
              FROM event_assignments ea
              JOIN events assigned ON assigned.id=ea.event_id
              JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
              WHERE ea.family_id=ff.id
                AND root.status IN ('draft','planned','applied','archived')
          )
        GROUP BY ff.id
        ORDER BY ff.selected_capture_time,ff.id
        """
    ).fetchall()

    result: list[dict[str, Any]] = []
    for raw in rows:
        item = dict(raw)
        capture = str(item.get("selected_capture_time") or "")[:19]
        if not _in_intervals(capture, normalized):
            continue
        file_rows = connection.execute(
            """SELECT original_filename,current_relative_path
               FROM files
               WHERE family_id=? AND job_id=?
                 AND current_root_kind='shared_workspace'
               ORDER BY id""",
            (int(item["family_id"]), str(item["job_id"])),
        ).fetchall()
        names: list[str] = []
        for row in file_rows:
            current = str(row["current_relative_path"] or "")
            name = PurePosixPath(current).name if current else str(row["original_filename"] or "")
            if name and name not in names:
                names.append(name)
        item["file_names"] = names
        item["day_key"] = capture[:10]
        item["has_date"] = True
        result.append(item)
    return result


def resolve_payload_membership(
    connection: Any,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Resolve explicit UI selection to the complete canonical active membership.

    The event interval remains authoritative: unchecked day cards inside that
    interval are included silently.  A confirmation is only needed for free
    stock coming from an active backup that is currently hidden by the backup
    filter.
    """
    intervals = intervals_for_event_payload(payload)
    selected_ids = sorted({
        int(value) for value in (payload.get("selected_family_ids") or [])
        if int(value) > 0
    })
    visible_active_job_ids = {
        str(value)
        for value in (payload.get("visible_active_job_ids") or [])
        if str(value)
    }
    families = global_free_families(connection, intervals)
    canonical_ids = sorted({int(row["family_id"]) for row in families} | set(selected_ids))
    by_id = {int(row["family_id"]): row for row in families}
    additional_ids = [
        fid for fid in canonical_ids
        if fid not in set(selected_ids) and fid in by_id
    ]
    additional = [by_id[fid] for fid in additional_ids]

    # Older clients do not send filter provenance. In that case retain the
    # conservative pre-0.43 confirmation behavior.
    if visible_active_job_ids:
        hidden_additional = [
            row for row in additional
            if str(row.get("job_id") or "") not in visible_active_job_ids
        ]
    else:
        hidden_additional = list(additional)

    def grouped_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources: dict[str, dict[str, Any]] = {}
        for family in rows:
            job_id = str(family.get("job_id") or "")
            source = sources.setdefault(job_id, {
                "job_id": job_id,
                "source_label": str(family.get("source_volume_label") or job_id),
                "family_count": 0,
                "file_count": 0,
                "families": [],
            })
            source["family_count"] += 1
            source["file_count"] += int(family.get("file_count") or 0)
            source["families"].append({
                "family_id": int(family["family_id"]),
                "original_stem": str(
                    family.get("original_stem")
                    or family.get("family_key")
                    or ""
                ),
                "capture_time": str(
                    family.get("selected_capture_time") or ""
                )[:19],
                "file_count": int(family.get("file_count") or 0),
                "file_names": list(family.get("file_names") or []),
            })
        return sorted(
            sources.values(),
            key=lambda row: (row["source_label"].casefold(), row["job_id"]),
        )

    hidden_ids = sorted(int(row["family_id"]) for row in hidden_additional)
    return {
        "intervals": [
            {"start_datetime": a, "end_datetime": b}
            for a, b in intervals
        ],
        "selected_family_ids": selected_ids,
        "canonical_family_ids": canonical_ids,
        # Total automatic interval expansion, including unchecked cards from
        # already visible backups.
        "additional_family_ids": additional_ids,
        "additional_family_count": len(additional_ids),
        "additional_file_count": sum(
            int(row.get("file_count") or 0) for row in additional
        ),
        "sources": grouped_sources(additional),
        # Only these rows require the user-facing cross-backup confirmation.
        "hidden_additional_family_ids": hidden_ids,
        "hidden_additional_family_count": len(hidden_ids),
        "hidden_additional_file_count": sum(
            int(row.get("file_count") or 0) for row in hidden_additional
        ),
        "hidden_sources": grouped_sources(hidden_additional),
        "visible_active_job_ids": sorted(visible_active_job_ids),
    }


def event_contains_capture(connection: Any, event: dict[str, Any], capture: str) -> bool:
    value = str(capture or "")[:19]
    if not value:
        return False
    if str(event.get("event_kind") or "event") == "no_event":
        row = connection.execute(
            """SELECT 1 FROM event_time_segments
               WHERE event_id=? AND start_datetime<=? AND end_datetime>=?
               LIMIT 1""",
            (str(event["id"]), value, value),
        ).fetchone()
        return row is not None
    return (
        str(event.get("start_datetime") or "")[:19]
        <= value
        <= str(event.get("end_datetime") or "")[:19]
    )
