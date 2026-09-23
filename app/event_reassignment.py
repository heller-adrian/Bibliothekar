"""Neu-Zuordnung von Familien, die bei einer Ereignisbearbeitung herausfallen.

0.16.3 baut bewusst auf der 0.16.2-Reapply-Warteschlange auf. Dadurch bleibt
bei angewendeten Ereignissen die Dateioperation Teil desselben geprüften
Nachsortierlaufs und es entsteht kein zweiter, konkurrierender Move-Workflow.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.database import database_connection, create_planned_event
from app.event_structure import build_event_preview


class EventReassignmentError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ids(values: Iterable[Any]) -> list[int]:
    result = sorted({int(v) for v in values if int(v) > 0})
    if not result:
        raise EventReassignmentError("Es wurden keine herausfallenden Familien ausgewählt.")
    return result


def _normalize_reassignment_segments(values: Iterable[Any] | None) -> list[dict[str,str]]:
    result=[]
    seen=set()
    for value in values or []:
        if not isinstance(value,dict):
            raise EventReassignmentError("Ein Tages-/Zeitsegment ist ungültig.")
        start=str(value.get("start_datetime") or "")[:19]
        end=str(value.get("end_datetime") or "")[:19]
        if len(start)!=19 or len(end)!=19 or start>end or start[:10] != end[:10]:
            raise EventReassignmentError("Ein Tages-/Zeitsegment besitzt ungültige Grenzen.")
        key=(start,end)
        if key in seen:
            continue
        seen.add(key)
        result.append({"day_key":start[:10],"start_datetime":start,"end_datetime":end,
                       "start_time":start[11:16],"end_time":end[11:16]})
    result.sort(key=lambda x:(x["start_datetime"],x["end_datetime"]))
    return result


def _root_event(connection, event_id: str):
    return connection.execute(
        "SELECT * FROM events WHERE id = ? AND parent_event_id IS NULL",
        (event_id,),
    ).fetchone()


def _assignment_event_id(connection, target, capture_time: str) -> str:
    children = connection.execute(
        "SELECT * FROM events WHERE parent_event_id = ? ORDER BY start_datetime, id",
        (target["id"],),
    ).fetchall()
    for child in children:
        start = str(child["start_datetime"] or "")[:19]
        end = str(child["end_datetime"] or "")[:19]
        if start <= capture_time[:19] <= end:
            return str(child["id"])
    return str(target["id"])


def _effective_target_intervals(connection, target) -> list[tuple[str, str, str]]:
    """Return the actual occupied intervals of one normal target event."""
    children = connection.execute(
        "SELECT id,start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
        (target["id"],),
    ).fetchall()
    if children and int(dict(target).get('time_model_version',1)) < 2:
        return [
            (
                str(child["start_datetime"] or "")[:19],
                str(child["end_datetime"] or "")[:19],
                str(child["id"]),
            )
            for child in children
        ]
    return [(
        str(target["start_datetime"] or "")[:19],
        str(target["end_datetime"] or "")[:19],
        str(target["id"]),
    )]




def reconcile_stale_event_reassignments(connection, job_id: str | None = None, event_id: str | None = None) -> int:
    """Remove pending reassignment rows that are no longer actually unassigned.

    A row with target_event_id IS NULL represents user work only while the family
    has no active event assignment. If the family has meanwhile been assigned
    again (including back to the edited source event), the durable queue row is
    stale and must not create a task or block further editing.
    """
    clauses=["r.target_event_id IS NULL"]
    params=[]
    if job_id is not None:
        clauses.append("r.job_id=?"); params.append(str(job_id))
    if event_id is not None:
        clauses.append("r.event_id=?"); params.append(str(event_id))
    where=" AND ".join(clauses)
    rows=connection.execute(f"""
        SELECT r.job_id,r.event_id,r.family_id
        FROM event_reapply_removed_families r
        WHERE {where}
          AND EXISTS (
            SELECT 1
            FROM event_assignments ea
            JOIN events e ON e.id=ea.event_id
            WHERE ea.family_id=r.family_id
              AND e.job_id=r.job_id
              AND e.status IN ('draft','planned','applied','archived')
          )
    """, params).fetchall()
    for r in rows:
        source = connection.execute('SELECT status FROM events WHERE id=?',(r['event_id'],)).fetchone()
        target = connection.execute("SELECT COALESCE(e.parent_event_id,e.id) AS id, e.status,e.event_kind,e.name,e.folder_name,e.preserve_day_folders,e.linkage_kind FROM event_assignments a JOIN events e ON e.id=a.event_id WHERE a.family_id=? AND e.status IN ('draft','planned','applied','archived') LIMIT 1",(r['family_id'],)).fetchone()
        if source and source['status']=='applied' and target and target['id'] != r['event_id']:
            connection.execute("UPDATE event_reapply_removed_families SET target_event_id=?,target_status=?,target_kind=?,target_name=?,target_folder_name=?,target_preserve_day_folders=?,target_linkage_kind=? WHERE job_id=? AND event_id=? AND family_id=?",(target['id'],target['status'],target['event_kind'],target['name'],target['folder_name'],target['preserve_day_folders'],target['linkage_kind'],r['job_id'],r['event_id'],r['family_id']))
        else:
            connection.execute("DELETE FROM event_reapply_removed_families WHERE job_id=? AND event_id=? AND family_id=? AND target_event_id IS NULL",(r['job_id'],r['event_id'],r['family_id']))
    return len(rows)


def finalize_reconciled_deleted_sources(connection, target_event_id: str, now: str) -> list[str]:
    """Remove soft-deleted sources only after every replacement is applied.

    The source mutation and audit rows retain their textual event ID.  Queue
    rows have a source FK and are consumed by the final source deletion.
    """
    sources = connection.execute(
        """SELECT DISTINCT source.id,source.job_id
           FROM event_reapply_removed_families queue
           JOIN events source ON source.id=queue.event_id
           WHERE queue.target_event_id=? AND source.pending_delete=1
             AND source.resort_required=0""",
        (target_event_id,),
    ).fetchall()
    completed: list[str] = []
    for source in sources:
        source_id = str(source["id"])
        rows = connection.execute(
            """SELECT queue.family_id,queue.target_event_id,
                      target.status,target.resort_required,target.pending_delete
               FROM event_reapply_removed_families queue
               LEFT JOIN events target ON target.id=queue.target_event_id
               WHERE queue.event_id=?""",
            (source_id,),
        ).fetchall()
        if not rows or any(
            row["target_event_id"] is None
            or row["status"] != "applied"
            or int(row["resort_required"] or 0)
            or int(row["pending_delete"] or 0)
            or not connection.execute(
                """SELECT 1 FROM event_assignments assignment
                   JOIN events assigned ON assigned.id=assignment.event_id
                   WHERE assignment.family_id=?
                     AND COALESCE(assigned.parent_event_id,assigned.id)=?
                   LIMIT 1""",
                (row["family_id"], row["target_event_id"]),
            ).fetchone()
            for row in rows
        ):
            continue
        if connection.execute(
            """SELECT 1 FROM event_assignments assignment
               JOIN events assigned ON assigned.id=assignment.event_id
               WHERE COALESCE(assigned.parent_event_id,assigned.id)=?
               LIMIT 1""",
            (source_id,),
        ).fetchone():
            continue
        connection.execute(
            """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'event_deleted_after_target_apply','event',?,'{}',?)""",
            (source["job_id"], source_id, now),
        )
        connection.execute("DELETE FROM events WHERE id=?", (source_id,))
        completed.append(source_id)
    return completed


def list_event_reassignments(database_path: Path, job_id: str, event_id: str) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        if reconcile_stale_event_reassignments(connection, job_id, event_id):
            connection.commit()
        source = _root_event(connection, event_id)
        if source is None or str(source["job_id"]) != job_id:
            raise EventReassignmentError("Quellereignis wurde nicht gefunden.")

        rows = connection.execute(
            """
            SELECT r.*, ff.family_key, ff.original_stem, ff.selected_capture_time,
                   COUNT(f.id) AS file_count, COALESCE(SUM(f.size_bytes), 0) AS total_size_bytes
            FROM event_reapply_removed_families r
            JOIN file_families ff ON ff.id = r.family_id AND ff.job_id = r.job_id
            LEFT JOIN files f ON f.family_id = ff.id AND f.job_id = ff.job_id
            WHERE r.job_id = ? AND r.event_id = ? AND r.target_event_id IS NULL
            GROUP BY r.event_id, r.family_id
            ORDER BY ff.selected_capture_time, ff.id
            """,
            (job_id, event_id),
        ).fetchall()

        captures = [str(r["selected_capture_time"] or "")[:19] for r in rows if r["selected_capture_time"]]
        min_capture = min(captures) if captures else None
        max_capture = max(captures) if captures else None

        pending_months = sorted({capture[:7] for capture in captures if len(capture) >= 7})
        target_rows = []
        if pending_months:
            placeholders = ",".join("?" for _ in pending_months)
            target_rows = connection.execute(
                f"""
                SELECT id, job_id, name, start_datetime, end_datetime, status,
                       event_kind, folder_name, preserve_day_folders, linkage_kind,
                       substr(start_datetime,1,7) AS month_key, updated_at
                FROM events
                WHERE parent_event_id IS NULL
                  AND (id <> ? OR (? = 'no_event' AND id = ?))
                  AND status IN ('planned','applied','archived')
                  AND (event_kind != 'no_event' OR substr(start_datetime,1,7) IN ({placeholders}))
                ORDER BY CASE WHEN job_id=? THEN 0 ELSE 1 END,
                         CASE status WHEN 'planned' THEN 1 WHEN 'applied' THEN 2 ELSE 3 END,
                         updated_at DESC, id DESC
                """,
                (event_id, str(source["event_kind"]), event_id, *pending_months, job_id),
            ).fetchall()

    # Mehrere Sicherungen können technisch eigene Event-Zeilen für denselben
    # Monatsordner besitzen. In der UI soll diese Sammlung dennoch nur einmal
    # erscheinen. Bevorzugt wird eine Zeile aus derselben Sicherung.
    target_list = []
    seen_months: set[str] = set()
    for target in target_rows:
        month_key = str(target["month_key"] or "")
        if str(target["event_kind"]) != "no_event" and str(target["status"]) == "archived":
            continue
        if str(target["event_kind"]) == "no_event":
            if not month_key or month_key in seen_months:
                continue
            seen_months.add(month_key)
        target_list.append({
            "event_id": str(target["id"]),
            "job_id": str(target["job_id"]),
            "name": str(target["name"]),
            "status": str(target["status"]),
            "event_kind": str(target["event_kind"]),
            "folder_name": str(target["folder_name"]),
            "month_key": month_key,
            "start_datetime": target["start_datetime"],
            "end_datetime": target["end_datetime"],
            "same_job": str(target["job_id"]) == job_id,
        })

    # 0.21.2: released time pieces are persisted when the source definition
    # changes. They are the canonical reassignment units; family capture times
    # decide membership only, never the displayed/created range boundaries.
    segment_groups: dict[tuple[str,str], list[Any]] = {}
    fallback_by_day: dict[str,list[Any]] = {}
    for row in rows:
        a=str(row["released_start_datetime"] or "")[:19]
        b=str(row["released_end_datetime"] or "")[:19]
        if a and b:
            segment_groups.setdefault((a,b),[]).append(row)
        else:
            day=str(row["selected_capture_time"] or "")[:10]
            fallback_by_day.setdefault(day,[]).append(row)
    reassignment_segments=[]
    for (a,b),items in sorted(segment_groups.items()):
        reassignment_segments.append({
            "segment_key": f"{a}/{b}", "day_key": a[:10],
            "start_time": a[11:16], "end_time": b[11:16],
            "start_datetime": a, "end_datetime": b,
            "family_ids": [int(item["family_id"]) for item in items],
            "family_count": len(items),
            "file_count": sum(int(item["file_count"] or 0) for item in items),
        })
    for day,items in sorted(fallback_by_day.items()):
        captures=[str(item["selected_capture_time"] or "")[:19] for item in items if item["selected_capture_time"]]
        if captures:
            a=min(captures); b=max(captures)
            reassignment_segments.append({
                "segment_key": f"fallback:{day}", "day_key": day,
                "start_time": a[11:16], "end_time": b[11:16],
                "start_datetime": a, "end_datetime": b,
                "family_ids": [int(item["family_id"]) for item in items],
                "family_count": len(items),
                "file_count": sum(int(item["file_count"] or 0) for item in items),
                "fallback": True,
            })
    reassignment_time_ranges = {
        seg["day_key"]: {"start_time":seg["start_time"],"end_time":seg["end_time"]}
        for seg in reassignment_segments
    }

    return {
        "source_event": {
            "id": str(source["id"]), "name": str(source["name"]),
            "status": str(source["status"]), "job_id": str(source["job_id"]),
        },
        "families": [dict(r) for r in rows],
        "family_count": len(rows),
        "capture_start": min_capture,
        "capture_end": max_capture,
        "targets": target_list,
        "new_event_supported": True,
        # Eine Monats-Sammlung ist eindeutig. Sobald fuer einen der betroffenen
        # Monate bereits ein Ziel existiert, darf die UI keine zweite Sammlung
        # fuer denselben Monat anbieten.
        "new_no_event_supported": not any(str(item.get("event_kind")) == "no_event" for item in target_list),
        "pending_months": pending_months,
        "reassignment_time_ranges": reassignment_time_ranges,
        "reassignment_segments": reassignment_segments,
    }


def _create_linked_followup(connection, job_id: str, target, family_ids: list[int], now: str) -> dict[str, Any]:
    status = str(target["status"])
    linkage = {
        "planned": "planned_extension",
        "applied": "applied_followup",
        "archived": "archived_manual",
    }[status]
    prefix = {
        "planned": "Ergänzung",
        "applied": "Nachtrag",
        "archived": "Später zuzuordnen",
    }[status]
    event_id = "EVENT_" + uuid.uuid4().hex.upper()
    name = f"{prefix}: {target['name']}"
    connection.execute(
        """
        INSERT INTO events (
            id, job_id, parent_event_id, event_level, name,
            start_datetime, end_datetime, uses_time_range, folder_name,
            status, created_at, updated_at, event_kind, preserve_day_folders,
            revision, applied_at, archived_at, linked_event_id, linkage_kind
        ) VALUES (?, ?, NULL, 'parent', ?, ?, ?, 0, ?, 'planned', ?, ?,
                  'event', ?, 1, NULL, NULL, ?, ?)
        """,
        (event_id, job_id, name, target["start_datetime"], target["end_datetime"],
         target["folder_name"], now, now, int(target["preserve_day_folders"] or 0),
         target["id"], linkage),
    )
    connection.executemany(
        "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'manual',?)",
        [(event_id, fid, now) for fid in family_ids],
    )
    return {
        "event_id": event_id, "name": name, "status": "planned",
        "folder_name": str(target["folder_name"]),
        "preserve_day_folders": bool(target["preserve_day_folders"]),
        "linkage_kind": linkage, "linked_target_status": status,
    }


def _create_new_event(
    database_path: Path, job_id: str, family_ids: list[int], name: str,
    *, ignore_event_ids: set[str] | None = None, segment: dict[str,str] | None = None,
    preserve_day_folders: bool = False,
) -> dict[str, Any]:
    clean_name = str(name or "").strip()
    if not clean_name:
        raise EventReassignmentError("Für das neue Ereignis fehlt ein Name.")
    with database_connection(database_path) as connection:
        placeholders = ",".join("?" for _ in family_ids)
        rows = connection.execute(
            f"""
            SELECT ff.id AS family_id, ff.family_key, ff.selected_capture_time,
                   ff.capture_time_confidence, COUNT(f.id) AS file_count,
                   COALESCE(SUM(f.size_bytes),0) AS total_size_bytes
            FROM file_families ff
            LEFT JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
            WHERE ff.job_id=? AND ff.id IN ({placeholders})
            GROUP BY ff.id ORDER BY ff.selected_capture_time, ff.id
            """,
            (job_id, *family_ids),
        ).fetchall()
    if len(rows) != len(family_ids):
        raise EventReassignmentError("Mindestens eine Familie wurde nicht gefunden.")
    captures = [str(r["selected_capture_time"] or "")[:19] for r in rows]
    if any(not c for c in captures):
        raise EventReassignmentError("Für ein neues Ereignis benötigen alle Familien ein Aufnahmedatum.")
    start_date = (segment["start_datetime"] if segment else min(captures))[:10]
    end_date = (segment["end_datetime"] if segment else max(captures))[:10]
    available = [{
        "family_id": int(r["family_id"]), "family_key": r["family_key"],
        "selected_capture_time": r["selected_capture_time"],
        "capture_time_confidence": r["capture_time_confidence"],
        "day_key": str(r["selected_capture_time"])[:10], "has_date": True,
        "file_count": int(r["file_count"] or 0), "total_size_bytes": int(r["total_size_bytes"] or 0),
        "review_required_count": 0,
    } for r in rows]
    preview = build_event_preview({
        "event_kind": "event", "event_name": clean_name,
        "start_date": start_date, "end_date": end_date,
        "uses_time_range": True,
        "child_event_name": "",
        "start_time": (segment["start_datetime"][11:16] if segment else min(captures)[11:16]),
        "end_time": (segment["end_datetime"][11:16] if segment else max(captures)[11:16]),
        "preserve_day_folders": preserve_day_folders,
        "selected_day_keys": sorted({a["day_key"] for a in available}),
        "selected_family_ids": family_ids,
    }, available)
    created = create_planned_event(database_path, job_id, preview, ignore_event_ids=ignore_event_ids)
    event = created["parent_event"]
    return {
        "event_id": str(event["id"]),
        "name": str(event["name"]),
        "status": "planned", "folder_name": str(event["folder_name"]),
        "preserve_day_folders": bool(event.get("preserve_day_folders")),
        "linkage_kind": "", "linked_target_status": "planned",
    }



def _selected_capture_rows(connection, job_id: str, family_ids: list[int]):
    placeholders = ",".join("?" for _ in family_ids)
    rows = connection.execute(
        f"SELECT id, selected_capture_time FROM file_families WHERE job_id=? AND id IN ({placeholders}) ORDER BY selected_capture_time,id",
        (job_id, *family_ids),
    ).fetchall()
    if len(rows) != len(family_ids) or any(not row["selected_capture_time"] for row in rows):
        raise EventReassignmentError("Für die Neu-Zuordnung fehlen Aufnahmezeiten.")
    return rows


def _capture_month(rows) -> str:
    months = {str(row["selected_capture_time"] or "")[:7] for row in rows}
    if len(months) != 1 or "" in months:
        raise EventReassignmentError(
            "Eine „Ohne Ereignis“-Zuordnung muss innerhalb eines Monats liegen. "
            "Wähle Familien aus demselben Monat gemeinsam aus."
        )
    return next(iter(months))


def _no_event_segments_for_rows(rows) -> list[dict[str, str]]:
    by_day: dict[str, list[str]] = {}
    for row in rows:
        cap = str(row["selected_capture_time"] or "")[:19]
        by_day.setdefault(cap[:10], []).append(cap)
    return [
        {"day_key": day, "start_time": min(values)[11:16], "end_time": max(values)[11:16]}
        for day, values in sorted(by_day.items())
    ]


def _create_new_no_event(
    database_path: Path, job_id: str, family_ids: list[int],
    *, ignore_event_ids: set[str] | None = None, segments: list[dict[str,str]] | None = None,
) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        rows = _selected_capture_rows(connection, job_id, family_ids)
        month = _capture_month(rows)
        existing = connection.execute(
            """SELECT id,job_id,status,folder_name FROM events
               WHERE parent_event_id IS NULL AND event_kind='no_event'
                 AND status IN ('planned','applied','archived')
                 AND substr(start_datetime,1,7)=?
               ORDER BY updated_at DESC,id DESC LIMIT 1""",
            (month,),
        ).fetchone()
        if existing is not None:
            raise EventReassignmentError(
                f"Für {month[5:7]}.{month[:4]} existiert bereits eine „Ohne Ereignis“-Sammlung. "
                "Wähle diese vorhandene Sammlung als Ziel."
            )
        placeholders = ",".join("?" for _ in family_ids)
        families = connection.execute(
            f"""SELECT ff.id AS family_id, ff.family_key, ff.selected_capture_time,
                       ff.capture_time_confidence, COUNT(f.id) AS file_count,
                       COALESCE(SUM(f.size_bytes),0) AS total_size_bytes
                FROM file_families ff LEFT JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
                WHERE ff.job_id=? AND ff.id IN ({placeholders})
                GROUP BY ff.id ORDER BY ff.selected_capture_time,ff.id""",
            (job_id,*family_ids),
        ).fetchall()
    available = [{
        "family_id": int(r["family_id"]), "family_key": r["family_key"],
        "selected_capture_time": r["selected_capture_time"],
        "capture_time_confidence": r["capture_time_confidence"],
        "day_key": str(r["selected_capture_time"])[:10], "has_date": True,
        "file_count": int(r["file_count"] or 0), "total_size_bytes": int(r["total_size_bytes"] or 0),
        "review_required_count": 0,
    } for r in families]
    preview = build_event_preview({
        "event_kind": "no_event",
        "event_name": "Ohne Ereignis",
        "no_event_segments": (segments or _no_event_segments_for_rows(rows)),
        "selected_family_ids": family_ids,
    }, available)
    created = create_planned_event(database_path, job_id, preview, ignore_event_ids=ignore_event_ids)
    event = created["parent_event"]
    return {
        "event_id": str(event["id"]), "name": str(event["name"]),
        "status": "planned", "folder_name": str(event["folder_name"]),
        "preserve_day_folders": False, "linkage_kind": "",
        "linked_target_status": "planned",
    }


def _create_cross_job_no_event_extension(connection, job_id: str, target, family_ids: list[int], now: str, segments: list[dict[str,str]] | None = None) -> dict[str, Any]:
    rows = _selected_capture_rows(connection, job_id, family_ids)
    month = _capture_month(rows)
    target_month = str(target["start_datetime"] or "")[:7]
    if month != target_month:
        raise EventReassignmentError("Die ausgewählten Familien passen nicht zum Monat dieser „Ohne Ereignis“-Sammlung.")
    if str(target["status"]) == "archived":
        info = _create_linked_followup(connection, job_id, target, family_ids, now)
        # Semantisch bleibt der Nachtrag Teil der Ohne-Ereignis-Sammlung.
        connection.execute("UPDATE events SET event_kind='no_event' WHERE id=?", (info["event_id"],))
        return info

    event_id = "EVENT_" + uuid.uuid4().hex.upper()
    captures = [str(row["selected_capture_time"])[:19] for row in rows]
    connection.execute(
        """INSERT INTO events (
            id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,
            folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,
            applied_at,archived_at,linked_event_id,linkage_kind,timeline_model,resort_required
        ) VALUES (?,?,NULL,'parent','Ohne Ereignis',?,?,0,?,'planned',?,?,'no_event',0,1,NULL,NULL,?,
                  'planned_extension','segments',0)""",
        (event_id,job_id,min(captures),max(captures),target["folder_name"],now,now,target["id"]),
    )
    connection.executemany(
        "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
        [(event_id,fid,now) for fid in family_ids],
    )
    for seg in (segments or _no_event_segments_for_rows(rows)):
        day=seg["day_key"]
        start=seg.get("start_datetime") or f"{day}T{seg['start_time']}:00"
        end=seg.get("end_datetime") or f"{day}T{seg['end_time']}:59"
        connection.execute(
            """INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (event_id,job_id,day,seg["start_time"],seg["end_time"],start,end,'reassignment',now,now),
        )
    return {
        "event_id": event_id, "name": "Ohne Ereignis", "status": "planned",
        "folder_name": str(target["folder_name"]), "preserve_day_folders": False,
        "linkage_kind": "planned_extension", "linked_target_status": str(target["status"]),
    }


