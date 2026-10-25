from __future__ import annotations

from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any, Iterator
from datetime import datetime, timezone
import json
import sqlite3
import re
import uuid


MIGRATION_DIR = Path(__file__).parent / "migrations"


class DatabaseError(RuntimeError):
    pass


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        database_path,
        timeout=30,
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    connection.execute(
        "PRAGMA synchronous = FULL"
    )

    connection.execute(
        "PRAGMA busy_timeout = 30000"
    )

    return connection


@contextmanager
def database_connection(
    database_path: Path,
) -> Iterator[sqlite3.Connection]:
    connection = connect(database_path)

    try:
        yield connection
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def ensure_schema_version_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )


def applied_versions(
    connection: sqlite3.Connection,
) -> set[int]:
    ensure_schema_version_table(connection)

    rows = connection.execute(
        """
        SELECT version
        FROM schema_versions
        ORDER BY version
        """
    ).fetchall()

    return {
        int(row["version"])
        for row in rows
    }


def available_migrations() -> list[tuple[int, Path]]:
    if not MIGRATION_DIR.is_dir():
        raise DatabaseError(
            f"Migrationsordner fehlt: {MIGRATION_DIR}"
        )

    migrations: list[tuple[int, Path]] = []

    for path in sorted(
        MIGRATION_DIR.glob("*.sql")
    ):
        prefix = path.stem.split("_", 1)[0]

        if not prefix.isdigit():
            raise DatabaseError(
                f"Ungültiger Migrationsname: {path.name}"
            )

        migrations.append(
            (int(prefix), path)
        )

    if not migrations:
        raise DatabaseError(
            "Keine Datenbankmigrationen gefunden."
        )

    versions = [
        version
        for version, _ in migrations
    ]

    if len(versions) != len(set(versions)):
        raise DatabaseError(
            "Doppelte Migrationsversion gefunden."
        )

    return migrations


def _apply_trash_root_kind_migration(
    connection: sqlite3.Connection,
    version: int,
) -> None:
    """Rebuild the files CHECK constraint, preserving all existing columns/FKs."""
    connection.commit()
    connection.execute("PRAGMA foreign_keys=OFF")
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='files'"
        ).fetchone()
        if row is None or not row[0]:
            raise DatabaseError("Die Tabelle files fehlt für die Papierkorb-Migration.")
        create_sql = str(row[0])
        renamed, count = re.subn(
            r"(?i)^CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?files\b",
            "CREATE TABLE files_trash_upgrade",
            create_sql,
            count=1,
        )
        if count != 1:
            raise DatabaseError("Das Schema der Tabelle files ist unbekannt.")
        upgraded, count = re.subn(
            r"(current_root_kind\s+IN\s*\(\s*'job_root'\s*,"
            r"\s*'shared_workspace'\s*,\s*'camera_archive')",
            r"\1, 'trash'",
            renamed,
            count=1,
            flags=re.IGNORECASE,
        )
        if count != 1:
            raise DatabaseError("Die Root-Kind-Constraint ist unbekannt.")
        definitions = [
            str(record[0])
            for record in connection.execute(
                """SELECT sql FROM sqlite_master
                   WHERE tbl_name='files'
                     AND type IN ('index','trigger')
                     AND sql IS NOT NULL
                   ORDER BY type,name"""
            ).fetchall()
        ]
        connection.execute(upgraded)
        columns = [
            str(item[1])
            for item in connection.execute("PRAGMA table_info(files)").fetchall()
        ]
        if not columns:
            raise DatabaseError("Die bestehenden Dateispalten fehlen.")
        column_list = ",".join('"' + name.replace('"', '""') + '"' for name in columns)
        connection.execute(
            f"INSERT INTO files_trash_upgrade ({column_list}) "
            f"SELECT {column_list} FROM files"
        )
        connection.execute("DROP TABLE files")
        connection.execute("ALTER TABLE files_trash_upgrade RENAME TO files")
        for sql in definitions:
            connection.execute(sql)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise DatabaseError("Fremdschlüsselprüfung nach Papierkorb-Migration fehlgeschlagen.")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise DatabaseError("SQLite-Integrität nach Papierkorb-Migration: " + str(integrity))
        connection.execute(
            "INSERT INTO schema_versions(version,applied_at) VALUES (?,datetime('now'))",
            (version,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys=ON")


def apply_migration(
    connection: sqlite3.Connection,
    version: int,
    path: Path,
) -> None:
    sql = path.read_text(
        encoding="utf-8"
    )

    if not sql.strip():
        raise DatabaseError(
            f"Migration ist leer: {path}"
        )

    if version == 48:
        _apply_trash_root_kind_migration(connection, version)
        return

    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            """
            + sql
            + f"""
            INSERT INTO schema_versions (
                version,
                applied_at
            )
            VALUES (
                {version},
                datetime('now')
            );
            COMMIT;
            """
        )

    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass

        raise


def initialize_database(
    database_path: Path,
) -> dict[str, object]:
    migrations = available_migrations()

    with database_connection(
        database_path
    ) as connection:
        current = applied_versions(
            connection
        )

        # Never start an older binary on a database created by a newer release.
        # Applying known migrations cannot make a future schema compatible.
        known_versions = {version for version, _path in migrations}
        unsupported_versions = sorted(current - known_versions)
        if unsupported_versions:
            raise DatabaseError(
                "Diese Datenbank verwendet nicht unterstützte, neuere "
                "Migrationsversionen: " + ", ".join(map(str, unsupported_versions))
            )

        newly_applied: list[int] = []

        for version, path in migrations:
            if version in current:
                continue

            apply_migration(
                connection,
                version,
                path,
            )

            newly_applied.append(version)

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise DatabaseError(
                f"Integritätsprüfung fehlgeschlagen: "
                f"{integrity}"
            )

        foreign_keys = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if foreign_keys:
            raise DatabaseError(
                "Fremdschlüsselprüfung fehlgeschlagen."
            )

        versions = sorted(
            applied_versions(connection)
        )

        tables = [
            row["name"]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        ]

    return {
        "database_path": str(database_path),
        "applied_versions": versions,
        "newly_applied_versions": newly_applied,
        "tables": tables,
        "integrity": integrity,
        "foreign_key_errors": 0,
    }


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .astimezone()
        .isoformat()
    )


def create_job(
    database_path: Path,
    *,
    job_id: str,
    kind: str,
    trigger_type: str,
    source_path: str | None = None,
    working_path: str | None = None,
    operation: str = "legacy_simulation",
    source_volume_label: str | None = None,
    source_signature: str | None = None,
    source_device_id: str | None = None,
    reimport_of_job_id: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()

    with database_connection(
        database_path
    ) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                id,
                kind,
                trigger_type,
                state,
                stage,
                source_path,
                working_path,
                progress_current,
                progress_total,
                progress_message,
                operation,
                source_volume_label,
                source_signature,
                source_device_id,
                duplicate_of_job_id,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                ?,
                'queued',
                'queued',
                ?,
                ?,
                0,
                0,
                'Auftrag wartet auf Verarbeitung.',
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?
            )
            """,
            (
                job_id,
                kind,
                trigger_type,
                source_path,
                working_path,
                operation,
                source_volume_label,
                source_signature,
                source_device_id,
                reimport_of_job_id,
                now,
                now,
            ),
        )

    job = get_job(
        database_path,
        job_id,
    )

    if job is None:
        raise DatabaseError(
            f"Auftrag wurde nicht angelegt: {job_id}"
        )

    return job



def find_folder_import_by_identity(
    database_path: Path,
    *,
    source_signature: str | None = None,
    source_fingerprint: str | None = None,
    exclude_job_id: str | None = None,
    include_active: bool = True,
    include_completed: bool = True,
) -> dict[str, Any] | None:
    conditions = ["operation = 'folder_import'"]
    values: list[Any] = []
    identity_parts: list[str] = []
    if source_signature:
        identity_parts.append("source_signature = ?")
        values.append(source_signature)
    if source_fingerprint:
        identity_parts.append("source_fingerprint = ?")
        values.append(source_fingerprint)
    if not identity_parts:
        return None
    conditions.append("(" + " OR ".join(identity_parts) + ")")
    states = ["completed"] if include_completed else []
    if include_active:
        states += ["queued", "copying", "verifying", "backup_verified", "analyzing_metadata", "organizing"]
    if not states:
        return None
    conditions.append("state IN (" + ",".join("?" for _ in states) + ")")
    values.extend(states)
    if exclude_job_id:
        conditions.append("id <> ?")
        values.append(exclude_job_id)
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM jobs WHERE " + " AND ".join(conditions) + " ORDER BY CASE WHEN state='completed' THEN 1 ELSE 0 END, created_at ASC, id LIMIT 1",
            values,
        ).fetchone()
    return row_to_job(row) if row is not None else None


def set_job_source_identity(
    database_path: Path,
    job_id: str,
    *,
    source_signature: str,
    source_fingerprint: str,
    allow_completed_duplicate: bool = False,
) -> dict[str, Any]:
    # Serialize identity publication before any filesystem publication. A
    # second worker cannot pass the same active fingerprint simultaneously.
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        states = ["queued", "copying", "verifying", "backup_verified", "analyzing_metadata", "organizing"]
        if not allow_completed_duplicate:
            states.append("completed")
        duplicate = connection.execute(
            "SELECT id FROM jobs WHERE operation='folder_import' AND source_fingerprint=? AND id<>? AND state IN (" + ",".join("?" for _ in states) + ") ORDER BY created_at,id LIMIT 1",
            (source_fingerprint,job_id,*states),
        ).fetchone()
        connection.execute(
            "UPDATE jobs SET source_signature=?,source_fingerprint=?,updated_at=? WHERE id=?",
            (source_signature,source_fingerprint,utc_now_iso(),job_id),
        )
        if duplicate is not None:
            connection.execute("UPDATE jobs SET duplicate_of_job_id=? WHERE id=?",(duplicate["id"],job_id))
    if duplicate is not None:
        raise DatabaseError("Diese Quelle wird bereits verarbeitet: " + str(duplicate["id"]))
    job = get_job(database_path, job_id)
    if job is None:
        raise DatabaseError(f"Auftrag fehlt nach Quellenidentität: {job_id}")
    return job


def row_to_job(
    row: sqlite3.Row,
) -> dict[str, Any]:
    result = dict(row)

    # API-Kompatibilität mit den bisherigen JSON-Protokollen.
    result["job_id"] = result["id"]
    result["simulation"] = (
        result.get("kind") == "simulation"
    )

    raw_result = result.get(
        "result_json"
    )

    if raw_result:
        try:
            result["result"] = json.loads(
                raw_result
            )
        except json.JSONDecodeError:
            result["result"] = None
            result["result_json_invalid"] = True
    else:
        result["result"] = None

    result.pop(
        "result_json",
        None,
    )

    return result


def get_job(
    database_path: Path,
    job_id: str,
) -> dict[str, Any] | None:
    with database_connection(
        database_path
    ) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if row is None:
        return None

    return row_to_job(row)


def _job_workflow_states(connection: sqlite3.Connection) -> dict[str, dict[str, int | str]]:
    """Derive backup state from its real remaining active workspace stock.

    Source jobs are provenance, not event containers.  Files released from an
    archive edit deliberately do not reactivate the historical backup in the
    normal backup filter.
    """
    jobs = connection.execute(
        "SELECT id FROM jobs WHERE operation IN ('folder_import','sd_import') OR kind='sd_import'"
    ).fetchall()
    result: dict[str, dict[str, int | str]] = {}
    for job in jobs:
        job_id = str(job["id"])
        families = connection.execute(
            "SELECT id FROM file_families WHERE job_id=? ORDER BY id",
            (job_id,),
        ).fetchall()
        family_ids = [int(row["id"]) for row in families]
        total = len(family_ids)
        if not family_ids:
            result[job_id] = {
                "workflow_status": "planned",
                "total_family_count": 0,
                "active_family_count": 0,
                "planned_family_count": 0,
                "applied_family_count": 0,
                "archived_family_count": 0,
            }
            continue

        ph = ",".join("?" for _ in family_ids)
        active_rows = connection.execute(
            f"""SELECT DISTINCT f.family_id
                FROM files f
                WHERE f.family_id IN ({ph})
                  AND f.current_root_kind='shared_workspace'
                  AND COALESCE(f.current_relative_path,'') NOT LIKE 'Freigewordene Archivdateien/%' AND COALESCE(f.current_relative_path,'') NOT LIKE 'Released Archive Files/%'""",
            tuple(family_ids),
        ).fetchall()
        active_ids = {int(row["family_id"]) for row in active_rows if row["family_id"] is not None}

        assignments = connection.execute(
            f"""SELECT DISTINCT ea.family_id,
                       root.status AS root_status
                FROM event_assignments ea
                JOIN events assigned ON assigned.id=ea.event_id
                JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                WHERE ea.family_id IN ({ph})
                  AND root.status IN ('draft','planned','applied','archived')""",
            tuple(family_ids),
        ).fetchall()
        statuses: dict[int, set[str]] = {}
        for row in assignments:
            statuses.setdefault(int(row["family_id"]), set()).add(str(row["root_status"]))

        archived = sum(1 for fid in family_ids if "archived" in statuses.get(fid, set()))
        applied = sum(1 for fid in active_ids if statuses.get(fid, set()) & {"applied","archived"})
        planned = sum(
            1 for fid in active_ids
            if not statuses.get(fid) or bool(statuses.get(fid, set()) & {"draft","planned"})
        )
        active = len(active_ids)

        if total > 0 and active == 0:
            status = "archived"
        elif active > 0 and planned == 0 and applied == active:
            status = "applied"
        else:
            status = "planned"

        result[job_id] = {
            "workflow_status": status,
            "total_family_count": total,
            "active_family_count": active,
            "planned_family_count": planned,
            "applied_family_count": applied,
            "archived_family_count": archived,
        }
    return result


