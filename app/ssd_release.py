from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat
import uuid

from app.archive_transfer import ArchiveVerificationError, verify_event_archive
from app.archive_locations import ArchiveLocationError, archive_path_without_symlinks
from app.database import database_connection
from app.event_inventory import EventInventoryError, match_inventory_by_content, scan_event_inventory
from app.workspace_layout import shared_work_root


class SsdReleaseError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def _safe_relative(value: Any) -> PurePosixPath:
    raw = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)

    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SsdReleaseError("Unsicherer relativer Dateipfad: " + raw)

    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY

    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _event_and_files(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with database_connection(database_path) as connection:
        event = connection.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
              AND job_id = ?
              AND parent_event_id IS NULL
            """,
            (event_id, job_id),
        ).fetchone()

        if event is None:
            raise SsdReleaseError("Ereignis wurde nicht gefunden.")

        rows = connection.execute(
            """
            WITH RECURSIVE event_tree AS (
                SELECT id
                FROM events
                WHERE id = ?

                UNION ALL

                SELECT child.id
                FROM events AS child
                JOIN event_tree AS parent
                    ON child.parent_event_id = parent.id
            ),
            assigned_families AS (
                SELECT DISTINCT family_id
                FROM event_assignments
                WHERE event_id IN (SELECT id FROM event_tree)
                  AND family_id IS NOT NULL
            ),
            assigned_files AS (
                SELECT DISTINCT file_id
                FROM event_assignments
                WHERE event_id IN (SELECT id FROM event_tree)
                  AND file_id IS NOT NULL
            )
            SELECT DISTINCT
                files.id AS file_id,
                files.current_relative_path,
                files.original_relative_path,
                files.current_root_kind,
                files.size_bytes,
                files.sha256_current,
                files.sha256_original
            FROM files
            WHERE files.job_id = ?
              AND (
                    files.family_id IN (SELECT family_id FROM assigned_families)
                    OR files.id IN (SELECT file_id FROM assigned_files)
                  )
            ORDER BY files.current_relative_path, files.id
            """,
            (event_id, job_id),
        ).fetchall()

    return dict(event), [dict(row) for row in rows]


def _latest_completed_release(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM event_ssd_releases
            WHERE job_id = ?
              AND event_id = ?
              AND status = 'completed'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (job_id, event_id),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    raw = result.pop("details_json", None)
    result["details"] = json.loads(raw) if raw else None
    result["released"] = True
    result["message"] = "SSD-Bestand wurde bereits freigegeben."
    return result


def _latest_open_release(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM event_ssd_releases
            WHERE job_id = ?
              AND event_id = ?
              AND status <> 'completed'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (job_id, event_id),
        ).fetchone()

    return dict(row) if row is not None else None


def _expected_hash(row: dict[str, Any]) -> str:
    value = str(
        row.get("sha256_current")
        or row.get("sha256_original")
        or ""
    ).strip()

    if not value:
        raise SsdReleaseError(
            "Gespeicherte SHA-256-Summe fehlt: "
            + str(row.get("current_relative_path") or row.get("file_id"))
        )

    return value


def _event_prefix(event: dict[str, Any]) -> PurePosixPath:
    start = str(event.get("start_datetime") or "")
    year = start[:4]
    folder = str(event.get("folder_name") or "").strip()

    if len(year) != 4 or not year.isdigit() or not folder:
        raise SsdReleaseError(
            "Ereignis besitzt keinen eindeutigen Jahres-/Ordnerpfad."
        )

    return _safe_relative(PurePosixPath(year, folder).as_posix())


def _validate_event_tree(
    work_root: Path,
    event: dict[str, Any],
    files: list[dict[str, Any]],
    allow_missing_sources: bool,
) -> tuple[Path, list[dict[str, Any]]]:
    prefix = _event_prefix(event)
    event_root = work_root.joinpath(*prefix.parts).resolve(strict=False)

    if not _is_relative_to(event_root, work_root):
        raise SsdReleaseError("Ereignisordner verlässt den Arbeitsbereich.")

    prepared: list[dict[str, Any]] = []
    tracked: set[str] = set()

    for row in files:
        if str(row.get("current_root_kind")) != "shared_workspace":
            raise SsdReleaseError(
                "Mindestens eine Datei liegt nicht mehr im SSD-Arbeitsbereich."
            )

        relative = _safe_relative(
            row.get("current_relative_path")
            or row.get("original_relative_path")
        )

        if tuple(relative.parts[:2]) != tuple(prefix.parts):
            raise SsdReleaseError(
                "Eine zugeordnete Datei liegt außerhalb des Ereignisordners: "
                + relative.as_posix()
            )

        source = work_root.joinpath(*relative.parts).resolve(strict=False)

        if not _is_relative_to(source, work_root):
            raise SsdReleaseError("Quelldatei verlässt den Arbeitsbereich.")

        tracked.add(relative.as_posix())
        prepared.append(
            {
                **row,
                "relative": relative,
                "source": source,
                "expected_sha256": _expected_hash(row),
            }
        )

    if not prepared:
        raise SsdReleaseError("Dem Ereignis sind keine Dateien zugeordnet.")

    existing: set[str] = set()
    unexpected: list[str] = []

    def allowed_companion_file(entry: Path) -> bool:
        # event.json is the portable event description generated by the app.
        # Finder metadata and AppleDouble sidecars must never block release.
        name = entry.name
        return name == "event.json" or name == ".DS_Store" or name.startswith("._")

    if event_root.exists():
        for entry in event_root.rglob("*"):
            if entry.is_symlink():
                unexpected.append(str(entry.relative_to(work_root)))
                continue
            if entry.is_file():
                relative = entry.relative_to(work_root).as_posix()
                existing.add(relative)
                if relative not in tracked and not allowed_companion_file(entry):
                    unexpected.append(relative)
            elif not entry.is_dir():
                unexpected.append(str(entry.relative_to(work_root)))

    if unexpected:
        sample = ", ".join(sorted(unexpected)[:5])
        raise SsdReleaseError(
            "Im Ereignisordner liegen nicht erfasste Dateien oder Einträge. "
            "SSD-Freigabe wurde gesperrt: " + sample
        )

    missing = sorted(tracked - existing)
    if missing and not allow_missing_sources:
        raise SsdReleaseError(
            "Im SSD-Ereignisordner fehlen Dateien. Freigabe wurde gesperrt: "
            + ", ".join(missing[:5])
        )

    return event_root, prepared


def _create_release_run(
    database_path: Path,
    job_id: str,
    event_id: str,
    verification_id: str,
    work_root: Path,
    archive_root: Path,
    files: list[dict[str, Any]],
    assets: list[dict[str, Any]],
) -> str:
    release_id = "RELEASE_" + uuid.uuid4().hex.upper()
    now = _now()
    all_rows = list(files) + list(assets)
    total_size = sum(int(row["size_bytes"]) for row in all_rows)

    with database_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO event_ssd_releases (
                id, job_id, event_id, verification_id, status,
                workspace_root, archive_root, file_count,
                total_size_bytes, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'verifying', ?, ?, ?, ?, ?, ?)
            """,
            (
                release_id,
                job_id,
                event_id,
                verification_id,
                str(work_root),
                str(archive_root),
                len(all_rows),
                total_size,
                now,
                now,
            ),
        )

        connection.executemany(
            """
            INSERT INTO event_ssd_release_files (
                release_id, file_id, source_relative_path,
                archive_relative_path, expected_size_bytes,
                expected_sha256, status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'planned')
            """,
            [
                (
                    release_id,
                    int(row["file_id"]),
                    row["relative"].as_posix(),
                    row["archive_relative"].as_posix(),
                    int(row["size_bytes"]),
                    str(row["expected_sha256"]),
                )
                for row in files
            ],
        )

        connection.executemany(
            """
            INSERT INTO event_ssd_release_assets (
                release_id,asset_kind,source_relative_path,archive_relative_path,
                expected_size_bytes,expected_sha256,status
            ) VALUES (?,?,?,?,?,?,'planned')
            """,
            [
                (
                    release_id,
                    str(row.get("asset_kind") or "other"),
                    row["relative"].as_posix(),
                    row["archive_relative"].as_posix(),
                    int(row["size_bytes"]),
                    str(row["expected_sha256"]),
                )
                for row in assets
            ],
        )

    return release_id


