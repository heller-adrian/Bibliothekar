from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
import json

from app.event_layout import layout_paths


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def organization_path_for_event_relative(
    event_relative_path: str,
    layout_state: dict[str, Any],
) -> str:
    """Return the configured organization path immediately before a filename."""
    raw = str(event_relative_path or "").replace("\\", "/").strip("/")
    if not raw or not bool(layout_state.get("structure_enabled")):
        return ""
    parent_parts = PurePosixPath(raw).parts[:-1]
    candidates = sorted(
        (PurePosixPath(path) for path in layout_paths(layout_state.get("layout") or {})),
        key=lambda path: (-len(path.parts), path.as_posix().casefold()),
    )
    for candidate in candidates:
        if not candidate.parts:
            continue
        if len(parent_parts) >= len(candidate.parts) and tuple(parent_parts[-len(candidate.parts):]) == candidate.parts:
            return candidate.as_posix()
    return ""


def placement_snapshot_map(
    connection: Any,
    event_id: str,
    *,
    pending_only: bool = False,
) -> dict[int, str]:
    where = " AND restore_pending=1" if pending_only else ""
    rows = connection.execute(
        f"""SELECT file_id,organization_path
            FROM event_file_placement_snapshots
            WHERE event_id=?{where}""",
        (event_id,),
    ).fetchall()
    return {int(row["file_id"]): str(row["organization_path"] or "") for row in rows}


