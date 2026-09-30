from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.database import database_connection


ACTIVE_EVENT_STATUSES = (
    "draft",
    "planned",
    "applied",
    "archived",
)


def _day_key(capture_time: Any) -> str | None:
    value = str(capture_time or "").strip()

    if len(value) >= 10:
        return value[:10]

    return None


def _load_family_stats(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                ff.id AS family_id,
                ff.family_key,
                ff.selected_capture_time,
                ff.capture_time_confidence,

                COUNT(f.id) AS file_count,

                COALESCE(
                    SUM(f.size_bytes),
                    0
                ) AS total_size_bytes,

                COALESCE(
                    SUM(
                        CASE
                            WHEN f.review_status = 'required'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS review_required_count

            FROM file_families AS ff

            LEFT JOIN files AS f
                ON f.family_id = ff.id
               AND f.job_id = ff.job_id

            WHERE ff.job_id = ?

            GROUP BY
                ff.id,
                ff.family_key,
                ff.selected_capture_time,
                ff.capture_time_confidence

            ORDER BY
                ff.selected_capture_time,
                ff.id
            """,
            (job_id,),
        ).fetchall()

    return [
        {
            "family_id": int(row["family_id"]),
            "family_key": str(row["family_key"]),
            "selected_capture_time": row[
                "selected_capture_time"
            ],
            "capture_time_confidence": row[
                "capture_time_confidence"
            ],
            "day_key": _day_key(
                row["selected_capture_time"]
            ),
            "has_date": row[
                "selected_capture_time"
            ]
            is not None,
            "file_count": int(row["file_count"]),
            "total_size_bytes": int(
                row["total_size_bytes"]
            ),
            "review_required_count": int(
                row["review_required_count"]
            ),
        }
        for row in rows
    ]


def _load_active_assignments(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                ea.family_id,

                assigned.id AS assigned_event_id,
                assigned.parent_event_id,
                assigned.name AS assigned_event_name,
                assigned.folder_name AS assigned_folder_name,
                assigned.start_datetime
                    AS assigned_start_datetime,
                assigned.end_datetime
                    AS assigned_end_datetime,

                root.id AS root_event_id,
                root.name AS root_event_name,
                root.folder_name AS root_folder_name,
                root.start_datetime AS root_start_datetime,
                root.end_datetime AS root_end_datetime,
                root.status AS root_status,
                root.event_kind,
                root.preserve_day_folders,
                root.resort_required AS root_resort_required,
                root.job_id AS root_job_id,
                root.linked_event_id AS root_linked_event_id,
                root.linkage_kind AS root_linkage_kind

            FROM event_assignments AS ea

            JOIN file_families AS source_family
                ON source_family.id = ea.family_id

            JOIN events AS assigned
                ON assigned.id = ea.event_id

            JOIN events AS root
                ON root.id = COALESCE(
                    assigned.parent_event_id,
                    assigned.id
                )

            WHERE source_family.job_id = ?
              AND ea.family_id IS NOT NULL
              AND assigned.status IN (
                    'draft',
                    'planned',
                    'applied',
                    'archived'
                  )
              AND root.status IN (
                    'draft',
                    'planned',
                    'applied',
                    'archived'
                  )

            ORDER BY
                root.start_datetime,
                root.id,
                assigned.start_datetime,
                ea.family_id
            """,
            (job_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def list_job_available_families(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    """Return unassigned families for safe event planning."""

    family_stats = _load_family_stats(
        database_path,
        job_id,
    )

    active_assignments = _load_active_assignments(
        database_path,
        job_id,
    )

    assigned_family_ids = {
        int(row["family_id"])
        for row in active_assignments
        if row.get("family_id") is not None
    }

    return [
        family
        for family in family_stats
        if int(family["family_id"]) not in assigned_family_ids
    ]



def _group_available_families(
    available_families: list[dict[str, Any]],
    total_by_day: dict[str | None, int],
) -> list[dict[str, Any]]:
    grouped: dict[
        str | None,
        dict[str, Any],
    ] = {}

    for family in available_families:
        day_key = family.get("day_key")

        group = grouped.setdefault(
            day_key,
            {
                "group_type": "day",
                "day_key": day_key,
                "has_date": day_key is not None,
                "family_ids": [],
                "family_count": 0,
                "file_count": 0,
                "total_size_bytes": 0,
                "review_required_count": 0,
            },
        )

        group["family_ids"].append(
            int(family["family_id"])
        )
        group["family_count"] += 1
        group["file_count"] += int(
            family["file_count"]
        )
        group["total_size_bytes"] += int(
            family["total_size_bytes"]
        )
        group["review_required_count"] += int(
            family["review_required_count"]
        )

    result = list(grouped.values())

    for group in result:
        group["family_ids"].sort()

        total_family_count = int(
            total_by_day.get(
                group["day_key"],
                group["family_count"],
            )
        )

        group["total_family_count"] = (
            total_family_count
        )
        group["partially_assigned"] = (
            int(group["family_count"])
            < total_family_count
        )

    result.sort(
        key=lambda group: (
            group["day_key"] is None,
            str(group["day_key"] or ""),
        )
    )

    return result


def _released_archive_family_ids(
    database_path: Path,
    job_id: str,
) -> set[int]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT DISTINCT marker.family_id
               FROM released_free_families marker
               JOIN files f ON f.family_id=marker.family_id
               WHERE marker.job_id=?
                 AND f.current_root_kind='shared_workspace'
                 AND f.current_relative_path LIKE 'Freigewordene Archivdateien/%'""",
            (job_id,),
        ).fetchall()
    return {int(row["family_id"]) for row in rows}


def list_global_released_archive_groups(
    database_path: Path,
) -> list[dict[str, Any]]:
    """Globaler freier SSD-Bestand, der aus abgeschlossenen Archivänderungen stammt."""
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT
                   marker.job_id,
                   marker.family_id,
                   marker.released_start_datetime,
                   marker.released_end_datetime,
                   ff.family_key,
                   ff.selected_capture_time,
                   ff.capture_time_confidence,
                   COALESCE(j.source_volume_label,marker.job_id) AS source_label,
                   COUNT(DISTINCT f.id) AS file_count,
                   COALESCE(SUM(CASE WHEN f.id IS NOT NULL THEN f.size_bytes ELSE 0 END),0) AS total_size_bytes,
                   COALESCE(SUM(CASE WHEN f.review_status='required' THEN 1 ELSE 0 END),0) AS review_required_count
               FROM released_free_families marker
               JOIN file_families ff ON ff.id=marker.family_id
               JOIN jobs j ON j.id=marker.job_id
               LEFT JOIN files f ON f.family_id=ff.id
               WHERE ff.selected_capture_time IS NOT NULL
                 AND marker.archive_origin=1
                 AND NOT EXISTS (
                     SELECT 1 FROM event_assignments ea
                     JOIN events e ON e.id=ea.event_id
                     WHERE ea.family_id=ff.id
                       AND e.status IN ('draft','planned','applied','archived')
                 )
                 AND EXISTS (
                     SELECT 1 FROM files rf
                     WHERE rf.family_id=ff.id
                       AND rf.current_root_kind='shared_workspace'
                       AND rf.current_relative_path LIKE 'Freigewordene Archivdateien/%'
                 )
               GROUP BY marker.job_id,marker.family_id,
                        marker.released_start_datetime,marker.released_end_datetime,
                        ff.family_key,ff.selected_capture_time,ff.capture_time_confidence,
                        j.source_volume_label
               ORDER BY marker.released_start_datetime,marker.job_id,marker.family_id"""
        ).fetchall()
        released_asset_rows = connection.execute(
            """SELECT job_id,family_id,COUNT(*) AS n,COALESCE(SUM(size_bytes),0) AS bytes
               FROM released_archive_assets
               WHERE family_id IS NOT NULL
               GROUP BY job_id,family_id"""
        ).fetchall()

    released_asset_stats = {
        (str(row["job_id"]), int(row["family_id"])): {
            "file_count": int(row["n"]),
            "total_size_bytes": int(row["bytes"]),
        }
        for row in released_asset_rows
    }

    from app.free_stock_layout import effective_released_range
    effective_by_family: dict[int, tuple[str, str] | None] = {}
    with database_connection(database_path) as effective_connection:
        for row in rows:
            effective_by_family[int(row["family_id"])] = effective_released_range(
                effective_connection,
                int(row["family_id"]),
                str(row["selected_capture_time"] or ""),
                physical=False,
            )

    grouped: dict[tuple[str,str], dict[str, Any]] = {}
    for row in rows:
        job_id = str(row["job_id"])
        effective = effective_by_family.get(int(row["family_id"]))
        if effective is None:
            continue
        start, end = effective
        key = (start, end)
        item = grouped.setdefault(key, {
            "group_type": "released_archive",
            "released_archive": True,
            "job_id": job_id,
            "source_label": str(row["source_label"] or job_id),
            "start_datetime": start,
            "end_datetime": end,
            "day_key": start[:10] if len(start) >= 10 else None,
            "start_time": start[11:16] if len(start) >= 16 else "00:00",
            "end_time": end[11:16] if len(end) >= 16 else "23:59",
            "has_date": bool(start[:10]),
            "family_ids": [],
            "source_job_ids": [],
            "source_groups": [],
            "family_count": 0,
            "file_count": 0,
            "total_size_bytes": 0,
            "review_required_count": 0,
            "families": [],
            "card_key": f"released:{start}:{end}",
        })
        family_id = int(row["family_id"])
        extra = released_asset_stats.get((job_id, family_id), {})
        family = {
            "family_id": family_id,
            "job_id": job_id,
            "family_key": str(row["family_key"]),
            "selected_capture_time": row["selected_capture_time"],
            "capture_time_confidence": row["capture_time_confidence"],
            "day_key": str(row["selected_capture_time"] or "")[:10] or None,
            "has_date": row["selected_capture_time"] is not None,
            "file_count": int(row["file_count"]) + int(extra.get("file_count") or 0),
            "total_size_bytes": int(row["total_size_bytes"]) + int(extra.get("total_size_bytes") or 0),
            "review_required_count": int(row["review_required_count"]),
        }
        item["family_ids"].append(family["family_id"])
        item["family_count"] += 1
        item["file_count"] += family["file_count"]
        item["total_size_bytes"] += family["total_size_bytes"]
        item["review_required_count"] += family["review_required_count"]
        item["families"].append(family)
        if job_id not in item["source_job_ids"]:
            item["source_job_ids"].append(job_id)
        item["source_groups"].append({
            "job_id": job_id,
            "source_label": str(row["source_label"] or job_id),
            "start_datetime": start,
            "end_datetime": end,
            "day_key": start[:10] if len(start) >= 10 else None,
            "family_ids": [family_id],
            "family_count": 1,
            "file_count": family["file_count"],
            "total_size_bytes": family["total_size_bytes"],
            "review_required_count": family["review_required_count"],
            "families": [family],
        })

    result = list(grouped.values())
    for item in result:
        item["family_ids"].sort()
        item["source_job_ids"] = sorted(set(item["source_job_ids"]))
        item["source_groups"].sort(
            key=lambda group: (
                str(group.get("source_label") or "").casefold(),
                str(group.get("job_id") or ""),
            )
        )
        if len(item["source_job_ids"]) > 1:
            item["source_label"] = f"{len(item['source_job_ids'])} Sicherungen"
        item["total_family_count"] = item["family_count"]
        item["partially_assigned"] = False
    result.sort(key=lambda item: (
        str(item.get("start_datetime") or ""),
        str(item.get("end_datetime") or ""),
    ))
    return result

def interval_cards(database_path, job_id, available_families, total_by_day):
    from app.free_time import free_ranges_for_day
    from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
    result = []
    with database_connection(database_path) as c:
        pending = {
            int(r['family_id'])
            for r in c.execute(
                """SELECT family_id
                   FROM event_reapply_removed_families
                   WHERE job_id=? AND target_event_id IS NULL
                     AND COALESCE(target_kind,'') <> 'released_free'""",
                (job_id,),
            )
        }
        released = {
            int(r['family_id'])
            for r in c.execute(
                """SELECT family_id
                   FROM released_free_families
                   WHERE job_id=?""",
                (job_id,),
            )
        }
        for day in sorted(d for d in total_by_day if d):
            a,b = day+'T00:00:00', day+'T23:59:59'
            occupied = [(r['effective_start'],r['effective_end']) for r in continuous_event_overlaps(c,job_id,a,b)]
            occupied += [(r['start_datetime'],r['end_datetime']) for r in no_event_segment_overlaps(c,job_id,a,b)]
            for segment in free_ranges_for_day(day, occupied):
                families = [f for f in available_families if segment['start_datetime'] <= str(f.get('selected_capture_time') or '')[:19] <= segment['end_datetime']]
                if not families:
                    continue
                group = _group_available_families(families,total_by_day)[0]
                result.append({**group, **segment, 'card_key': segment['start_datetime']+'/'+segment['end_datetime'],
                    'families': families,
                    'reassignment_pending': any(f['family_id'] in pending for f in families),
                    'released_free': any(f['family_id'] in released for f in families)})
    result.extend(_group_available_families([f for f in available_families if not f.get('day_key')],total_by_day))
    return result


def list_job_planning_overview(
    database_path: Path,
    job_id: str,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """
    Return existing event groups and only the still-free day stock.

    The function is read-only. It never changes files, folders, or
    database rows.
    """

    family_stats = _load_family_stats(
        database_path,
        job_id,
    )

    # Vor dem ersten Anwenden existieren Lightroom-XMP/Exporte unter
    # Umständen bereits physisch im freien SSD-Bestand, aber noch nicht als
    # files-Zeilen. Für die sichtbare Planung werden sie read-only zur
    # jeweiligen Familie hinzugerechnet. Applied-Bestände werden weiter unten
    # unverändert vom persistierten Live-Inventar überstimmt.
    if workspace_path is not None and family_stats:
        from app.workspace_assets import discover_workspace_family_assets
        physical_assets = discover_workspace_family_assets(
            database_path,
            workspace_path,
            [int(family["family_id"]) for family in family_stats],
        )
        for family in family_stats:
            extra = physical_assets.get(int(family["family_id"]))
            if not extra:
                continue
            family["file_count"] = int(family["file_count"]) + int(
                extra.get("file_count") or 0
            )
            family["total_size_bytes"] = int(family["total_size_bytes"]) + int(
                extra.get("total_size_bytes") or 0
            )
            family["workspace_asset_kinds"] = list(
                extra.get("asset_kinds") or []
            )
            family["workspace_asset_count"] = int(
                extra.get("file_count") or 0
            )

    active_assignments = _load_active_assignments(
        database_path,
        job_id,
    )

    with database_connection(database_path) as connection:
        live_rows = connection.execute(
            """SELECT event_id,root_kind,
                      COUNT(*) AS file_count,
                      COUNT(DISTINCT family_id) AS family_count,
                      COALESCE(SUM(size_bytes),0) AS total_size_bytes
               FROM event_inventory_files
               WHERE job_id=?
                 AND asset_kind IN ('camera_original','xmp','export','derived_media')
               GROUP BY event_id,root_kind""",
            (job_id,),
        ).fetchall()
    live_counts = {
        (str(row["event_id"]), str(row["root_kind"])): dict(row)
        for row in live_rows
    }

    families_by_id = {
        int(family["family_id"]): family
        for family in family_stats
    }

    total_by_day: dict[
        str | None,
        int,
    ] = defaultdict(int)

    for family in family_stats:
        total_by_day[family.get("day_key")] += 1

    assigned_family_ids: set[int] = set()
    event_groups_by_id: dict[
        str,
        dict[str, Any],
    ] = {}
    counted_event_families: set[
        tuple[str, int]
    ] = set()

    for row in active_assignments:
        family_id = int(row["family_id"])
        family = families_by_id.get(family_id)

        if family is None:
            continue

        root_event_id = str(row["root_event_id"])
        counted_key = (
            root_event_id,
            family_id,
        )

        if counted_key in counted_event_families:
            continue

        counted_event_families.add(counted_key)
        assigned_family_ids.add(family_id)

        event = event_groups_by_id.setdefault(
            root_event_id,
            {
                "group_type": "event",
                "event_id": root_event_id,
                "job_id": str(row["root_job_id"]),
                "linked_event_id": (
                    str(row["root_linked_event_id"])
                    if row["root_linked_event_id"] is not None
                    else None
                ),
                "linkage_kind": (
                    str(row["root_linkage_kind"])
                    if row["root_linkage_kind"] is not None
                    else None
                ),
                "event_name": str(
                    row["root_event_name"]
                ),
                "folder_name": str(
                    row["root_folder_name"]
                ),
                "start_datetime": str(
                    row["root_start_datetime"]
                ),
                "end_datetime": str(
                    row["root_end_datetime"]
                ),
                "status": str(row["root_status"]),
                "event_kind": str(
                    row["event_kind"]
                ),
                "preserve_day_folders": bool(
                    row["preserve_day_folders"]
                ),
                "resort_required": bool(
                    row["root_resort_required"]
                ),
                "day_keys": [],
                "child_events": [],
                "family_ids": [],
                "family_count": 0,
                "file_count": 0,
                "total_size_bytes": 0,
                "review_required_count": 0,
            },
        )

        day_key = family.get("day_key")

        if (
            day_key is not None
            and day_key not in event["day_keys"]
        ):
            event["day_keys"].append(day_key)

        event["family_ids"].append(family_id)
        event["family_count"] += 1
        event["file_count"] += int(
            family["file_count"]
        )
        event["total_size_bytes"] += int(
            family["total_size_bytes"]
        )
        event["review_required_count"] += int(
            family["review_required_count"]
        )

        if row.get("parent_event_id") is not None:
            child_id = str(row["assigned_event_id"])

            if not any(
                child["id"] == child_id
                for child in event["child_events"]
            ):
                event["child_events"].append(
                    {
                        "id": child_id,
                        "name": str(
                            row["assigned_event_name"]
                        ),
                        "folder_name": str(
                            row["assigned_folder_name"]
                        ),
                        "start_datetime": str(
                            row[
                                "assigned_start_datetime"
                            ]
                        ),
                        "end_datetime": str(
                            row[
                                "assigned_end_datetime"
                            ]
                        ),
                    }
                )

    released_archive_ids = _released_archive_family_ids(database_path, job_id)
    available_families = [
        family
        for family in family_stats
        if int(family["family_id"]) not in assigned_family_ids
        and int(family["family_id"]) not in released_archive_ids
    ]

    available_day_groups = interval_cards(database_path, job_id, available_families, total_by_day)

    available_day_groups.sort(key=lambda x:(str(x.get('start_datetime') or ''),str(x.get('card_key') or '')))
    # Archivierte Ereignisse belegen ihren Bestand weiterhin, gehören aber
    # nicht mehr in die aktive Aufnahmenansicht. Dort erscheinen nur freie,
    # geplante und angewendete Arbeitsbestände.
    event_groups = [
        event
        for event in event_groups_by_id.values()
        if str(event.get("status") or "") != "archived"
    ]

    for event in event_groups:
        live_root_kind = (
            "camera_archive"
            if event["status"] == "archived"
            else "shared_workspace"
            if event["status"] == "applied"
            else None
        )
        live = (
            live_counts.get((str(event["event_id"]), live_root_kind))
            if live_root_kind is not None
            else None
        )
        if live is not None:
            event["file_count"] = int(live["file_count"] or 0)
            event["family_count"] = int(live["family_count"] or 0)
            event["total_size_bytes"] = int(live["total_size_bytes"] or 0)
            event["live_inventory"] = True
        if event['event_kind']=='no_event':
            from app.event_timeline import list_event_segments
            segments=list_event_segments(database_path,event['event_id'])
            if segments:
                event['start_datetime']=segments[0]['start_datetime']
                event['end_datetime']=segments[-1]['end_datetime']
        event["day_keys"].sort()
        event["family_ids"].sort()
        event["child_events"].sort(
            key=lambda child: (
                child["start_datetime"],
                child["id"],
            )
        )

    def timeline_sort_key(
        group: dict[str, Any],
    ) -> tuple[str, int, str]:
        if group["group_type"] == "event":
            return (
                str(group["start_datetime"])[:10],
                0,
                str(group["event_name"]),
            )

        day_key = group.get("day_key")

        return (
            str(day_key or "9999-99-99"),
            1,
            "",
        )

    event_groups.sort(key=timeline_sort_key)

    timeline_groups = (
        event_groups
        + available_day_groups
    )
    timeline_groups.sort(key=timeline_sort_key)

    return {
        "event_groups": event_groups,
        "available_day_groups": (
            available_day_groups
        ),
        "timeline_groups": timeline_groups,
        "assigned_event_count": len(event_groups),
        "assigned_family_count": len(
            assigned_family_ids
        ),
        "available_family_count": len(
            available_families
        ),
    }

