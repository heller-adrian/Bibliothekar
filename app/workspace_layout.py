from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import uuid

from app.database import database_connection


BACKUP_DIRECTORY_NAME = "SD-Kartensicherungen"
WORK_DIRECTORY_NAME = "Arbeitsbereich"


class WorkspaceLayoutError(RuntimeError):
    """Raised when the shared SSD layout cannot be created or migrated safely."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_relative(value: Any) -> PurePosixPath:
    raw = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)

    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WorkspaceLayoutError(
            "Unsicherer relativer Dateipfad: " + raw
        )

    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY

    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY

    descriptor = os.open(path, flags)

    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def resolve_workspace_root(workspace_path: Path) -> Path:
    root = workspace_path.expanduser().resolve(strict=False)

    if not root.exists() or not root.is_dir():
        raise WorkspaceLayoutError(
            "Das SSD-Dataset ist nicht verfügbar: " + str(root)
        )

    if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
        raise WorkspaceLayoutError(
            "Das SSD-Dataset ist nicht vollständig zugreifbar: " + str(root)
        )

    return root


def ensure_workspace_layout(workspace_path: Path) -> dict[str, Any]:
    root = resolve_workspace_root(workspace_path)
    backup_root = root / BACKUP_DIRECTORY_NAME
    work_root = root / WORK_DIRECTORY_NAME

    created: list[str] = []

    for directory in (backup_root, work_root):
        if directory.exists() and not directory.is_dir():
            raise WorkspaceLayoutError(
                "Ein benötigter Strukturpfad ist kein Ordner: "
                + str(directory)
            )

        if not directory.exists():
            directory.mkdir(mode=0o775)
            _fsync_directory(root)
            created.append(str(directory))

        if not os.access(directory, os.R_OK | os.W_OK | os.X_OK):
            raise WorkspaceLayoutError(
                "Ein Strukturordner ist nicht vollständig zugreifbar: "
                + str(directory)
            )

    if int(root.stat().st_dev) != int(work_root.stat().st_dev):
        raise WorkspaceLayoutError(
            "Der dauerhafte Arbeitsbereich liegt nicht auf demselben Dateisystem."
        )

    return {
        "workspace_root": str(root),
        "backup_root": str(backup_root),
        "work_root": str(work_root),
        "created_directories": created,
    }


def shared_work_root(workspace_path: Path) -> Path:
    root = resolve_workspace_root(workspace_path)
    entry = root / WORK_DIRECTORY_NAME
    target = entry.resolve(strict=False)

    if not target.exists() or not target.is_dir():
        raise WorkspaceLayoutError(
            "Der dauerhafte Arbeitsbereich fehlt: " + str(target)
        )

    if not entry.is_symlink() and not _is_relative_to(target, root):
        raise WorkspaceLayoutError(
            "Der dauerhafte Arbeitsbereich verlässt das SSD-Dataset."
        )

    return target


def resolve_library_work_root(
    workspace_path: Path,
    requested_work_root: Path | None = None,
) -> Path:
    shared_root = shared_work_root(workspace_path)

    if requested_work_root is None:
        return shared_root

    target = requested_work_root.expanduser().resolve(strict=False)
    backup = backup_root(workspace_path)

    if (
        target == backup
        or _is_relative_to(target, backup)
        or _is_relative_to(backup, target)
    ):
        raise WorkspaceLayoutError(
            "Der Bibliotheks-Arbeitsbereich darf nicht innerhalb der "
            "SD-Kartensicherungen liegen und beide Bereiche dürfen sich "
            "nicht überlappen."
        )

    if not target.exists():
        if _is_relative_to(target, shared_root):
            target.mkdir(parents=True, exist_ok=True)
        else:
            raise WorkspaceLayoutError(
                "Der Bibliotheks-Arbeitsbereich ist nicht verfügbar: "
                + str(target)
            )
    if not target.is_dir():
        raise WorkspaceLayoutError(
            "Der Bibliotheks-Arbeitsbereich ist kein Verzeichnis: "
            + str(target)
        )
    if not os.access(target, os.R_OK | os.W_OK | os.X_OK):
        raise WorkspaceLayoutError(
            "Der Bibliotheks-Arbeitsbereich ist nicht vollständig zugreifbar: "
            + str(target)
        )

    if int(target.stat().st_dev) != int(backup.stat().st_dev):
        raise WorkspaceLayoutError(
            "Der Bibliotheks-Arbeitsbereich muss auf demselben Dateisystem "
            "wie die gemeinsamen SD-Kartensicherungen liegen, damit "
            "Hardlinks sicher funktionieren."
        )

    return target


def backup_root(workspace_path: Path) -> Path:
    root = resolve_workspace_root(workspace_path)
    entry = root / BACKUP_DIRECTORY_NAME
    target = entry.resolve(strict=False)

    if not target.exists() or not target.is_dir():
        raise WorkspaceLayoutError(
            "Der Ordner für SD-Kartensicherungen fehlt: " + str(target)
        )

    if not entry.is_symlink() and not _is_relative_to(target, root):
        raise WorkspaceLayoutError(
            "Der Sicherungsordner verlässt das SSD-Dataset."
        )

    return target


def _job_root_candidates(job: dict[str, Any], workspace_root: Path) -> list[Path]:
    result: list[Path] = []

    for field in ("working_path", "source_path"):
        value = job.get(field)

        if not value:
            continue

        candidate = Path(str(value)).expanduser().resolve(strict=False)

        if not _is_relative_to(candidate, workspace_root):
            continue

        if candidate not in result:
            result.append(candidate)

    return result


def _load_legacy_applied_files(
    database_path: Path,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            WITH assigned_files AS (
                SELECT DISTINCT
                    f.id AS file_id,
                    root.id AS root_event_id
                FROM files AS f
                JOIN event_assignments AS ea
                    ON ea.family_id = f.family_id
                JOIN events AS assigned
                    ON assigned.id = ea.event_id
                JOIN events AS root
                    ON root.id = COALESCE(
                        assigned.parent_event_id,
                        assigned.id
                    )
                WHERE root.status = 'applied'

                UNION

                SELECT DISTINCT
                    f.id AS file_id,
                    root.id AS root_event_id
                FROM files AS f
                JOIN event_assignments AS ea
                    ON ea.file_id = f.id
                JOIN events AS assigned
                    ON assigned.id = ea.event_id
                JOIN events AS root
                    ON root.id = COALESCE(
                        assigned.parent_event_id,
                        assigned.id
                    )
                WHERE root.status = 'applied'
            )

            SELECT
                f.id AS file_id,
                f.job_id,
                f.current_relative_path,
                f.original_relative_path,
                f.size_bytes,
                f.sha256_current,
                f.sha256_original,
                f.current_root_kind,
                j.working_path,
                j.source_path,
                assigned_files.root_event_id,
                root.folder_name AS root_folder_name,
                root.start_datetime AS root_start_datetime

            FROM assigned_files
            JOIN files AS f
                ON f.id = assigned_files.file_id
            JOIN jobs AS j
                ON j.id = f.job_id
            JOIN events AS root
                ON root.id = assigned_files.root_event_id

            WHERE f.current_root_kind = 'job_root'

            ORDER BY
                f.job_id,
                assigned_files.root_event_id,
                f.id
            """
        ).fetchall()

    return [dict(row) for row in rows]


