"""BA-01: durable SQLite -> portable event.json repair outbox.

Only an applied event with existing physical workspace directory is repaired.
Original photographs and archive directories are never moved or deleted here.
A successful document write is idempotent; the same event revision can be
replayed after a crash between atomic os.replace and SQLite acknowledgement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from app.database import database_connection
from app.event_document import (
    build_event_document_from_db,
    event_document_path,
    write_event_document,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def queue_event_document_sync(
    connection: sqlite3.Connection, job_id: str, event_id: str,
    revision: int, *, now: str | None = None,
) -> None:
    """Call in the SAME SQLite transaction as the event revision update."""
    stamp = now or _now()
    connection.execute(
        """INSERT INTO event_document_sync_tasks
               (event_id, job_id, revision, status, error_message,
                attempts, created_at, updated_at, completed_at)
           VALUES (?, ?, ?, 'pending', '', 0, ?, ?, NULL)
           ON CONFLICT(event_id) DO UPDATE SET
               job_id=excluded.job_id,
               revision=excluded.revision,
               status='pending',
               error_message='',
               attempts=0,
               updated_at=excluded.updated_at,
               completed_at=NULL""",
        (event_id, job_id, int(revision), stamp, stamp),
    )


def sync_event_document_task(
    database_path: Path,
    workspace_root: Path,
    event_id: str,
    *, app_version: str | None = None,
) -> dict[str, object]:
    """Attempt one durable repair, serialized against concurrent event edits.

    Holding BEGIN IMMEDIATE across document rendering and atomic replacement
    prevents stale outbox writers from overwriting newer event revisions.
    A retryable error is committed as 'blocked', never treated as completed.
    """
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute(
            """SELECT job_id, revision, status FROM event_document_sync_tasks
               WHERE event_id=?""",
            (event_id,),
        ).fetchone()
        if task is None:
            return {"status": "absent"}
        if str(task["status"]) == "completed":
            return {"status": "completed"}

        error_message = ""
        document_path: Path | None = None
        try:
            event = connection.execute(
                """SELECT status, start_datetime, folder_name, revision
                   FROM events WHERE id=? AND parent_event_id IS NULL
                     AND job_id=?""",
                (event_id, str(task["job_id"])),
            ).fetchone()
            if event is None or str(event["status"]) != "applied":
                raise ValueError(
                    "Das Ereignis ist nicht mehr im angewendeten Arbeitsbereich."
                )
            if int(event["revision"] or 1) != int(task["revision"]):
                raise ValueError(
                    "Die Revision der Dokumentaufgabe stimmt nicht mit dem Ereignis überein."
                )
            document = build_event_document_from_db(
                database_path, workspace_root, str(task["job_id"]),
                event_id, transaction_connection=connection,
            )
            if document is None:
                raise ValueError(
                    "Das angewendete Ereignis besitzt keine vollständige Dateizuweisung."
                )
            ev = document["event"]
            document_path = event_document_path(
                workspace_root, str(ev["start_date"])[:4],
                str(ev["folder_name"]),
            )
            if not document_path.parent.is_dir():
                # Never create an empty orphan event folder for a missing
                # or not-yet-reconciled applied event.
                raise ValueError(
                    "Der physische Ereignisordner fehlt; Dokument nicht geschrieben."
                )
            write_event_document(workspace_root, document, app_version=app_version)
        except Exception as error:
            error_message = str(error)[:800] or type(error).__name__

        stamp = _now()
        if error_message:
            connection.execute(
                """UPDATE event_document_sync_tasks
                   SET status='blocked', error_message=?,
                       attempts=attempts+1, updated_at=?
                   WHERE event_id=? AND revision=?""",
                (error_message, stamp, event_id, int(task["revision"])),
            )
            return {
                "status": "blocked",
                "revision": int(task["revision"]),
                "error": error_message,
            }

        connection.execute(
            """UPDATE event_document_sync_tasks
               SET status='completed', error_message='',
                   attempts=attempts+1, updated_at=?, completed_at=?
               WHERE event_id=? AND revision=?""",
            (stamp, stamp, event_id, int(task["revision"])),
        )
        return {
            "status": "completed",
            "revision": int(task["revision"]),
            "path": str(document_path),
        }


def recover_event_document_sync_tasks(
    database_path: Path, workspace_root: Path,
    *, app_version: str | None = None,
    limit: int = 500,
) -> dict[str, int]:
    """Retry outstanding writes after startup, without touching media files."""
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT event_id FROM event_document_sync_tasks
               WHERE status IN ('pending', 'blocked')
               ORDER BY updated_at, event_id LIMIT ?""",
            (max(1, int(limit)),),
        ).fetchall()
    result = {"recovered": 0, "blocked": 0}
    for row in rows:
        try:
            current = sync_event_document_task(
                database_path, workspace_root, str(row["event_id"]),
                app_version=app_version,
            )
            if current["status"] == "completed":
                result["recovered"] += 1
            else:
                result["blocked"] += 1
        except Exception:
            # A real database failure cannot be marked "completed".
            result["blocked"] += 1
    return result
