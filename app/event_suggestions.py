from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import uuid

from app.database import database_connection


class EventSuggestionError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capture_day(value: str | None) -> str:
    return str(value or "")[:10]


def _action_label(status: str) -> str:
    return {
        "planned": "Zum Ereignis hinzufügen",
        "applied": "Zum Ereignis hinzufügen",
        "archived": "Zum archivierten Ereignis hinzufügen",
    }[status]


def list_event_suggestions(database_path: Path, job_id: str) -> list[dict[str, Any]]:
    """Return grouped cross-import event matches for unassigned families.

    Normal event occupancy is library-wide. Therefore a later import whose capture
    time lies inside an existing normal event must also get a reachable target,
    otherwise it is counted as unassigned while no free interval can be displayed.
    The suggestion remains explicit/user-confirmed and creates a current-job linked
    follow-up rather than assigning foreign-job files directly to the target row.
    """
    with database_connection(database_path) as connection:
        family_rows = connection.execute(
            """
            SELECT ff.id, ff.family_key, ff.original_stem,
                   ff.selected_capture_time, ff.capture_time_confidence,
                   COUNT(f.id) AS file_count
            FROM file_families AS ff
            JOIN files AS f ON f.family_id = ff.id AND f.job_id = ff.job_id
            WHERE ff.job_id = ?
              AND ff.selected_capture_time IS NOT NULL
              AND NOT EXISTS (
                    SELECT 1
                    FROM event_assignments AS ea
                    JOIN events AS assigned ON assigned.id = ea.event_id
                    WHERE ea.family_id = ff.id
                      AND assigned.status IN ('draft','planned','applied','archived')
              )
            GROUP BY ff.id
            ORDER BY ff.selected_capture_time, ff.id
            """,
            (job_id,),
        ).fetchall()

        grouped: dict[str, dict[str, Any]] = {}
        for family in family_rows:
            capture = str(family["selected_capture_time"])
            capture_day = _capture_day(capture)
            if not capture_day:
                continue

            candidates = connection.execute(
                """
                SELECT e.id, e.job_id, e.name, e.folder_name, e.status,
                       e.event_kind, e.start_datetime, e.end_datetime,
                       e.created_at, e.preserve_day_folders
                FROM events AS e
                WHERE e.parent_event_id IS NULL
                  AND e.job_id <> ?
                  AND e.event_kind = 'event'
                  AND COALESCE(e.linkage_kind,'') = ''
                  AND e.status IN ('planned', 'applied', 'archived')
                  AND ? BETWEEN e.start_datetime AND e.end_datetime
                ORDER BY
                    CASE e.status
                        WHEN 'planned' THEN 1
                        WHEN 'applied' THEN 2
                        ELSE 3
                    END,
                    e.created_at DESC,
                    e.id DESC
                """,
                (job_id, capture),
            ).fetchall()

            # Global normal-event occupancy must have one reachable target. If an
            # old/legacy database contains several best-rank overlaps, keep the case
            # explicit by withholding an automatic suggestion.
            if not candidates:
                continue
            best_rank = {"planned": 1, "applied": 2, "archived": 3}[str(candidates[0]["status"])]
            best = [row for row in candidates if {"planned": 1, "applied": 2, "archived": 3}[str(row["status"])] == best_rank]
            unique_targets = {str(row["id"]): dict(row) for row in best}
            if len(unique_targets) != 1:
                continue

            target = next(iter(unique_targets.values()))
            target_id = str(target["id"])
            item = grouped.get(target_id)
            if item is None:
                item = {
                    "id": f"{job_id}:{target_id}",
                    "target_event_id": target_id,
                    "target_job_id": target["job_id"],
                    "target_name": target["name"],
                    "target_folder_name": target["folder_name"],
                    "target_status": target["status"],
                    "target_start_datetime": target["start_datetime"],
                    "target_end_datetime": target["end_datetime"],
                    "action_label": _action_label(str(target["status"])),
                    "families": [],
                    "family_ids": [],
                    "family_count": 0,
                    "file_count": 0,
                }
                grouped[target_id] = item

            family_item = {
                "family_id": int(family["id"]),
                "family_key": family["family_key"],
                "original_stem": family["original_stem"],
                "capture_time": capture,
                "capture_time_confidence": family["capture_time_confidence"],
                "file_count": int(family["file_count"] or 0),
            }
            item["families"].append(family_item)
            item["family_ids"].append(int(family["id"]))
            item["family_count"] += 1
            item["file_count"] += int(family["file_count"] or 0)

        suggestions = list(grouped.values())
        for item in suggestions:
            item["families"].sort(key=lambda row: (row["capture_time"], row["family_id"]))
            item["family_ids"].sort()
        suggestions.sort(
            key=lambda item: (
                {"planned": 1, "applied": 2, "archived": 3}[str(item["target_status"])],
                str(item["target_name"]).casefold(),
                str(item["target_event_id"]),
            )
        )
    return suggestions


