"""Durable, restartable server-side release of a SHA-256-verified SSD event.

Tasks are claimed atomically by SQLite; the already journaled release_event_ssd
routine remains the sole owner of verification, unlink and final commit.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database import database_connection
from app.ssd_release import release_event_ssd


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def enqueue_release(db: Path, job_id: str, event_id: str) -> dict[str, Any]:
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        event = connection.execute(
            "SELECT status,resort_required FROM events WHERE id=? AND job_id=? AND parent_event_id IS NULL",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            raise ValueError("Das angegebene Hauptereignis existiert nicht.")
        if event["status"] not in ("applied", "archived") or int(event["resort_required"] or 0):
            raise ValueError("Nur vollständig angewendete Ereignisse dürfen freigegeben werden.")
        existing = connection.execute(
            """SELECT * FROM ssd_release_tasks
               WHERE event_id=? AND status IN ('queued','running')
               ORDER BY created_at DESC LIMIT 1""",
            (event_id,),
        ).fetchone()
        if existing:
            return dict(existing)
        from app.ssd_release import _latest_completed_release
        if _latest_completed_release(db, job_id, event_id) is not None:
            raise ValueError("Der Arbeitsbereich wurde für dieses Ereignis bereits freigegeben.")
        task_id = "REL_" + uuid.uuid4().hex
        now = _now()
        connection.execute(
            """INSERT INTO ssd_release_tasks
               (id,job_id,event_id,status,created_at,updated_at)
               VALUES(?,?,?,'queued',?,?)""",
            (task_id, job_id, event_id, now, now),
        )
        return dict(connection.execute(
            "SELECT * FROM ssd_release_tasks WHERE id=?", (task_id,)
        ).fetchone())


def recover_releases(db: Path) -> int:
    # A crashed process can never carry a running Python thread with it.
    # Partially completed deletions remain in event_ssd_release_files and are
    # handled idempotently by release_event_ssd on its next invocation.
    with database_connection(db) as connection:
        cur = connection.execute(
            """UPDATE ssd_release_tasks SET status='queued',updated_at=?
               WHERE status='running'""", (_now(),)
        )
        return int(cur.rowcount)


def claim_release(db: Path) -> dict[str, Any] | None:
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            """SELECT * FROM ssd_release_tasks WHERE status='queued'
               ORDER BY created_at,id LIMIT 1"""
        ).fetchone()
        if row is None:
            return None
        now = _now()
        connection.execute(
            """UPDATE ssd_release_tasks SET status='running',
               started_at=COALESCE(started_at,?),updated_at=? WHERE id=?""",
            (now, now, row["id"]),
        )
        return dict(row)


def process_release(db: Path, workspace: Path, archive: Path, task: dict[str, Any]) -> None:
    try:
        result = release_event_ssd(
            db, workspace, archive, str(task["job_id"]), str(task["event_id"])
        )
    except Exception as exc:
        with database_connection(db) as connection:
            connection.execute(
                """UPDATE ssd_release_tasks SET status='failed',
                   error_message=?,updated_at=?,finished_at=? WHERE id=?""",
                (str(exc), _now(), _now(), task["id"]),
            )
        return
    with database_connection(db) as connection:
        connection.execute(
            """UPDATE ssd_release_tasks SET status='completed',
               error_message=NULL,result_json=?,updated_at=?,finished_at=?
               WHERE id=?""",
            (json.dumps(result, ensure_ascii=False, default=str), _now(), _now(), task["id"]),
        )


def get_release_task(db: Path, job_id: str, event_id: str) -> dict[str, Any] | None:
    with database_connection(db) as connection:
        task = connection.execute(
            """SELECT * FROM ssd_release_tasks WHERE job_id=? AND event_id=?
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (job_id, event_id),
        ).fetchone()
        if task is None:
            return None
        row = dict(task)
        run = connection.execute(
            """SELECT id,status,file_count,verified_archive_count,
                      deleted_file_count
               FROM event_ssd_releases WHERE job_id=? AND event_id=?
               ORDER BY created_at DESC,id DESC LIMIT 1""",
            (job_id, event_id),
        ).fetchone()
    status = str(row["status"])
    if status == "completed":
        progress = 100
    elif status == "queued":
        progress = 0
    elif run is None:
        progress = 1 if status == "running" else None
    else:
        total = max(1, int(run["file_count"] or 0))
        run_status = str(run["status"])
        if run_status == "completed":
            progress = 99 if status == "running" else 100
        elif run_status in ("deleting", "finalizing"):
            progress = min(99, 55 + round(44 * int(run["deleted_file_count"] or 0) / total))
        else:
            progress = min(54, 5 + round(49 * int(run["verified_archive_count"] or 0) / total))
    row["progress_percent"] = progress
    row["result"] = json.loads(row["result_json"]) if row.get("result_json") else None
    return row


def visible_release_tasks(db: Path, limit: int = 8) -> list[dict[str, Any]]:
    with database_connection(db) as connection:
        rows = connection.execute(
            """SELECT job_id,event_id FROM ssd_release_tasks
               WHERE status IN ('queued','running','failed')
               ORDER BY created_at DESC LIMIT ?""", (limit,)
        ).fetchall()
    return [task for row in rows if (task := get_release_task(db, str(row["job_id"]), str(row["event_id"]))) is not None]
