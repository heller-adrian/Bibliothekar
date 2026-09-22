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
                root.preserve_day_folders

            FROM event_assignments AS ea

            JOIN events AS assigned
                ON assigned.id = ea.event_id

            JOIN events AS root
                ON root.id = COALESCE(
                    assigned.parent_event_id,
                    assigned.id
                )

            WHERE assigned.job_id = ?
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

    result=[f for f in family_stats if int(f['family_id']) not in assigned_family_ids]
    known={f['family_id'] for f in result}
    for card in archive_free_cards(database_path,job_id):
        for family in card['families']:
            if family['family_id'] not in known:
                result.append(family);known.add(family['family_id'])
    return result



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


def archive_free_cards(database_path, job_id):
    from app.archive_reassignment import list_archive_reassignments
    families={f['family_id']:f for f in _load_family_stats(database_path,job_id)}
    with database_connection(database_path) as c:
        requests=[str(r['id']) for r in c.execute("SELECT id FROM event_change_requests WHERE job_id=? AND status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')",(job_id,))]
    result=[]
    for cr_id in requests:
        task=list_archive_reassignments(database_path,cr_id)
        for segment in task['reassignment_segments']:
            fs=[families[f] for f in segment['family_ids'] if f in families]
            if not fs: continue
            group=_group_available_families(fs,{segment['day_key']:len(fs)})[0]
            result.append({**group,**segment,'families':fs,'card_key':cr_id+'/'+segment['start_datetime']+'/'+segment['end_datetime'],
                'reassignment_pending':True,'archive_change_request_id':cr_id})
    return result


def interval_cards(database_path, job_id, available_families, total_by_day):
    from app.free_time import free_ranges_for_day
    from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
    result = []
    with database_connection(database_path) as c:
        pending = {int(r['family_id']) for r in c.execute("SELECT family_id FROM event_reapply_removed_families WHERE job_id=? AND target_event_id IS NULL", (job_id,))}
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
                    'families': families, 'reassignment_pending': any(f['family_id'] in pending for f in families)})
    result.extend(_group_available_families([f for f in available_families if not f.get('day_key')],total_by_day))
    return result


def list_job_planning_overview(
    database_path: Path,
    job_id: str,
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

    active_assignments = _load_active_assignments(
        database_path,
        job_id,
    )

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

    available_families = [
        family
        for family in family_stats
        if int(family["family_id"])
        not in assigned_family_ids
    ]

    available_day_groups = interval_cards(database_path, job_id, available_families, total_by_day)

    available_day_groups.extend(archive_free_cards(database_path,job_id))
    available_day_groups.sort(key=lambda x:(str(x.get('start_datetime') or ''),str(x.get('card_key') or '')))
    event_groups = list(
        event_groups_by_id.values()
    )

    for event in event_groups:
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