def capture_placement_snapshot(
    connection: Any,
    event_id: str,
    layout_state: dict[str, Any],
    *,
    root_kind: str = "shared_workspace",
    restore_pending: bool = False,
    now: str | None = None,
) -> int:
    """Capture current physical organization while the old structure still exists."""
    if not bool(layout_state.get("structure_enabled")):
        return 0
    timestamp = now or _now()
    rows = [
        {
            "known_file_id": int(row["known_file_id"]),
            "event_relative_path": str(row["event_relative_path"] or ""),
        }
        for row in connection.execute(
            """SELECT known_file_id,event_relative_path
               FROM event_inventory_files
               WHERE event_id=? AND root_kind=? AND known_file_id IS NOT NULL
               ORDER BY known_file_id""",
            (event_id, root_kind),
        ).fetchall()
    ]
    if not rows:
        event = connection.execute(
            "SELECT start_datetime,folder_name FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
        if event is not None:
            prefix = PurePosixPath(
                str(event["start_datetime"] or "")[:4],
                str(event["folder_name"] or ""),
            )
            fallback = connection.execute(
                """SELECT DISTINCT f.id,f.current_relative_path
                   FROM files f
                   JOIN event_assignments ea ON ea.family_id=f.family_id OR ea.file_id=f.id
                   JOIN events assigned ON assigned.id=ea.event_id
                   WHERE COALESCE(assigned.parent_event_id,assigned.id)=?
                     AND f.current_relative_path IS NOT NULL
                   ORDER BY f.id""",
                (event_id,),
            ).fetchall()
            for row in fallback:
                path = PurePosixPath(str(row["current_relative_path"] or ""))
                try:
                    rel = path.relative_to(prefix)
                except ValueError:
                    continue
                rows.append({
                    "known_file_id": int(row["id"]),
                    "event_relative_path": rel.as_posix(),
                })

    captured = 0
    for row in rows:
        file_id = int(row["known_file_id"])
        organization = organization_path_for_event_relative(
            str(row["event_relative_path"] or ""),
            layout_state,
        )
        connection.execute(
            """INSERT INTO event_file_placement_snapshots(
                   event_id,file_id,organization_path,restore_pending,captured_at)
               VALUES (?,?,?,?,?)
               ON CONFLICT(event_id,file_id) DO UPDATE SET
                   organization_path=excluded.organization_path,
                   restore_pending=excluded.restore_pending,
                   captured_at=excluded.captured_at""",
            (event_id, file_id, organization, int(bool(restore_pending)), timestamp),
        )
        captured += 1
    return captured


def mark_placement_restore_pending(
    connection: Any,
    event_id: str,
    pending: bool,
) -> int:
    cursor = connection.execute(
        """UPDATE event_file_placement_snapshots
           SET restore_pending=?
           WHERE event_id=?""",
        (int(bool(pending)), event_id),
    )
    return int(cursor.rowcount or 0)


def clear_placement_restore(
    connection: Any,
    event_id: str,
) -> None:
    connection.execute(
        "DELETE FROM event_file_placement_snapshots WHERE event_id=?",
        (event_id,),
    )


def sync_placement_moves(
    connection: Any,
    event: dict[str, Any],
    layout_state: dict[str, Any],
    root_kind: str,
    file_moves: list[dict[str, Any]],
    *,
    now: str | None = None,
) -> int:
    """Adopt user file moves that do not change the known directory structure."""
    timestamp = now or _now()
    count = 0
    for move in file_moves:
        file_id = int(move["file_id"])
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,current_root_kind=?,updated_at=?
               WHERE id=?""",
            (str(move["new_path"]), root_kind, timestamp, file_id),
        )
        count += 1

    if bool(layout_state.get("structure_enabled")):
        inventory = connection.execute(
            """SELECT known_file_id,event_relative_path
               FROM event_inventory_files
               WHERE event_id=? AND root_kind=? AND known_file_id IS NOT NULL""",
            (str(event["id"]), root_kind),
        ).fetchall()
        by_id = {int(row["known_file_id"]): str(row["event_relative_path"] or "") for row in inventory}
        for move in file_moves:
            file_id = int(move["file_id"])
            event_relative = by_id.get(file_id)
            if event_relative is None:
                continue
            organization = organization_path_for_event_relative(event_relative, layout_state)
            # A pending app-controlled restore remains authoritative until the
            # verified reapply finishes; ordinary user moves update the snapshot.
            connection.execute(
                """INSERT INTO event_file_placement_snapshots(
                       event_id,file_id,organization_path,restore_pending,captured_at)
                   VALUES (?,?,?,?,?)
                   ON CONFLICT(event_id,file_id) DO UPDATE SET
                       organization_path=CASE
                           WHEN event_file_placement_snapshots.restore_pending=1
                           THEN event_file_placement_snapshots.organization_path
                           ELSE excluded.organization_path END,
                       captured_at=excluded.captured_at""",
                (str(event["id"]), file_id, organization, 0, timestamp),
            )

    if count:
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'event_file_placements_observed','event',?,?,?)""",
            (
                str(event["job_id"]),
                str(event["id"]),
                json.dumps(
                    {
                        "root_kind": root_kind,
                        "file_count": count,
                        "moves": [
                            {
                                "file_id": int(move["file_id"]),
                                "old_path": str(move["old_path"]),
                                "new_path": str(move["new_path"]),
                            }
                            for move in file_moves
                        ],
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                timestamp,
            ),
        )
    return count


def reconcile_missing_files(
    connection: Any,
    event: dict[str, Any],
    root_kind: str,
    missing_file_ids: list[int],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Require two consecutive complete scans before accepting a deletion."""
    timestamp = now or _now()
    event_id = str(event["id"])
    missing = {int(value) for value in missing_file_ids}

    prior_rows = connection.execute(
        """SELECT file_id,consecutive_misses
           FROM event_missing_file_observations
           WHERE event_id=? AND root_kind=?""",
        (event_id, root_kind),
    ).fetchall()
    prior = {int(row["file_id"]): int(row["consecutive_misses"] or 0) for row in prior_rows}

    # Reappeared files immediately clear the provisional missing state.
    for file_id in set(prior) - missing:
        connection.execute(
            """DELETE FROM event_missing_file_observations
               WHERE event_id=? AND root_kind=? AND file_id=?""",
            (event_id, root_kind, file_id),
        )

    confirmed: list[int] = []
    pending: list[int] = []
    for file_id in sorted(missing):
        count = prior.get(file_id, 0) + 1
        if file_id in prior:
            connection.execute(
                """UPDATE event_missing_file_observations
                   SET consecutive_misses=?,last_missing_at=?
                   WHERE event_id=? AND root_kind=? AND file_id=?""",
                (count, timestamp, event_id, root_kind, file_id),
            )
        else:
            connection.execute(
                """INSERT INTO event_missing_file_observations(
                       event_id,root_kind,file_id,consecutive_misses,
                       first_missing_at,last_missing_at)
                   VALUES (?,?,?,1,?,?)""",
                (event_id, root_kind, file_id, timestamp, timestamp),
            )

        if count < 2:
            pending.append(file_id)
            continue

        file_row = connection.execute(
            """SELECT f.*,ff.family_key
               FROM files f LEFT JOIN file_families ff ON ff.id=f.family_id
               WHERE f.id=?""",
            (file_id,),
        ).fetchone()
        if file_row is None:
            confirmed.append(file_id)
            continue
        details = {
            "file_id": file_id,
            "family_id": int(file_row["family_id"]) if file_row["family_id"] is not None else None,
            "family_key": str(file_row["family_key"] or ""),
            "filename": str(file_row["original_filename"] or ""),
            "last_relative_path": str(file_row["current_relative_path"] or ""),
            "sha256": str(file_row["sha256_current"] or file_row["sha256_original"] or ""),
            "root_kind": root_kind,
            "confirmed_after_scans": count,
        }
        family_id = int(file_row["family_id"]) if file_row["family_id"] is not None else None
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'manual_file_deletion_confirmed','file',?,?,?)""",
            (
                str(file_row["job_id"]),
                str(file_id),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                timestamp,
            ),
        )
        connection.execute("DELETE FROM files WHERE id=?", (file_id,))
        if family_id is not None:
            remaining = connection.execute(
                "SELECT COUNT(*) FROM files WHERE family_id=?",
                (family_id,),
            ).fetchone()[0]
            if int(remaining or 0) == 0:
                connection.execute("DELETE FROM file_families WHERE id=?", (family_id,))
        confirmed.append(file_id)

    return {"pending": pending, "confirmed_deleted": confirmed}
