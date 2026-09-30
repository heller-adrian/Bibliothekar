"""Canonical event-centric data access for Bibliothekar 0.28.0.

An event may own families from several import jobs. events.job_id remains the
technical workflow anchor; provenance is derived from assigned families and
persisted in event_source_jobs.
"""
from __future__ import annotations

from typing import Any, Iterable


def root_event(connection: Any, event_id: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
        (event_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def event_tree_ids(connection: Any, event_id: str) -> list[str]:
    rows = connection.execute(
        """WITH RECURSIVE tree(id) AS (
               SELECT id FROM events WHERE id=? AND parent_event_id IS NULL
               UNION ALL
               SELECT child.id
               FROM events child JOIN tree parent ON child.parent_event_id=parent.id
           )
           SELECT id FROM tree ORDER BY id""",
        (event_id,),
    ).fetchall()
    return [str(row["id"]) for row in rows]


def event_family_ids(connection: Any, event_id: str) -> list[int]:
    ids = event_tree_ids(connection, event_id)
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""SELECT DISTINCT ea.family_id
            FROM event_assignments ea
            WHERE ea.event_id IN ({placeholders})
              AND ea.family_id IS NOT NULL
            ORDER BY ea.family_id""",
        tuple(ids),
    ).fetchall()
    return [int(row["family_id"]) for row in rows]


def event_family_rows(connection: Any, event_id: str) -> list[dict[str, Any]]:
    family_ids = event_family_ids(connection, event_id)
    if not family_ids:
        return []
    placeholders = ",".join("?" for _ in family_ids)
    rows = connection.execute(
        f"""SELECT ff.id AS family_id, ff.*, j.source_volume_label AS source_label,
                   COUNT(DISTINCT f.id) AS file_count,
                   COALESCE(SUM(f.size_bytes),0) AS total_size_bytes
            FROM file_families ff
            JOIN jobs j ON j.id=ff.job_id
            LEFT JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
            WHERE ff.id IN ({placeholders})
            GROUP BY ff.id
            ORDER BY ff.selected_capture_time,ff.id""",
        tuple(family_ids),
    ).fetchall()
    return [dict(row) for row in rows]


def event_file_rows(connection: Any, event_id: str) -> list[dict[str, Any]]:
    family_ids = event_family_ids(connection, event_id)
    ids = event_tree_ids(connection, event_id)
    direct_file_ids: list[int] = []
    if ids:
        placeholders = ",".join("?" for _ in ids)
        direct_file_ids = [
            int(row["file_id"])
            for row in connection.execute(
                f"""SELECT DISTINCT file_id FROM event_assignments
                    WHERE event_id IN ({placeholders}) AND file_id IS NOT NULL""",
                tuple(ids),
            ).fetchall()
        ]
    clauses: list[str] = []
    values: list[Any] = []
    if family_ids:
        placeholders = ",".join("?" for _ in family_ids)
        clauses.append(f"f.family_id IN ({placeholders})")
        values.extend(family_ids)
    if direct_file_ids:
        placeholders = ",".join("?" for _ in direct_file_ids)
        clauses.append(f"f.id IN ({placeholders})")
        values.extend(direct_file_ids)
    if not clauses:
        return []
    rows = connection.execute(
        f"""SELECT f.id AS file_id, f.*, ff.family_key,
                   ff.selected_capture_time AS family_capture_time,
                   ff.capture_time_confidence AS family_confidence,
                   j.source_volume_label AS source_label
            FROM files f
            LEFT JOIN file_families ff ON ff.id=f.family_id
            JOIN jobs j ON j.id=f.job_id
            WHERE {" OR ".join(clauses)}
            ORDER BY ff.selected_capture_time,f.id""",
        tuple(values),
    ).fetchall()
    return [dict(row) for row in rows]


def event_source_jobs(connection: Any, event_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        """SELECT DISTINCT ff.job_id,
                  COALESCE(j.source_volume_label,ff.job_id) AS source_label,
                  j.created_at
           FROM event_assignments ea
           JOIN events assigned ON assigned.id=ea.event_id
           JOIN file_families ff ON ff.id=ea.family_id
           JOIN jobs j ON j.id=ff.job_id
           WHERE ea.family_id IS NOT NULL
             AND COALESCE(assigned.parent_event_id,assigned.id)=?
           ORDER BY j.created_at,ff.job_id""",
        (event_id,),
    ).fetchall()
    if rows:
        return [dict(row) for row in rows]
    rows = connection.execute(
        """SELECT esj.job_id,COALESCE(j.source_volume_label,esj.job_id) AS source_label,
                  j.created_at
           FROM event_source_jobs esj JOIN jobs j ON j.id=esj.job_id
           WHERE esj.event_id=? ORDER BY j.created_at,esj.job_id""",
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def event_anchor_job(connection: Any, event_id: str) -> str | None:
    row = connection.execute(
        "SELECT job_id FROM events WHERE id=? AND parent_event_id IS NULL",
        (event_id,),
    ).fetchone()
    return str(row["job_id"]) if row is not None else None


def register_source_jobs(
    connection: Any,
    event_id: str,
    job_ids: Iterable[str],
    *,
    created_at: str,
) -> None:
    rows = sorted({str(value) for value in job_ids if str(value)})
    connection.executemany(
        """INSERT OR IGNORE INTO event_source_jobs(event_id,job_id,created_at)
           VALUES (?,?,?)""",
        [(event_id, job_id, created_at) for job_id in rows],
    )


def sync_event_source_jobs(connection: Any, event_id: str, *, created_at: str) -> list[str]:
    rows = connection.execute(
        """SELECT DISTINCT ff.job_id
           FROM event_assignments ea
           JOIN events assigned ON assigned.id=ea.event_id
           JOIN file_families ff ON ff.id=ea.family_id
           WHERE ea.family_id IS NOT NULL
             AND COALESCE(assigned.parent_event_id,assigned.id)=?
           ORDER BY ff.job_id""",
        (event_id,),
    ).fetchall()
    job_ids = [str(row["job_id"]) for row in rows]
    if job_ids:
        register_source_jobs(connection, event_id, job_ids, created_at=created_at)
    return job_ids