def _find_existing_source(
    row: dict[str, Any],
    workspace_root: Path,
    relative_path: PurePosixPath,
) -> tuple[Path, Path]:
    candidates = _job_root_candidates(row, workspace_root)

    if not candidates:
        raise WorkspaceLayoutError(
            "Für einen angewendeten Bestand fehlt ein gültiger alter Stamm: "
            + str(row.get("job_id"))
        )

    for root in candidates:
        candidate = root.joinpath(*relative_path.parts).resolve(strict=False)

        if not _is_relative_to(candidate, root):
            continue

        if candidate.exists() or candidate.is_symlink():
            return root, candidate

    # Return the first safe expected location so recovery can still detect
    # a file that was already moved before SQLite was updated.
    root = candidates[0]
    candidate = root.joinpath(*relative_path.parts).resolve(strict=False)
    return root, candidate


def _expected_checksum(row: dict[str, Any]) -> str:
    value = str(
        row.get("sha256_current")
        or row.get("sha256_original")
        or ""
    ).strip()

    if not value:
        raise WorkspaceLayoutError(
            "Für eine zu migrierende Datei fehlt die SHA-256-Summe: "
            + str(row.get("current_relative_path"))
        )

    return value


def _rollback_moved(entries: list[tuple[Path, Path]]) -> list[str]:
    errors: list[str] = []

    for source, destination in reversed(entries):
        try:
            source_exists = source.exists() or source.is_symlink()
            destination_exists = destination.exists() or destination.is_symlink()

            if destination_exists and not source_exists:
                source.parent.mkdir(parents=True, exist_ok=True)
                os.link(destination, source, follow_symlinks=False)
                destination.unlink()
                _fsync_directory(source.parent)
                _fsync_directory(destination.parent)
                continue

            if source_exists and destination_exists:
                source_stat = os.lstat(source)
                destination_stat = os.lstat(destination)

                if (
                    int(source_stat.st_dev) == int(destination_stat.st_dev)
                    and int(source_stat.st_ino) == int(destination_stat.st_ino)
                ):
                    destination.unlink()
                    _fsync_directory(destination.parent)
                    continue

            if source_exists and not destination_exists:
                continue

            errors.append(
                "Rollback-Zustand ist mehrdeutig: "
                + str(source)
                + " ↔ "
                + str(destination)
            )
        except Exception as error:  # pragma: no cover - last safety net
            errors.append(str(error))

    return errors