def list_database_jobs(
    database_path: Path,
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    safe_limit = max(
        1,
        min(int(limit), 500),
    )

    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE operation <> 'sd_recheck'
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()
        workflow = _job_workflow_states(connection)

    jobs = [row_to_job(row) for row in rows]
    for job in jobs:
        stats = workflow.get(str(job["id"]))
        if stats is None:
            duplicate_count = int(
                ((job.get("result") or {}).get("source") or {}).get(
                    "already_imported_file_count", 0
                )
                or 0
            )
            stats = {
                "workflow_status": (
                    "archived"
                    if str(job.get("state") or "") == "completed"
                    and duplicate_count > 0
                    and int(job.get("file_count") or 0) == 0
                    else "planned"
                ),
                "total_family_count": 0,
                "active_family_count": 0,
                "planned_family_count": 0,
                "applied_family_count": 0,
                "archived_family_count": 0,
            }
        job.update(stats)
    return jobs


def list_imported_media_origins(
    database_path: Path,
    *,
    exclude_job_id: str | None = None,
) -> list[dict[str, Any]]:
    conditions = [
        "j.operation IN ('folder_import','sd_import','metadata_multiple_import')",
        "j.state='completed'",
        "COALESCE(TRIM(f.sha256_original),'')<>''",
    ]
    params: list[Any] = []
    if exclude_job_id:
        conditions.append("f.job_id<>?")
        params.append(str(exclude_job_id))
    with database_connection(database_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                f.job_id,
                f.original_relative_path,
                f.current_relative_path,
                f.current_root_kind, f.sha256_current, f.size_bytes AS current_size_bytes,
                f.original_filename,
                COALESCE(f.source_size_bytes, f.size_bytes) AS size_bytes,
                f.sha256_original AS sha256,
                j.source_volume_label,
                j.created_at
            FROM files f
            JOIN jobs j ON j.id=f.job_id
            WHERE {" AND ".join(conditions)}
            ORDER BY j.created_at,f.id
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def claim_next_job(
    database_path: Path,
    *,
    operation: str | None = None,
) -> dict[str, Any] | None:
    connection = connect(
        database_path
    )

    try:
        connection.execute(
            "BEGIN IMMEDIATE"
        )

        if operation is None:
            row = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE state = 'queued'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ).fetchone()
        else:
            row = connection.execute(
                """
                SELECT *
                FROM jobs
                WHERE state = 'queued'
                  AND operation = ?
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """,
                (str(operation),),
            ).fetchone()

        if row is None:
            connection.commit()
            return None

        now = utc_now_iso()
        job_id = str(row["id"])

        cursor = connection.execute(
            """
            UPDATE jobs
            SET
                state = 'copying',
                stage = 'starting',
                progress_message =
                    'Auftrag wurde vom Worker übernommen.',
                started_at = COALESCE(
                    started_at,
                    ?
                ),
                updated_at = ?
            WHERE id = ?
              AND state = 'queued'
            """,
            (
                now,
                now,
                job_id,
            ),
        )

        if cursor.rowcount != 1:
            connection.rollback()
            return None

        claimed = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        connection.commit()

        if claimed is None:
            raise DatabaseError(
                f"Reservierter Auftrag fehlt: {job_id}"
            )

        return row_to_job(claimed)

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_job_progress(
    database_path: Path,
    job_id: str,
    *,
    stage: str,
    state: str | None = None,
    current: int = 0,
    total: int = 0,
    message: str | None = None,
    file_count: int | None = None,
    total_size_bytes: int | None = None,
    working_path: str | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()

    allowed_active_states = {
        "copying",
        "verifying",
        "backup_verified",
        "analyzing_metadata",
        "organizing",
    }

    if state is not None and state not in allowed_active_states:
        raise DatabaseError(
            f"Ungültiger aktiver Auftragszustand: {state}"
        )

    assignments = [
        "stage = ?",
        "progress_current = ?",
        "progress_total = ?",
        "progress_message = ?",
        "updated_at = ?",
    ]

    values: list[Any] = [
        stage,
        max(0, int(current)),
        max(0, int(total)),
        message,
        now,
    ]

    if state is not None:
        assignments.append(
            "state = ?"
        )
        values.append(
            state
        )

    if file_count is not None:
        assignments.append(
            "file_count = ?"
        )
        values.append(
            int(file_count)
        )

    if total_size_bytes is not None:
        assignments.append(
            "total_size_bytes = ?"
        )
        values.append(
            int(total_size_bytes)
        )

    if working_path is not None:
        assignments.append(
            "working_path = ?"
        )
        values.append(
            working_path
        )

    values.append(job_id)

    with database_connection(
        database_path
    ) as connection:
        cursor = connection.execute(
            f"""
            UPDATE jobs
            SET {", ".join(assignments)}
            WHERE id = ?
              AND state IN (
                  'copying',
                  'verifying',
                  'backup_verified',
                  'analyzing_metadata',
                  'organizing'
              )
            """,
            values,
        )

        if cursor.rowcount != 1:
            raise DatabaseError(
                "Laufender Auftrag wurde nicht gefunden: "
                + job_id
            )

    job = get_job(
        database_path,
        job_id,
    )

    if job is None:
        raise DatabaseError(
            f"Auftrag fehlt nach Aktualisierung: {job_id}"
        )

    return job


def complete_job(
    database_path: Path,
    job_id: str,
    *,
    stage: str,
    result: dict[str, Any],
    message: str = "Auftrag erfolgreich abgeschlossen.",
) -> dict[str, Any]:
    now = utc_now_iso()

    serialized_result = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    with database_connection(
        database_path
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE jobs
            SET
                state = 'completed',
                stage = ?,
                progress_current = CASE
                    WHEN progress_total > 0
                    THEN progress_total
                    ELSE progress_current
                END,
                progress_message = ?,
                result_json = ?,
                error_message = NULL,
                updated_at = ?,
                finished_at = ?
            WHERE id = ?
              AND state IN (
                  'copying',
                  'verifying',
                  'backup_verified',
                  'analyzing_metadata',
                  'organizing'
              )
            """,
            (
                stage,
                message,
                serialized_result,
                now,
                now,
                job_id,
            ),
        )

        if cursor.rowcount != 1:
            raise DatabaseError(
                "Laufender Auftrag konnte nicht "
                "abgeschlossen werden: "
                + job_id
            )

    job = get_job(
        database_path,
        job_id,
    )

    if job is None:
        raise DatabaseError(
            f"Auftrag fehlt nach Abschluss: {job_id}"
        )

    return job



def recover_failed_job_as_completed(
    database_path: Path,
    job_id: str,
    *,
    stage: str,
    result: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    now = utc_now_iso()
    serialized_result = json.dumps(
        result,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE jobs
            SET
                state = 'completed',
                stage = ?,
                progress_current = CASE
                    WHEN progress_total > 0 THEN progress_total
                    ELSE progress_current
                END,
                progress_message = ?,
                result_json = ?,
                error_message = NULL,
                updated_at = ?,
                finished_at = ?
            WHERE id = ?
              AND state = 'failed'
              AND error_message LIKE '%Invalid cross-device link%'
            """,
            (stage, message, serialized_result, now, now, job_id),
        )
        if cursor.rowcount != 1:
            raise DatabaseError(
                "Fehlgeschlagener EXDEV-Auftrag konnte nicht wiederhergestellt werden: "
                + job_id
            )

    job = get_job(database_path, job_id)
    if job is None:
        raise DatabaseError(
            f"Auftrag fehlt nach Wiederherstellung: {job_id}"
        )
    return job

def fail_job(
    database_path: Path,
    job_id: str,
    *,
    error_message: str,
    stage: str = "failed",
) -> dict[str, Any]:
    now = utc_now_iso()

    with database_connection(
        database_path
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE jobs
            SET
                state = 'failed',
                stage = ?,
                progress_message =
                    'Auftrag ist fehlgeschlagen.',
                error_message = ?,
                updated_at = ?,
                finished_at = ?
            WHERE id = ?
              AND state IN (
                  'queued',
                  'copying',
                  'verifying',
                  'backup_verified',
                  'analyzing_metadata',
                  'organizing'
              )
            """,
            (
                stage,
                error_message,
                now,
                now,
                job_id,
            ),
        )

        if cursor.rowcount != 1:
            raise DatabaseError(
                "Auftrag konnte nicht als "
                "fehlgeschlagen markiert werden: "
                + job_id
            )

    job = get_job(
        database_path,
        job_id,
    )

    if job is None:
        raise DatabaseError(
            f"Auftrag fehlt nach Fehlerstatus: {job_id}"
        )

    return job

def mark_running_jobs_interrupted(
    database_path: Path,
) -> int:
    now = utc_now_iso()

    with database_connection(
        database_path
    ) as connection:
        cursor = connection.execute(
            """
            UPDATE jobs
            SET
                state = 'interrupted',
                stage = 'interrupted_after_restart',
                progress_message = ?,
                error_message = ?,
                updated_at = ?,
                finished_at = ?
            WHERE state IN (
                'copying',
                'verifying',
                'backup_verified',
                'analyzing_metadata',
                'organizing'
            )
            """,
            (
                "Auftrag wurde durch einen Neustart unterbrochen.",
                "Die Anwendung wurde während der Verarbeitung "
                "neu gestartet.",
                now,
                now,
            ),
        )

        return int(
            cursor.rowcount
        )



def repair_interrupted_jobs_from_terminal_evidence(
    database_path: Path,
) -> int:
    """
    Repair stale interrupted states only when a later terminal operation proves
    that the job completed safely.

    A completed SSD release is the strongest evidence. A fully applied sort run
    is accepted only when no later non-terminal sort or release operation exists.
    """

    now = utc_now_iso()
    repaired = 0
    sortable_operations = {
        "folder_import",
        "sd_import",
        "metadata_fixture_analysis",
        "legacy_simulation",
    }

    with database_connection(database_path) as connection:
        jobs = connection.execute(
            """
            SELECT id, operation
            FROM jobs
            WHERE state = 'interrupted'
            ORDER BY created_at, id
            """
        ).fetchall()

        for job in jobs:
            job_id = str(job["id"])
            operation = str(job["operation"] or "")

            if operation not in sortable_operations:
                continue

            evidence = connection.execute(
                """
                SELECT evidence_kind, evidence_stage, evidence_at, evidence_jd
                FROM (
                    SELECT
                        'ssd_release' AS evidence_kind,
                        'event_ssd_released' AS evidence_stage,
                        COALESCE(completed_at, updated_at, created_at) AS evidence_at,
                        julianday(COALESCE(completed_at, updated_at, created_at)) AS evidence_jd
                    FROM event_ssd_releases
                    WHERE job_id = ?
                      AND status = 'completed'

                    UNION ALL

                    SELECT
                        'sort_run' AS evidence_kind,
                        'event_sort_applied' AS evidence_stage,
                        COALESCE(completed_at, updated_at, created_at) AS evidence_at,
                        julianday(COALESCE(completed_at, updated_at, created_at)) AS evidence_jd
                    FROM sort_runs
                    WHERE job_id = ?
                      AND status = 'applied'
                )
                WHERE evidence_jd IS NOT NULL
                ORDER BY evidence_jd DESC
                LIMIT 1
                """,
                (job_id, job_id),
            ).fetchone()

            if evidence is None:
                continue

            evidence_jd = float(evidence["evidence_jd"])

            later_nonterminal = connection.execute(
                """
                SELECT 1
                FROM (
                    SELECT julianday(COALESCE(updated_at, created_at)) AS activity_jd
                    FROM sort_runs
                    WHERE job_id = ?
                      AND status IN (
                          'queued',
                          'verifying',
                          'moving',
                          'finalizing',
                          'rolling_back',
                          'interrupted'
                      )

                    UNION ALL

                    SELECT julianday(COALESCE(updated_at, created_at)) AS activity_jd
                    FROM event_ssd_releases
                    WHERE job_id = ?
                      AND status IN (
                          'verifying',
                          'deleting',
                          'finalizing',
                          'interrupted'
                      )
                )
                WHERE activity_jd IS NOT NULL
                  AND activity_jd > ?
                LIMIT 1
                """,
                (job_id, job_id, evidence_jd),
            ).fetchone()

            if later_nonterminal is not None:
                continue

            evidence_stage = str(evidence["evidence_stage"])
            evidence_at = str(evidence["evidence_at"] or now)
            evidence_kind = str(evidence["evidence_kind"])

            cursor = connection.execute(
                """
                UPDATE jobs
                SET state = 'completed',
                    stage = ?,
                    progress_message = ?,
                    error_message = NULL,
                    updated_at = ?,
                    finished_at = COALESCE(finished_at, ?)
                WHERE id = ?
                  AND state = 'interrupted'
                """,
                (
                    evidence_stage,
                    "Unterbrochener Status anhand eines vollständig "
                    "abgeschlossenen Folgevorgangs wiederhergestellt.",
                    now,
                    evidence_at,
                    job_id,
                ),
            )

            if cursor.rowcount != 1:
                continue

            connection.execute(
                """
                INSERT INTO audit_log (
                    job_id,
                    action,
                    entity_type,
                    entity_id,
                    details_json,
                    created_at
                )
                VALUES (?, 'job_state_recovered', 'job', ?, ?, ?)
                """,
                (
                    job_id,
                    job_id,
                    json.dumps(
                        {
                            "evidence_kind": evidence_kind,
                            "evidence_stage": evidence_stage,
                            "evidence_at": evidence_at,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            repaired += 1

    return repaired

def store_metadata_analysis(
    database_path: Path,
    job_id: str,
    analysis: dict[str, Any],
    checksums: dict[str, str],
    *,
    finalize_job: bool = True,
) -> dict[str, Any]:
    now = utc_now_iso()

    files = analysis.get(
        "files",
        [],
    )

    families = analysis.get(
        "families",
        [],
    )

    if not isinstance(files, list):
        raise DatabaseError(
            "Analysefeld 'files' ist ungültig."
        )

    if not isinstance(families, list):
        raise DatabaseError(
            "Analysefeld 'families' ist ungültig."
        )

    expected_paths = {
        str(record["relative_path"])
        for record in files
    }

    checksum_paths = set(
        checksums
    )

    missing_checksums = (
        expected_paths
        - checksum_paths
    )

    if missing_checksums:
        raise DatabaseError(
            "Prüfsummen fehlen für: "
            + ", ".join(
                sorted(missing_checksums)
            )
        )

    family_ids: dict[str, int] = {}

    with database_connection(
        database_path
    ) as connection:
        job = connection.execute(
            """
            SELECT
                id,
                state
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if job is None:
            raise DatabaseError(
                f"Auftrag wurde nicht gefunden: {job_id}"
            )

        if job["state"] not in {
            "backup_verified",
            "analyzing_metadata",
            "organizing",
        }:
            raise DatabaseError(
                "Metadatenanalyse kann in diesem "
                "Auftragszustand nicht gespeichert werden: "
                + str(job["state"])
            )

        # Eine erneute Analyse ersetzt nur die abgeleiteten
        # Metadaten dieses Auftrags. Andere Auftragsdaten
        # bleiben unverändert.
        connection.execute(
            """
            DELETE FROM file_families
            WHERE job_id = ?
            """,
            (job_id,),
        )

        for family in families:
            family_key = str(
                family["family_key"]
            )

            status = str(
                family.get(
                    "status",
                    "detected",
                )
            )

            if status not in {
                "detected",
                "complete",
                "incomplete",
                "ambiguous",
                "review_required",
            }:
                raise DatabaseError(
                    "Ungültiger Familienstatus: "
                    + status
                )

            cursor = connection.execute(
                """
                INSERT INTO file_families (
                    job_id,
                    family_key,
                    original_stem,
                    status,
                    selected_capture_time,
                    capture_time_confidence
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?
                )
                """,
                (
                    job_id,
                    family_key,
                    Path(family_key).name,
                    status,
                    family.get(
                        "selected_capture_time"
                    ),
                    family.get(
                        "capture_time_confidence"
                    ),
                ),
            )

            family_ids[family_key] = int(
                cursor.lastrowid
            )

        stored_file_count = 0
        stored_candidate_count = 0
        review_required_count = 0

        for record in files:
            relative_path = str(
                record["relative_path"]
            )

            family_key = str(
                record["family_key"]
            )

            family_id = family_ids.get(
                family_key
            )

            if family_id is None:
                raise DatabaseError(
                    "Familie fehlt für Datei: "
                    + relative_path
                )

            confidence = str(
                record.get(
                    "capture_time_confidence",
                    "missing",
                )
            )

            review_required = bool(
                record.get(
                    "review_required",
                    True,
                )
            )

            review_status = (
                "required"
                if review_required
                else "not_required"
            )

            if review_required:
                review_required_count += 1

            checksum = str(
                checksums[relative_path]
            )

            cursor = connection.execute(
                """
                INSERT INTO files (
                    job_id,
                    family_id,
                    original_relative_path,
                    current_relative_path,
                    original_filename,
                    extension,
                    media_type,
                    size_bytes,
                    source_size_bytes,
                    sha256_original,
                    sha256_current,
                    selected_capture_time,
                    selected_capture_source,
                    capture_time_confidence,
                    review_status,
                    metadata_write_status,
                    created_at,
                    updated_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    ?,
                    'not_requested',
                    ?,
                    ?
                )
                """,
                (
                    job_id,
                    family_id,
                    relative_path,
                    relative_path,
                    str(record["filename"]),
                    str(record["extension"]),
                    str(record["media_type"]),
                    int(record["size_bytes"]),
                    int(record["size_bytes"]),
                    checksum,
                    checksum,
                    record.get(
                        "selected_capture_time"
                    ),
                    record.get(
                        "selected_capture_source"
                    ),
                    confidence,
                    review_status,
                    now,
                    now,
                ),
            )

            file_id = int(
                cursor.lastrowid
            )

            stored_file_count += 1

            candidates = record.get(
                "metadata_candidates",
                [],
            )

            if not isinstance(candidates, list):
                raise DatabaseError(
                    "Metadatenkandidaten sind ungültig: "
                    + relative_path
                )

            for candidate in candidates:
                connection.execute(
                    """
                    INSERT INTO metadata_candidates (
                        file_id,
                        metadata_group,
                        tag_name,
                        raw_value,
                        normalized_datetime,
                        timezone_source,
                        priority,
                        confidence,
                        is_selected,
                        conflicts_with_selected
                    )
                    VALUES (
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        file_id,
                        str(
                            candidate.get(
                                "metadata_group",
                                "",
                            )
                        ),
                        str(
                            candidate.get(
                                "tag_name",
                                "",
                            )
                        ),
                        candidate.get(
                            "raw_value"
                        ),
                        candidate.get(
                            "normalized_datetime"
                        ),
                        candidate.get(
                            "timezone_source"
                        ),
                        int(
                            candidate.get(
                                "priority",
                                9999,
                            )
                        ),
                        str(
                            candidate.get(
                                "confidence",
                                "unusable",
                            )
                        ),
                        1 if candidate.get(
                            "is_selected"
                        ) else 0,
                        1 if candidate.get(
                            "conflicts_with_selected"
                        ) else 0,
                    ),
                )

                stored_candidate_count += 1

        summary = analysis.get(
            "summary",
            {},
        )

        next_state = (
            "waiting_for_review"
            if finalize_job
            else "analyzing_metadata"
        )

        connection.execute(
            """
            UPDATE jobs
            SET
                state = ?,
                stage = 'metadata_analyzed',
                file_count = ?,
                total_size_bytes = ?,
                progress_current = ?,
                progress_total = ?,
                progress_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_state,
                stored_file_count,
                sum(
                    int(record["size_bytes"])
                    for record in files
                ),
                stored_file_count,
                stored_file_count,
                (
                    f"Metadatenanalyse abgeschlossen. "
                    f"{review_required_count} Dateien "
                    "benötigen eine Prüfung."
                ),
                now,
                job_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (
                ?,
                'metadata_analysis_stored',
                'job',
                ?,
                ?,
                ?
            )
            """,
            (
                job_id,
                job_id,
                json.dumps(
                    {
                        "summary": summary,
                        "stored_file_count":
                            stored_file_count,
                        "stored_family_count":
                            len(family_ids),
                        "stored_candidate_count":
                            stored_candidate_count,
                        "review_required_count":
                            review_required_count,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
                now,
            ),
        )

    return {
        "job_id": job_id,
        "stored_file_count": stored_file_count,
        "stored_family_count": len(family_ids),
        "stored_candidate_count": stored_candidate_count,
        "review_required_count": review_required_count,
    }


def list_job_families(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                ff.*,
                COUNT(f.id) AS member_count
            FROM file_families AS ff
            LEFT JOIN files AS f
                ON f.family_id = ff.id
            WHERE ff.job_id = ?
            GROUP BY ff.id
            ORDER BY ff.family_key
            """,
            (job_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def update_import_file_paths(
    database_path: Path,
    job_id: str,
    plan: list[dict[str, Any]],
    *,
    working_path: str,
) -> dict[str, Any]:
    """Persist the verified workspace path and effective capture state.

    The physical folder-import pipeline has already moved and SHA-verified the
    files before this callback runs.  SQLite must therefore mirror that exact
    Arbeitsbereich/Jahr/Tag state at both file and family level.
    """
    by_source = {
        str(item["source_relative_path"]): dict(item)
        for item in plan
    }
    if len(by_source) != len(plan):
        raise DatabaseError("Importplan enthält einen Quellpfad mehrfach.")

    now = utc_now_iso()
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT id,family_id,original_relative_path
               FROM files WHERE job_id=?""",
            (job_id,),
        ).fetchall()
        stored_paths = {str(row["original_relative_path"]) for row in rows}
        if stored_paths != set(by_source):
            missing = sorted(stored_paths - set(by_source))
            unexpected = sorted(set(by_source) - stored_paths)
            raise DatabaseError(
                "Importplan und gespeicherte Mediendateien stimmen nicht überein. "
                f"Ohne Ziel: {missing}; unbekannt: {unexpected}"
            )

        family_effective: dict[int, tuple[str | None, str]] = {}
        for row in rows:
            original = str(row["original_relative_path"])
            item = by_source[original]
            capture = (
                str(item.get("selected_capture_time") or "").strip() or None
            )
            confidence = str(
                item.get("capture_time_confidence") or "missing"
            )
            family_id = int(row["family_id"]) if row["family_id"] is not None else None
            if family_id is not None:
                existing = family_effective.get(family_id)
                candidate = (capture, confidence)
                if existing is None:
                    family_effective[family_id] = candidate
                elif existing[0] != capture:
                    raise DatabaseError(
                        "Eine importierte Dateifamilie besitzt widersprüchliche "
                        "wirksame Aufnahmezeiten."
                    )

            connection.execute(
                """UPDATE files
                   SET current_relative_path=?,
                       current_root_kind='shared_workspace',
                       selected_capture_time=?,
                       capture_time_confidence=?,
                       sha256_current=sha256_original,
                       updated_at=?
                   WHERE id=?""",
                (
                    str(item["destination_relative_path"]),
                    capture,
                    confidence,
                    now,
                    int(row["id"]),
                ),
            )

        for family_id, (capture, confidence) in family_effective.items():
            connection.execute(
                """UPDATE file_families
                   SET selected_capture_time=?,
                       capture_time_confidence=?
                   WHERE id=? AND job_id=?""",
                (capture, confidence, family_id, job_id),
            )

        connection.execute(
            """UPDATE jobs
               SET state='organizing',
                   stage='workspace_paths_persisted',
                   working_path=?,
                   progress_current=progress_total,
                   progress_message=?,
                   updated_at=?
               WHERE id=?""",
            (
                working_path,
                "Geprüfte Zielpfade und Tageszuordnung wurden in SQLite übernommen.",
                now,
                job_id,
            ),
        )

    return {
        "job_id": job_id,
        "updated_file_count": len(by_source),
        "updated_family_count": len(family_effective),
    }


def set_job_source_volume_label(
    database_path: Path,
    job_id: str,
    label: str,
) -> dict[str, Any]:
    clean = " ".join(str(label or "").split()).strip()
    if not clean:
        raise DatabaseError("Der sichtbare Sicherungsname darf nicht leer sein.")
    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE jobs SET source_volume_label=?,updated_at=? WHERE id=?",
            (clean, utc_now_iso(), job_id),
        )
    job = get_job(database_path, job_id)
    if job is None:
        raise DatabaseError(f"Auftrag fehlt nach Namensaktualisierung: {job_id}")
    return job


def list_job_files(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                f.*,
                ff.family_key,
                ff.status AS family_status
            FROM files AS f
            LEFT JOIN file_families AS ff
                ON ff.id = f.family_id
            WHERE f.job_id = ?
            ORDER BY f.original_relative_path
            """,
            (job_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def list_file_metadata_candidates(
    database_path: Path,
    file_id: int,
) -> list[dict[str, Any]]:
    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM metadata_candidates
            WHERE file_id = ?
            ORDER BY
                priority,
                tag_name,
                id
            """,
            (int(file_id),),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def list_job_day_groups(
    database_path: Path,
    job_id: str,
    *,
    excluded_family_ids: set[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Liefert die für den Arbeitsbereich benötigten Tagesgruppen.

    Es werden noch keine Ordner erzeugt. Die Gruppen werden
    ausschließlich aus den in SQLite gespeicherten Aufnahmezeiten
    berechnet.
    """

    excluded = sorted({int(value) for value in (excluded_family_ids or set())})
    exclusion_sql = ""
    exclusion_params: list[Any] = []
    if excluded:
        placeholders = ",".join("?" for _ in excluded)
        exclusion_sql = f" AND (family_id IS NULL OR family_id NOT IN ({placeholders}))"
        exclusion_params = excluded

    with database_connection(
        database_path
    ) as connection:
        dated_rows = connection.execute(
            f"""
            SELECT
                substr(
                    selected_capture_time,
                    1,
                    10
                ) AS day_key,

                COUNT(*) AS file_count,

                COUNT(
                    DISTINCT family_id
                ) AS family_count,

                COALESCE(
                    SUM(size_bytes),
                    0
                ) AS total_size_bytes,

                SUM(
                    CASE
                        WHEN review_status = 'required'
                        THEN 1
                        ELSE 0
                    END
                ) AS review_required_count,

                MIN(
                    selected_capture_time
                ) AS first_capture_time,

                MAX(
                    selected_capture_time
                ) AS last_capture_time

            FROM files

            WHERE job_id = ?
              AND selected_capture_time IS NOT NULL
              AND COALESCE(current_root_kind,'job_root') <> 'trash'
              AND NOT (
                  current_root_kind='shared_workspace'
                  AND (
                      current_relative_path IN ('Ohne_Datum','No Date')
                      OR (current_relative_path LIKE 'Ohne_Datum/%' OR current_relative_path LIKE 'No Date/%')
                  )
              )
              {exclusion_sql}

            GROUP BY
                substr(
                    selected_capture_time,
                    1,
                    10
                )

            ORDER BY day_key
            """,
            (job_id, *exclusion_params),
        ).fetchall()

        undated_row = connection.execute(
            f"""
            SELECT
                COUNT(*) AS file_count,

                COUNT(
                    DISTINCT family_id
                ) AS family_count,

                COALESCE(
                    SUM(size_bytes),
                    0
                ) AS total_size_bytes,

                SUM(
                    CASE
                        WHEN review_status = 'required'
                        THEN 1
                        ELSE 0
                    END
                ) AS review_required_count

            FROM files

            WHERE job_id = ?
              AND COALESCE(current_root_kind,'job_root') <> 'trash'
              AND (
                  selected_capture_time IS NULL
                  OR (
                      current_root_kind='shared_workspace'
                      AND (
                          current_relative_path IN ('Ohne_Datum','No Date')
                          OR (current_relative_path LIKE 'Ohne_Datum/%' OR current_relative_path LIKE 'No Date/%')
                      )
                  )
              )
              {exclusion_sql}
            """,
            (job_id, *exclusion_params),
        ).fetchone()

    result = []

    for row in dated_rows:
        item = dict(row)

        item["group_type"] = "day"
        item["has_date"] = True

        result.append(item)

    if (
        undated_row is not None
        and int(undated_row["file_count"]) > 0
    ):
        result.append({
            "day_key": None,
            "group_type": "without_date",
            "has_date": False,
            "file_count": int(
                undated_row["file_count"]
            ),
            "family_count": int(
                undated_row["family_count"]
            ),
            "total_size_bytes": int(
                undated_row["total_size_bytes"]
            ),
            "review_required_count": int(
                undated_row[
                    "review_required_count"
                ]
                or 0
            ),
            "first_capture_time": None,
            "last_capture_time": None,
        })

    return result


def event_display(connection, row):
    result=dict(row)
    if result.get('event_kind')=='no_event':
        segments=connection.execute('SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id',(result['id'],)).fetchall()
        if segments:
            result['start_datetime']=segments[0]['start_datetime']
            result['end_datetime']=segments[-1]['end_datetime']
        a=str(result['start_datetime'])[:10];b=str(result['end_datetime'])[:10]
        def de(day): return '.'.join(reversed(day.split('-')))
        result['display_title']=de(a)+(('–'+de(b)) if a!=b else '')+' · '+str(result.get('name') or 'Ohne Ereignis')
        result['time_segment_count']=len(segments)
    return result


def list_job_events(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            WITH direct_counts AS (
                SELECT
                    event_id,
                    COUNT(
                        DISTINCT family_id
                    ) AS family_count,
                    COUNT(
                        DISTINCT file_id
                    ) AS file_count

                FROM event_assignments

                GROUP BY event_id
            ),

            root_counts AS (
                SELECT
                    COALESCE(
                        assigned.parent_event_id,
                        assigned.id
                    ) AS root_event_id,

                    COUNT(
                        DISTINCT ea.family_id
                    ) AS family_count,

                    COUNT(
                        DISTINCT ea.file_id
                    ) AS file_count

                FROM event_assignments AS ea

                JOIN events AS assigned
                    ON assigned.id = ea.event_id

                WHERE assigned.job_id = ?

                GROUP BY root_event_id
            ),

            inventory_counts AS (
                SELECT event_id, root_kind,
                       COUNT(*) AS file_count,
                       COUNT(DISTINCT family_id) AS family_count
                FROM event_inventory_files
                WHERE job_id = ?
                  AND asset_kind IN ('camera_original','xmp','export','derived_media')
                GROUP BY event_id, root_kind
            ),

            pending_reassignments AS (
                SELECT event_id, COUNT(*) AS pending_count
                FROM event_reapply_removed_families
                WHERE target_event_id IS NULL
                  AND COALESCE(target_kind,'') <> 'released_free'
                GROUP BY event_id
            ),

            reconcile_targets AS (
                SELECT target_event_id,
                       MIN(event_id) AS reconcile_source_event_id,
                       COUNT(*) AS reconcile_link_count
                FROM event_reapply_removed_families
                WHERE job_id = ? AND target_event_id IS NOT NULL
                GROUP BY target_event_id
            )

            SELECT
                e.*,

                CASE
                    WHEN e.event_level = 'parent' AND e.status = 'archived'
                         AND archive_inventory.file_count IS NOT NULL
                    THEN archive_inventory.family_count
                    WHEN e.event_level = 'parent' AND e.status = 'applied'
                         AND workspace_inventory.file_count IS NOT NULL
                    THEN workspace_inventory.family_count
                    WHEN e.event_level = 'parent'
                    THEN COALESCE(root.family_count, 0)
                    ELSE COALESCE(direct.family_count, 0)
                END AS assigned_family_count,

                CASE
                    WHEN e.event_level = 'parent' AND e.status = 'archived'
                         AND archive_inventory.file_count IS NOT NULL
                    THEN archive_inventory.file_count
                    WHEN e.event_level = 'parent' AND e.status = 'applied'
                         AND workspace_inventory.file_count IS NOT NULL
                    THEN workspace_inventory.file_count
                    WHEN e.event_level = 'parent'
                    THEN COALESCE(root.file_count, 0)
                    ELSE COALESCE(direct.file_count, 0)
                END AS assigned_file_count,

                CASE
                    WHEN e.event_level = 'parent'
                    THEN COALESCE(pending.pending_count, 0)
                    ELSE 0
                END AS pending_reassignment_count,

                CASE WHEN reconcile_target.target_event_id IS NOT NULL THEN 1 ELSE 0 END
                    AS reconcile_target,
                reconcile_target.reconcile_source_event_id AS reconcile_source_event_id,
                COALESCE(reconcile_target.reconcile_link_count, 0) AS reconcile_link_count

            FROM events AS e

            LEFT JOIN direct_counts AS direct
                ON direct.event_id = e.id

            LEFT JOIN root_counts AS root
                ON root.root_event_id = e.id

            LEFT JOIN inventory_counts AS workspace_inventory
                ON workspace_inventory.event_id = e.id
               AND workspace_inventory.root_kind = 'shared_workspace'

            LEFT JOIN inventory_counts AS archive_inventory
                ON archive_inventory.event_id = e.id
               AND archive_inventory.root_kind = 'camera_archive'

            LEFT JOIN pending_reassignments AS pending
                ON pending.event_id = e.id

            LEFT JOIN reconcile_targets AS reconcile_target
                ON reconcile_target.target_event_id = e.id

            WHERE e.job_id = ?

            ORDER BY
                e.start_datetime,
                e.event_level,
                e.name
            """,
            (
                job_id,
                job_id,
                job_id,
                job_id,
            ),
        ).fetchall()

    with database_connection(database_path) as connection:
        return [event_display(connection,row) for row in rows]



def search_events(
    database_path: Path,
    query: str = "",
    limit: int = 25,
    offset: int = 0,
) -> dict[str, Any]:
    """Search parent events across all jobs without loading the full history."""
    needle = str(query or "").strip().lower()
    safe_limit = max(1, min(int(limit or 25), 100))
    safe_offset = max(0, int(offset or 0))
    params: list[Any] = []
    where = ["e.event_level='parent'", "COALESCE(TRIM(e.linkage_kind),'')=''" ]
    if needle:
        where.append("(LOWER(e.name) LIKE ? OR LOWER(e.folder_name) LIKE ? OR LOWER(e.start_datetime) LIKE ? OR LOWER(e.end_datetime) LIKE ? OR LOWER(COALESCE(j.source_volume_label,'')) LIKE ?)")
        like = f"%{needle}%"
        params.extend([like, like, like, like, like])
    where_sql = " AND ".join(where)
    with database_connection(database_path) as connection:
        total = connection.execute("SELECT COUNT(*) AS n FROM events WHERE event_level='parent' AND COALESCE(TRIM(linkage_kind),'')='' ").fetchone()["n"]
        matching = connection.execute(
            f"SELECT COUNT(*) AS n FROM events e JOIN jobs j ON j.id=e.job_id WHERE {where_sql}",
            params,
        ).fetchone()["n"]
        rows = connection.execute(
            f'''
            WITH root_counts AS (
              SELECT COALESCE(a.parent_event_id,a.id) AS root_event_id,
                     COUNT(DISTINCT ea.family_id) AS family_count,
                     COUNT(DISTINCT ea.file_id) AS file_count
              FROM event_assignments ea JOIN events a ON a.id=ea.event_id
              GROUP BY COALESCE(a.parent_event_id,a.id)
            ), inventory_counts AS (
              SELECT event_id,root_kind,COUNT(*) AS file_count,
                     COUNT(DISTINCT family_id) AS family_count
              FROM event_inventory_files
              WHERE asset_kind IN ('camera_original','xmp','export','derived_media')
              GROUP BY event_id,root_kind
            ), pending AS (
              SELECT event_id, COUNT(*) AS pending_count
              FROM event_reapply_removed_families
              WHERE target_event_id IS NULL
                AND COALESCE(target_kind,'') <> 'released_free'
              GROUP BY event_id
            ), active_mutation AS (
              SELECT id,job_id,anchor_event_id,status,affected_event_ids_json
              FROM event_mutations
              WHERE status IN ('pending_reassignment','pending_apply','manual_archive')
            ), reconcile_target AS (
              SELECT target_event_id, MIN(event_id) AS source_event_id, COUNT(*) AS link_count
              FROM event_reapply_removed_families
              WHERE target_event_id IS NOT NULL
              GROUP BY target_event_id
            )
            SELECT e.*,
                   CASE
                     WHEN e.status='archived' AND archive_inventory.file_count IS NOT NULL
                       THEN archive_inventory.family_count
                     WHEN e.status='applied' AND workspace_inventory.file_count IS NOT NULL
                       THEN workspace_inventory.family_count
                     ELSE COALESCE(root.family_count,0)
                   END AS assigned_family_count,
                   CASE
                     WHEN e.status='archived' AND archive_inventory.file_count IS NOT NULL
                       THEN archive_inventory.file_count
                     WHEN e.status='applied' AND workspace_inventory.file_count IS NOT NULL
                       THEN workspace_inventory.file_count
                     ELSE COALESCE(root.file_count,0)
                   END AS assigned_file_count,
                   COALESCE(pending.pending_count,0) AS pending_reassignment_count,
                   active_mutation.id AS mutation_id, active_mutation.status AS mutation_status,
                   active_mutation.anchor_event_id AS mutation_anchor_event_id,
                   CASE WHEN reconcile_target.target_event_id IS NOT NULL THEN 1 ELSE 0 END AS reconcile_target,
                   reconcile_target.source_event_id AS reconcile_source_event_id,
                   COALESCE(reconcile_target.link_count,0) AS reconcile_link_count,
                   j.created_at AS job_created_at, j.source_volume_label, j.operation
            FROM events e
            JOIN jobs j ON j.id=e.job_id
            LEFT JOIN root_counts root ON root.root_event_id=e.id
            LEFT JOIN inventory_counts workspace_inventory
              ON workspace_inventory.event_id=e.id
             AND workspace_inventory.root_kind='shared_workspace'
            LEFT JOIN inventory_counts archive_inventory
              ON archive_inventory.event_id=e.id
             AND archive_inventory.root_kind='camera_archive'
            LEFT JOIN pending ON pending.event_id=e.id
            LEFT JOIN active_mutation ON active_mutation.job_id=e.job_id
            LEFT JOIN reconcile_target ON reconcile_target.target_event_id=e.id
            WHERE {where_sql}
            ORDER BY COALESCE(e.updated_at,e.created_at) DESC, e.start_datetime DESC
            LIMIT ? OFFSET ?
            ''',
            [*params, safe_limit, safe_offset],
        ).fetchall()
    with database_connection(database_path) as connection:
        display_events=[event_display(connection,r) for r in rows]
    return {
        "events": display_events,
        "total_count": int(total or 0),
        "matching_count": int(matching or 0),
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": safe_offset + len(rows) < int(matching or 0),
    }

def list_archive_change_reviews(
    database_path: Path,
    job_id: str,
) -> list[dict[str, Any]]:
    with database_connection(
        database_path
    ) as connection:
        rows = connection.execute(
            """
            SELECT
                acr.*,
                f.original_filename,
                f.sha256_original,
                e.name AS event_name,
                e.folder_name AS event_folder_name

            FROM archive_change_reviews AS acr

            LEFT JOIN files AS f
                ON f.id = acr.file_id

            LEFT JOIN events AS e
                ON e.id = acr.event_id

            WHERE acr.job_id = ?

            ORDER BY
                CASE acr.review_status
                    WHEN 'manual_move_required' THEN 1
                    WHEN 'missing' THEN 2
                    WHEN 'ambiguous' THEN 3
                    WHEN 'pending' THEN 4
                    ELSE 5
                END,
                acr.expected_relative_path
            """,
            (job_id,),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def _validated_adjacent_extension(
    existing_range: tuple[str, str],
    selected_intervals: list[dict[str, Any]],
) -> dict[str, str]:
    """Validate one contiguous extension directly before or after an event."""
    from datetime import datetime, timedelta
    from app.released_ranges import merge_intervals

    selected = [
        (
            str(item.get("start_datetime") or "")[:19],
            str(item.get("end_datetime") or "")[:19],
        )
        for item in (selected_intervals or [])
        if item.get("start_datetime") and item.get("end_datetime")
    ]
    merged = merge_intervals(selected)
    if len(merged) != 1:
        raise ValueError(
            "Die Erweiterung muss aus einem zusammenhängenden freien Zeitraum bestehen."
        )

    current_start, current_end = (str(existing_range[0])[:19], str(existing_range[1])[:19])
    extension_start, extension_end = merged[0]
    if extension_end < extension_start:
        raise ValueError("Der Erweiterungszeitraum ist ungültig.")

    expected_after_start = (
        datetime.fromisoformat(current_end) + timedelta(seconds=1)
    ).isoformat(timespec="seconds")
    expected_before_end = (
        datetime.fromisoformat(current_start) - timedelta(seconds=1)
    ).isoformat(timespec="seconds")

    if extension_start == expected_after_start:
        return {
            "direction": "after",
            "current_start": current_start,
            "current_end": current_end,
            "extension_start": extension_start,
            "extension_end": extension_end,
            "new_start": current_start,
            "new_end": extension_end,
        }
    if extension_end == expected_before_end:
        return {
            "direction": "before",
            "current_start": current_start,
            "current_end": current_end,
            "extension_start": extension_start,
            "extension_end": extension_end,
            "new_start": extension_start,
            "new_end": current_end,
        }
    raise ValueError(
        "Ein bestehendes Ereignis kann nur durch unmittelbar angrenzende freie Zeit erweitert werden."
    )


def create_planned_event(
    database_path: Path,
    job_id: str,
    preview: dict[str, Any],
    *,
    ignore_event_ids: set[str] | None = None,
    transaction_connection: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """
    Store a server-validated event plan.

    Only SQLite rows are created. Files and folders are never changed.
    """

    import json
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(
        timezone.utc
    ).isoformat()

    event_kind = str(
        preview["event_kind"]
    )

    uses_time_range = bool(
        preview["uses_time_range"]
    )

    preserve_day_folders = bool(
        preview["preserve_day_folders"]
    )

    start_date = str(
        preview["start_date"]
    )

    end_date = str(
        preview["end_date"]
    )

    ignored_event_ids = {str(value) for value in (ignore_event_ids or set()) if str(value)}
    existing_parent_event_id = str(preview.get("existing_parent_event_id") or "").strip()
    if existing_parent_event_id:
        ignored_event_ids.add(existing_parent_event_id)
        if event_kind != "event":
            raise ValueError("Das Ziel muss ein normales Ereignis sein.")

        context = get_event_edit_context(database_path, job_id, existing_parent_event_id)
        existing = context['event']
        if existing['status'] == 'applied':
            from app.event_timeline import assert_editable_normal
            from app.event_structure import build_event_preview
            with database_connection(database_path) as connection:
                current = assert_editable_normal(connection, existing_parent_event_id)
            selected = preview.get('selected_intervals') or [{
                'start_datetime': start_date + 'T' + str(preview.get('start_time') or '00:00') + ':00',
                'end_datetime': end_date + 'T' + str(preview.get('end_time') or '23:59') + ':59'}]
            extension = _validated_adjacent_extension(current, selected)
            start, end = extension['new_start'], extension['new_end']
            from app.subevents import normalize_subevents
            added_subevents = normalize_subevents(
                preview.get('subevents') or [],
                extension['extension_start'],
                extension['extension_end'],
            )
            expanded = build_event_preview({
                'event_kind': 'event', 'event_name': existing['name'],
                'start_date': start[:10], 'end_date': end[:10],
                'start_time': start[11:16], 'end_time': end[11:16], 'uses_time_range': True,
                'preserve_day_folders': bool(existing['preserve_day_folders']),
                'subevents': [*(context['child_events'] or []), *added_subevents],
            }, [f for f in context['families'] if not f['assigned_elsewhere']])
            changed = update_event_definition(database_path, job_id, existing_parent_event_id, expanded,
                event_name=existing['name'], notes=existing['notes'] or '', expected_revision=existing['revision'])
            return {'parent_event': changed['event'], 'child_event': None,
                'assignment_event_id': existing_parent_event_id, 'assignment_source': 'date_range',
                'assigned_family_count': len(expanded['selected_family_ids']),
                'assigned_family_ids': expanded['selected_family_ids'], 'resort_required': True}

    requested_family_ids = sorted({
        int(value)
        for value in (
            preview.get(
                "selected_family_ids",
                [],
            )
        )
    })

    if not requested_family_ids:
        raise ValueError(
            "Es wurden keine freien "
            "Dateifamilien ausgewählt."
        )

    no_event_segments = []
    if event_kind == "no_event":
        from app.event_timeline import normalize_no_event_segments
        no_event_segments = normalize_no_event_segments(preview.get("no_event_segments") or [])
        months = {segment["day_key"][:7] for segment in no_event_segments}
        if len(months) != 1:
            raise ValueError(
                "Eine „Ohne Ereignis“-Sammlung bleibt ein Monatsordner. "
                "Bitte Tage aus verschiedenen Monaten getrennt anlegen."
            )
        # Die beiden alten Event-Spalten dienen fuer no_event nur noch als
        # technischer Kompatibilitaetsrahmen. Fuehrend sind die Segmente.
        parent_start = no_event_segments[0]["start_datetime"]
        parent_end = no_event_segments[-1]["end_datetime"]
        assignment_start = parent_start
        assignment_end = parent_end
        assignment_source = "date_time_range"
    else:
        parent_start = f"{start_date}T00:00:00"
        parent_end = f"{end_date}T23:59:59"

    if event_kind != "no_event" and uses_time_range:
        assignment_start = (
            f"{start_date}T"
            f"{preview['start_time']}:00"
        )

        assignment_end = (
            f"{end_date}T"
            f"{preview['end_time']}:59"
        )

        assignment_source = (
            "date_time_range"
        )

    elif event_kind != "no_event":
        assignment_start = parent_start
        assignment_end = parent_end
        assignment_source = "date_range"

    if event_kind == "event":
        parent_start, parent_end = assignment_start, assignment_end

    parent_event_id = existing_parent_event_id or (
        "EVENT_"
        + uuid.uuid4().hex.upper()
    )

    child_event_id = (
        "EVENT_"
        + uuid.uuid4().hex.upper()
        if preview.get("child_folder") and not existing_parent_event_id
        else None
    )

    assignment_event_id = (
        child_event_id
        if child_event_id is not None
        else parent_event_id
    )

    placeholders = ",".join(
        "?"
        for _ in requested_family_ids
    )

    with (
        database_connection(database_path)
        if transaction_connection is None
        else nullcontext(transaction_connection)
    ) as connection:
        if transaction_connection is None:
            connection.execute("BEGIN IMMEDIATE")

        job = connection.execute(
            """
            SELECT id
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if job is None:
            connection.rollback()

            raise ValueError(
                "Sicherung wurde nicht gefunden."
            )

        # 0.19.0: Pro Kalendermonat existiert genau eine sichtbare
        # „Ohne Ereignis“-Sammlung. Neue Segmente müssen die bestehende
        # Sammlung fortführen statt einen zweiten Monatsordner anzulegen.
        if event_kind == "no_event":
            month_key = no_event_segments[0]["day_key"][:7]
            existing_no_event = connection.execute(
                """SELECT id,status,folder_name FROM events
                   WHERE parent_event_id IS NULL AND event_kind='no_event'
                     AND status IN ('planned','applied','archived')
                     AND substr(start_datetime,1,7)=?
                   ORDER BY CASE status WHEN 'planned' THEN 0 WHEN 'applied' THEN 1 ELSE 2 END,
                            updated_at DESC LIMIT 1""",
                (month_key,),
            ).fetchone()
            if existing_no_event is not None and str(existing_no_event["id"]) not in ignored_event_ids:
                connection.rollback()
                raise ValueError(
                    f"Für {month_key} existiert bereits die Monats-Sammlung „{existing_no_event['folder_name']}“ "
                    f"({existing_no_event['status']}). Bitte diese bestehende „Ohne Ereignis“-Sammlung fortführen."
                )

        existing_parent_row = None
        extension_details = None
        if existing_parent_event_id:
            existing_parent_row = connection.execute(
                """SELECT * FROM events WHERE id=? AND job_id=? AND parent_event_id IS NULL""",
                (existing_parent_event_id, job_id),
            ).fetchone()
            if existing_parent_row is None:
                connection.rollback()
                raise ValueError("Das ausgewählte Oberereignis wurde nicht gefunden.")
            if str(existing_parent_row["event_kind"]) != "event" or str(existing_parent_row["status"]) != "planned":
                connection.rollback()
                raise ValueError("Dieses normale Ereignis kann nicht direkt erweitert werden.")
            from app.event_timeline import assert_editable_normal
            existing_range = assert_editable_normal(connection, existing_parent_event_id)
            selected = preview.get('selected_intervals') or [{'start_datetime': assignment_start, 'end_datetime': assignment_end}]
            extension_details = _validated_adjacent_extension(existing_range, selected)
            parent_start, parent_end = extension_details['new_start'], extension_details['new_end']

        family_rows = connection.execute(
            f"""
            SELECT
                id,
                job_id,
                family_key,
                selected_capture_time

            FROM file_families

            WHERE id IN (
                    {placeholders}
                  )

            ORDER BY
                selected_capture_time,
                id
            """,
            tuple(requested_family_ids),
        ).fetchall()

        found_family_ids = {
            int(row["id"])
            for row in family_rows
        }

        missing_family_ids = sorted(
            set(requested_family_ids)
            - found_family_ids
        )

        if missing_family_ids:
            connection.rollback()

            raise ValueError(
                "Die Auswahl ist nicht mehr aktuell. "
                "Mindestens eine Dateifamilie fehlt. "
                "Bitte den Arbeitsbereich aktualisieren."
            )

        outside_range = []
        for row in family_rows:
            capture = str(row["selected_capture_time"] or "")[:19]
            if not capture:
                outside_range.append(int(row["id"]))
                continue
            if event_kind == "no_event":
                if not any(seg["start_datetime"] <= capture <= seg["end_datetime"] for seg in no_event_segments):
                    outside_range.append(int(row["id"]))
            elif not (assignment_start <= capture <= assignment_end):
                outside_range.append(int(row["id"]))

        if outside_range:
            connection.rollback()

            raise ValueError(
                "Die ausgewählten Dateifamilien "
                "passen nicht vollständig zum "
                "eingetragenen Zeitraum."
            )

        conflicting_rows = connection.execute(
            f"""
            SELECT
                ea.family_id,
                COALESCE(
                    parent.id,
                    assigned.id
                ) AS root_event_id,
                COALESCE(
                    parent.name,
                    assigned.name
                ) AS root_event_name

            FROM event_assignments AS ea

            JOIN events AS assigned
                ON assigned.id = ea.event_id

            LEFT JOIN events AS parent
                ON parent.id =
                   assigned.parent_event_id

            WHERE ea.family_id IN (
                {placeholders}
            )
              AND assigned.status IN (
                    'draft',
                    'planned',
                    'applied',
                    'archived'
                  )
              AND (
                    parent.id IS NULL
                    OR parent.status IN (
                        'draft',
                        'planned',
                        'applied',
                        'archived'
                    )
                  )

            ORDER BY
                ea.family_id,
                root_event_name
            """,
            tuple(requested_family_ids),
        ).fetchall()

        if ignored_event_ids and conflicting_rows:
            conflicting_rows = [
                row for row in conflicting_rows
                if str(row["root_event_id"]) not in ignored_event_ids
            ]

        if conflicting_rows:
            connection.rollback()

            conflicting_family_count = len({
                int(row["family_id"])
                for row in conflicting_rows
            })

            event_names = sorted({
                str(row["root_event_name"])
                for row in conflicting_rows
            })

            if conflicting_family_count == 1:
                subject = (
                    "1 Dateifamilie ist"
                )
            else:
                subject = (
                    f"{conflicting_family_count} "
                    "Dateifamilien sind"
                )

            raise ValueError(
                subject
                + " bereits zugeordnet: "
                + ", ".join(
                    f"„{name}“"
                    for name in event_names
                )
                + ". Bitte den Arbeitsbereich aktualisieren."
            )

        # 0.16.5: Zeitdefinitionen duerfen sich unabhaengig von der
        # aktuell sichtbaren Familienauswahl nicht widersprechen.
        from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
        if event_kind == "no_event":
            overlaps = []
            segment_overlaps = []
            for segment in no_event_segments:
                overlaps.extend(continuous_event_overlaps(
                    connection, job_id, segment["start_datetime"], segment["end_datetime"]
                ))
                segment_overlaps.extend(no_event_segment_overlaps(
                    connection, job_id, segment["start_datetime"], segment["end_datetime"]
                ))
            if ignored_event_ids:
                overlaps = [item for item in overlaps if str(item.get("id") or item.get("event_id") or "") not in ignored_event_ids]
                segment_overlaps = [item for item in segment_overlaps if str(item.get("event_id") or "") not in ignored_event_ids]
            if overlaps:
                names = sorted({str(item["name"]) for item in overlaps})
                connection.rollback()
                raise ValueError(
                    "„Ohne Ereignis“ überschneidet sich mit einem bestehenden Ereignis: "
                    + ", ".join(f"„{name}“" for name in names)
                    + ". Bitte die Uhrzeiten der betroffenen Tage anpassen."
                )
            if segment_overlaps:
                connection.rollback()
                raise ValueError(
                    "Dieser Zeitraum gehört bereits zu einer bestehenden „Ohne Ereignis“-Sammlung. "
                    "Bitte diese Sammlung erweitern oder bearbeiten, statt eine überlappende zweite anzulegen."
                )
        else:
            overlaps = continuous_event_overlaps(connection, job_id, assignment_start, assignment_end)
            no_event_overlaps = no_event_segment_overlaps(connection, job_id, assignment_start, assignment_end)
            if ignored_event_ids:
                overlaps = [item for item in overlaps if str(item.get("id") or "") not in ignored_event_ids]
                no_event_overlaps = [item for item in no_event_overlaps if str(item.get("event_id") or "") not in ignored_event_ids]
            if overlaps or no_event_overlaps:
                names = sorted({str(item.get("name") or "Ohne Ereignis") for item in overlaps + no_event_overlaps})
                connection.rollback()
                raise ValueError(
                    "Der neue Ereigniszeitraum überschneidet sich mit bereits belegter Zeit: "
                    + ", ".join(f"„{name}“" for name in names)
                    + ". Die App hat freie Zeitbereiche vorausgefüllt, soweit sie eindeutig waren."
                )

        if not existing_parent_event_id:
            connection.execute(
                """
                INSERT INTO events (
                    id,
                    job_id,
                    parent_event_id,
                    event_level,
                    name,
                    start_datetime,
                    end_datetime,
                    uses_time_range,
                    folder_name,
                    status,
                    created_at,
                    updated_at,
                    event_kind,
                    preserve_day_folders,
                    revision,
                    applied_at,
                    archived_at
                )
                VALUES (
                    ?,
                    ?,
                    NULL,
                    'parent',
                    ?,
                    ?,
                    ?,
                    0,
                    ?,
                    'planned',
                    ?,
                    ?,
                    ?,
                    ?,
                    1,
                    NULL,
                    NULL
                )
                """,
                (
                    parent_event_id,
                    job_id,
                    str(preview["event_name"]),
                    parent_start,
                    parent_end,
                    str(preview["parent_folder"]),
                    now,
                    now,
                    event_kind,
                    int(preserve_day_folders),
                ),
            )
            connection.execute(
                "UPDATE events SET folder_naming_json=? WHERE id=?",
                (
                    json.dumps(
                        preview.get("folder_naming") or {},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    parent_event_id,
                ),
            )

        if event_kind == "event":
            connection.execute("UPDATE events SET start_datetime=?,end_datetime=?,time_model_version=2,updated_at=?,revision=revision+? WHERE id=?",
                (parent_start,parent_end,now,int(bool(existing_parent_event_id)),parent_event_id))

        if event_kind == "no_event":
            from app.event_timeline import replace_event_segments
            connection.execute(
                "UPDATE events SET timeline_model='segments' WHERE id = ?",
                (parent_event_id,),
            )
            replace_event_segments(
                connection, event_id=parent_event_id, job_id=job_id,
                segments=no_event_segments, now=now, source="user",
            )

        if child_event_id is not None:
            connection.execute(
                """
                INSERT INTO events (
                    id,
                    job_id,
                    parent_event_id,
                    event_level,
                    name,
                    start_datetime,
                    end_datetime,
                    uses_time_range,
                    folder_name,
                    status,
                    created_at,
                    updated_at,
                    event_kind,
                    preserve_day_folders,
                    revision,
                    applied_at,
                    archived_at
                )
                VALUES (
                    ?,
                    ?,
                    ?,
                    'child',
                    ?,
                    ?,
                    ?,
                    1,
                    ?,
                    'planned',
                    ?,
                    ?,
                    'event',
                    ?,
                    1,
                    NULL,
                    NULL
                )
                """,
                (
                    child_event_id,
                    job_id,
                    parent_event_id,
                    str(
                        preview[
                            "child_event_name"
                        ]
                    ),
                    assignment_start,
                    assignment_end,
                    str(preview["child_folder"]),
                    now,
                    now,
                    int(preserve_day_folders),
                ),
            )

        connection.executemany(
            """
            INSERT INTO event_assignments (
                event_id,
                family_id,
                file_id,
                assignment_source,
                created_at
            )
            VALUES (
                ?,
                ?,
                NULL,
                ?,
                ?
            )
            """,
            [
                (
                    assignment_event_id,
                    family_id,
                    assignment_source,
                    now,
                )
                for family_id
                in requested_family_ids
            ],
        )

        if preview.get('subevents'):
            from app.subevents import normalize_subevents,store_subevents,assignment_target,append_extension_subevents
            if existing_parent_event_id:
                if extension_details is None:
                    raise ValueError("Der Erweiterungsbereich konnte nicht bestimmt werden.")
                children=append_extension_subevents(
                    connection,
                    parent_event_id,
                    preview['subevents'],
                    extension_details['extension_start'],
                    extension_details['extension_end'],
                    now,
                    naming=preview.get("folder_naming"),
                )
                for row in family_rows:
                    connection.execute('UPDATE event_assignments SET event_id=? WHERE family_id=? AND event_id=?',
                        (assignment_target(parent_event_id,children,str(row['selected_capture_time'])[:19]),row['id'],assignment_event_id))
            else:
                organizational=normalize_subevents(
                    preview['subevents'],
                    parent_start,
                    parent_end,
                    naming=preview.get("folder_naming"),
                )
                children=store_subevents(connection,parent_event_id,organizational,now)
                for row in family_rows:
                    connection.execute('UPDATE event_assignments SET event_id=? WHERE family_id=? AND event_id=?',
                        (assignment_target(parent_event_id,children,str(row['selected_capture_time'])[:19]),row['id'],assignment_event_id))

        from app.event_access import register_source_jobs
        from app.event_layout import ensure_event_layout_snapshot, update_event_layout
        source_job_ids = sorted({
            str(row["job_id"]) for row in family_rows
            if row["job_id"] is not None
        })
        register_source_jobs(
            connection,
            parent_event_id,
            [job_id, *source_job_ids],
            created_at=now,
        )
        ensure_event_layout_snapshot(connection, parent_event_id, now=now)
        preview_layout = preview.get("folder_layout")
        if isinstance(preview_layout, dict):
            update_event_layout(
                connection,
                parent_event_id,
                structure_enabled=bool(preview_layout.get("structure_enabled", True)),
                input_path=str(preview_layout.get("input_path") or ""),
                layout=preview_layout.get("layout") or {},
                updated_at=now,
            )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (
                ?,
                'event_planned',
                'event',
                ?,
                ?,
                ?
            )
            """,
            (
                job_id,
                parent_event_id,
                json.dumps(
                    {
                        "event_kind": event_kind,
                        "parent_event_id": (
                            parent_event_id
                        ),
                        "child_event_id": (
                            child_event_id
                        ),
                        "assignment_event_id": (
                            assignment_event_id
                        ),
                        "assignment_source": (
                            assignment_source
                        ),
                        "assigned_family_count": len(
                            requested_family_ids
                        ),
                        "assigned_family_ids": (
                            requested_family_ids
                        ),
                        "start_datetime": (
                            assignment_start
                        ),
                        "end_datetime": (
                            assignment_end
                        ),
                        "preserve_day_folders": (
                            preserve_day_folders
                        ),
                        "structure_lines": (
                            preview.get(
                                "structure_lines",
                                [],
                            )
                        ),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                now,
            ),
        )

        # The owner of the shared SQLite connection commits all dependent state.
        if transaction_connection is None:
            connection.commit()

        parent_row = connection.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
            """,
            (parent_event_id,),
        ).fetchone()

        child_row = (
            connection.execute(
                """
                SELECT *
                FROM events
                WHERE id = ?
                """,
                (child_event_id,),
            ).fetchone()
            if child_event_id
            else None
        )

    return {
        "parent_event": dict(parent_row),
        "child_event": (
            dict(child_row)
            if child_row is not None
            else None
        ),
        "assignment_event_id": (
            assignment_event_id
        ),
        "assignment_source": assignment_source,
        "assigned_family_count": len(
            requested_family_ids
        ),
        "assigned_family_ids": (
            requested_family_ids
        ),
    }


def delete_planned_event(
    database_path: Path,
    job_id: str,
    event_id: str,
    *,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Delete or safely prepare deletion of one parent event.

    * draft/planned: DB-only deletion, families become free immediately.
    * applied: all assigned families enter the durable reassignment queue;
      after reassignment a verified reapply moves the files and removes the
      now-empty source event.
    * archived: a manual read-only archive change request is created.  The
      camera library itself is never modified by this function.
    """
    now = datetime.now(timezone.utc).isoformat()

    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
            (event_id,),
        ).fetchone()
        if event is None:
            raise ValueError("Ereignis wurde nicht gefunden.")
        job_id = str(event["job_id"])
        from app.event_mutation import assert_no_active_mutation
        assert_no_active_mutation(connection, job_id, event_id=event_id)
        if event["event_level"] != "parent":
            raise ValueError("Unterereignisse können nicht einzeln gelöscht werden. Bitte das Hauptereignis löschen.")
        from app.event_structure_changes import assert_no_open_structure_change
        assert_no_open_structure_change(connection, event_id)
        if int(event["pending_delete"] or 0):
            raise ValueError("Für dieses Ereignis läuft bereits ein Löschvorgang.")

        active_sort_run = connection.execute(
            """SELECT id FROM sort_runs WHERE event_id=? AND status IN
               ('queued','verifying','moving','finalizing','rolling_back','interrupted')
               ORDER BY created_at DESC LIMIT 1""", (event_id,)
        ).fetchone()
        if active_sort_run is not None:
            raise ValueError("Das Ereignis besitzt einen aktiven oder unterbrochenen Sortierlauf: " + str(active_sort_run["id"]))

        child_rows = connection.execute(
            "SELECT id FROM events WHERE parent_event_id=? AND job_id=? ORDER BY id",
            (event_id, job_id),
        ).fetchall()
        event_ids = [event_id, *[str(row["id"]) for row in child_rows]]
        placeholders = ",".join("?" for _ in event_ids)
        assigned_rows = connection.execute(
            f"""SELECT DISTINCT ea.family_id
                FROM event_assignments ea
                WHERE ea.event_id IN ({placeholders}) AND ea.family_id IS NOT NULL
                ORDER BY ea.family_id""", tuple(event_ids)
        ).fetchall()
        family_ids = [int(row["family_id"]) for row in assigned_rows]
        file_count = 0
        if family_ids:
            fp = ",".join("?" for _ in family_ids)
            file_count = int(connection.execute(
                f"SELECT COUNT(*) FROM files WHERE family_id IN ({fp})",
                tuple(family_ids),
            ).fetchone()[0])

        status = str(event["status"])
        event_name = str(event["name"])
        folder_name = str(event["folder_name"])

        if status in {"draft", "planned"} and event["applied_at"] is None and event["archived_at"] is None:
            connection.execute("BEGIN IMMEDIATE")
            if family_ids:
                if str(event["event_kind"] or "event") == "no_event":
                    release_rows = connection.execute(
                        "SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                        (event_id,),
                    ).fetchall()
                    release_ranges = [
                        (str(r["start_datetime"])[:19], str(r["end_datetime"])[:19])
                        for r in release_rows
                    ]
                else:
                    from app.event_timeline import normal_event_ranges
                    release_ranges = normal_event_ranges(connection, event_id)
                from app.released_ranges import split_intervals_by_day, range_for_capture
                release_ranges = split_intervals_by_day(release_ranges)
                fp = ",".join("?" for _ in family_ids)
                capture_rows = connection.execute(
                    f"SELECT id,job_id,selected_capture_time FROM file_families WHERE id IN ({fp})",
                    tuple(family_ids),
                ).fetchall()
                release_by_family = {
                    int(r["id"]): range_for_capture(
                        str(r["selected_capture_time"] or "")[:19], release_ranges
                    )
                    for r in capture_rows
                }
                existing_release_markers = {
                    int(row["family_id"]): dict(row)
                    for row in connection.execute(
                        f"""SELECT job_id,family_id,released_start_datetime,
                                   released_end_datetime,created_at,archive_origin
                            FROM released_free_families
                            WHERE family_id IN ({fp})""",
                        tuple(family_ids),
                    ).fetchall()
                }
                release_marker_rows = []
                for fid in family_ids:
                    capture_row = next(
                        row for row in capture_rows if int(row["id"]) == fid
                    )
                    existing_marker = existing_release_markers.get(fid)
                    archive_origin = bool(
                        existing_marker
                        and int(existing_marker.get("archive_origin") or 0)
                    )
                    fresh_range = release_by_family.get(fid)
                    if archive_origin:
                        # Familien aus einer bestätigten Archivänderung behalten
                        # ihre ursprüngliche Freigabe-Provenienz auch dann, wenn
                        # eine zwischenzeitliche Planung wieder gelöscht wird.
                        # Sonst würde INSERT OR REPLACE archive_origin auf 0
                        # zurücksetzen und der Bestand aus „Freigewordene
                        # Archivdateien“ aus der UI verschwinden.
                        released_start = existing_marker.get(
                            "released_start_datetime"
                        )
                        released_end = existing_marker.get(
                            "released_end_datetime"
                        )
                        created_at = str(existing_marker.get("created_at") or now)
                    else:
                        released_start = fresh_range[0] if fresh_range else None
                        released_end = fresh_range[1] if fresh_range else None
                        created_at = now
                    release_marker_rows.append((
                        str(capture_row["job_id"]),
                        fid,
                        released_start,
                        released_end,
                        created_at,
                        1 if archive_origin else 0,
                    ))
                connection.executemany(
                    """INSERT OR REPLACE INTO released_free_families(
                           job_id,family_id,released_start_datetime,released_end_datetime,
                           created_at,archive_origin)
                       VALUES (?,?,?,?,?,?)""",
                    release_marker_rows,
                )
            connection.execute("DELETE FROM events WHERE id=? AND job_id=?", (event_id, job_id))
            connection.execute(
                """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'event_plan_deleted','event',?,?,?)""",
                (job_id, event_id, json.dumps({
                    "event_name": event_name, "folder_name": folder_name,
                    "released_family_count": len(family_ids), "released_file_count": file_count,
                }, ensure_ascii=False, sort_keys=True), now),
            )
            connection.commit()
            return {
                "job_id": job_id, "event_id": event_id, "event_name": event_name,
                "folder_name": folder_name, "deleted_child_count": len(child_rows),
                "deleted_assignment_count": len(family_ids), "released_family_count": len(family_ids),
                "released_file_count": file_count, "files_changed": False,
                "folders_changed": False, "pending_delete": False,
                "reassignment_required": False,
            }

        if status == "applied" and event["applied_at"] is not None and event["archived_at"] is None:
            if int(event["resort_required"] or 0):
                raise ValueError("Für dieses Ereignis ist bereits eine Nachsortierung offen. Bitte diese zuerst abschließen oder verwerfen.")
            from app.event_mutation import capture_job_event_state, begin_mutation, set_mutation_target
            original_mutation_state = capture_job_event_state(connection, job_id)
            connection.execute("BEGIN IMMEDIATE")
            mutation_id = begin_mutation(
                connection, job_id=job_id, anchor_event_id=event_id, mutation_kind="delete",
                affected_event_ids=[event_id], original_state=original_mutation_state,
                status="pending_apply",
            )
            connection.execute("DELETE FROM event_reapply_removed_families WHERE event_id=?", (event_id,))
            if family_ids:
                if str(event["event_kind"] or "event") == "no_event":
                    delete_definition_rows = connection.execute(
                        "SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                        (event_id,),
                    ).fetchall()
                else:
                    delete_definition_rows = connection.execute(
                        "SELECT start_datetime,end_datetime FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
                        (event_id,),
                    ).fetchall()
                delete_ranges = (
                    [(str(r["start_datetime"])[:19],str(r["end_datetime"])[:19]) for r in delete_definition_rows]
                    if delete_definition_rows else
                    [(str(event["start_datetime"])[:19],str(event["end_datetime"])[:19])]
                )
                from app.released_ranges import split_intervals_by_day, range_for_capture
                delete_ranges = split_intervals_by_day(delete_ranges)
                fp = ",".join("?" for _ in family_ids)
                delete_capture_rows = connection.execute(
                    f"SELECT id,job_id,selected_capture_time FROM file_families WHERE id IN ({fp})",
                    tuple(family_ids),
                ).fetchall()
                delete_range_by_family = {
                    int(r["id"]): range_for_capture(str(r["selected_capture_time"] or "")[:19], delete_ranges)
                    for r in delete_capture_rows
                }
                connection.executemany(
                    """INSERT INTO event_reapply_removed_families(
                           event_id,job_id,family_id,created_at,released_start_datetime,released_end_datetime)
                       VALUES (?,?,?,?,?,?)""",
                    [(
                        event_id,
                        str(next(row["job_id"] for row in delete_capture_rows if int(row["id"]) == fid)),
                        fid,
                        now,
                        delete_range_by_family.get(fid)[0] if delete_range_by_family.get(fid) else None,
                        delete_range_by_family.get(fid)[1] if delete_range_by_family.get(fid) else None,
                    ) for fid in family_ids],
                )
            connection.execute(
                "DELETE FROM event_assignments WHERE event_id=? OR event_id IN (SELECT id FROM events WHERE parent_event_id=?)",
                (event_id, event_id),
            )
            connection.execute(
                "UPDATE events SET pending_delete=1,resort_required=1,updated_at=?,edited_at=? WHERE id=?",
                (now, now, event_id),
            )
            set_mutation_target(
                connection, mutation_id, capture_job_event_state(connection, job_id),
                status="pending_apply",
            )
            connection.execute(
                """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'event_delete_prepared','event',?,?,?)""",
                (job_id, event_id, json.dumps({
                    "event_name": event_name, "family_ids": family_ids,
                    "archive_read_only": False,
                }, ensure_ascii=False, sort_keys=True), now),
            )
            connection.commit()
            return {
                "job_id": job_id, "event_id": event_id, "event_name": event_name,
                "folder_name": folder_name, "released_family_count": len(family_ids),
                "released_file_count": file_count, "files_changed": False,
                "folders_changed": False, "pending_delete": True,
                "reassignment_required": False, "removed_family_ids": family_ids,
                "status": "pending_delete", "mutation_id": mutation_id,
                "message": "Löschung vorbereitet. Bitte den Zielplan prüfen und die Löschung jetzt anwenden oder verwerfen.",
            }

        if status == "archived" or event["archived_at"] is not None:
            # Import late to avoid a module cycle at import time.
            from app.event_change_request import propose_archived_event_deletion
            return propose_archived_event_deletion(
                database_path,
                job_id,
                event_id,
                archive_root=archive_root,
            )

        raise ValueError("Dieser Ereigniszustand kann nicht sicher gelöscht werden.")



def get_event_edit_context(
    database_path: Path,
    job_id: str,
    event_id: str,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Return one parent event plus all library families for safe editing.

    Import jobs are provenance only. Structural edits of applied events and
    „Ohne Ereignis“ must therefore be able to absorb free families from every
    backup projected into this library, not only from the anchor job.
    """
    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND job_id = ?",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            raise ValueError("Ereignis wurde nicht gefunden.")
        if event["event_level"] != "parent":
            raise ValueError("Nur Hauptereignisse können bearbeitet werden.")
        if str(event["linkage_kind"] or "").strip():
            raise ValueError("Technische Nachträge werden nicht als Ereignisse bearbeitet.")

        children = connection.execute(
            "SELECT * FROM events WHERE parent_event_id = ? ORDER BY start_datetime, id",
            (event_id,),
        ).fetchall()
        child = children[0] if children else None
        assigned_rows = connection.execute(
            """
            SELECT DISTINCT ea.family_id
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            LEFT JOIN events root ON root.id = assigned.parent_event_id
            WHERE ea.family_id IS NOT NULL
              AND (
                    COALESCE(root.id, assigned.id) = ?
                    OR (
                         COALESCE(root.linked_event_id, assigned.linked_event_id) = ?
                         AND COALESCE(root.linkage_kind, assigned.linkage_kind) = 'archived_manual'
                         AND COALESCE(root.status, assigned.status) = 'archived'
                       )
                  )
            """,
            (event_id, event_id),
        ).fetchall()
        assigned_ids = {int(row["family_id"]) for row in assigned_rows}

        segment_rows = connection.execute(
            """SELECT * FROM event_time_segments WHERE event_id = ?
               ORDER BY start_datetime, id""",
            (event_id,),
        ).fetchall()

        family_rows = connection.execute(
            """
            SELECT ff.id AS family_id, ff.job_id, ff.family_key, ff.original_stem,
                   ff.selected_capture_time, ff.capture_time_confidence,
                   COUNT(DISTINCT f.id) AS file_count,
                   COALESCE(SUM(f.size_bytes), 0) AS total_size_bytes,
                   COALESCE(SUM(CASE WHEN f.review_status = 'required' THEN 1 ELSE 0 END), 0) AS review_required_count,
                   GROUP_CONCAT(DISTINCT COALESCE(linked_target.name, root.name, assigned.name)) AS assigned_event_names,
                   MAX(CASE WHEN (
                         COALESCE(root.id, assigned.id) = ?
                         OR (
                              COALESCE(root.linked_event_id, assigned.linked_event_id) = ?
                              AND COALESCE(root.linkage_kind, assigned.linkage_kind) = 'archived_manual'
                              AND COALESCE(root.status, assigned.status) = 'archived'
                            )
                       ) THEN 1 ELSE 0 END) AS assigned_here,
                   MAX(CASE WHEN assigned.id IS NOT NULL AND NOT (
                         COALESCE(root.id, assigned.id) = ?
                         OR (
                              COALESCE(root.linked_event_id, assigned.linked_event_id) = ?
                              AND COALESCE(root.linkage_kind, assigned.linkage_kind) = 'archived_manual'
                              AND COALESCE(root.status, assigned.status) = 'archived'
                            )
                       ) THEN 1 ELSE 0 END) AS assigned_elsewhere
            FROM file_families ff
            LEFT JOIN files f ON f.family_id = ff.id AND f.job_id = ff.job_id
            LEFT JOIN event_assignments ea ON ea.family_id = ff.id
            LEFT JOIN events assigned ON assigned.id = ea.event_id AND assigned.status IN ('draft','planned','applied','archived')
            LEFT JOIN events root ON root.id = assigned.parent_event_id
            LEFT JOIN events linked_target ON linked_target.id = COALESCE(root.linked_event_id, assigned.linked_event_id)
            GROUP BY ff.id
            ORDER BY ff.selected_capture_time, ff.id
            """,
            (event_id, event_id, event_id, event_id),
        ).fetchall()

        from app.event_access import event_source_jobs
        from app.event_layout import ensure_event_layout_snapshot
        folder_layout = ensure_event_layout_snapshot(
            connection, event_id, now=utc_now_iso()
        )
        source_jobs = event_source_jobs(connection, event_id)

        live_root_kind = (
            "camera_archive"
            if str(event["status"] or "") == "archived"
            else "shared_workspace"
            if str(event["status"] or "") == "applied"
            else None
        )
        live_inventory_rows = []
        if live_root_kind is not None:
            live_inventory_rows = connection.execute(
                """SELECT family_id,filename,asset_kind,known_file_id,event_relative_path,
                          selected_capture_time,selected_capture_source,capture_time_confidence
                   FROM event_inventory_files
                   WHERE event_id=? AND root_kind=?
                     AND asset_kind IN ('camera_original','xmp','export','derived_media')
                   ORDER BY CASE WHEN known_file_id IS NOT NULL THEN 0 ELSE 1 END,
                            event_relative_path""",
                (event_id, live_root_kind),
            ).fetchall()

    from app.released_ranges import merge_intervals
    legacy = int(event['time_model_version']) < 2 and bool(children) and event['event_kind'] == 'event'
    legacy_ranges = merge_intervals((str(c['start_datetime']),str(c['end_datetime'])) for c in children) if legacy else []
    legacy_blocked = len(legacy_ranges) > 1
    event_dict = dict(event)
    try:
        event_dict["folder_naming"] = json.loads(
            str(event_dict.get("folder_naming_json") or "{}")
        )
    except (TypeError, ValueError):
        event_dict["folder_naming"] = {}
    if legacy and not legacy_blocked:
        event_dict['start_datetime'], event_dict['end_datetime'] = legacy_ranges[0]
    status = str(event["status"])
    archived_change_request = status == "archived" or event["archived_at"] is not None
    structural_editable = (
        status in {"draft", "planned", "applied"} and event["archived_at"] is None
    ) or archived_change_request
    live_inventory_available = bool(live_inventory_rows)

    planned_physical_assets: dict[int, dict[str, Any]] = {}
    if (
        workspace_path is not None
        and str(event["status"] or "") in {"draft", "planned"}
        and assigned_ids
    ):
        from app.workspace_assets import discover_workspace_family_assets
        planned_physical_assets = discover_workspace_family_assets(
            database_path,
            workspace_path,
            assigned_ids,
        )

    live_by_family: dict[int, dict[str, Any]] = {}
    for live_row in live_inventory_rows:
        if live_row["family_id"] is None:
            continue
        family_id = int(live_row["family_id"])
        stats = live_by_family.setdefault(
            family_id,
            {
                "file_count": 0,
                "camera_file_count": 0,
                "asset_kinds": set(),
                "display_stem": None,
                "capture_times": set(),
                "capture_confidences": set(),
                "capture_sources": set(),
            },
        )
        stats["file_count"] += 1
        asset_kind = str(live_row["asset_kind"] or "")
        if live_row["known_file_id"] is not None:
            stats["camera_file_count"] += 1
            live_capture = str(live_row["selected_capture_time"] or "").strip()
            live_confidence = str(live_row["capture_time_confidence"] or "missing")
            if live_capture and live_confidence in {"high", "medium"}:
                stats["capture_times"].add(live_capture)
                stats["capture_confidences"].add(live_confidence)
                live_source = str(live_row["selected_capture_source"] or "").strip()
                if live_source:
                    stats["capture_sources"].add(live_source)
        elif asset_kind:
            stats["asset_kinds"].add(asset_kind)
        if stats["display_stem"] is None or live_row["known_file_id"] is not None:
            stats["display_stem"] = Path(str(live_row["filename"] or "")).stem or None

    def _family_payload(row: Any) -> dict[str, Any]:
        item = dict(row)
        family_id = int(row["family_id"])
        assigned_here = bool(row["assigned_here"])
        database_file_count = int(row["file_count"] or 0)
        live = live_by_family.get(family_id)
        item["database_file_count"] = database_file_count
        item["live_inventory"] = live_inventory_available
        item["live_file_count"] = int(live["file_count"]) if live is not None else 0
        item["live_camera_file_count"] = int(live["camera_file_count"]) if live is not None else 0
        item["live_asset_kinds"] = sorted(live["asset_kinds"]) if live is not None else []
        item["live_display_stem"] = str(live.get("display_stem") or "") if live is not None else ""
        item["live_missing_camera_file_count"] = (
            max(0, database_file_count - item["live_camera_file_count"])
            if assigned_here and live_inventory_available
            else 0
        )
        if assigned_here and live_inventory_available:
            item["file_count"] = item["live_file_count"]
            # Bei archivierten/angewendeten Ereignissen ist der aktuelle
            # physische Bestand maßgeblich. Wenn alle real gelesenen
            # Kameraoriginale einer Familie dieselbe belastbare Aufnahmezeit
            # liefern, verwendet auch der Editor genau diese Zeit statt eines
            # möglicherweise veralteten SQLite-Werts. Widersprüche werden
            # sichtbar als Konflikt behandelt und niemals geraten.
            live_capture_times = sorted(live.get("capture_times") or []) if live is not None else []
            if len(live_capture_times) == 1:
                item["selected_capture_time"] = live_capture_times[0]
                confidences = set(live.get("capture_confidences") or []) if live is not None else set()
                item["capture_time_confidence"] = (
                    "high" if confidences == {"high"} else "medium"
                )
                item["live_capture_source"] = ", ".join(
                    sorted(live.get("capture_sources") or [])
                ) if live is not None else ""
                item["live_capture_conflict"] = False
            elif len(live_capture_times) > 1:
                item["selected_capture_time"] = None
                item["capture_time_confidence"] = "conflict"
                item["live_capture_source"] = ""
                item["live_capture_conflict"] = True

        # Planned Ereignisse besitzen noch kein Event-Inventar. XMP/Exporte,
        # die bereits physisch neben der Kamerafamilie liegen, sollen im
        # Nur-Lesen-Inspector trotzdem sofort sichtbar sein.
        physical = planned_physical_assets.get(family_id) if assigned_here else None
        if physical:
            item["file_count"] = database_file_count + int(
                physical.get("file_count") or 0
            )
            item["workspace_asset_count"] = int(
                physical.get("file_count") or 0
            )
            item["workspace_asset_kinds"] = list(
                physical.get("asset_kinds") or []
            )
            item["live_asset_kinds"] = sorted(set([
                *item.get("live_asset_kinds", []),
                *item["workspace_asset_kinds"],
            ]))
        item["day_key"] = str(row["selected_capture_time"] or "")[:10] or None
        item["has_date"] = row["selected_capture_time"] is not None
        item["assigned_here"] = assigned_here
        item["assigned_elsewhere"] = bool(row["assigned_elsewhere"])
        return item

    return {
        "event": event_dict,
        "legacy_disjoint": legacy_blocked,
        "legacy_warning": "Älteres Ereignis mit getrennten Zeitbereichen: manuelle Aufteilung erforderlich." if legacy_blocked else None,
        "child_event": dict(child) if child is not None else None,
        "child_events": [dict(row) for row in children],
        "assigned_family_ids": sorted(assigned_ids),
        "time_segments": [dict(row) for row in segment_rows],
        "structural_editable": structural_editable,
        "archived_change_request": archived_change_request,
        "folder_layout": folder_layout,
        "source_jobs": source_jobs,
        "families": [
            _family_payload(row)
            for row in family_rows
        ],
    }


def update_event_definition(
    database_path: Path,
    job_id: str,
    event_id: str,
    preview: dict[str, Any] | None,
    *,
    event_name: str,
    notes: str,
    expected_revision: int,
    workspace_path: Path | None = None,
    app_version: str | None = None,
    cascade_confirmed: bool = False,
    allow_archived_manual: bool = False,
    guided_structure_change_id: str | None = None,
) -> dict[str, Any]:
    """Edit an event transactionally; keep parent/child and index consistent.

    Draft/planned events: structural edits only touch the index.
    Applied (not archived) events: structural edits update the index
    (parent, child, assignments) and mark the portable document as
    requiring a re-sort; files are only moved by the confirmed re-apply
    run. This keeps the event editable after "Änderungen anwenden"
    until it is finally archived.
    Archived events: only the visible name and notes change.
    """
    import json
    import uuid
    from datetime import datetime, timezone

    if cascade_confirmed or allow_archived_manual:
        raise ValueError('Automatische gemeinsame Anpassungen sind nicht mehr zulässig. Bitte das andere Ereignis zuerst bearbeiten.')
    if preview and preview.get('child_segments'):
        raise ValueError('Getrennte Zeitbereiche sind für normale Ereignisse nicht zulässig.')
    clean_name = str(event_name or "").strip()
    if not clean_name:
        raise ValueError("Ereignisname fehlt.")
    if any(ch in clean_name for ch in ("/", "\\", "\0")):
        raise ValueError("Ereignisname enthält ein unzulässiges Zeichen.")
    clean_notes = str(notes or "").strip()
    if len(clean_notes) > 4000:
        raise ValueError("Notizen dürfen höchstens 4000 Zeichen enthalten.")

    now = datetime.now(timezone.utc).isoformat()
    cascade_result: dict[str, Any] | None = None
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        from app.event_mutation import assert_no_active_mutation, capture_job_event_state, begin_mutation, set_mutation_target
        assert_no_active_mutation(connection, job_id, event_id=event_id)
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND job_id = ?",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            connection.rollback()
            raise ValueError("Ereignis wurde nicht gefunden.")
        if event["event_level"] != "parent":
            connection.rollback()
            raise ValueError("Nur Hauptereignisse können bearbeitet werden.")
        if str(event["linkage_kind"] or "").strip():
            connection.rollback()
            raise ValueError("Technische Nachträge werden nicht als Ereignisse bearbeitet.")
        if int(event["revision"] or 1) != int(expected_revision):
            connection.rollback()
            raise ValueError("Das Ereignis wurde zwischenzeitlich geändert. Bitte neu laden.")
        if event["archived_at"] is not None:
            connection.rollback()
            raise ValueError("Archivierte Ereignisse können nicht mehr bearbeitet werden.")

        from app.event_structure_changes import assert_no_open_structure_change
        assert_no_open_structure_change(
            connection, event_id,
            guided_change_id=guided_structure_change_id,
            preview=preview,
        )

        status = str(event["status"])
        is_applied = status == "applied" and event["applied_at"] is not None
        structural_editable = (
            (status in {"draft", "planned"} and event["applied_at"] is None)
            or is_applied
        )
        old_snapshot = dict(event)
        from app.event_layout import ensure_event_layout_snapshot
        old_layout_state = ensure_event_layout_snapshot(
            connection,
            event_id,
            now=now,
        )
        # A coordinated planned edit must be cancellable until all affected
        # plans are first applied. Capture the complete graph before cascade.
        original_mutation_state = capture_job_event_state(connection, job_id) if (is_applied or cascade_confirmed) else None

        if not structural_editable:
            # Nur noch sichtbarer Name und Notizen (Archivzustand).
            connection.execute(
                """UPDATE events SET name = ?, notes = ?, revision = revision + 1,
                   updated_at = ?, edited_at = ? WHERE id = ?""",
                (clean_name, clean_notes, now, now, event_id),
            )
            connection.execute(
                """INSERT INTO audit_log(job_id, action, entity_type, entity_id, details_json, created_at)
                   VALUES (?, 'event_metadata_edited', 'event', ?, ?, ?)""",
                (job_id, event_id, json.dumps({"old_name": old_snapshot["name"], "new_name": clean_name, "folder_unchanged": True}, ensure_ascii=False), now),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            return {"event": dict(row), "structural_changed": False, "resort_required": False}

        # 0.26.11: Draft/planned edits are complete when saved. Legacy
        # reassignment rows from older versions are informational free stock now,
        # not unfinished user work. Applied events keep their durable physical
        # reconcile evidence until the confirmed workspace transaction finishes.
        if not is_applied:
            connection.execute(
                """INSERT OR REPLACE INTO released_free_families(
                       job_id,family_id,released_start_datetime,released_end_datetime,created_at)
                   SELECT job_id,family_id,released_start_datetime,released_end_datetime,?
                   FROM event_reapply_removed_families
                   WHERE event_id=? AND job_id=? AND target_event_id IS NULL
                     AND COALESCE(target_kind,'') <> 'released_free'""",
                (now, event_id, job_id),
            )
            connection.execute(
                """DELETE FROM event_reapply_removed_families
                   WHERE event_id=? AND job_id=? AND target_event_id IS NULL
                     AND COALESCE(target_kind,'') <> 'released_free'""",
                (event_id, job_id),
            )

        pending_reassignment = connection.execute(
            """SELECT COUNT(*) AS n FROM event_reapply_removed_families
               WHERE event_id = ?
                 AND target_event_id IS NULL
                 AND COALESCE(target_kind,'') <> 'released_free'""",
            (event_id,),
        ).fetchone()
        if is_applied and pending_reassignment is not None and int(pending_reassignment["n"] or 0) > 0:
            connection.rollback()
            raise ValueError(
                "Für dieses angewendete Ereignis ist noch ein physischer Abgleich offen. "
                "Bitte diesen zuerst anwenden oder vollständig verwerfen."
            )

        if is_applied and int(event["resort_required"] or 0):
            connection.rollback()
            raise ValueError(
                "Für dieses Ereignis ist bereits eine Nachsortierung offen. "
                "Bitte diese zuerst abschließen."
            )

        if is_applied:
            active_run = connection.execute(
                """SELECT id FROM sort_runs
                   WHERE event_id = ?
                     AND status IN ('queued','verifying','moving','finalizing','rolling_back','interrupted')
                   LIMIT 1""",
                (event_id,),
            ).fetchone()
            if active_run is not None:
                connection.rollback()
                raise ValueError(
                    "Das Ereignis hat einen aktiven oder unterbrochenen Sortierlauf "
                    f"({active_run['id']}). Bitte zuerst klären, dann erneut bearbeiten."
                )

        if preview is None:
            # 0.16.4: Bei einem bereits angewendeten Ereignis darf eine reine
            # Namens-/Notizkorrektur keine komplette Nachsortierung auslösen.
            # Der bestehende SSD-Ordner bleibt dabei bewusst unverändert.
            connection.execute(
                """UPDATE events SET name = ?, notes = ?, revision = revision + 1,
                   updated_at = ?, edited_at = ? WHERE id = ?""",
                (clean_name, clean_notes, now, now, event_id),
            )
            connection.execute(
                """INSERT INTO audit_log(job_id, action, entity_type, entity_id, details_json, created_at)
                   VALUES (?, 'event_metadata_edited', 'event', ?, ?, ?)""",
                (job_id, event_id, json.dumps({
                    "old_name": old_snapshot["name"], "new_name": clean_name,
                    "folder_unchanged": True, "applied_event": is_applied,
                }, ensure_ascii=False), now),
            )
            if is_applied and workspace_path is not None:
                # BA-01: The durable repair intent and event revision are one
                # SQLite commit. If the process crashes before event.json is
                # replaced, startup can safely regenerate exactly this revision.
                from app.event_document_sync import queue_event_document_sync
                queue_event_document_sync(
                    connection, job_id, event_id,
                    int(event["revision"] or 1) + 1, now=now,
                )
            connection.commit()
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
            metadata_result = {
                "event": dict(row), "structural_changed": False,
                "resort_required": False, "removed_family_ids": [],
                "reassignment_required": False,
            }
            if workspace_path is not None and is_applied:
                from app.event_document_sync import sync_event_document_task
                sync_result = sync_event_document_task(
                    database_path, workspace_path, event_id,
                    app_version=app_version,
                )
                if sync_result["status"] == "completed":
                    metadata_result["event_document"] = sync_result.get("path")
                    metadata_result["event_document_sync_pending"] = False
                else:
                    # The edit was already committed. Do not raise a fake
                    # pre-commit error or force the user to resubmit the stale
                    # expected_revision. Make the durable pending work visible.
                    metadata_result["event_document_sync_pending"] = True
                    metadata_result["event_document_sync_error"] = str(
                        sync_result.get("error") or "event.json konnte nicht synchronisiert werden"
                    )
            return metadata_result
        requested_ids = sorted({int(v) for v in preview.get("selected_family_ids", [])})
        if not requested_ids:
            connection.rollback()
            raise ValueError("Mindestens eine Dateifamilie muss zugeordnet bleiben.")

        old_assigned_rows = connection.execute(
            """
            SELECT ea.family_id
            FROM event_assignments ea
            JOIN events e ON e.id = ea.event_id
            WHERE e.job_id = ?
              AND COALESCE(e.parent_event_id, e.id) = ?
              AND ea.family_id IS NOT NULL
            """,
            (job_id, event_id),
        ).fetchall()
        old_assigned_ids = {int(row["family_id"]) for row in old_assigned_rows}

        # Preserve the old canonical time definition so every released family
        # can carry the exact free segment that produced the reassignment task.
        # This avoids reconstructing time truth from min/max capture timestamps.
        if str(event["event_kind"] or "event") == "no_event":
            old_definition_rows = connection.execute(
                "SELECT start_datetime,end_datetime FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id",
                (event_id,),
            ).fetchall()
            old_definition_ranges = [(str(r["start_datetime"])[:19], str(r["end_datetime"])[:19]) for r in old_definition_rows]
        else:
            from app.event_timeline import normal_event_ranges, assert_editable_normal
            assert_editable_normal(connection, event_id)
            old_definition_ranges = normal_event_ranges(connection, event_id)

        placeholders = ",".join("?" for _ in requested_ids)
        rows = connection.execute(
            f"SELECT id, job_id, selected_capture_time FROM file_families WHERE id IN ({placeholders})",
            tuple(requested_ids),
        ).fetchall()
        if len(rows) != len(requested_ids):
            connection.rollback()
            raise ValueError("Die Familienauswahl ist nicht mehr aktuell.")


        if not cascade_confirmed:
            conflicts = connection.execute(
                f"""
                SELECT DISTINCT ea.family_id, COALESCE(root.name, assigned.name) AS event_name
                FROM event_assignments ea
                JOIN events assigned ON assigned.id = ea.event_id
                LEFT JOIN events root ON root.id = assigned.parent_event_id
                WHERE ea.family_id IN ({placeholders})
                  AND COALESCE(root.id, assigned.id) != ?
                  AND assigned.status IN ('draft','planned','applied','archived')
                """,
                (*requested_ids, event_id),
            ).fetchall()
            if conflicts:
                names = sorted({str(r["event_name"]) for r in conflicts})
                connection.rollback()
                raise ValueError("Mindestens eine Familie gehört bereits zu: " + ", ".join(f"„{n}“" for n in names) + ".")

        start_date = str(preview["start_date"])
        end_date = str(preview["end_date"])
        event_kind = str(preview.get("event_kind") or "event")
        multi_segments = list(preview.get("child_segments") or []) if event_kind == "event" else []
        no_event_segments = []
        if event_kind == "no_event":
            from app.event_timeline import normalize_no_event_segments
            no_event_segments = normalize_no_event_segments(preview.get("no_event_segments") or [])
            parent_start = no_event_segments[0]["start_datetime"]
            parent_end = no_event_segments[-1]["end_datetime"]
            uses_time_range = False
            assignment_start, assignment_end = parent_start, parent_end
        else:
            parent_start = f"{start_date}T00:00:00"
            parent_end = f"{end_date}T23:59:59"
            uses_time_range = bool(preview["uses_time_range"]) or bool(multi_segments)
            assignment_start = f"{start_date}T{preview['start_time']}:00" if uses_time_range and not multi_segments else parent_start
            assignment_end = f"{end_date}T{preview['end_time']}:59" if uses_time_range and not multi_segments else parent_end
        if event_kind == "event":
            parent_start, parent_end = assignment_start, assignment_end
        if event_kind == "no_event":
            new_definition_ranges = [(seg["start_datetime"], seg["end_datetime"]) for seg in no_event_segments]
        elif multi_segments:
            new_definition_ranges = [
                (f"{start_date}T{str(seg.get('start_time') or '00:00')}:00",
                 f"{end_date}T{str(seg.get('end_time') or '23:59')}:59")
                for seg in multi_segments
            ]
        else:
            new_definition_ranges = [(assignment_start, assignment_end)]
        from app.event_timeline import continuous_event_overlaps, no_event_segment_overlaps
        for a, b in new_definition_ranges:
            conflicts = continuous_event_overlaps(connection,job_id,a,b,exclude_event_id=event_id) + no_event_segment_overlaps(connection,job_id,a,b,exclude_event_id=event_id)
            if conflicts:
                raise ValueError('Die Änderung überschneidet sich mit belegter Zeit. Bitte zuerst das andere Ereignis bearbeiten.')
        from app.released_ranges import subtract_intervals, split_intervals_by_day
        released_definition_ranges = split_intervals_by_day(
            subtract_intervals(old_definition_ranges, new_definition_ranges)
        )

        if cascade_confirmed and str(preview.get("event_kind") or "event") == "event":
            from app.event_timeline import apply_cascade_for_interval
            cascade_ranges = (
                new_definition_ranges
                if multi_segments
                else [(assignment_start, assignment_end)]
            )
            cascade_result = {
                "affected_event_ids": [],
                "removed_by_event": {},
                "archived_manual_items": [],
            }
            for cascade_start, cascade_end in cascade_ranges:
                part = apply_cascade_for_interval(
                    connection, job_id, event_id, cascade_start, cascade_end, now=now,
                    allow_archived_manual=allow_archived_manual,
                )
                cascade_result["affected_event_ids"].extend(part.get("affected_event_ids") or [])
                cascade_result["archived_manual_items"].extend(part.get("archived_manual_items") or [])
                for affected_event_id, removed_family_ids in (part.get("removed_by_event") or {}).items():
                    prior = set(cascade_result["removed_by_event"].get(affected_event_id) or [])
                    cascade_result["removed_by_event"][affected_event_id] = sorted(
                        prior | {int(fid) for fid in removed_family_ids}
                    )
            cascade_result["affected_event_ids"] = sorted(set(cascade_result["affected_event_ids"]))
            # Applied source events touched by the cascade need durable move
            # targets for their later verified reapply runs.
            for affected_event_id, removed_family_ids in (cascade_result.get("removed_by_event") or {}).items():
                if not removed_family_ids:
                    continue
                affected = connection.execute("SELECT * FROM events WHERE id=?", (affected_event_id,)).fetchone()
                if affected is None or str(affected["status"]) != "applied":
                    continue
                family_placeholders = ",".join("?" for _ in removed_family_ids)
                family_job_rows = connection.execute(
                    f"""SELECT id,job_id FROM file_families
                        WHERE id IN ({family_placeholders})""",
                    tuple(int(fid) for fid in removed_family_ids),
                ).fetchall()
                family_job_by_id = {
                    int(row["id"]): str(row["job_id"])
                    for row in family_job_rows
                }
                connection.executemany(
                    """INSERT OR REPLACE INTO event_reapply_removed_families(
                       event_id,job_id,family_id,created_at,target_event_id,target_status,target_kind,
                       target_name,target_folder_name,target_preserve_day_folders,target_linkage_kind,reassigned_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    [(
                        affected_event_id, family_job_by_id[int(fid)], int(fid), now,
                        event_id, str(event["status"]), "cascade_event", clean_name,
                        str(preview.get("parent_folder") or event["folder_name"]),
                        int(bool(preview.get("preserve_day_folders"))), "", now,
                    ) for fid in removed_family_ids],
                )
        if cascade_confirmed:
            remaining_conflicts = connection.execute(
                f"""SELECT DISTINCT ea.family_id, COALESCE(root.name, assigned.name) AS event_name, assigned.status AS assigned_status
                    FROM event_assignments ea
                    JOIN events assigned ON assigned.id = ea.event_id
                    LEFT JOIN events root ON root.id = assigned.parent_event_id
                    WHERE ea.family_id IN ({placeholders})
                      AND COALESCE(root.id, assigned.id) != ?
                      AND assigned.status IN ('draft','planned','applied','archived')""",
                (*requested_ids, event_id),
            ).fetchall()
            if allow_archived_manual:
                remaining_conflicts = [r for r in remaining_conflicts if str(r["assigned_status"]) != "archived"]
            if remaining_conflicts:
                names=sorted({str(r["event_name"]) for r in remaining_conflicts})
                connection.rollback()
                raise ValueError("Die gemeinsame Anpassung konnte nicht vollständig aufgelöst werden: " + ", ".join(names))
        for row in rows:
            capture = str(row["selected_capture_time"] or "")[:19]
            valid = bool(capture)
            if valid and event_kind == "no_event":
                valid = any(seg["start_datetime"] <= capture <= seg["end_datetime"] for seg in no_event_segments)
            elif valid and multi_segments:
                valid = any(
                    f"{start_date}T{str(seg.get('start_time') or '00:00')}:00" <= capture <=
                    f"{end_date}T{str(seg.get('end_time') or '23:59')}:59"
                    for seg in multi_segments
                )
            elif valid:
                valid = assignment_start <= capture <= assignment_end
            if not valid:
                connection.rollback()
                raise ValueError("Mindestens eine Familie liegt außerhalb der neuen Zeitdefinition.")

        mutation_id = None
        if (is_applied and not guided_structure_change_id) or (cascade_result and status in {"draft", "planned"}):
            affected_ids = [event_id]
            if cascade_result:
                affected_ids.extend(str(v) for v in (cascade_result.get("affected_event_ids") or []))
            mutation_kind = (
                "cascade" if cascade_result else "edit"
            )
            mutation_id = begin_mutation(
                connection, job_id=job_id, anchor_event_id=event_id, mutation_kind=mutation_kind,
                affected_event_ids=affected_ids, original_state=original_mutation_state or {}, status="pending_apply",
            )

        connection.execute(
            """UPDATE events SET name = ?, start_datetime = ?, end_datetime = ?, folder_name = ?,
               event_kind = ?, preserve_day_folders = ?, notes = ?, revision = revision + 1,
               resort_required = ?, updated_at = ?, edited_at = ? WHERE id = ?""",
            (clean_name, parent_start, parent_end, str(preview["parent_folder"]), str(preview["event_kind"]), int(bool(preview["preserve_day_folders"])), clean_notes, int(is_applied and not guided_structure_change_id), now, now, event_id),
        )

        if event_kind == "no_event":
            from app.event_timeline import replace_event_segments
            connection.execute("UPDATE events SET timeline_model='segments' WHERE id=?", (event_id,))
            replace_event_segments(connection, event_id=event_id, job_id=job_id, segments=no_event_segments, now=now, source="user")
        else:
            connection.execute("UPDATE events SET timeline_model='continuous',time_model_version=2 WHERE id=?", (event_id,))

        from app.subevents import normalize_subevents, store_subevents, assignment_target
        organizational = list(preview.get('subevents') or [])
        if preview.get('child_folder') and not organizational:
            organizational=[{'name':preview['child_event_name'],'start_datetime':assignment_start,'end_datetime':assignment_end}]
        organizational=normalize_subevents(
            organizational,
            parent_start,
            parent_end,
            naming=preview.get("folder_naming"),
        )
        children=store_subevents(connection,event_id,organizational,now)
        if guided_structure_change_id:
            # Removed physical child leaves must not survive as ghost folders
            # in event.json or in the destination structure preview.
            retained_children = {str(child["id"]) for child in children}
            for old_child in connection.execute(
                "SELECT leaf_key FROM event_leaf_folder_layouts WHERE parent_event_id=?",
                (event_id,),
            ).fetchall():
                stable = str(old_child["leaf_key"]).split("@", 1)[0]
                if stable != event_id and stable not in retained_children:
                    connection.execute(
                        "DELETE FROM event_leaf_folder_layouts WHERE parent_event_id=? AND leaf_key=?",
                        (event_id, str(old_child["leaf_key"])),
                    )
        assignment_rows=[(assignment_target(event_id,children,str(row['selected_capture_time'])[:19]),int(row['id']),'date_time_range',now) for row in rows]
        assignment_event_id = event_id
        # 0.26.11: A planned definition is only database planning. Saving an
        # edit therefore finishes the change immediately: removed families are
        # free stock (yellow informational marker), never a reassignment task.
        # Applied events still need the durable queue as physical move evidence
        # until their mandatory workspace reconcile is confirmed.
        removed_ids = sorted(old_assigned_ids - set(requested_ids))
        connection.execute(
            "DELETE FROM event_reapply_removed_families WHERE event_id = ?",
            (event_id,),
        )
        if removed_ids:
            rp = ",".join("?" for _ in removed_ids)
            removed_capture_rows = connection.execute(
                f"SELECT id,job_id,selected_capture_time FROM file_families WHERE id IN ({rp})",
                tuple(removed_ids),
            ).fetchall()
            from app.released_ranges import range_for_capture
            released_by_family = {
                int(r["id"]): range_for_capture(str(r["selected_capture_time"] or "")[:19], released_definition_ranges)
                for r in removed_capture_rows
            }
            if is_applied:
                connection.executemany(
                    """INSERT INTO event_reapply_removed_families
                       (event_id, job_id, family_id, created_at, released_start_datetime, released_end_datetime)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [(
                        event_id,
                        str(next(r["job_id"] for r in removed_capture_rows if int(r["id"]) == family_id)),
                        family_id, now,
                        released_by_family.get(family_id)[0] if released_by_family.get(family_id) else None,
                        released_by_family.get(family_id)[1] if released_by_family.get(family_id) else None,
                    ) for family_id in removed_ids],
                )
            else:
                connection.executemany(
                    """INSERT OR REPLACE INTO released_free_families(
                           job_id,family_id,released_start_datetime,released_end_datetime,created_at)
                       VALUES (?,?,?,?,?)""",
                    [(
                        str(next(r["job_id"] for r in removed_capture_rows if int(r["id"]) == family_id)),
                        family_id,
                        released_by_family.get(family_id)[0] if released_by_family.get(family_id) else None,
                        released_by_family.get(family_id)[1] if released_by_family.get(family_id) else None,
                        now,
                    ) for family_id in removed_ids],
                )

        connection.execute(
            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN (SELECT id FROM events WHERE parent_event_id = ?)",
            (event_id, event_id),
        )
        if assignment_rows:
            connection.executemany(
                """INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at)
                   VALUES (?, ?, NULL, ?, ?)""",
                assignment_rows,
            )
        else:
            connection.executemany(
                """INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at)
                   VALUES (?, ?, NULL, ?, ?)""",
                [(assignment_event_id, family_id, "date_time_range" if uses_time_range else "date_range", now) for family_id in requested_ids],
            )
        if requested_ids:
            rp = ",".join("?" for _ in requested_ids)
            connection.execute(
                f"""DELETE FROM released_free_families
                    WHERE archive_origin=0
                      AND family_id IN ({rp})""",
                tuple(requested_ids),
            )
        # archive_origin=1 bleibt als Rückkehrherkunft erhalten.
        if mutation_id is not None:
            target_state = capture_job_event_state(connection, job_id)
            set_mutation_target(
                connection, mutation_id, target_state,
                status="pending_apply",
            )

        if is_applied:
            latest_verification = connection.execute(
                """SELECT * FROM event_archive_verifications
                   WHERE job_id=? AND event_id=?
                   ORDER BY created_at DESC,id DESC LIMIT 1""",
                (job_id, event_id),
            ).fetchone()
            if (
                latest_verification is not None
                and str(latest_verification["status"] or "") == "verified"
            ):
                invalidation_id = "ARCHIVE_INVALIDATED_" + uuid.uuid4().hex.upper()
                connection.execute(
                    """INSERT INTO event_archive_verifications(
                           id,job_id,event_id,status,archive_root,file_count,
                           verified_file_count,total_size_bytes,verified_size_bytes,
                           missing_file_count,mismatched_file_count,details_json,
                           error_message,created_at,updated_at,completed_at
                       ) VALUES (?,?,?,'failed',?,?,?,?,?,0,0,?,?,?,?,?)""",
                    (
                        invalidation_id, job_id, event_id,
                        str(latest_verification["archive_root"] or ""),
                        int(latest_verification["file_count"] or 0),
                        0,
                        int(latest_verification["total_size_bytes"] or 0),
                        0,
                        json.dumps(
                            {
                                "invalidated": True,
                                "reason": "structural_applied_edit",
                                "supersedes_verification_id": str(latest_verification["id"]),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        "verification_invalidated_by_edit",
                        now, now, now,
                    ),
                )

        preview_layout = preview.get("folder_layout")
        if isinstance(preview_layout, dict):
            from app.event_layout import update_event_layout
            update_event_layout(
                connection,
                event_id,
                structure_enabled=bool(preview_layout.get("structure_enabled", True)),
                input_path=str(preview_layout.get("input_path") or ""),
                layout=preview_layout.get("layout") or {},
                updated_at=now,
            )

        connection.execute(
            """INSERT INTO audit_log(job_id, action, entity_type, entity_id, details_json, created_at)
               VALUES (?, 'event_edited', 'event', ?, ?, ?)""",
            (job_id, event_id, json.dumps({
                "old": {"name": old_snapshot["name"], "start": old_snapshot["start_datetime"], "end": old_snapshot["end_datetime"], "folder": old_snapshot["folder_name"], "preserve_day_folders": bool(old_snapshot["preserve_day_folders"])},
                "new": {"name": clean_name, "start": parent_start, "end": parent_end, "folder": preview["parent_folder"], "preserve_day_folders": bool(preview["preserve_day_folders"]), "family_ids": requested_ids},
                "applied_event": is_applied,
            }, ensure_ascii=False, sort_keys=True), now),
        )
        if guided_structure_change_id:
            # The physical file moves have *already* happened and were
            # cryptographically verified by the guided preflight. Do not
            # enqueue a second sort/physical mutation of the same event.
            if is_applied:
                from app.event_document_sync import queue_event_document_sync
                queue_event_document_sync(connection, job_id, event_id, int(event["revision"] or 1) + 1, now=now)
            # Finish the reviewed manual task atomically with the canonical
            # event edit. A failed editor transaction leaves the task intact.
            connection.execute(
                """UPDATE event_structure_changes
                   SET status='completed',updated_at=?,completed_at=?,error_message=NULL
                   WHERE id=? AND event_id=? AND status='blocked'""",
                (now, now, guided_structure_change_id, event_id),
            )
            connection.execute(
                """INSERT INTO audit_log(
                    job_id,action,entity_type,entity_id,details_json,created_at
                ) VALUES (?,'manual_structure_guided_edit','event',?,?,?)""",
                (job_id, event_id, json.dumps({
                    "change_id":guided_structure_change_id,
                    "mutation_id":mutation_id,
                    "removed_subevents":True,
                }, sort_keys=True), now),
            )
        connection.commit()
        row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    # 0.25.1 / F01:
    # Applied edits change only the index/plan. Removed families keep their
    # current workspace files until targets are assigned and the user explicitly
    # confirms the workspace reconciliation. The legacy neutralization module is
    # retained for restoring mutations that were already neutralized by older
    # versions.
    neutralized_files: list[dict[str, Any]] = []

    result: dict[str, Any] = {
        "event": dict(row),
        "structural_changed": True,
        "assigned_family_ids": requested_ids,
        "resort_required": bool(is_applied and not guided_structure_change_id),
        "removed_family_ids": removed_ids,
        "reassignment_required": False,
        "cascade": cascade_result,
        "mutation_id": mutation_id,
        "neutralized_files": neutralized_files,
        "neutralized_file_count": len(neutralized_files),
    }

    # A structural applied edit stores SOLL only in SQLite.  Its final portable
    # document is written after the explicitly confirmed physical reconcile.
    if workspace_path is not None and guided_structure_change_id and is_applied:
        from app.event_document_sync import recover_event_document_sync_tasks
        recover_event_document_sync_tasks(database_path, workspace_path)
    if workspace_path is not None and not is_applied:
        from app.event_document import (
            build_event_document_from_db,
            write_event_document,
        )

        document = build_event_document_from_db(
            database_path, workspace_path, job_id, event_id
        )
        if document is not None:
            result["event_document"] = str(
                write_event_document(workspace_path, document, app_version=app_version)
            )

    return result



def assign_free_families_to_existing_no_event(
    database_path: Path,
    job_id: str,
    target_event_id: str,
    segments: list[dict[str, Any]],
    *,
    family_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Assign free families to one canonical monthly collection.

    A non-empty segment list extends the collection. An empty segment list is
    valid only with explicit family ids and means that later-imported files must
    fit inside the already existing no-event segments.
    """
    from app.event_timeline import normalize_no_event_segments, continuous_event_overlaps

    raw_segments = list(segments or [])
    normalized = normalize_no_event_segments(raw_segments) if raw_segments else []
    extend_timeline = bool(normalized)
    requested_ids = sorted({int(value) for value in (family_ids or []) if int(value) > 0})
    if not extend_timeline and not requested_ids:
        raise ValueError("Mindestens ein Zeitsegment oder eine Dateifamilie muss ausgewählt sein.")

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        target = connection.execute(
            "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
            (target_event_id,),
        ).fetchone()
        if target is None or str(target["event_kind"]) != "no_event":
            connection.rollback()
            raise ValueError("Die gewählte „Ohne Ereignis“-Sammlung wurde nicht gefunden.")
        if str(target["status"]) not in {"planned","applied","archived"}:
            connection.rollback()
            raise ValueError("Die gewählte „Ohne Ereignis“-Sammlung ist nicht mehr aktiv.")

        if not normalized:
            segment_rows = connection.execute(
                """SELECT day_key,start_time,end_time,start_datetime,end_datetime
                   FROM event_time_segments
                   WHERE event_id=?
                   ORDER BY start_datetime,id""",
                (target_event_id,),
            ).fetchall()
            normalized = [
                {
                    "day_key": str(row["day_key"]),
                    "start_time": str(row["start_time"]),
                    "end_time": str(row["end_time"]),
                    "start_datetime": str(row["start_datetime"])[:19],
                    "end_datetime": str(row["end_datetime"])[:19],
                }
                for row in segment_rows
            ]
            if not normalized:
                connection.rollback()
                raise ValueError("Die bestehende „Ohne Ereignis“-Sammlung besitzt keine gültigen Zeitsegmente.")

        months = {seg["day_key"][:7] for seg in normalized}
        if len(months) != 1:
            connection.rollback()
            raise ValueError("Eine „Ohne Ereignis“-Sammlung bleibt ein Monatsordner.")
        month = next(iter(months))
        if str(target["start_datetime"] or "")[:7] != month:
            connection.rollback()
            raise ValueError("Die gewählte „Ohne Ereignis“-Sammlung gehört zu einem anderen Monat.")

        if extend_timeline:
            for seg in normalized:
                overlaps = continuous_event_overlaps(
                    connection, job_id, seg["start_datetime"], seg["end_datetime"]
                )
                if overlaps:
                    names = sorted({str(x["name"]) for x in overlaps})
                    connection.rollback()
                    raise ValueError(
                        "Der gewählte Zeitraum überschneidet sich mit einem Ereignis: "
                        + ", ".join(names)
                    )

        if requested_ids:
            placeholders = ",".join("?" for _ in requested_ids)
            rows = connection.execute(
                f"""SELECT ff.id,ff.job_id,ff.selected_capture_time
                    FROM file_families ff
                    WHERE ff.id IN ({placeholders}) AND ff.selected_capture_time IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM event_assignments ea
                        JOIN events assigned ON assigned.id=ea.event_id
                        JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                        WHERE ea.family_id=ff.id
                          AND root.status IN ('draft','planned','applied','archived')
                      )
                    ORDER BY ff.selected_capture_time,ff.id""",
                tuple(requested_ids),
            ).fetchall()
            if len(rows) != len(requested_ids):
                connection.rollback()
                raise ValueError("Mindestens eine ausgewählte Dateifamilie ist nicht mehr frei.")
        else:
            rows = connection.execute(
                """SELECT ff.id,ff.job_id,ff.selected_capture_time
                   FROM file_families ff
                   WHERE ff.job_id=? AND ff.selected_capture_time IS NOT NULL
                     AND NOT EXISTS (
                       SELECT 1 FROM event_assignments ea
                       JOIN events assigned ON assigned.id=ea.event_id
                       JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                       WHERE ea.family_id=ff.id
                         AND root.status IN ('draft','planned','applied','archived')
                     )
                   ORDER BY ff.selected_capture_time,ff.id""",
                (job_id,),
            ).fetchall()

        selected = []
        for row in rows:
            cap = str(row["selected_capture_time"] or "")[:19]
            if any(seg["start_datetime"] <= cap <= seg["end_datetime"] for seg in normalized):
                selected.append((int(row["id"]), cap, str(row["job_id"])))
        if not selected:
            connection.rollback()
            raise ValueError("In den gewählten Zeitsegmenten gibt es keine freien Dateifamilien.")
        if requested_ids and {fid for fid, _, _ in selected} != set(requested_ids):
            connection.rollback()
            raise ValueError("Mindestens eine ausgewählte Dateifamilie liegt außerhalb der gültigen Zeitsegmente.")

        source_job_ids = sorted({source_job_id for _, _, source_job_id in selected})
        same_job = source_job_ids == [str(target["job_id"])]
        if str(target["status"]) == "archived":
            connection.rollback()
            raise ValueError(
                "Archivierte „Ohne Ereignis“-Sammlungen werden nur über den Archivänderungsworkflow ergänzt."
            )

        effective_event_id = str(target["id"])
        if str(target["status"]) == "applied":
            from app.event_mutation import capture_job_event_state, begin_mutation, get_active_mutation

            active = get_active_mutation(connection, str(target["job_id"]))
            if int(target["resort_required"] or 0):
                if (
                    active is None
                    or str(active.get("anchor_event_id") or "") != effective_event_id
                    or str(active.get("status") or "") != "pending_apply"
                ):
                    connection.rollback()
                    raise ValueError("Für diese Sammlung ist bereits eine andere Nachsortierung offen.")
            else:
                original_state = capture_job_event_state(connection, str(target["job_id"]))
                begin_mutation(
                    connection,
                    job_id=str(target["job_id"]),
                    anchor_event_id=effective_event_id,
                    mutation_kind="edit",
                    affected_event_ids=[effective_event_id],
                    original_state=original_state,
                    status="pending_apply",
                )

        connection.executemany(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at)
               VALUES (?,?,NULL,'date_time_range',?)""",
            [(effective_event_id, fid, now) for fid, _, _ in selected],
        )

        if extend_timeline:
            for seg in normalized:
                existing = connection.execute(
                    """SELECT * FROM event_time_segments
                       WHERE event_id=? AND day_key=?
                       ORDER BY start_datetime""",
                    (effective_event_id, seg["day_key"]),
                ).fetchall()
                a, b = seg["start_datetime"], seg["end_datetime"]
                remove = []
                for old in existing:
                    if str(old["end_datetime"]) >= a and str(old["start_datetime"]) <= b:
                        a = min(a, str(old["start_datetime"]))
                        b = max(b, str(old["end_datetime"]))
                        remove.append(int(old["id"]))
                if remove:
                    connection.executemany(
                        "DELETE FROM event_time_segments WHERE id=?",
                        [(value,) for value in remove],
                    )
                connection.execute(
                    """INSERT INTO event_time_segments(
                           event_id,job_id,day_key,start_time,end_time,start_datetime,
                           end_datetime,source,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        effective_event_id, str(target["job_id"]), seg["day_key"],
                        a[11:16], b[11:16], a, b, "user", now, now,
                    ),
                )
            connection.execute(
                """UPDATE events
                   SET start_datetime=(
                         SELECT MIN(start_datetime) FROM event_time_segments WHERE event_id=?
                       ),
                       end_datetime=(
                         SELECT MAX(end_datetime) FROM event_time_segments WHERE event_id=?
                       )
                   WHERE id=?""",
                (effective_event_id, effective_event_id, effective_event_id),
            )

        connection.execute(
            """UPDATE events
               SET timeline_model='segments',revision=revision+1,updated_at=?,
                   resort_required=CASE WHEN status='applied' THEN 1 ELSE resort_required END
               WHERE id=?""",
            (now, effective_event_id),
        )
        from app.event_access import register_source_jobs
        register_source_jobs(
            connection,
            effective_event_id,
            [str(target["job_id"]), *source_job_ids],
            created_at=now,
        )
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'free_families_added_to_no_event','event',?,?,?)""",
            (
                str(target["job_id"]),
                effective_event_id,
                json.dumps({
                    "family_ids": [fid for fid, _, _ in selected],
                    "source_job_ids": source_job_ids,
                    "segments": normalized if extend_timeline else [],
                    "existing_segments_only": not extend_timeline,
                    "canonical_target_event_id": str(target["id"]),
                }, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        connection.commit()

    return {
        "status": "assigned",
        "event_id": effective_event_id,
        "canonical_target_event_id": str(target["id"]),
        "assigned_family_count": len(selected),
        "family_ids": [fid for fid, _, _ in selected],
        "source_job_ids": source_job_ids,
        "cross_job": not same_job,
        "linkage_kind": "",
        "target_status": str(target["status"]),
        "resort_required": str(target["status"]) == "applied",
    }

def list_no_event_month_targets(database_path: Path, month_keys: list[str], prefer_job_id: str | None = None) -> list[dict[str, Any]]:
    """Return one canonical no-event collection per requested month.

    Multiple jobs may contribute to the same physical monthly folder. The UI
    should nevertheless present a single target. A row from the current job is
    preferred when available; otherwise the most recently updated active row is
    used as the canonical collection target.
    """
    months = sorted({str(m)[:7] for m in month_keys if len(str(m)) >= 7})
    month_filter = ""
    params: tuple[Any, ...]
    if months:
        placeholders = ",".join("?" for _ in months)
        month_filter = f" AND substr(start_datetime,1,7) IN ({placeholders})"
        params = (*months, str(prefer_job_id or ""))
    else:
        # Leere Monatsliste bedeutet bewusst: alle aktiven Monats-Sammlungen
        # anbieten. Das wird in der Sortier-UI genutzt, wenn „Ohne Ereignis“
        # ohne vorausgewählten Tag geöffnet wird.
        params = (str(prefer_job_id or ""),)
    with database_connection(database_path) as connection:
        rows = connection.execute(
            f"""SELECT id,job_id,name,status,folder_name,start_datetime,end_datetime,updated_at,
                       substr(start_datetime,1,7) AS month_key
                FROM events
                WHERE parent_event_id IS NULL AND event_kind='no_event'
                  AND COALESCE(linkage_kind,'')=''
                  AND status IN ('planned','applied','archived')
                  {month_filter}
                ORDER BY CASE WHEN job_id=? THEN 0 ELSE 1 END,
                         substr(start_datetime,1,7) DESC,
                         CASE status WHEN 'planned' THEN 0 WHEN 'applied' THEN 1 ELSE 2 END,
                         updated_at DESC,id DESC""",
            params,
        ).fetchall()
    result=[]; seen=set()
    for row in rows:
        month=str(row["month_key"] or "")
        if not month or month in seen:
            continue
        seen.add(month)
        item=dict(row)
        item["same_job"] = str(item.get("job_id") or "") == str(prefer_job_id or "")
        with database_connection(database_path) as segment_connection:
            segment_rows = segment_connection.execute(
                """SELECT day_key,start_time,end_time,start_datetime,end_datetime
                   FROM event_time_segments WHERE event_id=?
                   ORDER BY day_key,start_time,end_time""",
                (str(item.get("id") or ""),),
            ).fetchall()
        item["segments"] = [dict(seg) for seg in segment_rows]
        result.append(item)
    return result


def list_global_tasks(database_path: Path) -> list[dict[str, Any]]:
    """Open user-visible work across all jobs.

    These tasks are deliberately derived from durable DB state so closing a
    dialog or reloading a page can never make pending work disappear.
    """
    tasks: list[dict[str, Any]] = []
    with database_connection(database_path) as connection:
        # Veraltete Neu-Zuordnungen sind keine Aufgaben. Sie entstehen z. B.,
        # wenn eine Familie spaeter wieder direkt einem gueltigen Ereignis
        # zugeordnet wurde.
        from app.event_reassignment import (
            reconcile_stale_event_reassignments,
            reconcile_released_free_markers,
        )
        cleaned = reconcile_stale_event_reassignments(connection)
        cleaned += reconcile_released_free_markers(connection)
        if cleaned:
            connection.commit()
        # A failed durable event.json write must remain visible in the
        # global task list until a later startup/retry repairs it.
        for document_task in connection.execute(
            """SELECT task.event_id,task.job_id,task.status,e.name AS event_name
               FROM event_document_sync_tasks task
               JOIN events e ON e.id=task.event_id
               WHERE task.status IN ('pending','blocked')
               ORDER BY task.updated_at,task.event_id"""
        ).fetchall():
            tasks.append({
                'kind': 'event_document_sync',
                'job_id': document_task['job_id'],
                'event_id': document_task['event_id'],
                'title': 'Ereignisdokument prüfen',
                'detail': str(document_task['event_name']) + ' · event.json-Synchronisierung offen',
                'count': 1,
                'href': f"/events?job={document_task['job_id']}",
            })
        active_reconcile_event_ids: set[str] = set()
        for active in connection.execute(
            """SELECT details_json FROM sort_runs
               WHERE status IN ('queued','verifying','moving','finalizing','rolling_back')
                 AND run_kind='reapply'"""
        ).fetchall():
            try:
                details = json.loads(str(active['details_json'] or '{}'))
            except Exception:
                details = {}
            for eid in details.get('event_ids') or []:
                active_reconcile_event_ids.add(str(eid))
        for row in connection.execute(
            """SELECT e.job_id AS anchor_job_id, r.event_id,
                      e.name AS event_name, COUNT(*) AS n
               FROM event_reapply_removed_families r
               JOIN events e ON e.id=r.event_id
               WHERE r.target_event_id IS NULL
                 AND COALESCE(r.target_kind,'') <> 'released_free'
                 AND NOT EXISTS (
                   SELECT 1 FROM event_mutations m
                   WHERE m.anchor_event_id=r.event_id
                     AND m.status IN ('pending_reassignment','pending_apply')
                 )
               GROUP BY e.job_id, r.event_id, e.name
               ORDER BY MIN(r.created_at)"""
        ).fetchall():
            tasks.append({
                'kind': 'reassignment', 'job_id': row['anchor_job_id'],
                'event_id': row['event_id'], 'title': 'Neu-Zuordnung',
                'detail': f"{row['n']} Familie" + ('' if int(row['n']) == 1 else 'n') + f" · {row['event_name']}",
                'count': 1, 'family_count': int(row['n']),
                'href': f"/events?job={row['anchor_job_id']}&task=reassign:{row['event_id']}",
            })
        for row in connection.execute(
            """SELECT sc.id,sc.job_id,sc.event_id,sc.status,e.name AS event_name,
                      sc.root_kind,sc.error_message
               FROM event_structure_changes sc
               JOIN events e ON e.id=sc.event_id
               WHERE sc.status IN ('pending','prepared','verified','blocked')
               ORDER BY sc.created_at"""
        ).fetchall():
            state = str(row["status"])
            detail = (
                f"{row['event_name']} · "
                + ("Archiv · event.json ersetzen und prüfen" if state == "prepared"
                   else "Prüfung erforderlich" if state == "blocked"
                   else "manuelle Ordner-/Dateiänderung erkannt")
            )
            tasks.append({
                'kind': 'event_structure_change',
                'job_id': row['job_id'],
                'event_id': row['event_id'],
                'structure_change_id': row['id'],
                'title': 'Manuelle Ereignisänderung',
                'detail': detail,
                'count': 1,
                'href': f"/events?job={row['job_id']}&task=structure:{row['id']}",
            })

        for row in connection.execute(
            """SELECT legacy.id AS legacy_event_id,
                      legacy.job_id AS legacy_job_id,
                      legacy.name AS legacy_name,
                      legacy.status AS legacy_status,
                      legacy.linkage_kind,
                      target.id AS target_event_id,
                      target.job_id AS target_job_id,
                      target.name AS target_name,
                      target.status AS target_status
               FROM events legacy
               JOIN events target ON target.id=legacy.linked_event_id
               WHERE legacy.parent_event_id IS NULL
                 AND legacy.linkage_kind IN ('planned_extension','applied_followup')
               ORDER BY legacy.created_at,legacy.id"""
        ).fetchall():
            archived = str(row["target_status"] or "") == "archived"
            tasks.append({
                'kind': 'legacy_multi_backup_structure',
                'job_id': row['target_job_id'],
                'event_id': row['target_event_id'],
                'legacy_event_id': row['legacy_event_id'],
                'title': 'Legacy-Mehrsicherungsstruktur muss vereinheitlicht werden',
                'detail': (
                    f"{row['target_name']} · "
                    + ("Archiv · manueller Archivweg erforderlich" if archived
                       else f"alter {row['linkage_kind']}-Bestand")
                ),
                'count': 1,
                'href': (
                    f"/events?job={row['target_job_id']}"
                    f"&task=legacy:{row['legacy_event_id']}"
                ),
            })

        for row in connection.execute(
            """SELECT id,job_id,event_id,event_name,status FROM event_change_requests
               WHERE status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')
               ORDER BY created_at"""
        ).fetchall():
            tasks.append({
                'kind': 'archive_change', 'job_id': row['job_id'],
                'event_id': row['event_id'], 'change_request_id': row['id'],
                'title': 'Archivänderung',
                'detail': f"{row['event_name']} · {row['status']}", 'count': 1,
                'href': f"/events?job={row['job_id']}&task=change:{row['id']}",
            })
        for row in connection.execute(
            """SELECT e.job_id,e.id,e.name FROM events e
               WHERE e.event_level='parent' AND e.resort_required=1
                 AND e.status='applied'
                 AND NOT EXISTS (
                   SELECT 1 FROM event_reapply_removed_families r
                   WHERE r.event_id=e.id AND r.target_event_id IS NULL
                     AND COALESCE(r.target_kind,'') <> 'released_free'
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM event_mutations m
                   WHERE m.job_id=e.job_id
                     AND m.anchor_event_id=e.id
                     AND m.status IN ('pending_reassignment','pending_apply')
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM sort_runs sr
                   WHERE sr.event_id=e.id AND sr.run_kind='reapply'
                     AND sr.status IN ('queued','verifying','moving','finalizing','rolling_back')
                 )
               ORDER BY e.updated_at"""
        ).fetchall():
            if str(row['id']) in active_reconcile_event_ids:
                continue
            tasks.append({
                'kind': 'resort', 'job_id': row['job_id'], 'event_id': row['id'],
                'title': 'Nachsortierung', 'detail': str(row['name']), 'count': 1,
                'href': f"/events?job={row['job_id']}&task=resort:{row['id']}",
            })
        # Geplante Ereignisse sind ein klarer, bewusst angelegter Arbeitsstand:
        # sie müssen noch angewendet werden. Erweiterungs-/Nachtragszeilen werden
        # dabei genauso behandelt, weil auch sie einen offenen Sortierlauf darstellen.
        for row in connection.execute(
            """SELECT e.id,e.job_id,e.name,e.folder_name FROM events e
               WHERE e.parent_event_id IS NULL AND e.status='planned'
                 AND COALESCE(TRIM(e.linkage_kind),'')=''
                 AND NOT EXISTS (
                   SELECT 1 FROM event_reapply_removed_families r
                   WHERE r.target_event_id=e.id
                 )
               ORDER BY e.updated_at"""
        ).fetchall():
            tasks.append({
                'kind': 'planned_apply', 'job_id': row['job_id'], 'event_id': row['id'],
                'title': 'Geplantes Ereignis anwenden', 'detail': str(row['name']), 'count': 1,
                'href': f"/workspace?job={row['job_id']}&task=planned:{row['id']}",
            })

        # Applied events are not finished until their camera archive verification
        # has completed. Keep one actionable task per active root event.
        for row in connection.execute(
            """SELECT e.id,e.job_id,e.name FROM events e
               WHERE e.parent_event_id IS NULL AND e.status='applied'
                 AND COALESCE(TRIM(e.linkage_kind),'')=''
                 AND NOT EXISTS (
                   SELECT 1 FROM sort_runs sr
                   WHERE sr.event_id=e.id
                     AND sr.status IN ('queued','verifying','moving','finalizing','rolling_back')
                 )
               ORDER BY e.updated_at"""
        ).fetchall():
            tasks.append({
                'kind':'archive_pending','job_id':row['job_id'],
                'event_id':row['id'],'title':'Ereignis archivieren',
                'detail':str(row['name']),'count':1,
                'href':f"/events?job={row['job_id']}",
            })

        # Nach einer abgeschlossenen Archivänderung liegen herausgefallene
        # Familien wieder sicher im SSD-Arbeitsbereich. Sie besitzen bewusst
        # keinen separaten Neu-Zuordnungsauftrag mehr, sollen aber als offene
        # Aufgabe sichtbar bleiben, bis sie über „Aufnahmen“ neu verplant sind.
        for row in connection.execute(
            """SELECT MIN(marker.job_id) AS anchor_job_id,
                      COUNT(DISTINCT marker.family_id) AS n
               FROM released_free_families marker
               JOIN file_families ff ON ff.id=marker.family_id
               WHERE ff.selected_capture_time IS NOT NULL
                 AND NOT EXISTS (
                   SELECT 1 FROM event_assignments ea
                   JOIN events e ON e.id=ea.event_id
                   WHERE ea.family_id=marker.family_id
                     AND e.status IN ('draft','planned','applied','archived')
                 )
                 AND EXISTS (
                   SELECT 1 FROM files f
                   WHERE f.family_id=marker.family_id
                     AND f.current_root_kind='shared_workspace'
                     AND (f.current_relative_path LIKE 'Freigewordene Archivdateien/%' OR f.current_relative_path LIKE 'Released Archive Files/%')
                 )
               HAVING COUNT(DISTINCT marker.family_id) > 0"""
        ).fetchall():
            tasks.append({
                'kind': 'released_archive_families',
                'job_id': row['anchor_job_id'],
                'title': 'Freigewordene Archivaufnahmen',
                'detail': f"{int(row['n'])} Familie" + ('' if int(row['n']) == 1 else 'n'),
                'count': 1,
                'family_count': int(row['n']),
                'href': f"/workspace?job={row['anchor_job_id']}&task=free",
            })

        # Ohne-Datum-Familien sind ein eigener, global sichtbarer Prüfschritt.
        # Der physische Bestand liegt zentral unter SD-Kartensicherungen und
        # soll deshalb nicht pro Importjob oder Bibliothek als Aufgabe
        # vervielfacht werden.
        undated = connection.execute(
            """SELECT
                   COUNT(DISTINCT CASE
                       WHEN ff.selected_capture_time IS NULL THEN ff.id
                   END) AS review_n,
                   COUNT(DISTINCT CASE
                       WHEN ff.selected_capture_time IS NOT NULL THEN ff.id
                   END) AS ready_n
               FROM file_families ff
               JOIN files f ON f.family_id=ff.id AND f.job_id=ff.job_id
               WHERE f.current_root_kind='shared_workspace'
                 AND (
                   f.current_relative_path IN ('Ohne_Datum','No Date')
                   OR (f.current_relative_path LIKE 'Ohne_Datum/%' OR f.current_relative_path LIKE 'No Date/%')
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM event_assignments ea
                   JOIN events e ON e.id=ea.event_id
                   WHERE ea.family_id=ff.id
                     AND e.status IN ('draft','planned','applied','archived')
                 )"""
        ).fetchone()
        review_n = int(undated["review_n"] or 0) if undated else 0
        ready_n = int(undated["ready_n"] or 0) if undated else 0
        if review_n or ready_n:
            if review_n:
                title = "Prüffälle bearbeiten"
            else:
                title = "Korrigierte Aufnahmen einsortieren"
            detail_parts = []
            if review_n:
                detail_parts.append(
                    f"{review_n} Prüffall" + ("" if review_n == 1 else "fälle")
                )
            if ready_n:
                detail_parts.append(
                    f"{ready_n} bereit zum Einsortieren"
                )
            tasks.append({
                "kind": "metadata_review",
                "title": title,
                "detail": " · ".join(detail_parts),
                "count": 1,
                "review_count": review_n,
                "ready_count": ready_n,
                "href": "/metadata-correction?area=library",
            })

        # Freie Familien folgen den normalen Workspace-Tageskarten.
        # Nur echte offene Neu-Zuordnungen oder gesondert angezeigte
        # Archivfreigaben werden ausgeschlossen; ein alter gewöhnlicher
        # released_free-Marker darf die Sammelaufgabe nicht unterdrücken.
        # Metadatenkorrekturen werden global nur pro Bereich gebündelt.
        # Einzeldateien bleiben auf der Metadatenseite nachvollziehbar, blähen
        # aber den allgemeinen Aufgabenindikator nicht mehr auf.
        for row in connection.execute(
            """SELECT area,
                      COUNT(*) AS n,
                      SUM(CASE WHEN status='blocked' THEN 1 ELSE 0 END) AS blocked_n,
                      MIN(id) AS single_id,
                      MIN(created_at) AS first_created
               FROM metadata_corrections
               WHERE status IN ('pending_review','prepared','writing','blocked')
               GROUP BY area
               ORDER BY first_created"""
        ).fetchall():
            area = str(row["area"])
            # Bibliotheks-Prüffälle und korrigierte Ohne-Datum-Familien werden
            # oben als eine fachliche Aufgabe dargestellt. Ein blockierter
            # Einzelauftrag bleibt auf der Metadatenseite sichtbar, soll den
            # globalen Aufgabenindikator aber nicht doppeln.
            if area == "library":
                continue
            label = "Allgemein" if area == "general" else "Bibliothek"
            count = int(row["n"] or 0)
            blocked = int(row["blocked_n"] or 0)
            detail = (
                f"{count} offene Korrektur"
                + ("" if count == 1 else "en")
            )
            if blocked:
                detail += (
                    f" · {blocked} blockiert"
                )
            tasks.append({
                "kind": "metadata_correction",
                "metadata_area": area,
                "metadata_correction_id": (
                    str(row["single_id"]) if count == 1 else None
                ),
                "title": f"Metadatenkorrektur · {label}",
                "detail": detail,
                "count": 1,
                "correction_count": count,
                "blocked_count": blocked,
                "href": f"/metadata-correction?area={area}",
            })

        placement = connection.execute(
            """SELECT COUNT(*) AS n,
                      SUM(CASE WHEN repairable=1 THEN 1 ELSE 0 END) AS repairable_n,
                      SUM(CASE WHEN root_kind='camera_archive' THEN 1 ELSE 0 END) AS archive_n
               FROM external_change_notices
               WHERE status='open' AND action_required=1"""
        ).fetchone()
        placement_n = int(placement["n"] or 0)
        if placement_n:
            detail = (
                f"{placement_n} Abweichung"
                + ("" if placement_n == 1 else "en")
                + " zwischen physischem Bestand und fachlicher Zuordnung"
            )
            archive_n = int(placement["archive_n"] or 0)
            if archive_n:
                detail += (
                    f" · {archive_n} im schreibgeschützten Archiv"
                )
            tasks.append({
                "kind": "placement_conflicts",
                "title": "Dateizuordnung prüfen",
                "detail": detail,
                "count": 1,
                "conflict_count": placement_n,
                "repairable_count": int(placement["repairable_n"] or 0),
                "archive_count": archive_n,
                "href": "/workspace?task=placement-conflicts",
            })

        row = connection.execute(
            """SELECT COUNT(*) AS n,
                      COUNT(DISTINCT ff.job_id) AS job_count,
                      MIN(COALESCE(j.source_volume_label,ff.job_id)) AS only_label
               FROM file_families ff JOIN jobs j ON j.id=ff.job_id
               WHERE ff.selected_capture_time IS NOT NULL
                 AND NOT EXISTS (
                   SELECT 1 FROM files undated_file
                   WHERE undated_file.family_id=ff.id
                     AND undated_file.job_id=ff.job_id
                     AND undated_file.current_root_kind='shared_workspace'
                     AND (
                       undated_file.current_relative_path IN ('Ohne_Datum','No Date')
                       OR (undated_file.current_relative_path LIKE 'Ohne_Datum/%' OR undated_file.current_relative_path LIKE 'No Date/%')
                     )
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM event_assignments ea JOIN events e ON e.id=ea.event_id
                   WHERE ea.family_id=ff.id
                     AND e.status IN ('draft','planned','applied','archived')
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM event_reapply_removed_families r
                   WHERE r.job_id=ff.job_id AND r.family_id=ff.id AND r.target_event_id IS NULL
                 )
                 AND NOT EXISTS (
                   SELECT 1 FROM released_free_families marker
                   WHERE marker.job_id=ff.job_id AND marker.family_id=ff.id
                     AND COALESCE(marker.archive_origin,0)=1
                     AND EXISTS (
                       SELECT 1 FROM files released
                       WHERE released.family_id=ff.id
                         AND released.current_root_kind='shared_workspace'
                         AND (released.current_relative_path LIKE 'Freigewordene Archivdateien/%'
                           OR released.current_relative_path LIKE 'Released Archive Files/%')
                     )
                 )"""
        ).fetchone()
        unassigned_count = int(row["n"] or 0) if row is not None else 0
        if unassigned_count:
            job_count = int(row["job_count"] or 0)
            suffix = (
                f" · {row['only_label']}"
                if job_count == 1 and str(row["only_label"] or "").strip()
                else " · freier Tagesbestand"
            )
            tasks.append({
                "kind": "unassigned_families",
                "title": "Noch nicht zugeordnet",
                "detail": (
                    f"{unassigned_count} Familie"
                    + ("" if unassigned_count == 1 else "n")
                    + suffix
                ),
                "count": 1,
                "family_count": unassigned_count,
                "job_count": job_count,
                "href": "/workspace?task=free",
            })
    return tasks


def list_job_time_segments(database_path: Path, job_id: str) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT s.*, e.name AS event_name, e.event_kind, e.status
               FROM event_time_segments s JOIN events e ON e.id=s.event_id
               WHERE s.job_id=? ORDER BY s.start_datetime,s.id""", (job_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_imported_source_files(
    database_path: Path,
    source_device_id: str,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            SELECT source_device_id, relative_path, size_bytes,
                   modified_at_ns, sha256, imported_job_id,
                   first_imported_at, last_seen_at
            FROM imported_source_files
            WHERE source_device_id = ?
            ORDER BY relative_path, id
            """,
            (source_device_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def store_imported_source_files(
    database_path: Path,
    *,
    source_device_id: str,
    job_id: str,
    entries: list[dict[str, Any]],
) -> None:
    now = utc_now_iso()
    with database_connection(database_path) as connection:
        for entry in entries:
            connection.execute(
                """
                INSERT INTO imported_source_files (
                    source_device_id,
                    relative_path,
                    size_bytes,
                    modified_at_ns,
                    sha256,
                    imported_job_id,
                    first_imported_at,
                    last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_device_id, relative_path, sha256)
                DO UPDATE SET
                    size_bytes = excluded.size_bytes,
                    modified_at_ns = excluded.modified_at_ns,
                    imported_job_id = excluded.imported_job_id,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    source_device_id,
                    str(entry["relative_path"]),
                    int(entry["size_bytes"]),
                    int(entry.get("modified_at_ns") or 0),
                    str(entry["sha256"]),
                    job_id,
                    now,
                    now,
                ),
            )
