"""Read-only, lightweight overview of server-side work for the desktop status dock.

No task is started or modified here. The three independent workflows continue
to run in their existing back-end workers and keep their existing safety rules.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timedelta, timezone
from sqlite3 import OperationalError
from typing import Any

from app.database import database_connection
from app.background_mutation_cancel import list_visible
from app.operation_batches import get_operation_batch
from app.sort_apply import get_sort_run
from app.ssd_release_background import visible_release_tasks


_IMPORT_STATES = (
    "queued", "copying", "verifying", "backup_verified",
    "analyzing_metadata", "organizing",
)
_SORT_STATES = ("queued", "verifying", "moving", "finalizing", "rolling_back")
_BATCH_STATES = ("queued", "running", "interrupted")


def current_activity(library_database: Path, global_import_database: Path) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    # Keep recently completed operations visible long enough for a 2.5s UI poll.
    recent_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()

    # Camera and folder imports are globally managed in the main DB, even
    # while a secondary library is selected in the browser.
    with database_connection(global_import_database) as connection:
        sql = """SELECT id,state,stage,source_volume_label,progress_current,
                      progress_total,error_message,operation,updated_at
               FROM jobs
               WHERE operation IN (
                   'folder_import','metadata_multiple_import',
                   'metadata_general_import','trash_import'
               )
                 AND (
                   state IN ('queued','copying','verifying','backup_verified',
                             'analyzing_metadata','organizing')
                   OR (operation='trash_import'
                       AND (state IN ('failed','interrupted')
                         OR (state='completed' AND updated_at>=?)))
                 )
               ORDER BY updated_at DESC,id DESC LIMIT 12"""
        try:
            rows=connection.execute(sql,(recent_cutoff,)).fetchall()
        except (OperationalError,TypeError) as error:
            # Legacy QA databases and read-only adapters can lack the newer
            # progress fields or accept only a single SQL string argument.
            if isinstance(error,OperationalError) and "no such column" not in str(error):
                raise
            rows=connection.execute(
                """SELECT id,state,stage,source_volume_label,operation
                   FROM jobs
                   WHERE operation IN (
                       'folder_import','metadata_multiple_import',
                       'metadata_general_import'
                   )
                   AND state IN ('queued','copying','verifying','backup_verified',
                                 'analyzing_metadata','organizing')
                   ORDER BY created_at DESC,id DESC LIMIT 8"""
            ).fetchall()
    for row in rows:
        status=str(row["state"])
        is_trash=str(row["operation"])=="trash_import"
        fields=set(row.keys()) if hasattr(row,"keys") else set(dict(row))
        total=int(row["progress_total"] or 0) if "progress_total" in fields else 0
        current=int(row["progress_current"] or 0) if "progress_current" in fields else 0
        if is_trash:
            detail=(
                "Wiederherstellung fehlgeschlagen: "+str(row["error_message"] or "Unbekannter Fehler")
                if status in {"failed","interrupted"}
                else "Wiederherstellung abgeschlossen"
                if status=="completed"
                else "Wiederherstellung wartet auf Verarbeitung"
                if status=="queued"
                else "Dateien werden im Hintergrund wiederhergestellt"
            )
        else:
            detail="Import läuft im Hintergrund" if status!="queued" else "Import wartet auf Verarbeitung"
        operations.append({
            "kind":"trash_restore" if is_trash else "import",
            "revision":status+":"+str(row["updated_at"] or "") if "updated_at" in fields else status+":",
            "id":str(row["id"]),
            "status":status,
            "label":str(row["source_volume_label"] or ("Aus Papierkorb" if is_trash else "Import")),
            "detail":detail,
            "href":"/trash" if is_trash else "/",
            "active":status in _IMPORT_STATES,
            "progress_percent":min(100,round(current*100/total)) if total>0 else None,
        })

    with database_connection(library_database) as connection:
        # SELECT * tolerates old SQLite schemas without completed_at/updated_at
        # and legacy lightweight QA connections accepting only execute(sql).
        batch_candidates = connection.execute(
            """SELECT * FROM operation_batches
               WHERE status IN ('queued','running','interrupted','applied','failed')
               ORDER BY created_at DESC,id DESC LIMIT 12"""
        ).fetchall()
        batches = [
            row for row in batch_candidates
            if str(row["status"]) in _BATCH_STATES or str(row["status"]) == "failed" or str(
                dict(row).get("completed_at") or dict(row).get("updated_at") or ""
            ) >= recent_cutoff
        ]
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
        # Reuse the authoritative child-run-aware batch progress.
        try:
            batch_progress = get_operation_batch(library_database, str(row["id"]))
            progress_percent = batch_progress["progress_percent"]
        except OperationalError as error:
            # Older databases / read-only QA snapshots can have a legacy
            # batch-item layout with no batch_id column. Show the durable
            # completed/item count until the full run schema is available.
            if "no such column: batch_id" not in str(error):
                raise
            total = max(1, int(row["item_count"] or 0))
            progress_percent = min(
                100, round(100 * int(row["completed_item_count"] or 0) / total)
            )
        operations.append({
            "progress_percent": progress_percent,
            "kind": "apply",
            "id": str(row["id"]),
            "revision": str(row["status"])+":"+str(dict(row).get("updated_at") or ""),
            "status": str(row["status"]),
            "label": "Ereignisse anwenden",
            "detail": f"{int(row['completed_item_count'] or 0)} von {int(row['item_count'] or 0)} Ereignissen verarbeitet"
                if row["status"] != "interrupted" else "Sortierung unterbrochen – Prüfung erforderlich",
            "href": "/events",
            "active": row["status"] in ("queued", "running"),
        })

    for row in runs:
        sort_run = get_sort_run(library_database, str(row["job_id"]), str(row["id"]))
        operations.append({
            "progress_percent": sort_run["progress_percent"] if sort_run is not None else None,
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
            "revision": status+":"+str(row.get("updated_at") or ""),
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

    try:
        releases = visible_release_tasks(library_database)
    except OperationalError as error:
        if "no such table: ssd_release_tasks" not in str(error):
            raise
        releases = []
    for task in releases:
        status = str(task["status"])
        operations.append({
            "kind": "release",
            "id": str(task["id"]),
            "revision": status+":"+str(task.get("updated_at") or ""),
            "status": status,
            "label": "Arbeitsbereich freigeben",
            "detail": (
                "Freigabe wartet auf Verarbeitung" if status == "queued"
                else "Freigabe läuft; Archiv und SSD werden geprüft"
                if status == "running"
                else "Freigabe abgeschlossen" if status == "completed"
                else "Freigabe angehalten: " + str(task.get("error_message") or "Unbekannter Fehler")
            ),
            "href": "/archive",
            "progress_percent": task.get("progress_percent"),
            "active": status in ("queued", "running"),
        })

    if all(item["active"] for item in operations):
        return {"operations": operations, "active_count": len(operations)}
    # Nur exakt dieser beendete Versuch wird ausgeblendet. Nach einem Retry
    # erzeugt der neue Status/Zeitstempel einen anderen Sichtbarkeitsschluessel.
    try:
        with database_connection(global_import_database) as connection:
            hidden = {
                (str(row["kind"]), str(row["operation_id"]), str(row["revision"]))
                for row in connection.execute(
                    "SELECT kind,operation_id,revision FROM background_activity_dismissals"
                )
            }
    except OperationalError as error:
        if "no such table: background_activity_dismissals" not in str(error):
            raise
        hidden = set()
    operations = [
        item for item in operations
        if item["active"] or (
            str(item["kind"]), str(item["id"]), str(item.get("revision") or "")
        ) not in hidden
    ]
    return {
        "operations": operations,
        "active_count": sum(1 for item in operations if item["active"]),
    }


def clear_finished_activity(library_database: Path, global_import_database: Path) -> dict[str, int]:
    """Only hide terminal operations; never delete their records or media."""
    terminal: set[tuple[str, str, str]] = set()
    with database_connection(global_import_database) as connection:
        for row in connection.execute(
            """SELECT id,state,updated_at FROM jobs
               WHERE operation='trash_import'
                 AND state IN ('completed','failed','interrupted')"""
        ):
            terminal.add((
                "trash_restore", str(row["id"]),
                str(row["state"])+":"+str(row["updated_at"] or ""),
            ))
    with database_connection(library_database) as connection:
        queries = (
            ("apply", """SELECT id,status,updated_at FROM operation_batches
                         WHERE status IN ('applied','failed','interrupted')"""),
            ("cancel", """SELECT id,status,updated_at FROM background_mutation_cancellations
                          WHERE status IN ('completed','failed')"""),
            ("release", """SELECT id,status,updated_at FROM ssd_release_tasks
                           WHERE status IN ('completed','failed')"""),
        )
        for kind, sql in queries:
            try:
                rows = connection.execute(sql).fetchall()
            except OperationalError as error:
                if "no such table" not in str(error):
                    raise
                continue
            for row in rows:
                terminal.add((
                    kind, str(row["id"]),
                    str(row["status"])+":"+str(row["updated_at"] or ""),
                ))
    with database_connection(global_import_database) as connection:
        connection.executemany(
            """INSERT OR IGNORE INTO background_activity_dismissals
               (kind,operation_id,revision) VALUES(?,?,?)""",
            sorted(terminal),
        )
    return {"cleared": len(terminal)}
