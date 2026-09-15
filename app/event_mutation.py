"""Durable suspension state for structural event changes (0.17.0).

A mutation keeps a complete DB snapshot of the event graph of one import job
until the corresponding SSD reconciliation or manual archive workflow is
finished.  This deliberately favours recoverability over compactness: the
camera archive is never touched here and the snapshot contains only SQLite
rows related to event planning/assignment.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _rows(connection: Any, sql: str, args: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [dict(r) for r in connection.execute(sql, args).fetchall()]


def capture_job_event_state(connection: Any, job_id: str) -> dict[str, Any]:
    """Capture all mutable event-planning rows of one backup job."""
    event_ids = [
        str(r["id"]) for r in connection.execute(
            "SELECT id FROM events WHERE job_id=? ORDER BY id", (job_id,)
        ).fetchall()
    ]
    if event_ids:
        ph = ",".join("?" for _ in event_ids)
        assignments = _rows(
            connection,
            f"SELECT * FROM event_assignments WHERE event_id IN ({ph}) ORDER BY id",
            tuple(event_ids),
        )
        segments = _rows(
            connection,
            f"SELECT * FROM event_time_segments WHERE event_id IN ({ph}) ORDER BY id",
            tuple(event_ids),
        )
    else:
        assignments = []
        segments = []
    return {
        "events": _rows(connection, "SELECT * FROM events WHERE job_id=? ORDER BY CASE event_level WHEN 'parent' THEN 0 ELSE 1 END, id", (job_id,)),
        "event_assignments": assignments,
        "event_time_segments": segments,
        "event_reapply_removed_families": _rows(
            connection,
            "SELECT * FROM event_reapply_removed_families WHERE job_id=? ORDER BY event_id,family_id",
            (job_id,),
        ),
    }


def get_active_mutation(connection: Any, job_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        """SELECT * FROM event_mutations
           WHERE job_id=? AND status IN ('pending_reassignment','pending_apply','manual_archive')
           ORDER BY created_at DESC LIMIT 1""",
        (job_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def assert_no_active_mutation(connection: Any, job_id: str, *, event_id: str | None = None) -> None:
    active = get_active_mutation(connection, job_id)
    if active is None:
        return
    try:
        affected = set(json.loads(str(active.get("affected_event_ids_json") or "[]")))
    except Exception:
        affected = set()
    # A mutation intentionally serializes structural work for one imported
    # backup.  This avoids a second edit invalidating the saved rollback state.
    if event_id is None or not affected or event_id in affected:
        raise ValueError(
            "Für diese Sicherung ist bereits eine noch nicht abgeschlossene Ereignisänderung offen. "
            "Bitte die Änderung zuerst anwenden oder verwerfen."
        )
    raise ValueError(
        "In dieser Sicherung läuft bereits eine Ereignisänderung. "
        "Weitere strukturelle Änderungen sind bis zu deren Abschluss gesperrt."
    )


def begin_mutation(
    connection: Any,
    *,
    job_id: str,
    anchor_event_id: str,
    mutation_kind: str,
    affected_event_ids: list[str],
    original_state: dict[str, Any],
    status: str,
) -> str:
    mutation_id = "MUT_" + uuid.uuid4().hex.upper()
    now = _now()
    connection.execute(
        """INSERT INTO event_mutations(
               id,job_id,anchor_event_id,mutation_kind,status,
               affected_event_ids_json,original_state_json,target_state_json,
               created_at,updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            mutation_id, job_id, anchor_event_id, mutation_kind, status,
            json.dumps(sorted(set(affected_event_ids)), ensure_ascii=False, sort_keys=True),
            json.dumps(original_state, ensure_ascii=False, sort_keys=True),
            "{}", now, now,
        ),
    )
    return mutation_id


def set_mutation_target(connection: Any, mutation_id: str, target_state: dict[str, Any], *, status: str | None = None) -> None:
    now = _now()
    if status is None:
        connection.execute(
            "UPDATE event_mutations SET target_state_json=?,updated_at=? WHERE id=?",
            (json.dumps(target_state, ensure_ascii=False, sort_keys=True), now, mutation_id),
        )
    else:
        connection.execute(
            "UPDATE event_mutations SET target_state_json=?,status=?,updated_at=? WHERE id=?",
            (json.dumps(target_state, ensure_ascii=False, sort_keys=True), status, now, mutation_id),
        )


def mark_job_mutation_completed(connection: Any, job_id: str) -> None:
    now = _now()
    connection.execute(
        """UPDATE event_mutations SET status='completed',completed_at=?,updated_at=?
           WHERE job_id=? AND status IN ('pending_reassignment','pending_apply')""",
        (now, now, job_id),
    )



