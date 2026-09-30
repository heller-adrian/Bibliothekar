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
    layouts = (
        _rows(
            connection,
            f"SELECT * FROM event_folder_layouts WHERE event_id IN ({ph}) ORDER BY event_id",
            tuple(event_ids),
        )
        if event_ids else []
    )
    return {
        "events": _rows(connection, "SELECT * FROM events WHERE job_id=? ORDER BY CASE event_level WHEN 'parent' THEN 0 ELSE 1 END, id", (job_id,)),
        "event_assignments": assignments,
        "event_time_segments": segments,
        "event_folder_layouts": layouts,
        "event_reapply_removed_families": (
            _rows(
                connection,
                f"""SELECT * FROM event_reapply_removed_families
                    WHERE event_id IN ({ph}) OR target_event_id IN ({ph})
                    ORDER BY event_id,family_id""",
                tuple(event_ids) + tuple(event_ids),
            )
            if event_ids else []
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
           WHERE event_id=? AND target_event_id IS NULL""",
        (str(active.get("anchor_event_id") or ""),),
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



def _update_dict_row(connection: Any, table: str, row: dict[str, Any], *, key: str = "id") -> None:
    """Restore one existing row without deleting its identity/FK dependants."""
    columns = [name for name in row.keys() if name != key]
    if not columns:
        return
    assignments = ",".join(f'"{name}"=?' for name in columns)
    connection.execute(
        f'UPDATE "{table}" SET {assignments} WHERE "{key}"=?',
        tuple(row[name] for name in columns) + (row[key],),
    )


def _root_id_map(events: list[dict[str, Any]]) -> dict[str, str]:
    """Map every root/child event id in a captured state to its root id."""
    result: dict[str, str] = {}
    for event in events:
        event_id = str(event.get("id") or "")
        if not event_id:
            continue
        parent = str(event.get("parent_event_id") or "")
        result[event_id] = parent or event_id
    return result


def _state_bundle(state: dict[str, Any], root_id: str) -> dict[str, Any]:
    """Canonical mutable event-graph bundle for one root event."""
    events = list(state.get("events") or [])
    root_map = _root_id_map(events)
    graph_ids = {event_id for event_id, root in root_map.items() if root == root_id}

    def rows_for(key: str, predicate) -> list[dict[str, Any]]:
        rows = [dict(row) for row in (state.get(key) or []) if predicate(row)]
        return sorted(rows, key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True, default=str))

    return {
        "events": rows_for("events", lambda row: str(row.get("id") or "") in graph_ids),
        "event_assignments": rows_for(
            "event_assignments",
            lambda row: str(row.get("event_id") or "") in graph_ids,
        ),
        "event_time_segments": rows_for(
            "event_time_segments",
            lambda row: str(row.get("event_id") or "") in graph_ids,
        ),
        "event_folder_layouts": rows_for(
            "event_folder_layouts",
            lambda row: str(row.get("event_id") or "") == root_id,
        ),
        "event_reapply_removed_families": rows_for(
            "event_reapply_removed_families",
            lambda row: str(row.get("event_id") or "") == root_id,
        ),
    }


def _changed_root_ids(original: dict[str, Any], current: dict[str, Any]) -> set[str]:
    original_roots = {
        str(row.get("id"))
        for row in (original.get("events") or [])
        if not row.get("parent_event_id")
    }
    current_roots = {
        str(row.get("id"))
        for row in (current.get("events") or [])
        if not row.get("parent_event_id")
    }
    result: set[str] = set()
    for root_id in original_roots | current_roots:
        if _state_bundle(original, root_id) != _state_bundle(current, root_id):
            result.add(root_id)
    return result

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

    # 0.24.1 / A04:
    # Never delete/recreate the complete job graph. Existing root-event rows are
    # referenced by durable sort/archive evidence with ON DELETE CASCADE. A
    # wholesale restore therefore destroyed independent history. Instead compare
    # the live mutable graph with the captured original state and restore only
    # roots that this mutation actually changed. Existing root identities are
    # updated in place, so unrelated FK dependants survive untouched.
    current_state = capture_job_event_state(connection, job_id)
    changed_roots = _changed_root_ids(state, current_state)

    original_events = [dict(item) for item in (state.get("events") or [])]
    original_root_ids = {
        str(item["id"]) for item in original_events if not item.get("parent_event_id")
    }
    original_by_id = {str(item["id"]): item for item in original_events}

    if changed_roots:
        placeholders = ",".join("?" for _ in changed_roots)

        # Remove mutation-created queue rows first, including references to a
        # newly created target root that will disappear below.
        connection.execute(
            f"""DELETE FROM event_reapply_removed_families
                WHERE event_id IN ({placeholders}) OR target_event_id IN ({placeholders})""",
            (*sorted(changed_roots), *sorted(changed_roots)),
        )

        for root_id in sorted(changed_roots):
            current_graph_rows = connection.execute(
                """SELECT id FROM events
                   WHERE job_id=? AND (id=? OR parent_event_id=?)""",
                (job_id, root_id, root_id),
            ).fetchall()
            current_graph_ids = [str(item["id"]) for item in current_graph_rows]
            if current_graph_ids:
                ph = ",".join("?" for _ in current_graph_ids)
                connection.execute(
                    f"DELETE FROM event_assignments WHERE event_id IN ({ph})",
                    tuple(current_graph_ids),
                )
                connection.execute(
                    f"DELETE FROM event_time_segments WHERE event_id IN ({ph})",
                    tuple(current_graph_ids),
                )

            if root_id not in original_root_ids:
                # A root created while this mutation was open belongs to the
                # mutation (e.g. a new reassignment target) and can be removed.
                connection.execute(
                    "DELETE FROM events WHERE job_id=? AND id=? AND parent_event_id IS NULL",
                    (job_id, root_id),
                )
                continue

            # Children are mutable structure and may legitimately be replaced.
            # Root rows are deliberately never deleted here.
            connection.execute(
                "DELETE FROM events WHERE job_id=? AND parent_event_id=?",
                (job_id, root_id),
            )
            original_root = original_by_id[root_id]
            exists = connection.execute(
                "SELECT 1 FROM events WHERE id=? AND job_id=?",
                (root_id, job_id),
            ).fetchone()
            if exists is None:
                # This is only a fallback for a root that disappeared during an
                # unfinished mutation. Normal applied edits retain the root.
                _insert_dict_rows(connection, "events", [original_root])
            else:
                _update_dict_row(connection, "events", original_root)

            original_children = [
                item for item in original_events
                if str(item.get("parent_event_id") or "") == root_id
            ]
            _insert_dict_rows(connection, "events", original_children)

            # 0.28.3: Das pro Ereignis eingefrorene Ordnerlayout gehört zur
            # Transaktion. Ohne diesen Teil würde „Änderungen verwerfen“ zwar
            # Dateien/Ordner zurückrollen, SQLite aber auf dem neuen AN/AUS-
            # Zustand belassen. Der Strukturwächter würde Bibliothekars eigene
            # Rückänderung anschließend fälschlich als manuell melden.
            original_layouts = [
                dict(item) for item in (state.get("event_folder_layouts") or [])
                if str(item.get("event_id") or "") == root_id
            ]
            if original_layouts:
                current_layout = connection.execute(
                    "SELECT 1 FROM event_folder_layouts WHERE event_id=?",
                    (root_id,),
                ).fetchone()
                if current_layout is None:
                    _insert_dict_rows(connection, "event_folder_layouts", original_layouts)
                else:
                    _update_dict_row(
                        connection,
                        "event_folder_layouts",
                        original_layouts[0],
                        key="event_id",
                    )
            else:
                connection.execute(
                    "DELETE FROM event_folder_layouts WHERE event_id=?",
                    (root_id,),
                )

            original_graph_ids = {root_id} | {str(item["id"]) for item in original_children}
            _insert_dict_rows(
                connection,
                "event_assignments",
                [
                    dict(item) for item in (state.get("event_assignments") or [])
                    if str(item.get("event_id") or "") in original_graph_ids
                ],
            )
            _insert_dict_rows(
                connection,
                "event_time_segments",
                [
                    dict(item) for item in (state.get("event_time_segments") or [])
                    if str(item.get("event_id") or "") in original_graph_ids
                ],
            )
            _insert_dict_rows(
                connection,
                "event_reapply_removed_families",
                [
                    dict(item) for item in (state.get("event_reapply_removed_families") or [])
                    if str(item.get("event_id") or "") == root_id
                ],
            )

    now = _now()
    connection.execute(
        "UPDATE event_mutations SET status='cancelled',cancelled_at=?,updated_at=? WHERE id=?",
        (now, now, mutation_id),
    )
    connection.execute(
        """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
           VALUES (?,'event_mutation_cancelled','event_mutation',?,?,?)""",
        (
            job_id,
            mutation_id,
            json.dumps(
                {
                    "anchor_event_id": row["anchor_event_id"],
                    "restored_root_event_ids": sorted(changed_roots),
                },
                sort_keys=True,
            ),
            now,
        ),
    )
    return {
        "status": "cancelled",
        "mutation_id": mutation_id,
        "job_id": job_id,
        "restored_file_count": restored_file_count,
        "restored_root_event_ids": sorted(changed_roots),
    }

