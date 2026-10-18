from __future__ import annotations

from app.root_operations import protect, validate_active_roots


from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import json
import uuid

from app.database import database_connection
from app.sort_apply import (
    CONFIRMATION_PHRASE,
    SortApplyError,
    execute_sort_run,
    get_sort_run,
    prepare_sort_run,
)


class OperationBatchError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_details(raw: Any) -> dict[str, Any]:
    try:
        value = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def create_apply_batch(
    database_path: Path,
    items: list[dict[str, Any]],
    *,
    confirmation_phrase: str,
) -> dict[str, Any]:
    if str(confirmation_phrase) != CONFIRMATION_PHRASE:
        raise OperationBatchError("Die ausdrückliche Bestätigung für die Sortierung fehlt.")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        job_id = str(item.get("job_id") or "").strip()
        event_id = str(item.get("event_id") or "").strip()
        plan_token = str(item.get("plan_token") or "").strip()
        if not job_id or not event_id or not plan_token:
            raise OperationBatchError("Ein Batch-Eintrag ist unvollständig.")
        if event_id in seen:
            raise OperationBatchError("Ein Ereignis wurde im Batch doppelt ausgewählt.")
        seen.add(event_id)
        normalized.append({"job_id": job_id, "event_id": event_id, "plan_token": plan_token})
    if not normalized:
        raise OperationBatchError("Keine Ereignisse zum Anwenden ausgewählt.")

    batch_id = "BATCH_" + uuid.uuid4().hex.upper()
    now = _now()
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for item in normalized:
            event = connection.execute(
                """SELECT id,status,applied_at,archived_at
                   FROM events WHERE id=? AND parent_event_id IS NULL""",
                (item["event_id"],),
            ).fetchone()
            if event is None:
                raise OperationBatchError("Mindestens ein Ereignis wurde nicht gefunden.")
            if str(event["status"]) not in {"draft", "planned"} or event["applied_at"] is not None or event["archived_at"] is not None:
                raise OperationBatchError("Mindestens ein ausgewähltes Ereignis ist nicht mehr anwendbar.")

        connection.execute(
            """INSERT INTO operation_batches(
                   id,batch_kind,status,item_count,completed_item_count,current_index,
                   error_message,details_json,created_at,started_at,updated_at,completed_at)
               VALUES (?,'apply_events','queued',?,0,0,NULL,?,?,NULL,?,NULL)""",
            (
                batch_id,
                len(normalized),
                json.dumps({"event_ids": [item["event_id"] for item in normalized]}, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        connection.executemany(
            """INSERT INTO operation_batch_items(
                   batch_id,sequence_number,job_id,event_id,plan_token,
                   sort_run_id,sort_run_job_id,status,error_message,
                   created_at,updated_at,completed_at)
               VALUES (?,?,?,?,?,NULL,NULL,'pending',NULL,?,?,NULL)""",
            [
                (batch_id, index, item["job_id"], item["event_id"], item["plan_token"], now, now)
                for index, item in enumerate(normalized, start=1)
            ],
        )
    return get_operation_batch(database_path, batch_id)


def _batch_row(database_path: Path, batch_id: str) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        row = connection.execute("SELECT * FROM operation_batches WHERE id=?", (str(batch_id),)).fetchone()
    if row is None:
        raise OperationBatchError("Vorgang wurde nicht gefunden.")
    result = dict(row)
    result["details"] = _load_details(result.pop("details_json", None))
    return result


def get_operation_batch(database_path: Path, batch_id: str) -> dict[str, Any]:
    batch = _batch_row(database_path, batch_id)
    with database_connection(database_path) as connection:
        items = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM operation_batch_items WHERE batch_id=? ORDER BY sequence_number",
                (str(batch_id),),
            ).fetchall()
        ]

    current_run = None
    running_item = next((item for item in items if str(item.get("status")) == "running"), None)
    if running_item and running_item.get("sort_run_id"):
        run_job = str(running_item.get("sort_run_job_id") or running_item.get("job_id") or "")
        current_run = get_sort_run(database_path, run_job, str(running_item["sort_run_id"]))

    completed = sum(1 for item in items if str(item.get("status")) == "applied")
    current_fraction = 0.0
    if current_run is not None and not bool(current_run.get("terminal")):
        current_fraction = float(current_run.get("progress_percent") or 0) / 100.0
    elif running_item is not None and current_run is not None and str(current_run.get("status")) == "applied":
        current_fraction = 1.0
    total = max(1, int(batch.get("item_count") or len(items) or 1))
    progress = min(100, round((completed + current_fraction) / total * 100))

    batch["items"] = items
    batch["current_run"] = current_run
    batch["completed_item_count"] = completed
    batch["progress_percent"] = 100 if str(batch.get("status")) == "applied" else progress
    batch["terminal"] = str(batch.get("status")) in {"applied", "failed"}
    return batch


def list_active_operation_batches(database_path: Path) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        ids = [
            str(row["id"])
            for row in connection.execute(
                """SELECT id FROM operation_batches
                   WHERE status IN ('queued','running','interrupted')
                   ORDER BY created_at"""
            ).fetchall()
        ]
    return [get_operation_batch(database_path, batch_id) for batch_id in ids]


def _set_batch_failed(database_path: Path, batch_id: str, message: str, *, item_id: int | None = None) -> None:
    now = _now()
    with database_connection(database_path) as connection:
        if item_id is not None:
            connection.execute(
                """UPDATE operation_batch_items
                   SET status='failed',error_message=?,updated_at=?,completed_at=?
                   WHERE id=?""",
                (str(message), now, now, int(item_id)),
            )
        connection.execute(
            """UPDATE operation_batches
               SET status='failed',error_message=?,updated_at=?,completed_at=?
               WHERE id=?""",
            (str(message), now, now, str(batch_id)),
        )


@protect(workspace_arg='workspace_path', database_arg='database_path', kind='batch', error_type=RuntimeError)
def execute_apply_batch(
    database_path: Path,
    batch_id: str,
    workspace_path: Path,
    *,
    after_run: Callable[[], None] | None = None,
) -> dict[str, Any]:
    now = _now()
    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """UPDATE operation_batches
               SET status='running',started_at=COALESCE(started_at,?),
                   error_message=NULL,updated_at=?
               WHERE id=? AND status IN ('queued','running','interrupted')""",
            (now, now, str(batch_id)),
        )
        if int(cursor.rowcount or 0) != 1:
            batch = get_operation_batch(database_path, batch_id)
            if bool(batch.get("terminal")):
                return batch
            raise OperationBatchError("Batch besitzt keinen ausführbaren Zustand.")

    with database_connection(database_path) as connection:
        items = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM operation_batch_items WHERE batch_id=? ORDER BY sequence_number",
                (str(batch_id),),
            ).fetchall()
        ]

    for item in items:
        if str(item.get("status")) == "applied":
            continue
        item_id = int(item["id"])
        sequence = int(item["sequence_number"])
        try:
            if str(item.get("status")) == "running" and item.get("sort_run_id"):
                run_job = str(item.get("sort_run_job_id") or item.get("job_id") or "")
                prior_run = get_sort_run(database_path, run_job, str(item["sort_run_id"]))
                if prior_run is not None and str(prior_run.get("status")) == "applied":
                    with database_connection(database_path) as connection:
                        connection.execute(
                            """UPDATE operation_batch_items
                               SET status='applied',error_message=NULL,updated_at=?,completed_at=?
                               WHERE id=?""",
                            (_now(), _now(), item_id),
                        )
                    if after_run is not None:
                        after_run()
                    continue
                if prior_run is not None and not bool(prior_run.get("terminal")):
                    raise OperationBatchError("Ein Sortierlauf dieses Batches ist bereits aktiv.")
                if prior_run is not None and str(prior_run.get("status")) not in {"rolled_back"}:
                    raise OperationBatchError(
                        str(prior_run.get("error_message") or "Vorheriger Sortierlauf des Batches wurde nicht sicher abgeschlossen.")
                    )

            run = prepare_sort_run(
                database_path,
                str(item["job_id"]),
                str(item["event_id"]),
                workspace_path,
                expected_plan_token=str(item["plan_token"]),
                confirmation_phrase=CONFIRMATION_PHRASE,
            )
            with database_connection(database_path) as connection:
                connection.execute(
                    """UPDATE operation_batch_items
                       SET status='running',sort_run_id=?,sort_run_job_id=?,
                           error_message=NULL,updated_at=? WHERE id=?""",
                    (str(run["id"]), str(run["job_id"]), _now(), item_id),
                )
                connection.execute(
                    "UPDATE operation_batches SET current_index=?,updated_at=? WHERE id=?",
                    (sequence, _now(), str(batch_id)),
                )

            execute_sort_run(database_path, str(run["id"]), workspace_path)
            finished = get_sort_run(database_path, str(run["job_id"]), str(run["id"]))
            if finished is None or str(finished.get("status")) != "applied":
                raise OperationBatchError(
                    str((finished or {}).get("error_message") or "Sortierlauf wurde nicht angewendet.")
                )

            with database_connection(database_path) as connection:
                connection.execute(
                    """UPDATE operation_batch_items
                       SET status='applied',error_message=NULL,updated_at=?,completed_at=?
                       WHERE id=?""",
                    (_now(), _now(), item_id),
                )
                completed = connection.execute(
                    "SELECT COUNT(*) FROM operation_batch_items WHERE batch_id=? AND status='applied'",
                    (str(batch_id),),
                ).fetchone()[0]
                connection.execute(
                    "UPDATE operation_batches SET completed_item_count=?,updated_at=? WHERE id=?",
                    (int(completed or 0), _now(), str(batch_id)),
                )
            if after_run is not None:
                after_run()
        except Exception as error:
            _set_batch_failed(database_path, batch_id, str(error), item_id=item_id)
            if isinstance(error, (OperationBatchError, SortApplyError)):
                raise
            raise OperationBatchError(str(error)) from error

    completed_at = _now()
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE operation_batches
               SET status='applied',completed_item_count=item_count,current_index=item_count,
                   error_message=NULL,updated_at=?,completed_at=? WHERE id=?""",
            (completed_at, completed_at, str(batch_id)),
        )
    return get_operation_batch(database_path, batch_id)


def recover_operation_batches(database_path: Path) -> list[str]:
    resumable: list[str] = []
    with database_connection(database_path) as connection:
        batch_ids = [
            str(row["id"])
            for row in connection.execute(
                """SELECT id FROM operation_batches
                   WHERE status IN ('queued','running','interrupted')
                   ORDER BY created_at"""
            ).fetchall()
        ]

    for batch_id in batch_ids:
        blocked_message = ""
        with database_connection(database_path) as connection:
            items = [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM operation_batch_items WHERE batch_id=? ORDER BY sequence_number",
                    (batch_id,),
                ).fetchall()
            ]
        for item in items:
            if str(item.get("status")) != "running":
                continue
            run_id = str(item.get("sort_run_id") or "")
            run_job = str(item.get("sort_run_job_id") or item.get("job_id") or "")
            run = get_sort_run(database_path, run_job, run_id) if run_id else None
            if run is not None and str(run.get("status")) == "applied":
                with database_connection(database_path) as connection:
                    connection.execute(
                        """UPDATE operation_batch_items
                           SET status='applied',updated_at=?,completed_at=? WHERE id=?""",
                        (_now(), _now(), int(item["id"])),
                    )
                continue
            if run is None or str(run.get("status")) == "rolled_back":
                with database_connection(database_path) as connection:
                    connection.execute(
                        """UPDATE operation_batch_items
                           SET status='pending',sort_run_id=NULL,sort_run_job_id=NULL,
                               error_message=NULL,updated_at=?,completed_at=NULL WHERE id=?""",
                        (_now(), int(item["id"])),
                    )
                continue
            blocked_message = str(
                run.get("error_message") or run.get("phase")
                or "Unterbrochener Sortierlauf ist nicht automatisch fortsetzbar."
            )
            break

        if blocked_message:
            _set_batch_failed(database_path, batch_id, blocked_message)
            continue

        with database_connection(database_path) as connection:
            completed = int(connection.execute(
                "SELECT COUNT(*) FROM operation_batch_items WHERE batch_id=? AND status='applied'",
                (batch_id,),
            ).fetchone()[0] or 0)
            total = int(connection.execute(
                "SELECT item_count FROM operation_batches WHERE id=?",
                (batch_id,),
            ).fetchone()[0] or 0)
            if total > 0 and completed >= total:
                now = _now()
                connection.execute(
                    """UPDATE operation_batches
                       SET status='applied',completed_item_count=?,current_index=?,
                           updated_at=?,completed_at=? WHERE id=?""",
                    (completed, total, now, now, batch_id),
                )
            else:
                connection.execute(
                    """UPDATE operation_batches
                       SET status='queued',completed_item_count=?,error_message=NULL,
                           updated_at=?,completed_at=NULL WHERE id=?""",
                    (completed, _now(), batch_id),
                )
                resumable.append(batch_id)
    return resumable