def _remove_empty_legacy_event_directories(
    event_roots: set[Path],
    workspace_root: Path,
) -> list[str]:
    removed: list[str] = []

    for event_root in sorted(
        event_roots,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if not _is_relative_to(event_root, workspace_root):
            continue

        if not event_root.exists() or not event_root.is_dir():
            continue

        directories = [
            path
            for path in event_root.rglob("*")
            if path.is_dir()
        ]
        directories.append(event_root)

        for directory in sorted(
            directories,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
                removed.append(str(directory))
                _fsync_directory(directory.parent)
            except OSError:
                pass

        year_root = event_root.parent
        if (
            _is_relative_to(year_root, workspace_root)
            and year_root != workspace_root
        ):
            try:
                year_root.rmdir()
                removed.append(str(year_root))
                _fsync_directory(year_root.parent)
            except OSError:
                pass

    return removed


def migrate_legacy_applied_files(
    database_path: Path,
    workspace_path: Path,
) -> dict[str, Any]:
    """
    Move already-applied legacy event files into the shared work area.

    The routine is idempotent and restart-safe for the specific transition:
    if a destination already exists with the expected checksum while the old
    source is gone, SQLite is repaired without moving the file again.
    """

    layout = ensure_workspace_layout(workspace_path)
    workspace_root = Path(layout["workspace_root"])
    target_root = Path(layout["work_root"])
    rows = _load_legacy_applied_files(database_path)

    if not rows:
        return {
            **layout,
            "status": "not_required",
            "file_count": 0,
            "moved_file_count": 0,
            "recovered_file_count": 0,
            "total_size_bytes": 0,
            "removed_legacy_directories": [],
        }

    run_id = "LAYOUT_" + uuid.uuid4().hex.upper()
    now = _now()
    total_size = sum(int(row.get("size_bytes") or 0) for row in rows)

    with database_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO workspace_layout_runs (
                id,
                status,
                source_root,
                target_root,
                file_count,
                moved_file_count,
                total_size_bytes,
                moved_size_bytes,
                details_json,
                created_at,
                updated_at
            )
            VALUES (?, 'running', NULL, ?, ?, 0, ?, 0, ?, ?, ?)
            """,
            (
                run_id,
                str(target_root),
                len(rows),
                total_size,
                json.dumps(
                    {"reason": "shared_workspace_layout_0.8.0"},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                now,
                now,
            ),
        )

    moved: list[tuple[Path, Path]] = []
    moved_ids: set[int] = set()
    migrated_ids: list[int] = []
    recovered_count = 0
    event_roots: set[Path] = set()

    try:
        for row in rows:
            relative = _safe_relative(
                row.get("current_relative_path")
                or row.get("original_relative_path")
            )
            source_root, source = _find_existing_source(
                row,
                workspace_root,
                relative,
            )
            destination = target_root.joinpath(*relative.parts).resolve(
                strict=False
            )

            if not _is_relative_to(destination, target_root):
                raise WorkspaceLayoutError(
                    "Ein Migrationsziel verlässt den Arbeitsbereich: "
                    + str(destination)
                )

            expected_size = int(row.get("size_bytes") or 0)
            expected_checksum = _expected_checksum(row)
            source_exists = source.exists() or source.is_symlink()
            destination_exists = (
                destination.exists() or destination.is_symlink()
            )

            if source_exists and source.is_symlink():
                raise WorkspaceLayoutError(
                    "Eine Legacy-Quelle ist ein symbolischer Link: "
                    + str(source)
                )

            if destination_exists and destination.is_symlink():
                raise WorkspaceLayoutError(
                    "Ein Migrationsziel ist ein symbolischer Link: "
                    + str(destination)
                )

            if source_exists and destination_exists:
                source_stat = os.lstat(source)
                destination_stat = os.lstat(destination)

                if (
                    int(source_stat.st_dev) == int(destination_stat.st_dev)
                    and int(source_stat.st_ino) == int(destination_stat.st_ino)
                ):
                    if _sha256_file(destination) != expected_checksum:
                        raise WorkspaceLayoutError(
                            "Ein bereits verlinktes Ziel hat eine falsche Prüfsumme: "
                            + str(destination)
                        )
                    source.unlink()
                    _fsync_directory(source.parent)
                    recovered_count += 1
                else:
                    raise WorkspaceLayoutError(
                        "Quelle und Ziel existieren gleichzeitig mit verschiedenen "
                        "Inodes. Es wird nichts automatisch überschrieben: "
                        + str(destination)
                    )

            elif not source_exists and destination_exists:
                destination_stat = destination.stat()

                if int(destination_stat.st_size) != expected_size:
                    raise WorkspaceLayoutError(
                        "Ein bereits vorhandenes Migrationsziel hat die falsche Größe: "
                        + str(destination)
                    )

                if _sha256_file(destination) != expected_checksum:
                    raise WorkspaceLayoutError(
                        "Ein bereits vorhandenes Migrationsziel hat die falsche Prüfsumme: "
                        + str(destination)
                    )

                recovered_count += 1

            elif source_exists and not destination_exists:
                source_stat = source.stat()

                if int(source_stat.st_size) != expected_size:
                    raise WorkspaceLayoutError(
                        "Eine Legacy-Datei hat nicht mehr die in SQLite gespeicherte Größe: "
                        + str(source)
                    )

                if _sha256_file(source) != expected_checksum:
                    raise WorkspaceLayoutError(
                        "Eine Legacy-Datei hat nicht mehr die gespeicherte SHA-256-Summe: "
                        + str(source)
                    )

                if int(source_stat.st_dev) != int(target_root.stat().st_dev):
                    raise WorkspaceLayoutError(
                        "Legacy-Quelle und dauerhafter Arbeitsbereich liegen nicht "
                        "auf demselben Dateisystem."
                    )

                destination.parent.mkdir(parents=True, exist_ok=True)
                os.link(source, destination, follow_symlinks=False)
                destination_stat = destination.stat()

                if (
                    int(source_stat.st_dev) != int(destination_stat.st_dev)
                    or int(source_stat.st_ino) != int(destination_stat.st_ino)
                ):
                    destination.unlink(missing_ok=True)
                    raise WorkspaceLayoutError(
                        "Der atomare Migrationslink konnte nicht bestätigt werden: "
                        + str(destination)
                    )

                if _sha256_file(destination) != expected_checksum:
                    destination.unlink(missing_ok=True)
                    raise WorkspaceLayoutError(
                        "Die Prüfsumme des Migrationsziels stimmt nicht: "
                        + str(destination)
                    )

                source.unlink()
                _fsync_directory(source.parent)
                _fsync_directory(destination.parent)
                moved.append((source, destination))
                moved_ids.add(int(row["file_id"]))

            else:
                raise WorkspaceLayoutError(
                    "Sowohl Legacy-Quelle als auch neues Ziel fehlen: "
                    + str(relative)
                )

            migrated_ids.append(int(row["file_id"]))

            parts = relative.parts
            if len(parts) >= 2:
                event_roots.add(source_root / parts[0] / parts[1])

            # Always preserve the standard empty sibling folders next to Alle.
            if destination.parent.name == "Alle":
                container = destination.parent.parent
                for name in ("Alle", "Sortiert", "Export"):
                    (container / name).mkdir(parents=True, exist_ok=True)

        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")

            placeholders = ",".join("?" for _ in migrated_ids)
            connection.execute(
                f"""
                UPDATE files
                SET current_root_kind = 'shared_workspace',
                    updated_at = ?
                WHERE id IN ({placeholders})
                """,
                (now, *migrated_ids),
            )

            details = {
                "reason": "shared_workspace_layout_0.8.0",
                "migrated_file_ids": migrated_ids,
                "moved_file_count": len(moved),
                "recovered_file_count": recovered_count,
                "target_root": str(target_root),
            }

            connection.execute(
                """
                UPDATE workspace_layout_runs
                SET status = 'completed',
                    moved_file_count = ?,
                    moved_size_bytes = ?,
                    details_json = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    len(moved),
                    sum(
                        int(row.get("size_bytes") or 0)
                        for row in rows
                        if int(row["file_id"]) in moved_ids
                    ),
                    json.dumps(details, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    run_id,
                ),
            )

            job_ids = sorted({str(row["job_id"]) for row in rows})
            for job_id in job_ids:
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
                    VALUES (?, 'workspace_layout_migrated', 'job', ?, ?, ?)
                    """,
                    (
                        job_id,
                        job_id,
                        json.dumps(details, ensure_ascii=False, sort_keys=True),
                        now,
                    ),
                )

        cleanup_warning: str | None = None

        try:
            removed = _remove_empty_legacy_event_directories(
                event_roots,
                workspace_root,
            )
        except Exception as cleanup_error:  # non-critical after DB commit
            removed = []
            cleanup_warning = str(cleanup_error)

        return {
            **layout,
            "status": "completed",
            "run_id": run_id,
            "file_count": len(rows),
            "moved_file_count": len(moved),
            "recovered_file_count": recovered_count,
            "total_size_bytes": total_size,
            "removed_legacy_directories": removed,
            "cleanup_warning": cleanup_warning,
        }

    except Exception as error:
        rollback_errors = _rollback_moved(moved)
        status = "failed" if rollback_errors else "rolled_back"
        message = str(error)

        if rollback_errors:
            message += " | Rollback: " + " | ".join(rollback_errors)

        try:
            with database_connection(database_path) as connection:
                connection.execute(
                    """
                    UPDATE workspace_layout_runs
                    SET status = ?,
                        moved_file_count = ?,
                        error_message = ?,
                        updated_at = ?,
                        completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        status,
                        len(moved),
                        message,
                        _now(),
                        _now(),
                        run_id,
                    ),
                )
        finally:
            raise WorkspaceLayoutError(message) from error