def maybe_complete_planned_cascade_after_initial_apply(connection: Any, job_id: str) -> None:
    """Complete a planned-cascade mutation once every affected root event is applied.

    Planned coordinated edits are durable/undoable until their first physical
    application.  Applying only one of several affected events must keep the
    mutation open so conflicting edits/deletes remain blocked.
    """
    active = get_active_mutation(connection, job_id)
    if active is None or str(active.get("mutation_kind") or "") != "cascade":
        return
    if str(active.get("status") or "") != "pending_apply":
        return
    # Only cascades that started while all affected root events were still
    # draft/planned belong to this completion path. Applied-event cascades are
    # completed by the verified workspace-reconcile flow instead.
    try:
        original = json.loads(str(active.get("original_state_json") or "{}"))
    except Exception:
        original = {}
    original_roots = {
        str(row.get("id")): str(row.get("status") or "")
        for row in (original.get("events") or [])
        if str(row.get("event_level") or "") == "parent"
    }
    try:
        affected = [str(v) for v in json.loads(str(active.get("affected_event_ids_json") or "[]"))]
    except Exception:
        affected = []
    if not affected:
        return
    if not all(original_roots.get(eid) in {"draft", "planned"} for eid in affected):
        return
    placeholders = ",".join("?" for _ in affected)
    rows = connection.execute(
        f"""SELECT id,status,applied_at FROM events
            WHERE job_id=? AND event_level='parent' AND id IN ({placeholders})""",
        (job_id, *affected),
    ).fetchall()
    if len(rows) != len(set(affected)):
        return
    if not all(str(row["status"]) == "applied" and row["applied_at"] is not None for row in rows):
        return
    now = _now()
    connection.execute(
        "UPDATE event_mutations SET status='completed',completed_at=?,updated_at=? WHERE id=?",
        (now, now, active["id"]),
    )


def advance_job_mutation_after_reassignment(connection: Any, job_id: str) -> None:
    """Switch pending_reassignment -> pending_apply when all targets exist."""
    active = get_active_mutation(connection, job_id)
    if active is None or active.get("status") != "pending_reassignment":
        return
    missing = connection.execute(
        """SELECT COUNT(*) FROM event_reapply_removed_families
           WHERE job_id=? AND target_event_id IS NULL""",
        (job_id,),
    ).fetchone()[0]
    if int(missing or 0) == 0:
        connection.execute(
            "UPDATE event_mutations SET status='pending_apply',updated_at=? WHERE id=?",
            (_now(), active["id"]),
        )


def _insert_dict_rows(connection: Any, table: str, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if not row:
            continue
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        connection.execute(
            f'INSERT INTO "{table}" ({",".join(cols)}) VALUES ({placeholders})',
            tuple(row[c] for c in cols),
        )


def cancel_mutation(connection: Any, mutation_id: str, job_id: str, *, workspace_path=None) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM event_mutations WHERE id=? AND job_id=?", (mutation_id, job_id)
    ).fetchone()
    if row is None:
        raise ValueError("Änderung wurde nicht gefunden.")
    if str(row["status"]) not in {"pending_reassignment", "pending_apply", "manual_archive"}:
        raise ValueError("Nur eine noch offene Änderung kann verworfen werden.")
    active_runs = connection.execute(
        """SELECT COUNT(*) FROM sort_runs WHERE job_id=? AND status IN
           ('queued','verifying','moving','finalizing','rolling_back','interrupted')""",
        (job_id,),
    ).fetchone()[0]
    if int(active_runs or 0):
        raise ValueError("Während eines aktiven Sortierlaufs kann die Änderung nicht verworfen werden.")
    try:
        state = json.loads(str(row["original_state_json"] or "{}"))
    except Exception as exc:
        raise ValueError("Der gespeicherte Ursprungszustand ist beschädigt.") from exc

    restored_file_count = 0
    if workspace_path is not None:
        from app.applied_neutralization import restore_neutralized_files
        restored_file_count = restore_neutralized_files(connection, workspace_path, row)

    event_ids = [str(r["id"]) for r in connection.execute(
        "SELECT id FROM events WHERE job_id=?", (job_id,)
    ).fetchall()]
    if event_ids:
        ph = ",".join("?" for _ in event_ids)
        connection.execute(f"DELETE FROM event_assignments WHERE event_id IN ({ph})", tuple(event_ids))
        connection.execute(f"DELETE FROM event_time_segments WHERE event_id IN ({ph})", tuple(event_ids))
    connection.execute("DELETE FROM event_reapply_removed_families WHERE job_id=?", (job_id,))
    connection.execute("DELETE FROM events WHERE job_id=?", (job_id,))

    _insert_dict_rows(connection, "events", list(state.get("events") or []))
    _insert_dict_rows(connection, "event_assignments", list(state.get("event_assignments") or []))
    _insert_dict_rows(connection, "event_time_segments", list(state.get("event_time_segments") or []))
    _insert_dict_rows(connection, "event_reapply_removed_families", list(state.get("event_reapply_removed_families") or []))

    now = _now()
    connection.execute(
        "UPDATE event_mutations SET status='cancelled',cancelled_at=?,updated_at=? WHERE id=?",
        (now, now, mutation_id),
    )
    connection.execute(
        """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
           VALUES (?,'event_mutation_cancelled','event_mutation',?,?,?)""",
        (job_id, mutation_id, json.dumps({"anchor_event_id": row["anchor_event_id"]}, sort_keys=True), now),
    )
    return {"status": "cancelled", "mutation_id": mutation_id, "job_id": job_id, "restored_file_count": restored_file_count}
