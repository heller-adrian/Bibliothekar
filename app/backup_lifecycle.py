from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json

from app.database import database_connection
from app.sqlite_retry import idempotent_write


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@idempotent_write
def upsert_backup_lifecycle(
    database_path: Path,
    *,
    job_id: str,
    status: str,
    source_path: str | None = None,
    temporary_backup_path: str | None = None,
    workspace_path: str | None = None,
    protocol_path: str | None = None,
    snapshot_backend: str | None = None,
    snapshot_reference: str | None = None,
    file_count: int | None = None,
    total_size_bytes: int | None = None,
    moved_file_count: int | None = None,
    temporary_backup_removed: bool | None = None,
    details: dict[str, Any] | None = None,
    error_message: str | None = None,
    completed: bool = False,
) -> dict[str, Any]:
    now = _now()
    details_json = (
        json.dumps(
            details,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if details is not None
        else None
    )

    with database_connection(database_path) as connection:
        existing = connection.execute(
            """
            SELECT job_id
            FROM backup_lifecycles
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

        if existing is None:
            connection.execute(
                """
                INSERT INTO backup_lifecycles (
                    job_id,
                    status,
                    source_path,
                    temporary_backup_path,
                    workspace_path,
                    protocol_path,
                    snapshot_backend,
                    snapshot_reference,
                    file_count,
                    total_size_bytes,
                    moved_file_count,
                    temporary_backup_removed,
                    details_json,
                    error_message,
                    created_at,
                    updated_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    status,
                    source_path,
                    temporary_backup_path,
                    workspace_path,
                    protocol_path,
                    snapshot_backend,
                    snapshot_reference,
                    int(file_count or 0),
                    int(total_size_bytes or 0),
                    int(moved_file_count or 0),
                    int(bool(temporary_backup_removed)),
                    details_json,
                    error_message,
                    now,
                    now,
                    now if completed else None,
                ),
            )
        else:
            fields = [
                "status = ?",
                "updated_at = ?",
            ]
            values: list[Any] = [status, now]

            optional_values = {
                "source_path": source_path,
                "temporary_backup_path": temporary_backup_path,
                "workspace_path": workspace_path,
                "protocol_path": protocol_path,
                "snapshot_backend": snapshot_backend,
                "snapshot_reference": snapshot_reference,
                "file_count": file_count,
                "total_size_bytes": total_size_bytes,
                "moved_file_count": moved_file_count,
                "details_json": details_json,
                "error_message": error_message,
            }

            for column, value in optional_values.items():
                if value is None:
                    continue
                fields.append(f"{column} = ?")
                values.append(value)

            if temporary_backup_removed is not None:
                fields.append("temporary_backup_removed = ?")
                values.append(int(bool(temporary_backup_removed)))

            if completed:
                fields.append("completed_at = ?")
                values.append(now)

            values.append(job_id)

            connection.execute(
                f"""
                UPDATE backup_lifecycles
                SET {', '.join(fields)}
                WHERE job_id = ?
                """,
                values,
            )

        row = connection.execute(
            """
            SELECT *
            FROM backup_lifecycles
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        raise RuntimeError("Sicherungslebenszyklus konnte nicht gespeichert werden.")

    result = dict(row)
    raw_details = result.pop("details_json", None)
    result["details"] = json.loads(raw_details) if raw_details else None
    result["temporary_backup_removed"] = bool(
        result.get("temporary_backup_removed")
    )
    return result


def list_backup_lifecycles(
    database_path: Path,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(1, min(int(limit), 500))

    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                lifecycle.*,
                jobs.kind,
                jobs.operation,
                jobs.state AS job_state,
                jobs.stage AS job_stage,
                jobs.progress_current,
                jobs.progress_total,
                jobs.progress_message,
                jobs.created_at AS job_created_at
            FROM backup_lifecycles AS lifecycle
            JOIN jobs
                ON jobs.id = lifecycle.job_id
            ORDER BY lifecycle.updated_at DESC, lifecycle.job_id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    results: list[dict[str, Any]] = []

    for row in rows:
        result = dict(row)
        raw_details = result.pop("details_json", None)
        result["details"] = json.loads(raw_details) if raw_details else None
        result["temporary_backup_removed"] = bool(
            result.get("temporary_backup_removed")
        )
        results.append(result)

    return results
