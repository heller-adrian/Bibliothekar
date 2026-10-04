from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import shutil

from app.database import database_connection
from app.global_library_inventory import backfill_library_inventory
from app.global_stock import project_import_job
from app.library_registry import (
    MAIN_LIBRARY_ID,
    list_libraries,
    remove_source_backup,
)
from app.pipeline import sha256_file


class BackupDeletionError(RuntimeError):
    pass


def _library_rows(registry_path: Path, main_database: Path) -> list[dict[str, Any]]:
    rows = list_libraries(
        registry_path,
        active_only=False,
        registered_only=False,
    )
    if not any(
        Path(str(row.get("database_path") or "")).resolve(strict=False)
        == main_database.resolve(strict=False)
        for row in rows
    ):
        rows.insert(
            0,
            {
                "library_id": MAIN_LIBRARY_ID,
                "display_name": "Main Library",
                "database_path": str(main_database),
                "is_main": 1,
            },
        )
    return rows


def _safe_central_file(central_root: Path, relative_path: str) -> Path:
    relative = Path(str(relative_path or ""))
    if (
        not relative.parts
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        raise BackupDeletionError(
            "Die Sicherung enthält einen unsicheren Arbeitsbereichspfad."
        )
    root = central_root.resolve(strict=False)
    candidate = (root / relative).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise BackupDeletionError(
            "Die Sicherung enthält einen Pfad außerhalb des Arbeitsbestands."
        ) from error
    return candidate


def _job_is_used_by_events(database_path: Path, job_id: str) -> bool:
    if not database_path.exists():
        raise BackupDeletionError(
            "Eine registrierte Bibliotheksdatenbank ist nicht erreichbar: "
            + str(database_path)
        )

    with database_connection(database_path) as connection:
        job = connection.execute(
            "SELECT id FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
        if job is None:
            return False

        direct = connection.execute(
            """
            SELECT 1
            FROM events
            WHERE job_id = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        if direct is not None:
            return True

        table = connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = 'event_source_jobs'
            """
        ).fetchone()
        if table is not None:
            source = connection.execute(
                """
                SELECT 1
                FROM event_source_jobs
                WHERE source_job_id = ?
                LIMIT 1
                """,
                (job_id,),
            ).fetchone()
            if source is not None:
                return True

        assigned = connection.execute(
            """
            SELECT 1
            FROM event_assignments AS assignment
            LEFT JOIN file_families AS direct_family
              ON direct_family.id = assignment.family_id
            LEFT JOIN files AS assigned_file
              ON assigned_file.id = assignment.file_id
            LEFT JOIN file_families AS file_family
              ON file_family.id = assigned_file.family_id
            WHERE COALESCE(direct_family.job_id, file_family.job_id) = ?
            LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        return assigned is not None


def _main_file_rows(main_database: Path, job_id: str) -> list[dict[str, Any]]:
    with database_connection(main_database) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                current_root_kind,
                current_relative_path,
                size_bytes,
                COALESCE(NULLIF(sha256_current, ''), sha256_original) AS sha256
            FROM files
            WHERE job_id = ?
            ORDER BY id
            """,
            (job_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def backup_deletion_status(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
    job_id: str,
) -> dict[str, Any]:
    with database_connection(main_database) as connection:
        job = connection.execute(
            """
            SELECT id, kind, operation, state
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    if job is None:
        return {
            "allowed": False,
            "reason": "Sicherung wurde nicht gefunden.",
        }

    if (
        str(job["kind"]) != "sd_import"
        or str(job["operation"]) != "folder_import"
    ):
        return {
            "allowed": False,
            "reason": "Nur abgeschlossene Kamera-Sicherungen können hier gelöscht werden.",
        }

    if str(job["state"]) != "completed":
        return {
            "allowed": False,
            "reason": "Die Sicherung ist noch nicht vollständig abgeschlossen.",
        }

    library_rows = _library_rows(registry_path, main_database)
    for library in library_rows:
        database_value = str(library.get("database_path") or "").strip()
        if not database_value:
            continue
        database_path = Path(database_value)
        if _job_is_used_by_events(database_path, job_id):
            return {
                "allowed": False,
                "reason": (
                    "Die Sicherung wird bereits von mindestens einem Ereignis "
                    "verwendet und kann deshalb nicht mehr vollständig gelöscht werden."
                ),
            }

    files = _main_file_rows(main_database, job_id)
    if not files:
        return {
            "allowed": False,
            "reason": "Die Sicherung enthält keinen vollständig löschbaren Arbeitsbestand.",
        }

    seen: set[str] = set()
    for row in files:
        if str(row.get("current_root_kind") or "") != "shared_workspace":
            return {
                "allowed": False,
                "reason": (
                    "Die Sicherung liegt nicht mehr vollständig im Arbeitsbestand."
                ),
            }
        relative = str(row.get("current_relative_path") or "").strip()
        if (
            not relative
            or relative.startswith("Freigewordene Archivdateien/")
            or relative in seen
        ):
            return {
                "allowed": False,
                "reason": (
                    "Die Sicherung liegt nicht mehr eindeutig und vollständig "
                    "im Arbeitsbestand."
                ),
            }
        seen.add(relative)
        path = _safe_central_file(central_root, relative)
        if not path.is_file() or path.is_symlink():
            return {
                "allowed": False,
                "reason": (
                    "Mindestens eine Datei der Sicherung fehlt im Arbeitsbestand."
                ),
            }

    return {
        "allowed": True,
        "reason": "",
        "file_count": len(files),
        "total_size_bytes": sum(int(row.get("size_bytes") or 0) for row in files),
    }


def _remove_empty_parents(path: Path, stop: Path) -> None:
    stop_resolved = stop.resolve(strict=False)
    current = path.resolve(strict=False)
    while current != stop_resolved:
        try:
            current.relative_to(stop_resolved)
        except ValueError:
            return
        try:
            current.rmdir()
        except OSError:
            return
        current = current.parent


def _delete_job_row(database_path: Path, job_id: str) -> bool:
    if not database_path.exists():
        return False
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM imported_source_files WHERE imported_job_id = ?",
            (job_id,),
        )
        cursor = connection.execute(
            "DELETE FROM jobs WHERE id = ?",
            (job_id,),
        )
        connection.commit()
        return cursor.rowcount == 1


def delete_backup(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
    job_id: str,
) -> dict[str, Any]:
    status = backup_deletion_status(
        main_database,
        registry_path,
        central_root,
        job_id,
    )
    if not status.get("allowed"):
        raise BackupDeletionError(str(status.get("reason") or "Sicherung ist nicht löschbar."))

    files = _main_file_rows(main_database, job_id)
    verified: list[tuple[dict[str, Any], Path]] = []
    for row in files:
        relative = str(row["current_relative_path"])
        path = _safe_central_file(central_root, relative)
        if path.stat().st_size != int(row["size_bytes"]):
            raise BackupDeletionError(
                "Dateigröße stimmt vor dem Löschen nicht mehr: " + relative
            )
        if sha256_file(path) != str(row["sha256"]):
            raise BackupDeletionError(
                "SHA-256 stimmt vor dem Löschen nicht mehr: " + relative
            )
        verified.append((row, path))

    staging_root = central_root / ".deleting" / job_id
    if staging_root.exists() or staging_root.is_symlink():
        raise BackupDeletionError(
            "Ein alter Lösch-Stagingbereich existiert bereits: " + str(staging_root)
        )
    staging_root.mkdir(parents=True, exist_ok=False)

    moved: list[tuple[Path, Path]] = []
    library_rows = _library_rows(registry_path, main_database)
    deleted_databases: list[Path] = []
    main_resolved = main_database.resolve(strict=False)

    try:
        for row, source in verified:
            relative = Path(str(row["current_relative_path"]))
            staged = staging_root / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, staged)
            moved.append((source, staged))

        database_rows: list[tuple[str, Path]] = []
        for library in library_rows:
            value = str(library.get("database_path") or "").strip()
            if not value:
                continue
            database_path = Path(value)
            if not database_path.exists():
                continue
            with database_connection(database_path) as connection:
                exists = connection.execute(
                    "SELECT 1 FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()
            if exists is not None:
                database_rows.append(
                    (str(library.get("library_id") or MAIN_LIBRARY_ID), database_path)
                )

        secondary_rows = [
            row
            for row in database_rows
            if row[1].resolve(strict=False) != main_resolved
        ]
        for _, database_path in secondary_rows:
            if _delete_job_row(database_path, job_id):
                deleted_databases.append(database_path)

        for library in library_rows:
            library_id = str(library.get("library_id") or MAIN_LIBRARY_ID)
            remove_source_backup(
                registry_path,
                f"{library_id}:{job_id}",
            )

        if not _delete_job_row(main_database, job_id):
            raise BackupDeletionError(
                "Der Hauptdatensatz der Sicherung konnte nicht gelöscht werden."
            )

    except Exception as error:
        # Solange der Main-Datensatz noch existiert, lassen sich entfernte
        # Projektionen und Registry-Einträge deterministisch wieder aufbauen.
        try:
            with database_connection(main_database) as connection:
                main_exists = connection.execute(
                    "SELECT 1 FROM jobs WHERE id = ?",
                    (job_id,),
                ).fetchone() is not None
        except Exception:
            main_exists = False

        if main_exists:
            for library in library_rows:
                database_value = str(library.get("database_path") or "").strip()
                library_id = str(library.get("library_id") or MAIN_LIBRARY_ID)
                if not database_value:
                    continue
                database_path = Path(database_value)
                try:
                    if database_path.resolve(strict=False) != main_resolved:
                        project_import_job(
                            main_database,
                            database_path,
                            job_id,
                        )
                    backfill_library_inventory(
                        registry_path,
                        database_path=database_path,
                        library_id=library_id,
                        claim_all_owned=False,
                    )
                except Exception:
                    pass

        rollback_errors: list[str] = []
        for source, staged in reversed(moved):
            try:
                if staged.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(staged, source)
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))

        shutil.rmtree(staging_root, ignore_errors=True)
        if rollback_errors:
            raise BackupDeletionError(
                "Sicherung konnte nicht gelöscht werden; Rückbau war unvollständig: "
                + " | ".join(rollback_errors)
            ) from error
        if isinstance(error, BackupDeletionError):
            raise
        raise BackupDeletionError(str(error)) from error

    deleted_size = sum(int(row.get("size_bytes") or 0) for row, _ in verified)
    shutil.rmtree(staging_root, ignore_errors=False)
    try:
        (central_root / ".deleting").rmdir()
    except OSError:
        pass

    for source, _ in moved:
        _remove_empty_parents(source.parent, central_root)

    return {
        "job_id": job_id,
        "deleted_file_count": len(verified),
        "deleted_size_bytes": deleted_size,
    }
