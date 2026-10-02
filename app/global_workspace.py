"""Server-side global workspace projection for Bibliothekar 0.28.0."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from app.database import database_connection, get_job, list_job_day_groups, list_job_time_segments, list_archive_change_reviews
from app.event_access import event_family_rows, event_source_jobs
from app.event_layout import ensure_event_layout_snapshot
from app.planning import list_job_planning_overview, list_global_released_archive_groups


def _event_counts(
    connection: Any,
    event_id: str,
    *,
    status: str | None = None,
) -> dict[str, int]:
    # Applied Ereignisse zeigen den tatsächlichen SSD-IST-Bestand. Dadurch
    # werden manuelle Verschiebungen/Löschungen nicht durch alte DB-Pfade oder
    # Dateizahlen überlagert.
    if str(status or "") == "applied":
        live = connection.execute(
            """SELECT COUNT(*) AS file_count,
                      COUNT(DISTINCT family_id) AS family_count,
                      COALESCE(SUM(size_bytes),0) AS total_size_bytes
               FROM event_inventory_files
               WHERE event_id=? AND root_kind='shared_workspace'
                 AND asset_kind IN ('camera_original','xmp','export','derived_media')""",
            (event_id,),
        ).fetchone()
        if live is not None and int(live["file_count"] or 0) > 0:
            return {
                "family_count": int(live["family_count"] or 0),
                "file_count": int(live["file_count"] or 0),
                "total_size_bytes": int(live["total_size_bytes"] or 0),
                "review_required_count": 0,
            }

    rows = event_family_rows(connection, event_id)
    family_ids = [int(row["id"]) for row in rows]
    if not family_ids:
        return {
            "family_count": 0,
            "file_count": 0,
            "total_size_bytes": 0,
            "review_required_count": 0,
        }
    ph = ",".join("?" for _ in family_ids)
    values = connection.execute(
        f"""SELECT COUNT(*) AS file_count,
                   COALESCE(SUM(size_bytes),0) AS total_size_bytes,
                   COALESCE(SUM(CASE WHEN review_status='required' THEN 1 ELSE 0 END),0)
                     AS review_required_count
            FROM files WHERE family_id IN ({ph})""",
        tuple(family_ids),
    ).fetchone()
    released_assets = {"file_count": 0, "total_size_bytes": 0}
    if str(status or "") in {"draft", "planned"}:
        asset_values = connection.execute(
            f"""SELECT COUNT(*) AS file_count,
                       COALESCE(SUM(size_bytes),0) AS total_size_bytes
                FROM released_archive_assets
                WHERE family_id IN ({ph})""",
            tuple(family_ids),
        ).fetchone()
        released_assets = {
            "file_count": int(asset_values["file_count"] or 0),
            "total_size_bytes": int(asset_values["total_size_bytes"] or 0),
        }
    return {
        "family_count": len(family_ids),
        "file_count": (
            int(values["file_count"] or 0)
            + int(released_assets["file_count"])
        ),
        "total_size_bytes": (
            int(values["total_size_bytes"] or 0)
            + int(released_assets["total_size_bytes"])
        ),
        "review_required_count": int(values["review_required_count"] or 0),
    }


def _visible_events(
    database_path: Path,
    selected_job_ids: set[str],
    workspace_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    with database_connection(database_path) as connection:
        roots = connection.execute(
            """SELECT * FROM events
               WHERE parent_event_id IS NULL
                 AND COALESCE(TRIM(linkage_kind),'')=''
                 AND status IN ('draft','planned','applied')
               ORDER BY start_datetime,id"""
        ).fetchall()
        for raw in roots:
            event = dict(raw)
            event_id = str(event["id"])
            source_rows = event_source_jobs(connection, event_id)
            source_ids = {str(row["job_id"]) for row in source_rows}
            if not source_ids:
                source_ids = {str(event["job_id"])}
            if not selected_job_ids or source_ids.isdisjoint(selected_job_ids):
                continue
            family_rows = event_family_rows(connection, event_id)
            counts = _event_counts(
                connection, event_id, status=str(event.get("status") or "")
            )
            if (
                workspace_path is not None
                and str(event.get("status") or "") in {"draft", "planned"}
                and family_rows
            ):
                from app.workspace_assets import discover_workspace_family_assets
                family_ids = [int(row["id"]) for row in family_rows]
                ph = ",".join("?" for _ in family_ids)
                physical_assets = discover_workspace_family_assets(
                    database_path,
                    workspace_path,
                    family_ids,
                )
                # Journalisierte released_archive_assets stecken bereits in
                # _event_counts(). Hier kommen nur später physisch hinzugekommene,
                # noch nicht journalisierte XMP-/Exportdateien dazu.
                counts["file_count"] += sum(
                    int(item.get("untracked_file_count") or 0)
                    for item in physical_assets.values()
                )
                counts["total_size_bytes"] += sum(
                    sum(
                        int(asset.get("size_bytes") or 0)
                        for asset in (item.get("assets") or [])
                        if not bool(asset.get("tracked"))
                    )
                    for item in physical_assets.values()
                )
            folder_layout = ensure_event_layout_snapshot(
                connection, event_id, now=str(event.get("updated_at") or event.get("created_at") or "")
            )
            event.update({
                "folder_layout": folder_layout,
                "assigned_family_count": counts["family_count"],
                "assigned_file_count": counts["file_count"],
                "source_job_ids": sorted(source_ids),
                "canonical_event_id": event_id,
                "component_events": [{
                    "job_id": str(event["job_id"]),
                    "event_id": event_id,
                    "status": str(event["status"]),
                    "linkage_kind": None,
                }],
                "has_planned_component": str(event["status"]) == "planned",
            })
            events.append(event)

            day_keys = sorted({
                str(row.get("selected_capture_time") or "")[:10]
                for row in family_rows
                if str(row.get("selected_capture_time") or "")[:10]
            })
            children = [
                dict(row) for row in connection.execute(
                    "SELECT * FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                    (event_id,),
                ).fetchall()
            ]
            group = {
                "group_type": "event",
                "event_id": event_id,
                "canonical_event_id": event_id,
                "job_id": str(event["job_id"]),
                "source_job_ids": sorted(source_ids),
                "event_name": str(event["name"]),
                "folder_name": str(event["folder_name"]),
                "start_datetime": str(event["start_datetime"]),
                "end_datetime": str(event["end_datetime"]),
                "status": str(event["status"]),
                "event_kind": str(event["event_kind"]),
                "preserve_day_folders": bool(event["preserve_day_folders"]),
                "folder_layout": folder_layout,
                "resort_required": bool(event["resort_required"]),
                "day_keys": day_keys,
                "child_events": children,
                "family_ids": [int(row["id"]) for row in family_rows],
                **counts,
                "component_events": event["component_events"],
                "linked_pending_count": 0,
            }
            groups.append(group)
            events.extend(children)
    return events, groups


def _merge_available(items: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for job_id, group in items:
        start = str(group.get("start_datetime") or "")
        end = str(group.get("end_datetime") or "")
        key = f"{group.get('day_key') or '__without_date__'}|{start}|{end}"
        local = {**group, "job_id": job_id}
        current = merged.get(key)
        source_group = {"job_id": job_id, "group": local}
        if current is None:
            current = {
                **local,
                "card_key": "global:" + key,
                "family_ids": list(group.get("family_ids") or []),
                "families": [{**family, "job_id": job_id} for family in (group.get("families") or [])],
                "source_job_ids": [job_id],
                "source_groups": [source_group],
            }
            merged[key] = current
            continue
        current["file_count"] = int(current.get("file_count") or 0) + int(group.get("file_count") or 0)
        current["family_count"] = int(current.get("family_count") or 0) + int(group.get("family_count") or 0)
        current["total_size_bytes"] = int(current.get("total_size_bytes") or 0) + int(group.get("total_size_bytes") or 0)
        current["review_required_count"] = int(current.get("review_required_count") or 0) + int(group.get("review_required_count") or 0)
        current["family_ids"] = sorted(set([*(current.get("family_ids") or []), *(group.get("family_ids") or [])]))
        current["families"].extend({**family, "job_id": job_id} for family in (group.get("families") or []))
        if job_id not in current["source_job_ids"]:
            current["source_job_ids"].append(job_id)
        current["source_groups"].append(source_group)
        current["partially_assigned"] = bool(current.get("partially_assigned") or group.get("partially_assigned"))
    return sorted(
        merged.values(),
        key=lambda item: str(item.get("start_datetime") or item.get("day_key") or "9999"),
    )


def build_global_workspace_summary(
    database_path: Path,
    selected_job_ids: list[str],
    workspace_path: Path | None = None,
    *,
    excluded_family_ids_by_job: dict[str, set[int]] | None = None,
) -> dict[str, Any]:
    selected = {str(value) for value in selected_job_ids if str(value)}
    jobs = [get_job(database_path, value) for value in sorted(selected)]
    jobs = [job for job in jobs if job is not None]

    available_items: list[tuple[str, dict[str, Any]]] = []
    day_groups: list[dict[str, Any]] = []
    time_segments: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    for job in jobs:
        job_id = str(job["id"])
        excluded = set(
            (excluded_family_ids_by_job or {}).get(job_id, set())
        )
        overview = list_job_planning_overview(
            database_path,
            job_id,
            workspace_path=workspace_path,
            excluded_family_ids=excluded,
        )
        available_items.extend(
            (job_id, dict(group))
            for group in (overview.get("available_day_groups") or [])
        )
        day_groups.extend(
            {**dict(group), "job_id": job_id}
            for group in list_job_day_groups(
                database_path,
                job_id,
                excluded_family_ids=excluded,
            )
        )
        time_segments.extend({**dict(row), "job_id": job_id} for row in list_job_time_segments(database_path, job_id))
        reviews.extend(dict(row) for row in list_archive_change_reviews(database_path, job_id))

    events, event_groups = _visible_events(
        database_path,
        selected,
        workspace_path=workspace_path,
    )
    available = _merge_available(available_items)
    timeline = sorted(
        [*event_groups, *available],
        key=lambda item: (
            str(item.get("start_datetime") or item.get("day_key") or "9999"),
            0 if item.get("group_type") == "event" else 1,
        ),
    )

    day_keys: set[str] = set()
    for group in timeline:
        if group.get("day_key"):
            day_keys.add(str(group["day_key"]))
        day_keys.update(str(day) for day in (group.get("day_keys") or []) if day)

    file_count = sum(int(group.get("file_count") or 0) for group in [*event_groups, *available])
    family_count = sum(int(group.get("family_count") or 0) for group in [*event_groups, *available])
    review_count = sum(int(group.get("review_required_count") or 0) for group in [*event_groups, *available])

    return {
        "job": jobs[0] if jobs else None,
        "jobs": jobs,
        "selected_job_ids": sorted(selected),
        "day_groups": day_groups,
        "event_count": len([event for event in events if event.get("event_level") == "parent"]),
        "events": events,
        "time_segments": time_segments,
        "planning_overview": {
            "event_groups": event_groups,
            "available_day_groups": available,
            "timeline_groups": timeline,
        },
        "released_archive_groups": list_global_released_archive_groups(
            database_path,
            excluded_family_ids={
                int(family_id)
                for values in (excluded_family_ids_by_job or {}).values()
                for family_id in values
            },
        ),
        "archive_change_review_count": len(reviews),
        "archive_change_reviews": reviews,
        "statistics": {
            "day_count": len(day_keys),
            "file_count": file_count,
            "family_count": family_count,
            "review_required_count": review_count,
            "without_date_file_count": sum(
                int(group.get("file_count") or 0)
                for group in available if not group.get("has_date")
            ),
        },
    }
