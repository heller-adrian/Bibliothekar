"""Safe 0.28 normalization for legacy multi-backup follow-up events.

Only purely database-planned planned_extension rows are folded automatically.
Any hint that physical work may already have happened leaves the legacy event
untouched for an explicit maintenance reconcile.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import json

from app.database import database_connection
from app.event_access import register_source_jobs, sync_event_source_jobs


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_children(connection: Any, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """SELECT * FROM events
               WHERE parent_event_id=?
               ORDER BY start_datetime,id""",
            (event_id,),
        ).fetchall()
    ]


def _event_tree_ids(connection: Any, event_id: str) -> list[str]:
    return [
        str(row["id"])
        for row in connection.execute(
            """WITH RECURSIVE tree(id) AS (
                   SELECT id FROM events WHERE id=?
                   UNION ALL
                   SELECT e.id FROM events e JOIN tree t ON e.parent_event_id=t.id
               )
               SELECT id FROM tree""",
            (event_id,),
        ).fetchall()
    ]


def _has_physical_evidence(connection: Any, legacy: dict[str, Any]) -> bool:
    legacy_id = str(legacy["id"])
    if connection.execute(
        "SELECT 1 FROM sort_runs WHERE event_id=? LIMIT 1",
        (legacy_id,),
    ).fetchone():
        return True
    if connection.execute(
        """SELECT 1 FROM event_mutations
           WHERE anchor_event_id=? OR instr(affected_event_ids_json,?)>0
           LIMIT 1""",
        (legacy_id, legacy_id),
    ).fetchone():
        return True
    if connection.execute(
        "SELECT 1 FROM event_change_requests WHERE event_id=? LIMIT 1",
        (legacy_id,),
    ).fetchone():
        return True

    tree_ids = _event_tree_ids(connection, legacy_id)
    if not tree_ids:
        return False
    ph = ",".join("?" for _ in tree_ids)
    if connection.execute(
        f"""SELECT 1 FROM event_assignments
            WHERE event_id IN ({ph}) AND file_id IS NOT NULL LIMIT 1""",
        tuple(tree_ids),
    ).fetchone():
        return True

    family_ids = [
        int(row["family_id"])
        for row in connection.execute(
            f"""SELECT DISTINCT family_id FROM event_assignments
                WHERE event_id IN ({ph}) AND family_id IS NOT NULL""",
            tuple(tree_ids),
        ).fetchall()
    ]
    if not family_ids:
        return False
    fp = ",".join("?" for _ in family_ids)
    return connection.execute(
        f"""SELECT 1 FROM files
            WHERE family_id IN ({fp})
              AND current_root_kind='shared_workspace'
              AND (
                    current_relative_path LIKE '%/Ergänzungen/%'
                 OR current_relative_path LIKE 'Ergänzungen/%'
                 OR current_relative_path LIKE '%/Nachträge/%'
                 OR current_relative_path LIKE 'Nachträge/%'
              )
            LIMIT 1""",
        tuple(family_ids),
    ).fetchone() is not None


def _merge_no_event_segments(
    connection: Any,
    target_id: str,
    legacy_id: str,
    anchor_job_id: str,
    now: str,
) -> None:
    rows = connection.execute(
        """SELECT day_key,start_datetime,end_datetime
           FROM event_time_segments
           WHERE event_id IN (?,?)
           ORDER BY day_key,start_datetime,id""",
        (target_id, legacy_id),
    ).fetchall()
    by_day: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        by_day.setdefault(str(row["day_key"]), []).append(
            (str(row["start_datetime"])[:19], str(row["end_datetime"])[:19])
        )

    merged: list[tuple[str, str, str]] = []
    for day, intervals in sorted(by_day.items()):
        current: list[list[str]] = []
        for start, end in sorted(set(intervals)):
            if current and start <= current[-1][1]:
                current[-1][1] = max(current[-1][1], end)
            else:
                current.append([start, end])
        merged.extend((day, start, end) for start, end in current)

    connection.execute(
        "DELETE FROM event_time_segments WHERE event_id=?",
        (target_id,),
    )
    connection.executemany(
        """INSERT INTO event_time_segments(
               event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,
               source,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                target_id, anchor_job_id, day, start[11:16], end[11:16],
                start, end, "migration", now, now,
            )
            for day, start, end in merged
        ],
    )
    if merged:
        connection.execute(
            """UPDATE events
               SET start_datetime=?,end_datetime=?,timeline_model='segments',
                   updated_at=?
               WHERE id=?""",
            (
                min(start for _day, start, _end in merged),
                max(end for _day, _start, end in merged),
                now,
                target_id,
            ),
        )


def _assignment_target(
    target_id: str,
    target_children: list[dict[str, Any]],
    capture: str,
) -> str:
    for child in target_children:
        if (
            str(child["start_datetime"])[:19]
            <= capture
            <= str(child["end_datetime"])[:19]
        ):
            return str(child["id"])
    return target_id


