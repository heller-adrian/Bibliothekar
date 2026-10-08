"""Read-only, lightweight overview of server-side work for the desktop status dock.

No task is started or modified here. The three independent workflows continue
to run in their existing back-end workers and keep their existing safety rules.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import database_connection
from app.background_mutation_cancel import list_visible


_IMPORT_STATES = (
    "queued", "copying", "verifying", "backup_verified",
    "analyzing_metadata", "organizing",
)
_SORT_STATES = ("queued", "verifying", "moving", "finalizing", "rolling_back")
_BATCH_STATES = ("queued", "running", "interrupted")


def current_activity(library_database: Path, global_import_database: Path) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []

    # Camera and folder imports are globally managed in the main DB, even
    # while a secondary library is selected in the browser.
    with database_connection(global_import_database) as connection:
        rows = connection.execute(
            """SELECT id, state, stage, source_volume_label
               FROM jobs
               WHERE operation IN (
                   'folder_import','metadata_multiple_import','metadata_general_import'
               )
                 AND state IN ('queued','copying','verifying','backup_verified',
                               'analyzing_metadata','organizing')
               ORDER BY created_at DESC,id DESC LIMIT 8"""
        ).fetchall()
    for row in rows:
        operations.append({
            "kind": "import",
            "id": str(row["id"]),
            "status": str(row["state"]),
            "label": str(row["source_volume_label"] or "Import"),
            "detail": "Import läuft im Hintergrund" if row["state"] != "queued"
                      else "Import wartet auf Verarbeitung",
            "href": "/",
            "active": True,
        })

    with database_connection(library_database) as connection:
        batches = connection.execute(
            """SELECT id,status,item_count,completed_item_count
               FROM operation_batches
               WHERE status IN ('queued','running','interrupted')
               ORDER BY created_at DESC,id DESC LIMIT 8"""
        ).fetchall()
        runs = connection.execute(
            """SELECT sr.id,sr.job_id,sr.event_id,sr.status,e.name AS event_name
               FROM sort_runs sr
               LEFT JOIN events e ON e.id=sr.event_id
               WHERE sr.status IN ('queued','verifying','moving','finalizing','rolling_back')
                 AND NOT EXISTS (
                   SELECT 1 FROM operation_batch_items bi
                   WHERE bi.sort_run_id=sr.id
                 )
               ORDER BY sr.created_at DESC,sr.id DESC LIMIT 8"""
        ).fetchall()

    for row in batches:
        operations.append({
            "kind": "apply",
            "id": str(row["id"]),
            "status": str(row["status"]),
            "label": "Ereignisse anwenden",
            "detail": f"{int(row['completed_item_count'] or 0)} von {int(row['item_count'] or 0)} Ereignissen verarbeitet"
                if row["status"] != "interrupted" else "Sortierung unterbrochen – Prüfung erforderlich",
            "href": "/events",
            "active": row["status"] != "interrupted",
        })

    for row in runs:
        operations.append({
            "kind": "apply",
            "id": str(row["id"]),
            "status": str(row["status"]),
            "label": str(row["event_name"] or "Ereignis") + " anwenden",
            "detail": "Sortierung läuft im Hintergrund",
            "href": "/events?job=" + str(row["job_id"]),
            "active": True,
        })

    for row in list_visible(library_database, limit=8):
        status = str(row["status"])
        operations.append({
            "kind": "cancel",
            "id": str(row["id"]),
            "job_id": str(row["job_id"]),
            "mutation_id": str(row["mutation_id"]),
            "status": status,
            "label": "Änderung verwerfen",
            "detail": (
                "Änderung vorgemerkt" if status == "queued"
                else "Änderung wird wiederhergestellt" if status == "running"
                else "Änderung erfolgreich verworfen" if status == "completed"
                else "Verwerfen fehlgeschlagen: " + str(row.get("error_message") or "Unbekannter Fehler")
            ),
            "href": "/events?job=" + str(row["job_id"]),
            "active": status in ("queued", "running"),
            "can_retry": status == "failed",
        })

    return {
        "operations": operations,
        "active_count": sum(1 for item in operations if item["active"]),
    }
