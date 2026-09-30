from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
import json

from app.database import database_connection
from app.event_access import register_source_jobs


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
    """Return existing events that can absorb still-free families of one import."""
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
            if not _capture_day(capture):
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
                  AND e.status IN ('planned','applied','archived')
                  AND ? BETWEEN e.start_datetime AND e.end_datetime
                ORDER BY
                    CASE e.status WHEN 'planned' THEN 1 WHEN 'applied' THEN 2 ELSE 3 END,
                    e.created_at DESC, e.id DESC
                """,
                (job_id, capture),
            ).fetchall()
            if not candidates:
                continue
            best_rank = {"planned": 1, "applied": 2, "archived": 3}[str(candidates[0]["status"])]
            best = [
                row for row in candidates
                if {"planned": 1, "applied": 2, "archived": 3}[str(row["status"])] == best_rank
            ]
            unique_targets = {str(row["id"]): dict(row) for row in best}
            if len(unique_targets) != 1:
                continue

            target = next(iter(unique_targets.values()))
            target_id = str(target["id"])
            item = grouped.setdefault(target_id, {
                "id": f"{job_id}:{target_id}",
                "target_event_id": target_id,
                "target_job_id": str(target["job_id"]),
                "target_name": str(target["name"]),
                "target_folder_name": str(target["folder_name"]),
                "target_status": str(target["status"]),
                "target_start_datetime": str(target["start_datetime"]),
                "target_end_datetime": str(target["end_datetime"]),
                "action_label": _action_label(str(target["status"])),
                "families": [],
                "family_ids": [],
                "family_count": 0,
                "file_count": 0,
            })
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


def _assignment_event_for(connection: Any, target_event_id: str, capture: str) -> str:
    children = connection.execute(
        """SELECT id,start_datetime,end_datetime
           FROM events WHERE parent_event_id=?
           ORDER BY start_datetime,id""",
        (target_event_id,),
    ).fetchall()
    for child in children:
        if str(child["start_datetime"]) <= capture <= str(child["end_datetime"]):
            return str(child["id"])
    return target_event_id


def accept_event_suggestion(
    database_path: Path,
    job_id: str,
    family_ids: Iterable[int],
    target_event_id: str,
) -> dict[str, Any]:
    """Attach later-imported families directly to one canonical event."""
    selected_ids = _normalize_family_ids(family_ids)
    now = _now()
    with database_connection(database_path) as connection:
        target = connection.execute(
            """SELECT * FROM events
               WHERE id=? AND parent_event_id IS NULL
                 AND event_kind='event'
                 AND COALESCE(linkage_kind,'')=''
                 AND status IN ('planned','applied','archived')""",
            (target_event_id,),
        ).fetchone()
        if target is None:
            raise EventSuggestionError("Das passende Ereignis ist nicht mehr verfügbar.")
        if str(target["job_id"]) == str(job_id):
            raise EventSuggestionError("Die ausgewählten Aufnahmen gehören bereits zur Sicherung des Zielereignisses.")
        if str(target["status"]) == "archived":
            raise EventSuggestionError("Archivierte Ereignisse werden ausschließlich über den Archivänderungsworkflow ergänzt.")

        placeholders = ",".join("?" for _ in selected_ids)
        families = connection.execute(
            f"""SELECT ff.*,COUNT(f.id) AS file_count
                FROM file_families ff
                JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
                WHERE ff.job_id=? AND ff.id IN ({placeholders})
                GROUP BY ff.id ORDER BY ff.selected_capture_time,ff.id""",
            (job_id, *selected_ids),
        ).fetchall()
        if len(families) != len(selected_ids):
            raise EventSuggestionError("Mindestens eine Dateifamilie wurde nicht gefunden.")

        total_files = 0
        for family in families:
            assigned = connection.execute(
                """SELECT 1 FROM event_assignments ea
                   JOIN events e ON e.id=ea.event_id
                   WHERE ea.family_id=?
                     AND e.status IN ('draft','planned','applied','archived')
                   LIMIT 1""",
                (family["id"],),
            ).fetchone()
            if assigned is not None:
                raise EventSuggestionError("Mindestens eine Dateifamilie ist bereits einem Ereignis zugeordnet.")
            capture = str(family["selected_capture_time"] or "")[:19]
            if not capture or not (
                str(target["start_datetime"])[:19] <= capture <= str(target["end_datetime"])[:19]
            ):
                raise EventSuggestionError("Mindestens ein Aufnahmezeitpunkt passt nicht mehr zum Ereignis.")
            total_files += int(family["file_count"] or 0)

        status = str(target["status"])
        if status == "applied":
            if int(target["resort_required"] or 0):
                raise EventSuggestionError("Für dieses Ereignis ist bereits eine Nachsortierung offen.")
            from app.event_mutation import capture_job_event_state, begin_mutation
            original_state = capture_job_event_state(connection, str(target["job_id"]))
            begin_mutation(
                connection,
                job_id=str(target["job_id"]),
                anchor_event_id=target_event_id,
                mutation_kind="edit",
                affected_event_ids=[target_event_id],
                original_state=original_state,
                status="pending_apply",
            )

        assignments = []
        for family in families:
            capture = str(family["selected_capture_time"] or "")[:19]
            assignments.append((
                _assignment_event_for(connection, target_event_id, capture),
                int(family["id"]),
                now,
            ))
        connection.executemany(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at)
               VALUES (?,?,NULL,'manual',?)""",
            assignments,
        )
        register_source_jobs(
            connection,
            target_event_id,
            [str(target["job_id"]), str(job_id)],
            created_at=now,
        )
        connection.execute(
            """UPDATE events
               SET revision=revision+1,
                   resort_required=CASE WHEN status='applied' THEN 1 ELSE resort_required END,
                   updated_at=?
               WHERE id=?""",
            (now, target_event_id),
        )
        connection.execute(
            """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'cross_backup_families_attached','event',?,?,?)""",
            (
                str(target["job_id"]),
                target_event_id,
                json.dumps({
                    "source_job_id": str(job_id),
                    "family_ids": selected_ids,
                    "target_status": status,
                }, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )

    return {
        "event_id": target_event_id,
        "canonical_target_event_id": target_event_id,
        "target_event_id": target_event_id,
        "target_job_id": str(target["job_id"]),
        "source_job_id": str(job_id),
        "family_ids": selected_ids,
        "family_count": len(selected_ids),
        "file_count": total_files,
        "target_status": status,
        "status": status,
        "linkage_kind": None,
        "name": str(target["name"]),
        "resort_required": status == "applied",
        "child_event_count": 0,
        "child_events": [],
    }