def _create_child_in_existing_event(connection, job_id: str, target, family_ids: list[int], name: str, now: str, segments: list[dict[str,str]] | None = None) -> dict[str, Any]:
    clean_name=str(name or "").strip()
    if not clean_name:
        raise EventReassignmentError("Für das neue Unterereignis fehlt ein Name.")
    if str(target["job_id"]) != job_id or str(target["status"]) not in {"planned","applied"} or str(target["event_kind"]) != "event":
        raise EventReassignmentError("Dieses Ereignis kann kein neues Unterereignis aufnehmen.")
    rows=_selected_capture_rows(connection,job_id,family_ids)
    captures=[str(r["selected_capture_time"])[:19] for r in rows]
    day_keys={c[:10] for c in captures}
    if len(day_keys) != 1:
        raise EventReassignmentError("Ein neues Unterereignis wird aus genau einem Tages-/Zeitsegment erzeugt.")
    if segments:
        if len(segments) != 1:
            raise EventReassignmentError("Ein neues Unterereignis übernimmt genau ein Tages-/Zeitsegment. Weitere Segmente danach separat zuordnen.")
        start=segments[0]["start_datetime"]; end=segments[0]["end_datetime"]
        if not all(start <= capture <= end for capture in captures):
            raise EventReassignmentError("Die ausgewählten Familien passen nicht vollständig in das Tages-/Zeitsegment.")
    else:
        start=min(captures); end=max(captures)
    overlaps=connection.execute(
        "SELECT name,start_datetime,end_datetime FROM events WHERE parent_event_id=? AND start_datetime<=? AND end_datetime>=? ORDER BY start_datetime",
        (target["id"],end,start),
    ).fetchall()
    if overlaps:
        raise EventReassignmentError("Der Zeitbereich überschneidet sich mit einem vorhandenen Unterereignis.")
    child_id="EVENT_"+uuid.uuid4().hex.upper()
    folder=f"{start[11:16].replace(':','-')} - {end[11:16].replace(':','-')} - {clean_name}"
    connection.execute(
        """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,
           folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,timeline_model)
           VALUES (?,?,?,'child',?,?,?,1,?,?,?,?, 'event',?,1,?,NULL,'','continuous')""",
        (child_id,job_id,target["id"],clean_name,start,end,folder,target["status"],now,now,
         int(target["preserve_day_folders"] or 0), now if str(target["status"])=='applied' else None),
    )
    connection.executemany(
        "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
        [(child_id,fid,now) for fid in family_ids],
    )
    if str(target["status"]) == "applied":
        connection.execute("UPDATE events SET resort_required=1,updated_at=? WHERE id=?",(now,target["id"]))
    return {"event_id":str(target["id"]),"child_event_id":child_id,"name":str(target["name"]),"status":str(target["status"]),
            "folder_name":str(target["folder_name"]),"preserve_day_folders":bool(target["preserve_day_folders"]),
            "linkage_kind":str(target["linkage_kind"] or ""),"linked_target_status":str(target["status"])}


