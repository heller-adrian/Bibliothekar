from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import database_connection
from app.safe_transfer import reconcile_migrated_file
from app.workspace_layout import backup_root, shared_work_root


class GlobalStockError(RuntimeError):
    pass


def _table_columns(connection: Any, table: str) -> list[str]:
    return [
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _insert_row(
    connection: Any,
    table: str,
    row: dict[str, Any],
    *,
    exclude: set[str] | None = None,
) -> None:
    excluded = exclude or set()
    available = set(_table_columns(connection, table))
    columns = [
        column
        for column in row
        if column in available and column not in excluded
    ]
    if not columns:
        raise GlobalStockError("Keine kompatiblen Spalten für Tabelle " + table)
    placeholders = ",".join("?" for _ in columns)
    names = ",".join(columns)
    connection.execute(
        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
        tuple(row[column] for column in columns),
    )


def project_import_job(
    source_database: Path,
    target_database: Path,
    job_id: str,
) -> dict[str, int]:
    """Project one completed global import into another library database.

    IDs of families/files are deliberately local to the target database.
    Natural keys (job_id/family_key and job_id/original_relative_path) provide
    the stable mapping. Existing target rows are never overwritten, because an
    applied library is allowed to have a different physical current path.
    """

    if source_database.resolve(strict=False) == target_database.resolve(strict=False):
        return {"jobs": 0, "families": 0, "files": 0}

    with database_connection(source_database) as source:
        raw_job = source.execute(
            "SELECT * FROM jobs WHERE id=? AND kind='sd_import'",
            (str(job_id),),
        ).fetchone()
        if raw_job is None:
            return {"jobs": 0, "families": 0, "files": 0}
        job = dict(raw_job)
        families = [
            dict(row)
            for row in source.execute(
                "SELECT * FROM file_families WHERE job_id=? ORDER BY id",
                (str(job_id),),
            ).fetchall()
        ]
        files = [
            dict(row)
            for row in source.execute(
                "SELECT * FROM files WHERE job_id=? ORDER BY id",
                (str(job_id),),
            ).fetchall()
        ]

    source_family_key = {
        int(row["id"]): str(row["family_key"])
        for row in families
    }

    inserted_jobs = 0
    inserted_families = 0
    inserted_files = 0

    with database_connection(target_database) as target:
        target.execute("BEGIN IMMEDIATE")

        existing_job = target.execute(
            "SELECT id FROM jobs WHERE id=?",
            (str(job_id),),
        ).fetchone()
        if existing_job is None:
            _insert_row(target, "jobs", job)
            inserted_jobs += 1

        family_id_by_key: dict[str, int] = {}
        for family in families:
            key = str(family["family_key"])
            existing = target.execute(
                "SELECT id FROM file_families WHERE job_id=? AND family_key=?",
                (str(job_id), key),
            ).fetchone()
            if existing is None:
                _insert_row(
                    target,
                    "file_families",
                    family,
                    exclude={"id"},
                )
                existing = target.execute(
                    "SELECT id FROM file_families WHERE job_id=? AND family_key=?",
                    (str(job_id), key),
                ).fetchone()
                inserted_families += 1
            if existing is None:
                raise GlobalStockError(
                    "Familienprojektion konnte nicht bestätigt werden: " + key
                )
            family_id_by_key[key] = int(existing["id"])

        for file_row in files:
            relative = str(file_row["original_relative_path"])
            existing = target.execute(
                "SELECT id FROM files WHERE job_id=? AND original_relative_path=?",
                (str(job_id), relative),
            ).fetchone()
            if existing is not None:
                continue

            projected = dict(file_row)
            source_family_id = projected.get("family_id")
            if source_family_id is not None:
                key = source_family_key.get(int(source_family_id))
                if not key or key not in family_id_by_key:
                    raise GlobalStockError(
                        "Dateifamilie der Projektion fehlt: " + relative
                    )
                projected["family_id"] = family_id_by_key[key]

            _insert_row(
                target,
                "files",
                projected,
                exclude={"id"},
            )
            inserted_files += 1

        target.commit()

    return {
        "jobs": inserted_jobs,
        "families": inserted_families,
        "files": inserted_files,
    }


def project_all_imports(
    source_database: Path,
    target_database: Path,
) -> dict[str, int]:
    if source_database.resolve(strict=False) == target_database.resolve(strict=False):
        return {"jobs": 0, "families": 0, "files": 0}

    with database_connection(source_database) as source:
        job_ids = [
            str(row["id"])
            for row in source.execute(
                """SELECT id FROM jobs
                   WHERE kind='sd_import' AND state='completed'
                   ORDER BY created_at,id"""
            ).fetchall()
        ]

    totals = {"jobs": 0, "families": 0, "files": 0}
    for job_id in job_ids:
        result = project_import_job(
            source_database,
            target_database,
            job_id,
        )
        for key in totals:
            totals[key] += int(result[key])
    return totals


def migrate_main_free_stock_to_central(
    database_path: Path,
    workspace_path: Path,
) -> dict[str, int]:
    """Move legacy free/planned Main files from Arbeitsbereich to central stock.

    Applied event files and library-specific "Später zuordnen" material remain
    in the Main library work root. The operation is idempotent and validates
    every destination before deleting a source.
    """

    central = backup_root(workspace_path).resolve(strict=False)
    work = shared_work_root(workspace_path).resolve(strict=False)

    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    f.id,
                    f.family_id,
                    f.current_relative_path,
                    f.size_bytes,
                    f.sha256_current,
                    f.sha256_original,
                    EXISTS (
                        SELECT 1
                        FROM event_assignments ea
                        JOIN events assigned ON assigned.id=ea.event_id
                        JOIN events root
                          ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                        WHERE root.status='applied'
                          AND (
                              (ea.family_id IS NOT NULL AND ea.family_id=f.family_id)
                              OR (ea.file_id IS NOT NULL AND ea.file_id=f.id)
                          )
                    ) AS belongs_to_applied
                FROM files f
                WHERE f.current_root_kind='shared_workspace'
                  AND COALESCE(TRIM(f.current_relative_path),'') <> ''
                ORDER BY f.id
                """
            ).fetchall()
        ]

    migrated = 0
    already = 0
    kept_applied = 0
    kept_staging = 0

    for row in rows:
        relative = Path(str(row["current_relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise GlobalStockError(
                "Unsicherer relativer Pfad in Main-Bestand: " + str(relative)
            )

        normalized = relative.as_posix()
        if normalized == "Später zuordnen" or normalized.startswith("Später zuordnen/"):
            kept_staging += 1
            continue
        if bool(row["belongs_to_applied"]):
            kept_applied += 1
            continue

        source = work / relative
        destination = central / relative
        expected_hash = str(
            row.get("sha256_current")
            or row.get("sha256_original")
            or ""
        ).strip()
        if not expected_hash:
            raise GlobalStockError(
                "Für die Migration fehlt SHA-256: " + str(relative)
            )

        result = reconcile_migrated_file(
            source,
            destination,
            expected_size=int(row["size_bytes"]),
            expected_sha256=expected_hash,
        )
        if str(result.get("status")) == "migrated":
            migrated += 1
        else:
            already += 1

    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE jobs
               SET working_path=?
               WHERE kind='sd_import'
                 AND operation='folder_import'""",
            (str(central),),
        )
        connection.commit()

    return {
        "migrated": migrated,
        "already_migrated": already,
        "kept_applied": kept_applied,
        "kept_staging": kept_staging,
    }