def _mark_release_failed(
    database_path: Path,
    release_id: str,
    message: str,
) -> None:
    with database_connection(database_path) as connection:
        connection.execute(
            """
            UPDATE event_ssd_releases
            SET status = 'failed',
                error_message = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (message, _now(), release_id),
        )


def _verify_regular_file(
    path: Path,
    expected_size: int,
    expected_sha256: str,
    label: str,
) -> tuple[os.stat_result, str]:
    before = os.lstat(path)

    if not stat.S_ISREG(before.st_mode):
        raise SsdReleaseError(f"{label} ist keine reguläre Datei: {path}")

    if int(before.st_size) != expected_size:
        raise SsdReleaseError(f"{label} hat eine abweichende Größe: {path}")

    actual_hash = _sha256_file(path)
    after = os.lstat(path)

    identity_before = (
        int(before.st_dev),
        int(before.st_ino),
        int(before.st_mtime_ns),
        int(before.st_size),
    )
    identity_after = (
        int(after.st_dev),
        int(after.st_ino),
        int(after.st_mtime_ns),
        int(after.st_size),
    )

    if identity_before != identity_after:
        raise SsdReleaseError(f"{label} änderte sich während der Prüfung: {path}")

    if actual_hash != expected_sha256:
        raise SsdReleaseError(f"{label} hat eine abweichende SHA-256-Summe: {path}")

    return after, actual_hash


def _remove_empty_event_tree(event_root: Path, work_root: Path) -> list[str]:
    removed: list[str] = []

    if not event_root.exists():
        return removed

    for current, directories, _files in os.walk(event_root, topdown=False):
        current_path = Path(current)
        for name in directories:
            child = current_path / name
            try:
                child.rmdir()
                _fsync_directory(child.parent)
                removed.append(str(child.relative_to(work_root)))
            except OSError:
                pass

    try:
        event_root.rmdir()
        _fsync_directory(event_root.parent)
        removed.append(str(event_root.relative_to(work_root)))
    except OSError:
        pass

    return removed


def _finalize_release(
    database_path: Path,
    release_id: str,
    job_id: str,
    event_id: str,
    removed_directories: list[str],
) -> dict[str, Any]:
    now = _now()

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        release = connection.execute(
            """
            SELECT *
            FROM event_ssd_releases
            WHERE id = ? AND job_id = ? AND event_id = ?
            """,
            (release_id, job_id, event_id),
        ).fetchone()

        if release is None:
            raise SsdReleaseError("SSD-Freigabelauf wurde nicht gefunden.")

        operations = connection.execute(
            """SELECT * FROM event_ssd_release_files
               WHERE release_id=? ORDER BY id""",
            (release_id,),
        ).fetchall()
        asset_operations = connection.execute(
            """SELECT * FROM event_ssd_release_assets
               WHERE release_id=? ORDER BY id""",
            (release_id,),
        ).fetchall()
        all_operations = list(operations) + list(asset_operations)

        if not all_operations or any(
            str(row["status"]) not in {"deleted", "already_released"}
            for row in all_operations
        ):
            raise SsdReleaseError(
                "Nicht alle SSD-Dateien wurden sicher freigegeben."
            )

        file_ids = [int(row["file_id"]) for row in operations]
        if file_ids:
            placeholders = ",".join("?" for _ in file_ids)
            connection.execute(
                f"""
                UPDATE files
                SET current_root_kind = 'camera_archive',
                    updated_at = ?
                WHERE job_id = ?
                  AND id IN ({placeholders})
                """,
                (now, job_id, *file_ids),
            )

        connection.execute(
            """
            UPDATE events
            SET status = 'archived',
                archived_at = COALESCE(archived_at, ?),
                updated_at = ?
            WHERE job_id = ?
              AND (id = ? OR parent_event_id = ?)
            """,
            (now, now, job_id, event_id, event_id),
        )

        connection.execute(
            "DELETE FROM event_inventory_files WHERE event_id=? AND root_kind='shared_workspace'",
            (event_id,),
        )

        details = {
            "removed_directories": removed_directories,
            "file_count": len(all_operations),
            "camera_file_count": len(operations),
            "asset_file_count": len(asset_operations),
            "deleted_file_count": sum(
                1 for row in all_operations if str(row["status"]) == "deleted"
            ),
            "already_released_file_count": sum(
                1
                for row in all_operations
                if str(row["status"]) == "already_released"
            ),
        }

        connection.execute(
            """
            UPDATE event_ssd_releases
            SET status = 'completed',
                removed_directory_count = ?,
                details_json = ?,
                error_message = NULL,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                len(removed_directories),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                now,
                now,
                release_id,
            ),
        )

        connection.execute(
            """
            UPDATE jobs
            SET state = 'completed',
                stage = 'event_ssd_released',
                progress_message = 'SSD-Bestand vollständig freigegeben und geprüft.',
                error_message = NULL,
                updated_at = ?,
                finished_at = COALESCE(finished_at, ?)
            WHERE id = ?
            """,
            (now, now, job_id),
        )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id, action, entity_type, entity_id,
                details_json, created_at
            )
            VALUES (?, 'event_ssd_released', 'event', ?, ?, ?)
            """,
            (
                job_id,
                event_id,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )

        final = connection.execute(
            "SELECT * FROM event_ssd_releases WHERE id=?",
            (release_id,),
        ).fetchone()

    result = dict(final)
    raw = result.pop("details_json", None)
    result["details"] = json.loads(raw) if raw else None
    result["released"] = True
    result["message"] = (
        "Kamerabibliothek erneut vollständig geprüft und "
        "SSD-Bestand einschließlich XMP/Export sicher freigegeben."
    )
    return result


def release_event_ssd(
    database_path: Path,
    workspace_path: Path,
    archive_root: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    completed = _latest_completed_release(database_path, job_id, event_id)
    if completed is not None:
        return completed

    event, files = _event_and_files(database_path, job_id, event_id)

    from app.database import database_connection
    with database_connection(database_path) as connection:
        pending = connection.execute(
            """SELECT COUNT(*) AS n FROM event_reapply_removed_families
               WHERE job_id=? AND target_event_id IS NULL""",
            (job_id,),
        ).fetchone()
        active_mutation = connection.execute(
            """SELECT id FROM event_mutations
               WHERE job_id=? AND status IN ('pending_reassignment','pending_apply','manual_archive')
               LIMIT 1""",
            (job_id,),
        ).fetchone()
    if int(pending["n"] or 0) > 0 or active_mutation is not None:
        raise SsdReleaseError(
            "SSD-Freigabe gesperrt: In dieser Sicherung ist noch eine Ereignisänderung bzw. Neu-Zuordnung offen. "
            "Bitte zuerst alle freien Familien zuordnen und die Nachsortierung abschließen."
        )

    if int(event.get("resort_required") or 0):
        raise SsdReleaseError(
            "SSD-Freigabe gesperrt: Für dieses Ereignis ist noch eine Nachsortierung offen."
        )

    if str(event.get("status")) == "archived":
        raise SsdReleaseError(
            "Ereignis ist bereits archiviert, aber ein abgeschlossener "
            "SSD-Freigabelauf fehlt."
        )

    if str(event.get("status")) != "applied":
        raise SsdReleaseError(
            "Nur ein angewendetes Ereignis kann von der SSD freigegeben werden."
        )

    archive_root = archive_root.expanduser().resolve(strict=False)
    if not archive_root.exists() or not archive_root.is_dir():
        raise SsdReleaseError("Kamerabibliothek ist nicht lesbar eingebunden.")

    open_release = _latest_open_release(database_path, job_id, event_id)
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    event_root, prepared = _validate_event_tree(
        work_root,
        event,
        files,
        allow_missing_sources=open_release is not None,
    )

    try:
        verification = verify_event_archive(
            database_path,
            archive_root,
            job_id,
            event_id,
        )
    except ArchiveVerificationError as exc:
        raise SsdReleaseError(str(exc)) from exc

    if not verification.get("verified"):
        raise SsdReleaseError(
            "Kamerabibliothek ist bei der erneuten Prüfung nicht vollständig identisch."
        )

    release_id = (
        str(open_release["id"])
        if open_release is not None
        else _create_release_run(
            database_path,
            job_id,
            event_id,
            str(verification["id"]),
            work_root,
            archive_root,
            prepared,
        )
    )

    try:
        with database_connection(database_path) as connection:
            connection.execute(
                """
                UPDATE event_ssd_releases
                SET status = 'verifying',
                    verification_id = ?,
                    error_message = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (str(verification["id"]), _now(), release_id),
            )

        for row in prepared:
            file_id = int(row["file_id"])
            relative = row["relative"]
            source = row["source"]
            try:
                archive = archive_path_without_symlinks(
                    archive_root,
                    relative.as_posix(),
                )
            except ArchiveLocationError as exc:
                raise SsdReleaseError(str(exc)) from exc
            expected_size = int(row["size_bytes"])
            expected_hash = str(row["expected_sha256"])

            _archive_stat, archive_hash = _verify_regular_file(
                archive,
                expected_size,
                expected_hash,
                "Archivdatei",
            )

            source_exists = source.exists() or source.is_symlink()
            source_hash: str | None = None
            source_stat: os.stat_result | None = None

            if source_exists:
                source_stat, source_hash = _verify_regular_file(
                    source,
                    expected_size,
                    expected_hash,
                    "SSD-Datei",
                )
            elif open_release is None:
                raise SsdReleaseError("SSD-Datei fehlt: " + str(source))

            with database_connection(database_path) as connection:
                connection.execute(
                    """
                    UPDATE event_ssd_release_files
                    SET status = 'archive_verified',
                        actual_source_size_bytes = ?,
                        actual_source_sha256 = ?,
                        actual_archive_size_bytes = ?,
                        actual_archive_sha256 = ?,
                        verified_at = ?,
                        error_message = NULL
                    WHERE release_id = ? AND file_id = ?
                    """,
                    (
                        expected_size if source_exists else None,
                        source_hash,
                        expected_size,
                        archive_hash,
                        _now(),
                        release_id,
                        file_id,
                    ),
                )

        with database_connection(database_path) as connection:
            verified_source_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_ssd_release_files
                WHERE release_id = ?
                  AND actual_source_sha256 IS NOT NULL
                """,
                (release_id,),
            ).fetchone()[0]
            verified_archive_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM event_ssd_release_files
                WHERE release_id = ?
                  AND status = 'archive_verified'
                """,
                (release_id,),
            ).fetchone()[0]
            connection.execute(
                """
                UPDATE event_ssd_releases
                SET status = 'deleting',
                    verified_source_count = ?,
                    verified_archive_count = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(verified_source_count),
                    int(verified_archive_count),
                    _now(),
                    release_id,
                ),
            )

        deleted_count = 0
        deleted_bytes = 0

        for row in prepared:
            file_id = int(row["file_id"])
            source = row["source"]
            expected_size = int(row["size_bytes"])
            expected_hash = str(row["expected_sha256"])

            if source.exists() or source.is_symlink():
                source_stat, _source_hash = _verify_regular_file(
                    source,
                    expected_size,
                    expected_hash,
                    "SSD-Datei vor dem Löschen",
                )
                current = os.lstat(source)
                if (
                    int(current.st_dev),
                    int(current.st_ino),
                    int(current.st_mtime_ns),
                    int(current.st_size),
                ) != (
                    int(source_stat.st_dev),
                    int(source_stat.st_ino),
                    int(source_stat.st_mtime_ns),
                    int(source_stat.st_size),
                ):
                    raise SsdReleaseError(
                        "SSD-Datei änderte sich unmittelbar vor dem Löschen: "
                        + str(source)
                    )

                source.unlink()
                _fsync_directory(source.parent)
                status_value = "deleted"
                deleted_count += 1
                deleted_bytes += expected_size
            else:
                status_value = "already_released"

            with database_connection(database_path) as connection:
                connection.execute(
                    """
                    UPDATE event_ssd_release_files
                    SET status = ?,
                        deleted_at = ?,
                        error_message = NULL
                    WHERE release_id = ? AND file_id = ?
                    """,
                    (status_value, _now(), release_id, file_id),
                )
                connection.execute(
                    """
                    UPDATE event_ssd_releases
                    SET deleted_file_count = ?,
                        deleted_size_bytes = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (deleted_count, deleted_bytes, _now(), release_id),
                )

        with database_connection(database_path) as connection:
            connection.execute(
                """
                UPDATE event_ssd_releases
                SET status = 'finalizing', updated_at = ?
                WHERE id = ?
                """,
                (_now(), release_id),
            )

        removed = _remove_empty_event_tree(event_root, work_root)
        return _finalize_release(
            database_path,
            release_id,
            job_id,
            event_id,
            removed,
        )

    except Exception as error:
        _mark_release_failed(database_path, release_id, str(error))
        if isinstance(error, SsdReleaseError):
            raise
        raise SsdReleaseError(str(error)) from error