def _normalize_family_ids(values: Iterable[int]) -> list[int]:
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        family_id = int(value)
        if family_id <= 0 or family_id in seen:
            continue
        seen.add(family_id)
        result.append(family_id)
    if not result:
        raise EventSuggestionError("Es wurden keine Dateifamilien ausgewählt.")
    return result


def accept_event_suggestion(
    database_path: Path,
    job_id: str,
    family_ids: Iterable[int],
    target_event_id: str,
) -> dict[str, Any]:
    """Create one safe current-job follow-up event for all selected families."""
    selected_ids = _normalize_family_ids(family_ids)
    now = _now()
    with database_connection(database_path) as connection:
        target = connection.execute(
            """
            SELECT * FROM events
            WHERE id = ? AND parent_event_id IS NULL
              AND job_id <> ?
              AND event_kind = 'event'
              AND status IN ('planned', 'applied', 'archived')
            """,
            (target_event_id, job_id),
        ).fetchone()
        if target is None:
            raise EventSuggestionError("Das passende Ereignis ist nicht mehr verfügbar.")

        placeholders = ",".join("?" for _ in selected_ids)
        families = connection.execute(
            f"""
            SELECT ff.*, COUNT(f.id) AS file_count
            FROM file_families AS ff
            JOIN files AS f ON f.family_id = ff.id AND f.job_id = ff.job_id
            WHERE ff.job_id = ? AND ff.id IN ({placeholders})
            GROUP BY ff.id
            ORDER BY ff.selected_capture_time, ff.id
            """,
            (job_id, *selected_ids),
        ).fetchall()
        if len(families) != len(selected_ids):
            raise EventSuggestionError("Mindestens eine Dateifamilie wurde nicht gefunden.")

        total_files = 0
        for family in families:
            assigned = connection.execute(
                """
                SELECT 1 FROM event_assignments AS ea
                JOIN events AS e ON e.id = ea.event_id
                WHERE ea.family_id = ?
                  AND e.status IN ('draft','planned','applied','archived')
                LIMIT 1
                """,
                (family["id"],),
            ).fetchone()
            if assigned is not None:
                raise EventSuggestionError("Mindestens eine Dateifamilie ist bereits einem Ereignis zugeordnet.")
            capture = str(family["selected_capture_time"] or "")
            if not capture or not (str(target["start_datetime"]) <= capture <= str(target["end_datetime"])):
                raise EventSuggestionError("Mindestens ein Aufnahmezeitpunkt passt nicht mehr zum Ereignis.")
            total_files += int(family["file_count"] or 0)

        status = str(target["status"])
        linkage = {
            "planned": "planned_extension",
            "applied": "applied_followup",
            "archived": "archived_manual",
        }[status]
        prefix = {
            "planned": "Ergänzung",
            "applied": "Ergänzung",
            "archived": "Archiv-Ergänzung",
        }[status]
        event_id = "EVENT_" + uuid.uuid4().hex.upper()
        name = f"{prefix}: {target['name']}"
        connection.execute(
            """
            INSERT INTO events (
                id, job_id, parent_event_id, event_level, name,
                start_datetime, end_datetime, uses_time_range,
                folder_name, status, created_at, updated_at,
                event_kind, preserve_day_folders, revision,
                applied_at, archived_at, linked_event_id, linkage_kind
            ) VALUES (?, ?, NULL, 'parent', ?, ?, ?, 0, ?, 'planned',
                      ?, ?, 'event', ?, 1, NULL, NULL, ?, ?)
            """,
            (
                event_id, job_id, name,
                target["start_datetime"], target["end_datetime"],
                target["folder_name"], now, now,
                int(target["preserve_day_folders"] or 0),
                target_event_id, linkage,
            ),
        )
        connection.executemany(
            """
            INSERT INTO event_assignments (
                event_id, family_id, file_id, assignment_source, created_at
            ) VALUES (?, ?, NULL, 'manual', ?)
            """,
            [(event_id, int(family["id"]), now) for family in families],
        )
    return {
        "event_id": event_id,
        "family_ids": selected_ids,
        "family_count": len(selected_ids),
        "target_event_id": target_event_id,
        "target_status": status,
        "linkage_kind": linkage,
        "name": name,
        "file_count": total_files,
        "status": "planned",
    }
