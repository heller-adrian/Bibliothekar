from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat
import uuid

from app.ssd_archive_guard import ArchiveGuard
from app.archive_transfer import ArchiveVerificationError, verify_event_archive
from app.archive_locations import ArchiveLocationError, archive_path_without_symlinks
from app.database import database_connection
from app.event_access import event_file_rows
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


def _is_release_companion_file(path: Path) -> bool:
    """Metadata generated/accepted by the app that must not keep SSD trees alive."""
    name = path.name
    return name == "event.json" or name == ".DS_Store" or name.startswith("._")


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
            """SELECT * FROM events
               WHERE id=? AND job_id=? AND parent_event_id IS NULL""",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            raise SsdReleaseError("Ereignis wurde nicht gefunden.")
        rows = event_file_rows(connection, event_id)
    return dict(event), rows


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
    result["message"] = "Arbeitsbereich-Bestand wurde bereits freigegeben."
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
                "Mindestens eine Datei liegt nicht mehr im Arbeitsbereich."
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

    if event_root.exists():
        for entry in event_root.rglob("*"):
            if entry.is_symlink():
                unexpected.append(str(entry.relative_to(work_root)))
                continue
            if entry.is_file():
                relative = entry.relative_to(work_root).as_posix()
                existing.add(relative)
                if relative not in tracked and not _is_release_companion_file(entry):
                    unexpected.append(relative)
            elif not entry.is_dir():
                unexpected.append(str(entry.relative_to(work_root)))

    if unexpected:
        sample = ", ".join(sorted(unexpected)[:5])
        raise SsdReleaseError(
            "Im Ereignisordner liegen nicht erfasste Dateien oder Einträge. "
            "Arbeitsbereich-Freigabe wurde gesperrt: " + sample
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
    *,
    archive_guard: ArchiveGuard | None = None,
    archive_relative: PurePosixPath | None = None,
) -> tuple[os.stat_result, str]:
    if archive_guard is not None:
        checked = archive_guard.verify(archive_relative, expected_size, expected_sha256)
        return checked, expected_sha256
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

    # Camera files and tracked assets have already passed their final SHA-256
    # check and were deleted before this helper runs. Portable event metadata
    # and harmless Finder sidecars are intentionally not release operations,
    # but they must not keep an otherwise released SSD event directory alive.
    remaining_unexpected: list[str] = []
    for entry in event_root.rglob("*"):
        if entry.is_symlink():
            remaining_unexpected.append(str(entry.relative_to(work_root)))
            continue
        if not entry.is_file():
            continue
        if not _is_release_companion_file(entry):
            remaining_unexpected.append(str(entry.relative_to(work_root)))
            continue
        entry.unlink()
        _fsync_directory(entry.parent)
        removed.append(str(entry.relative_to(work_root)))

    if remaining_unexpected:
        raise SsdReleaseError(
            "Der SSD-Ereignisordner enthält nach der Freigabe noch "
            "unerwartete Dateien oder Links: "
            + ", ".join(sorted(remaining_unexpected)[:5])
        )

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
    except OSError as exc:
        raise SsdReleaseError(
            "Der vollständig freigegebene SSD-Ereignisordner konnte nicht "
            "entfernt werden: " + str(event_root)
        ) from exc

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
            raise SsdReleaseError("Arbeitsbereich-Freigabelauf wurde nicht gefunden.")

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
                "Nicht alle Arbeitsbereich-Dateien wurden sicher freigegeben."
            )

        file_ids = [int(row["file_id"]) for row in operations]
        for operation in operations:
            connection.execute(
                """UPDATE files
                   SET current_relative_path=?,
                       current_root_kind='camera_archive',
                       updated_at=?
                   WHERE id=?""",
                (
                    str(operation["archive_relative_path"]),
                    now,
                    int(operation["file_id"]),
                ),
            )

        connection.execute(
            """
            UPDATE events
            SET status = 'archived',
                archived_at = COALESCE(archived_at, ?),
                updated_at = ?
            WHERE (id = ? OR parent_event_id = ?)
            """,
            (now, now, event_id, event_id),
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
                progress_message = 'Arbeitsbereich-Bestand vollständig freigegeben und geprüft.',
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
        "Arbeitsbereich-Bestand einschließlich XMP/Export sicher freigegeben."
    )
    return result