def _normalize_one(
    connection: Any,
    legacy: dict[str, Any],
    now: str,
) -> dict[str, Any] | None:
    legacy_id = str(legacy["id"])
    target_id = str(legacy.get("linked_event_id") or "")
    if not target_id:
        return None
    target_row = connection.execute(
        """SELECT * FROM events
           WHERE id=? AND parent_event_id IS NULL
             AND COALESCE(TRIM(linkage_kind),'')=''""",
        (target_id,),
    ).fetchone()
    if target_row is None:
        return None
    target = dict(target_row)

    if str(legacy.get("status") or "") not in {"draft", "planned"}:
        return None
    if legacy.get("applied_at") is not None or legacy.get("archived_at") is not None:
        return None
    if str(target.get("status") or "") not in {"draft", "planned"}:
        return None
    if target.get("applied_at") is not None or target.get("archived_at") is not None:
        return None
    if str(legacy.get("event_kind") or "event") != str(target.get("event_kind") or "event"):
        return None
    if _has_physical_evidence(connection, legacy):
        return None

    tree_ids = _event_tree_ids(connection, legacy_id)
    ph = ",".join("?" for _ in tree_ids)
    assignments = connection.execute(
        f"""SELECT DISTINCT ea.family_id,ff.selected_capture_time,ff.job_id
            FROM event_assignments ea
            JOIN file_families ff ON ff.id=ea.family_id
            WHERE ea.event_id IN ({ph}) AND ea.family_id IS NOT NULL
            ORDER BY ff.selected_capture_time,ea.family_id""",
        tuple(tree_ids),
    ).fetchall()

    target_children = _root_children(connection, target_id)
    moved_family_ids: list[int] = []
    source_jobs: set[str] = {str(target["job_id"])}

    for row in assignments:
        family_id = int(row["family_id"])
        capture = str(row["selected_capture_time"] or "")[:19]
        if not capture:
            return None
        assigned_target = _assignment_target(target_id, target_children, capture)
        already = connection.execute(
            """SELECT 1 FROM event_assignments ea
               JOIN events e ON e.id=ea.event_id
               WHERE ea.family_id=?
                 AND COALESCE(e.parent_event_id,e.id)=?
               LIMIT 1""",
            (family_id, target_id),
        ).fetchone()
        connection.execute(
            f"""DELETE FROM event_assignments
                WHERE family_id=? AND event_id IN ({ph})""",
            (family_id, *tree_ids),
        )
        if already is None:
            connection.execute(
                """INSERT INTO event_assignments(
                       event_id,family_id,file_id,assignment_source,created_at
                   ) VALUES (?,?,NULL,'manual',?)""",
                (assigned_target, family_id, now),
            )
        moved_family_ids.append(family_id)
        source_jobs.add(str(row["job_id"]))

    if str(target.get("event_kind") or "event") == "no_event":
        _merge_no_event_segments(
            connection, target_id, legacy_id, str(target["job_id"]), now
        )

    connection.execute(
        "UPDATE events SET revision=revision+1,updated_at=? WHERE id=?",
        (now, target_id),
    )
    sync_event_source_jobs(connection, target_id, created_at=now)
    register_source_jobs(
        connection, target_id, sorted(source_jobs), created_at=now
    )
    connection.execute(
        """INSERT INTO audit_log(
               job_id,action,entity_type,entity_id,details_json,created_at
           ) VALUES (?,'legacy_planned_extension_merged','event',?,?,?)""",
        (
            str(target["job_id"]),
            target_id,
            json.dumps(
                {
                    "legacy_event_id": legacy_id,
                    "legacy_job_id": str(legacy["job_id"]),
                    "family_ids": sorted(moved_family_ids),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            now,
        ),
    )
    connection.execute("DELETE FROM events WHERE id=?", (legacy_id,))
    return {
        "legacy_event_id": legacy_id,
        "target_event_id": target_id,
        "family_ids": sorted(moved_family_ids),
    }


def normalize_unapplied_legacy_extensions(database_path) -> dict[str, Any]:
    """Fold only provably DB-only planned_extension rows into canonical events."""
    now = _now()
    merged: list[dict[str, Any]] = []
    skipped: list[str] = []
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT * FROM events
                   WHERE parent_event_id IS NULL
                     AND linkage_kind='planned_extension'
                   ORDER BY created_at,id"""
            ).fetchall()
        ]
        for legacy in rows:
            connection.execute("SAVEPOINT legacy_merge")
            try:
                result = _normalize_one(connection, legacy, now)
                if result is None:
                    skipped.append(str(legacy["id"]))
                    connection.execute("ROLLBACK TO legacy_merge")
                else:
                    merged.append(result)
                connection.execute("RELEASE legacy_merge")
            except Exception:
                connection.execute("ROLLBACK TO legacy_merge")
                connection.execute("RELEASE legacy_merge")
                skipped.append(str(legacy["id"]))
        connection.commit()
    return {
        "merged": merged,
        "skipped": skipped,
        "merged_count": len(merged),
    }