def assign_event_reassignments(
    database_path: Path, job_id: str, event_id: str, family_ids: Iterable[Any],
    *, target_mode: str, target_event_id: str | None = None, new_event_name: str | None = None,
    segments: Iterable[Any] | None = None, preserve_day_folders: bool = False,
) -> dict[str, Any]:
    selected = _normalize_ids(family_ids)
    exact_segments = _normalize_reassignment_segments(segments)
    now = _now()

    with database_connection(database_path) as connection:
        source = _root_event(connection, event_id)
        if source is None or str(source["job_id"]) != job_id:
            raise EventReassignmentError("Quellereignis wurde nicht gefunden.")
        source_status = str(source["status"])
        if source_status not in {"draft", "planned", "applied"}:
            raise EventReassignmentError("Diese Neu-Zuordnung ist für noch nicht archivierte Ereignisse vorgesehen.")
        if source_status == "applied" and int(source["resort_required"] or 0):
            raise EventReassignmentError(
                "Bitte zuerst die bestätigte Nachsortierung des Quellereignisses abschließen."
            )
        placeholders = ",".join("?" for _ in selected)
        pending = connection.execute(
            f"""SELECT family_id,released_start_datetime,released_end_datetime
                FROM event_reapply_removed_families
                WHERE job_id=? AND event_id=? AND target_event_id IS NULL
                  AND family_id IN ({placeholders})""",
            (job_id, event_id, *selected),
        ).fetchall()
        if {int(r["family_id"]) for r in pending} != set(selected):
            raise EventReassignmentError("Mindestens eine Familie ist nicht mehr zur Neu-Zuordnung offen.")
        expected_ranges={
            (str(r["released_start_datetime"])[:19],str(r["released_end_datetime"])[:19])
            for r in pending if r["released_start_datetime"] and r["released_end_datetime"]
        }
        provided_ranges={(seg["start_datetime"],seg["end_datetime"]) for seg in exact_segments}
        if expected_ranges and provided_ranges != expected_ranges:
            raise EventReassignmentError("Die ausgewählten Tages-/Zeitsegmente sind nicht mehr aktuell. Bitte die Neu-Zuordnung neu öffnen.")
        if exact_segments:
            # Every persisted released range is an atomic reassignment unit.
            # Validate against ALL still-open families of the chosen segments,
            # not merely against the subset sent by the caller.
            all_open = connection.execute(
                """SELECT family_id,released_start_datetime,released_end_datetime
                   FROM event_reapply_removed_families
                   WHERE job_id=? AND event_id=? AND target_event_id IS NULL""",
                (job_id, event_id),
            ).fetchall()
            chosen_ranges = {
                (segment["start_datetime"], segment["end_datetime"])
                for segment in exact_segments
            }
            complete_family_ids = {
                int(item["family_id"])
                for item in all_open
                if (
                    str(item["released_start_datetime"] or "")[:19],
                    str(item["released_end_datetime"] or "")[:19],
                ) in chosen_ranges
            }
            if complete_family_ids != set(selected):
                raise EventReassignmentError(
                    "Tages-/Zeitsegmente können nur vollständig neu zugeordnet werden. "
                    "Bitte das komplette Segment auswählen."
                )
            capture_rows=_selected_capture_rows(connection,job_id,selected)
            for row in capture_rows:
                cap=str(row["selected_capture_time"] or "")[:19]
                if not any(seg["start_datetime"] <= cap <= seg["end_datetime"] for seg in exact_segments):
                    raise EventReassignmentError("Mindestens eine Familie liegt außerhalb der ausgewählten Tages-/Zeitsegmente.")

    # Validate reassignment against the mutation target state. The source
    # event may still exist in SQLite for rollback while being deleted or
    # shortened; it must not block the time that this very mutation releases.
    ignored_for_target = {str(event_id)}

    if target_mode == "new_event":
        if len(exact_segments) > 1:
            raise EventReassignmentError("Ein neues normales Ereignis übernimmt pro Schritt genau ein Tages-/Zeitsegment. Ordne weitere Segmente anschließend demselben Ereignis oder weiteren Zielen zu.")
        target_info = _create_new_event(
            database_path, job_id, selected, str(new_event_name or ""),
            ignore_event_ids=ignored_for_target,
            segment=exact_segments[0] if exact_segments else None,
            preserve_day_folders=preserve_day_folders,
        )
    elif target_mode == "new_no_event":
        target_info = _create_new_no_event(
            database_path, job_id, selected, ignore_event_ids=ignored_for_target, segments=exact_segments,
        )
    elif target_mode == "existing_no_event":
        if not target_event_id:
            raise EventReassignmentError("Die „Ohne Ereignis“-Sammlung fehlt.")
        with database_connection(database_path) as connection:
            target = _root_event(connection, target_event_id)
            if target is None or str(target["status"]) not in {"planned", "applied", "archived"}:
                raise EventReassignmentError("Die „Ohne Ereignis“-Sammlung ist nicht mehr verfügbar.")
            if str(target["event_kind"]) != "no_event":
                raise EventReassignmentError("Als bestehendes Ziel ist nur „Ohne Ereignis“ zulässig.")

            captures = _selected_capture_rows(connection, job_id, selected)
            selected_month = _capture_month(captures)
            target_month = str(target["start_datetime"] or "")[:7]
            if selected_month != target_month:
                raise EventReassignmentError("Die ausgewählten Familien passen nicht zum Monat dieser „Ohne Ereignis“-Sammlung.")

            if str(target["job_id"]) != job_id:
                target_info = _create_cross_job_no_event_extension(connection, job_id, target, selected, now, exact_segments)
                connection.commit()
            elif str(target["status"]) == "archived":
                # Archiv bleibt strikt read-only. Der vorhandene Follow-up-Mechanismus
                # erzeugt den global sichtbaren manuellen Arbeitsauftrag.
                target_info = _create_linked_followup(connection, job_id, target, selected, now)
            else:
                # Direkte Zuordnung und segmentweises Erweitern des Sammelereignisses.
                by_day: dict[str, list[str]] = {}
                for row in captures:
                    cap = str(row["selected_capture_time"])[:19]
                    by_day.setdefault(cap[:10], []).append(cap)
                    connection.execute(
                        "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
                        (target["id"], int(row["id"]), now),
                    )
                segment_values = exact_segments or [
                    {"day_key":day,"start_datetime":min(values),"end_datetime":max(values),
                     "start_time":min(values)[11:16],"end_time":max(values)[11:16]}
                    for day,values in by_day.items()
                ]
                for selected_segment in segment_values:
                    day=selected_segment["day_key"]
                    a=selected_segment["start_datetime"]; b=selected_segment["end_datetime"]
                    existing = connection.execute(
                        """SELECT * FROM event_time_segments WHERE event_id=? AND day_key=?
                           ORDER BY start_datetime""", (target["id"], day)
                    ).fetchall()
                    merged_start, merged_end = a, b
                    remove_ids=[]
                    for seg in existing:
                        # Same-day no-event pieces are a collection; when a newly
                        # reassigned family touches/extends a piece, merge it.
                        if str(seg["end_datetime"]) >= merged_start and str(seg["start_datetime"]) <= merged_end:
                            merged_start=min(merged_start,str(seg["start_datetime"]))
                            merged_end=max(merged_end,str(seg["end_datetime"]))
                            remove_ids.append(int(seg["id"]))
                    if remove_ids:
                        connection.executemany("DELETE FROM event_time_segments WHERE id=?", [(i,) for i in remove_ids])
                    connection.execute(
                        """INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?)""",
                        (target["id"], job_id, day, merged_start[11:16], merged_end[11:16], merged_start, merged_end, 'reassignment', now, now),
                    )
                connection.execute("UPDATE events SET timeline_model='segments', revision=revision+1, updated_at=? WHERE id=?", (now,target["id"]))
                if str(target["status"]) == "applied":
                    connection.execute("UPDATE events SET resort_required=1 WHERE id=?", (target["id"],))
                target_info = {
                    "event_id": str(target["id"]), "name": str(target["name"]),
                    "status": str(target["status"]), "folder_name": str(target["folder_name"]),
                    "preserve_day_folders": bool(target["preserve_day_folders"]),
                    "linkage_kind": str(target["linkage_kind"] or ""),
                    "linked_target_status": str(target["status"]),
                }
            connection.commit()
    elif target_mode == "existing_event":
        if not target_event_id:
            raise EventReassignmentError("Das Zielereignis fehlt.")
        with database_connection(database_path) as connection:
            target=_root_event(connection,target_event_id)
            if target is None or str(target["job_id"]) != job_id or str(target["event_kind"]) != "event" or str(target["status"]) not in {"planned","applied"}:
                raise EventReassignmentError("Das Zielereignis ist nicht mehr verfügbar.")
            capture_rows=_selected_capture_rows(connection,job_id,selected)
            target_intervals = _effective_target_intervals(connection, target)
            if exact_segments:
                for segment in exact_segments:
                    if not any(
                        start <= segment["start_datetime"]
                        and segment["end_datetime"] <= end
                        for start, end, _ in target_intervals
                    ):
                        raise EventReassignmentError(
                            "Mindestens ein vollständiges Tages-/Zeitsegment passt nicht "
                            "in den Zeitraum des Zielereignisses."
                        )
            assignments=[]
            for row in capture_rows:
                cap=str(row["selected_capture_time"] or "")[:19]
                if not any(start <= cap <= end for start,end,_ in target_intervals):
                    raise EventReassignmentError(
                        "Mindestens eine Familie liegt außerhalb des Zeitraums des Zielereignisses."
                    )
                assignment_id=_assignment_event_id(connection,target,cap)
                if assignment_id == str(target["id"]):
                    children=connection.execute("SELECT COUNT(*) FROM events WHERE parent_event_id=?",(target["id"],)).fetchone()[0]
                    if int(children or 0):
                        raise EventReassignmentError("Mindestens eine Familie passt in kein vorhandenes Unterereignis. Wähle dafür „Neues Unterereignis“.")
                assignments.append((assignment_id,int(row["id"]),now))
            connection.executemany(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
                assignments,
            )
            if str(target["status"]) == "applied":
                connection.execute("UPDATE events SET resort_required=1,updated_at=? WHERE id=?",(now,target["id"]))
            target_info={"event_id":str(target["id"]),"name":str(target["name"]),"status":str(target["status"]),
                         "folder_name":str(target["folder_name"]),"preserve_day_folders":bool(target["preserve_day_folders"]),
                         "linkage_kind":str(target["linkage_kind"] or ""),"linked_target_status":str(target["status"])}
            connection.commit()
    elif target_mode == "new_child":
        if not target_event_id:
            raise EventReassignmentError("Das Oberereignis fehlt.")
        with database_connection(database_path) as connection:
            target=_root_event(connection,target_event_id)
            if target is None:
                raise EventReassignmentError("Das Oberereignis ist nicht mehr verfügbar.")
            target_info=_create_child_in_existing_event(connection,job_id,target,selected,str(new_event_name or ""),now,exact_segments)
            connection.commit()
    else:
        raise EventReassignmentError("Unbekannte Zielart für die Neu-Zuordnung.")

    with database_connection(database_path) as connection:
        if source_status == "applied":
            connection.executemany(
                """
                UPDATE event_reapply_removed_families
                SET target_event_id=?, target_status=?, target_kind=?, target_name=?,
                    target_folder_name=?, target_preserve_day_folders=?, target_linkage_kind=?, reassigned_at=?
                WHERE job_id=? AND event_id=? AND family_id=?
                """,
                [(
                    target_info["event_id"], target_info["linked_target_status"], target_mode,
                    target_info["name"], target_info["folder_name"],
                    int(bool(target_info["preserve_day_folders"])), target_info["linkage_kind"], now,
                    job_id, event_id, fid,
                ) for fid in selected],
            )
        else:
            # planned: Es gibt noch keine angewendete SSD-Struktur, daher genügt
            # die neue DB-Zuordnung und die Warteschlange kann sofort verschwinden.
            connection.executemany(
                "DELETE FROM event_reapply_removed_families WHERE job_id=? AND event_id=? AND family_id=?",
                [(job_id, event_id, fid) for fid in selected],
            )
        connection.execute(
            "INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'event_families_reassigned','event',?,?,?)",
            (job_id, event_id, __import__('json').dumps({"family_ids": selected, "target": target_info}, ensure_ascii=False, sort_keys=True), now),
        )
        from app.event_mutation import advance_job_mutation_after_reassignment
        advance_job_mutation_after_reassignment(connection, job_id)
        connection.commit()

    state = list_event_reassignments(database_path, job_id, event_id)
    return {
        "status": "reassigned", "family_ids": selected, "target": target_info,
        "pending_family_count": state["family_count"],
        "source_resort_required": source_status == "applied",
    }