def finalize_manually_moved_event_if_verified(
    database_path: Path,
    workspace_path: Path,
    archive_root: Path,
    job_id: str,
    event_id: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    """Finalize an applied event that was physically moved to the archive.

    This is intentionally narrower than the normal SSD release: it runs only
    when the archive verification is fully green and the event has no physical
    files left in its workspace tree. The completed release journal therefore
    records an already-released source instead of deleting anything.
    """
    if not bool(verification.get("verified")):
        return {
            **verification,
            "manual_archive_finalized": False,
        }

    event, files = _event_and_files(
        database_path,
        job_id,
        event_id,
    )
    if str(event.get("status") or "") != "applied":
        return {
            **verification,
            "manual_archive_finalized": False,
        }

    work_root = shared_work_root(
        workspace_path
    ).resolve(strict=False)
    archive_root = archive_root.expanduser().resolve(
        strict=False
    )

    try:
        workspace_inventory = scan_event_inventory(
            database_path,
            work_root,
            job_id,
            event_id,
            root_kind="shared_workspace",
            persist=True,
            update_known_file_locations=False,
            fast_refresh=False,
        )
    except EventInventoryError as exc:
        if "Ereignisordner wurde nicht gefunden" not in str(exc):
            raise SsdReleaseError(str(exc)) from exc
        workspace_inventory = {"files": []}

    try:
        archive_inventory = scan_event_inventory(
            database_path,
            archive_root,
            job_id,
            event_id,
            root_kind="camera_archive",
            persist=True,
            update_known_file_locations=False,
            fast_refresh=False,
        )
    except EventInventoryError as exc:
        raise SsdReleaseError(str(exc)) from exc

    # Sobald noch irgendeine reale Ereignisdatei im Arbeitsbereich liegt,
    # bleibt der normale zweistufige Workflow "prüfen -> Arbeitsbereich freigeben" aktiv.
    if list(workspace_inventory.get("files") or []):
        return {
            **verification,
            "manual_archive_finalized": False,
        }

    archive_by_file_id = {
        int(item["known_file_id"]): item
        for item in (archive_inventory.get("files") or [])
        if item.get("known_file_id") is not None
    }
    prepared: list[dict[str, Any]] = []
    for row in files:
        file_id = int(row["file_id"])
        observed = archive_by_file_id.get(file_id)
        if observed is None:
            raise SsdReleaseError(
                "Manuelle Archivübernahme kann nicht abgeschlossen werden: "
                f"Datei {row.get('original_filename') or file_id} fehlt im Archiv."
            )
        expected_size = int(row.get("size_bytes") or 0)
        expected_sha = _expected_hash(row)
        if (
            int(observed.get("size_bytes") or -1) != expected_size
            or str(observed.get("sha256") or "") != expected_sha
        ):
            raise SsdReleaseError(
                "Manuelle Archivübernahme kann nicht abgeschlossen werden: "
                f"Datei {row.get('original_filename') or file_id} weicht im Archiv ab."
            )
        prepared.append({
            "file_id": file_id,
            "relative": _safe_relative(
                row.get("current_relative_path")
                or row.get("original_relative_path")
            ),
            "archive_relative": _safe_relative(
                observed.get("relative_path")
            ),
            "source": work_root.joinpath(
                *_safe_relative(
                    row.get("current_relative_path")
                    or row.get("original_relative_path")
                ).parts
            ),
            "size_bytes": expected_size,
            "expected_sha256": expected_sha,
            "asset_kind": "camera_original",
        })

    if not prepared:
        raise SsdReleaseError(
            "Manuelle Archivübernahme enthält keine prüfbaren Kameraoriginale."
        )

    completed = _latest_completed_release(
        database_path,
        job_id,
        event_id,
    )
    if completed is not None:
        return {
            **verification,
            **completed,
            "manual_archive_finalized": True,
        }

    release_id = _create_release_run(
        database_path,
        job_id,
        event_id,
        str(verification["id"]),
        work_root,
        archive_root,
        prepared,
        [],
    )
    now = _now()
    with database_connection(database_path) as connection:
        for row in prepared:
            connection.execute(
                """UPDATE event_ssd_release_files
                   SET status='already_released',
                       actual_source_size_bytes=NULL,
                       actual_source_sha256=NULL,
                       actual_archive_size_bytes=?,
                       actual_archive_sha256=?,
                       verified_at=?,
                       deleted_at=?,
                       error_message=NULL
                   WHERE release_id=? AND file_id=?""",
                (
                    int(row["size_bytes"]),
                    str(row["expected_sha256"]),
                    now,
                    now,
                    release_id,
                    int(row["file_id"]),
                ),
            )
        connection.execute(
            """UPDATE event_ssd_releases
               SET status='finalizing',
                   verified_source_count=0,
                   verified_archive_count=?,
                   deleted_file_count=0,
                   deleted_size_bytes=0,
                   details_json=?,
                   updated_at=?
               WHERE id=?""",
            (
                len(prepared),
                json.dumps(
                    {
                        "manual_archive_move": True,
                        "source_already_absent": True,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                now,
                release_id,
            ),
        )

    final = _finalize_release(
        database_path,
        release_id,
        job_id,
        event_id,
        [],
    )
    with database_connection(database_path) as connection:
        from app.external_changes import resolve_notice_key
        resolve_notice_key(
            connection,
            f"archive-transfer:{event_id}",
            now=_now(),
        )

    return {
        **verification,
        **final,
        "manual_archive_finalized": True,
        "message": (
            "Archiv vollständig per Größe und SHA-256 geprüft. "
            "Der bereits manuell verschobene Ereignisbestand wurde als "
            "archiviert übernommen."
        ),
    }


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

    event, _files = _event_and_files(database_path, job_id, event_id)

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
            "Arbeitsbereich-Freigabe gesperrt: In dieser Sicherung ist noch eine Ereignisänderung bzw. Neu-Zuordnung offen. "
            "Bitte zuerst alle freien Familien zuordnen und die Nachsortierung abschließen."
        )

    if int(event.get("resort_required") or 0):
        raise SsdReleaseError(
            "Arbeitsbereich-Freigabe gesperrt: Für dieses Ereignis ist noch eine Nachsortierung offen."
        )
    if str(event.get("status")) == "archived":
        raise SsdReleaseError(
            "Ereignis ist bereits archiviert, aber ein abgeschlossener Arbeitsbereich-Freigabelauf fehlt."
        )
    if str(event.get("status")) != "applied":
        raise SsdReleaseError(
            "Nur ein angewendetes Ereignis kann von der Arbeitsbereich freigegeben werden."
        )

    archive_root = archive_root.expanduser().resolve(strict=False)
    if not archive_root.exists() or not archive_root.is_dir():
        raise SsdReleaseError("Kamerabibliothek ist nicht lesbar eingebunden.")

    work_root = shared_work_root(workspace_path).resolve(strict=False)
    open_release = _latest_open_release(database_path, job_id, event_id)

    verification_options = {"workspace_path": workspace_path}
    if open_release is not None:
        verification_options["resume_release_id"] = str(open_release["id"])
    try:
        verification = verify_event_archive(
            database_path,
            archive_root,
            job_id,
            event_id,
            **verification_options,
        )
    except ArchiveVerificationError as exc:
        raise SsdReleaseError(str(exc)) from exc

    if not verification.get("verified"):
        raise SsdReleaseError(
            "Kamerabibliothek ist bei der erneuten Prüfung der Kameraoriginale nicht vollständig identisch."
        )

    prepared: list[dict[str, Any]] = []
    asset_prepared: list[dict[str, Any]] = []

    if open_release is None:
        try:
            workspace_inventory = scan_event_inventory(
                database_path,
                work_root,
                job_id,
                event_id,
                root_kind="shared_workspace",
                persist=True,
                update_known_file_locations=True,
            )
            archive_inventory = scan_event_inventory(
                database_path,
                archive_root,
                job_id,
                event_id,
                root_kind="camera_archive",
                persist=True,
                update_known_file_locations=False,
            )
        except EventInventoryError as exc:
            raise SsdReleaseError(str(exc)) from exc

        missing_known = list(
            workspace_inventory.get("summary", {}).get("missing_known_file_ids") or []
        )
        if missing_known:
            raise SsdReleaseError(
                "Im SSD-Ereignis fehlen importierte Kameraoriginale. "
                "Freigabe wurde gesperrt."
            )

        source_inventory = list(workspace_inventory["files"])
        if not source_inventory:
            raise SsdReleaseError("Der SSD-Ereignisordner enthält keine zu sichernden Dateien.")

        try:
            matches = match_inventory_by_content(
                source_inventory,
                list(archive_inventory["files"]),
            )
        except EventInventoryError as exc:
            raise SsdReleaseError(
                "Nicht der gesamte aktuelle SSD-Ereignisbestand wurde im Archiv gefunden: "
                + str(exc)
            ) from exc

        archive_by_source = {
            str(match["source"]["relative_path"]): match["target"]
            for match in matches
        }
        event_root = Path(str(workspace_inventory["event_root"]))

        for item in source_inventory:
            relative = _safe_relative(item["relative_path"])
            target = archive_by_source[str(item["relative_path"])]
            row = {
                "relative": relative,
                "archive_relative": _safe_relative(target["relative_path"]),
                "source": work_root.joinpath(*relative.parts),
                "size_bytes": int(item["size_bytes"]),
                "expected_sha256": str(item["sha256"]),
                "asset_kind": str(item.get("asset_kind") or "other"),
            }
            if item.get("known_file_id") is not None:
                row["file_id"] = int(item["known_file_id"])
                prepared.append(row)
            else:
                asset_prepared.append(row)

        release_id = _create_release_run(
            database_path,
            job_id,
            event_id,
            str(verification["id"]),
            work_root,
            archive_root,
            prepared,
            asset_prepared,
        )
    else:
        release_id = str(open_release["id"])
        event_root = work_root.joinpath(*_event_prefix(event).parts)
        with database_connection(database_path) as connection:
            camera_rows = connection.execute(
                """SELECT * FROM event_ssd_release_files
                   WHERE release_id=? ORDER BY id""",
                (release_id,),
            ).fetchall()
            asset_rows = connection.execute(
                """SELECT * FROM event_ssd_release_assets
                   WHERE release_id=? ORDER BY id""",
                (release_id,),
            ).fetchall()

        for stored in camera_rows:
            relative = _safe_relative(stored["source_relative_path"])
            prepared.append({
                "file_id": int(stored["file_id"]),
                "relative": relative,
                "archive_relative": _safe_relative(stored["archive_relative_path"]),
                "source": work_root.joinpath(*relative.parts),
                "size_bytes": int(stored["expected_size_bytes"]),
                "expected_sha256": str(stored["expected_sha256"]),
                "asset_kind": "camera_original",
            })
        for stored in asset_rows:
            relative = _safe_relative(stored["source_relative_path"])
            asset_prepared.append({
                "relative": relative,
                "archive_relative": _safe_relative(stored["archive_relative_path"]),
                "source": work_root.joinpath(*relative.parts),
                "size_bytes": int(stored["expected_size_bytes"]),
                "expected_sha256": str(stored["expected_sha256"]),
                "asset_kind": str(stored["asset_kind"]),
            })

    archive_guard = None
    try:
        archive_guard = ArchiveGuard(archive_root, [row["archive_relative"] for row in prepared + asset_prepared])
        with database_connection(database_path) as connection:
            connection.execute(
                """
                UPDATE event_ssd_releases
                SET status='verifying',verification_id=?,error_message=NULL,updated_at=?
                WHERE id=?
                """,
                (str(verification["id"]), _now(), release_id),
            )

        for row in prepared:
            file_id = int(row["file_id"])
            source = row["source"]
            archive_rel = row["archive_relative"]
            try:
                archive = archive_path_without_symlinks(
                    archive_root,
                    archive_rel.as_posix(),
                )
            except ArchiveLocationError as exc:
                raise SsdReleaseError(str(exc)) from exc

            expected_size = int(row["size_bytes"])
            expected_hash = str(row["expected_sha256"])
            _archive_stat, archive_hash = _verify_regular_file(
                archive, expected_size, expected_hash, "Archivdatei",
                archive_guard=archive_guard, archive_relative=archive_rel,
            )

            source_exists = source.exists() or source.is_symlink()
            source_hash = None
            if source_exists:
                _source_stat, source_hash = _verify_regular_file(
                    source, expected_size, expected_hash, "SSD-Datei"
                )
            elif open_release is None:
                raise SsdReleaseError("SSD-Datei fehlt: " + str(source))
            row["source_present_for_run"] = source_exists

            with database_connection(database_path) as connection:
                connection.execute(
                    """
                    UPDATE event_ssd_release_files
                    SET status='archive_verified',
                        actual_source_size_bytes=?,actual_source_sha256=?,
                        actual_archive_size_bytes=?,actual_archive_sha256=?,
                        verified_at=?,error_message=NULL
                    WHERE release_id=? AND file_id=?
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

        for row in asset_prepared:
            source = row["source"]
            source_rel = row["relative"].as_posix()
            archive_rel = row["archive_relative"]
            try:
                archive = archive_path_without_symlinks(
                    archive_root,
                    archive_rel.as_posix(),
                )
            except ArchiveLocationError as exc:
                raise SsdReleaseError(str(exc)) from exc

            expected_size = int(row["size_bytes"])
            expected_hash = str(row["expected_sha256"])
            _archive_stat, archive_hash = _verify_regular_file(
                archive, expected_size, expected_hash, "Archivdatei",
                archive_guard=archive_guard, archive_relative=archive_rel,
            )

            source_exists = source.exists() or source.is_symlink()
            source_hash = None
            if source_exists:
                _source_stat, source_hash = _verify_regular_file(
                    source, expected_size, expected_hash, "SSD-Datei"
                )
            elif open_release is None:
                raise SsdReleaseError("SSD-Datei fehlt: " + str(source))
            row["source_present_for_run"] = source_exists

            with database_connection(database_path) as connection:
                connection.execute(
                    """
                    UPDATE event_ssd_release_assets
                    SET status='archive_verified',
                        actual_source_size_bytes=?,actual_source_sha256=?,
                        actual_archive_size_bytes=?,actual_archive_sha256=?,
                        verified_at=?,error_message=NULL
                    WHERE release_id=? AND source_relative_path=?
                    """,
                    (
                        expected_size if source_exists else None,
                        source_hash,
                        expected_size,
                        archive_hash,
                        _now(),
                        release_id,
                        source_rel,
                    ),
                )

        with database_connection(database_path) as connection:
            camera_source = int(connection.execute(
                """SELECT COUNT(*) FROM event_ssd_release_files
                   WHERE release_id=? AND actual_source_sha256 IS NOT NULL""",
                (release_id,),
            ).fetchone()[0])
            asset_source = int(connection.execute(
                """SELECT COUNT(*) FROM event_ssd_release_assets
                   WHERE release_id=? AND actual_source_sha256 IS NOT NULL""",
                (release_id,),
            ).fetchone()[0])
            camera_archive = int(connection.execute(
                """SELECT COUNT(*) FROM event_ssd_release_files
                   WHERE release_id=? AND status='archive_verified'""",
                (release_id,),
            ).fetchone()[0])
            asset_archive = int(connection.execute(
                """SELECT COUNT(*) FROM event_ssd_release_assets
                   WHERE release_id=? AND status='archive_verified'""",
                (release_id,),
            ).fetchone()[0])
            connection.execute(
                """
                UPDATE event_ssd_releases
                SET status='deleting',verified_source_count=?,
                    verified_archive_count=?,updated_at=?
                WHERE id=?
                """,
                (
                    camera_source + asset_source,
                    camera_archive + asset_archive,
                    _now(),
                    release_id,
                ),
            )

        deleted_count = 0
        deleted_bytes = 0

        def delete_source(row: dict[str, Any], *, asset: bool) -> None:
            nonlocal deleted_count, deleted_bytes
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
                archive_guard.verify(row["archive_relative"], expected_size, expected_hash, source_stat)
                current = os.lstat(source)
                if (
                    int(current.st_dev),
                    int(current.st_ino),
                    int(current.st_mtime_ns),
                    int(current.st_size),
                    int(current.st_ctime_ns),
                    int(current.st_nlink),
                    int(current.st_mode),
                ) != (
                    int(source_stat.st_dev),
                    int(source_stat.st_ino),
                    int(source_stat.st_mtime_ns),
                    int(source_stat.st_size),
                    int(source_stat.st_ctime_ns),
                    int(source_stat.st_nlink),
                    int(source_stat.st_mode),
                ):
                    raise SsdReleaseError(
                        "SSD-Datei änderte sich unmittelbar vor dem Löschen: " + str(source)
                    )
                # Final non-atomic gate: external writers can still race unlink.
                archive_guard.check()
                source.unlink()
                _fsync_directory(source.parent)
                status_value = "deleted"
                deleted_count += 1
                deleted_bytes += expected_size
            else:
                if row.get("source_present_for_run"):
                    raise SsdReleaseError("Eine in diesem Lauf geprüfte SSD-Datei ist unerwartet verschwunden; weitere Löschungen gesperrt: " + str(source))
                status_value = "already_released"

            with database_connection(database_path) as connection:
                if asset:
                    connection.execute(
                        """UPDATE event_ssd_release_assets
                           SET status=?,deleted_at=?,error_message=NULL
                           WHERE release_id=? AND source_relative_path=?""",
                        (
                            status_value,
                            _now(),
                            release_id,
                            row["relative"].as_posix(),
                        ),
                    )
                else:
                    connection.execute(
                        """UPDATE event_ssd_release_files
                           SET status=?,deleted_at=?,error_message=NULL
                           WHERE release_id=? AND file_id=?""",
                        (status_value, _now(), release_id, int(row["file_id"])),
                    )
                connection.execute(
                    """UPDATE event_ssd_releases
                       SET deleted_file_count=?,deleted_size_bytes=?,updated_at=?
                       WHERE id=?""",
                    (deleted_count, deleted_bytes, _now(), release_id),
                )

            archive_guard.check()

        for row in prepared:
            delete_source(row, asset=False)
        for row in asset_prepared:
            delete_source(row, asset=True)

        with database_connection(database_path) as connection:
            connection.execute(
                "UPDATE event_ssd_releases SET status='finalizing',updated_at=? WHERE id=?",
                (_now(), release_id),
            )

        archive_guard.check()
        removed = _remove_empty_event_tree(event_root, work_root)
        return _finalize_release(
            database_path,
            release_id,
            job_id,
            event_id,
            removed,
        )

    except Exception as error:
        message = ("SSD-Freigabe gestoppt: " + str(error) +
                   " Noch vorhandene SSD-Dateien bleiben erhalten. Bereits entfernte Dateien werden nicht wiederhergestellt. "
                   "Eine erneute Freigabe benötigt einen neuen Auftrag und vollständige Prüfung.")
        _mark_release_failed(database_path, release_id, message)
        raise SsdReleaseError(message) from error
    finally:
        if archive_guard is not None:
            archive_guard.close()

