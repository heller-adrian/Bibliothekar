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
                WHERE job_id = ?
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



# BA-02: Journal-Dateien leben bewusst AUSSERHALB von .deleting/<job>.
# Ein Crash mitten im Aufräumen kann damit sicher erkannt und fortgesetzt werden.
import hashlib
import json
import re
import uuid


def _validate_backup_job_id(job_id: str) -> str:
    cleaned = str(job_id)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", cleaned):
        raise BackupDeletionError("Ungültige Sicherungs-ID für den Löschauftrag.")
    return cleaned


def _deletion_paths(central_root: Path, job_id: str) -> tuple[Path, Path]:
    cleaned = _validate_backup_job_id(job_id)
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
    return (
        central_root / ".deleting-journals" / (digest + ".json"),
        central_root / ".deleting" / cleaned,
    )


def _sync_dir(directory: Path) -> None:
    fd = os.open(str(directory), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_journal(path: Path, manifest: dict[str, Any], *, new: bool = False) -> None:
    """Atomic, fsync'ed recovery evidence independent from deletion staging."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")
    if new:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(path), flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        finally:
            _sync_dir(parent)
        return

    tmp = parent / (".tmp-" + uuid.uuid4().hex)
    try:
        with tmp.open("xb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(tmp, path)
        _sync_dir(parent)
    finally:
        tmp.unlink(missing_ok=True)


def _read_journal(path: Path, central_root: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise BackupDeletionError("Löschjournal ist kein reguläres Dokument.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BackupDeletionError("Löschjournal ist nicht lesbar: " + path.name) from error
    if not isinstance(manifest, dict) or manifest.get("format") != 1:
        raise BackupDeletionError("Löschjournal verwendet ein unbekanntes Format.")
    job_id = _validate_backup_job_id(str(manifest.get("job_id") or ""))
    journal_path, stage_root = _deletion_paths(central_root, job_id)
    if path != journal_path:
        raise BackupDeletionError("Löschjournal hat einen unerwarteten Dateinamen.")
    if str(manifest.get("central_root") or "") != str(central_root.resolve(strict=False)):
        raise BackupDeletionError("Löschjournal gehört zu einem anderen Arbeitsbestand.")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise BackupDeletionError("Löschjournal besitzt keine gültige Dateiliste.")
    if str(manifest.get("state")) not in {"prepared", "files_staged", "main_deleted"}:
        raise BackupDeletionError("Unbekannter Löschjournal-Zustand.")
    seen: set[str] = set()
    for item in manifest["files"]:
        if not isinstance(item, dict):
            raise BackupDeletionError("Ungültiger Dateieintrag im Löschjournal.")
        relative = str(item.get("relative") or "")
        source = _safe_central_file(central_root, relative)
        try:
            Path(relative).relative_to(".deleting")
            raise BackupDeletionError("Löschjournal verweist auf internen Stagingbereich.")
        except ValueError:
            pass
        if relative in seen or not relative or relative.startswith(".deleting"):
            raise BackupDeletionError("Ungültige oder doppelte Datei im Löschjournal.")
        seen.add(relative)
        if not isinstance(item.get("bytes"), int) or item["bytes"] < 0:
            raise BackupDeletionError("Ungültige Dateigröße im Löschjournal.")
        if not re.fullmatch(r"[a-fA-F0-9]{64}", str(item.get("sha256") or "")):
            raise BackupDeletionError("Ungültige SHA-256 im Löschjournal.")
        staged = (stage_root / relative).resolve(strict=False)
        try:
            staged.relative_to(stage_root.resolve(strict=False))
        except ValueError as error:
            raise BackupDeletionError("Stagingpfad verlässt den Löschbereich.") from error
        if source == staged:
            raise BackupDeletionError("Quelle und Staging dürfen nicht identisch sein.")
    return manifest


def _verify_journal_file(path: Path, row: dict[str, Any]) -> bool:
    if not path.exists() and not path.is_symlink():
        return False
    if path.is_symlink() or not path.is_file():
        raise BackupDeletionError("Löschjournal-Datei ist kein regulärer Datensatz: " + str(path))
    if path.stat().st_size != int(row["bytes"]) or sha256_file(path).lower() != str(row["sha256"]).lower():
        raise BackupDeletionError("SHA-256/Größe der Löschdatei stimmt nicht: " + str(path))
    return True


def _check_staging_contents(stage_root: Path, files: list[dict[str, Any]]) -> None:
    if stage_root.is_symlink():
        raise BackupDeletionError("Der Lösch-Stagingordner darf kein Symlink sein.")
    if not stage_root.exists():
        return
    if not stage_root.is_dir():
        raise BackupDeletionError("Der Lösch-Stagingpfad ist kein Verzeichnis.")
    expected = {str(item["relative"]) for item in files}
    for base, directories, names in os.walk(stage_root, followlinks=False):
        for name in directories:
            directory = Path(base) / name
            if directory.is_symlink():
                raise BackupDeletionError("Fremder Symlink im Lösch-Staging.")
        for name in names:
            child = Path(base) / name
            relative = child.relative_to(stage_root).as_posix()
            if relative not in expected or child.is_symlink() or not child.is_file():
                raise BackupDeletionError("Fremder oder unzulässiger Inhalt im Lösch-Staging: " + relative)


def _restore_library_projections(
    main_database: Path,
    registry_path: Path,
    job_id: str,
    library_rows: list[dict[str, Any]],
) -> None:
    for library in library_rows:
        value = str(library.get("database_path") or "").strip()
        if not value:
            continue
        database_path = Path(value)
        library_id = str(library.get("library_id") or MAIN_LIBRARY_ID)
        if database_path.resolve(strict=False) != main_database.resolve(strict=False):
            project_import_job(main_database, database_path, job_id)
        backfill_library_inventory(
            registry_path,
            database_path=database_path,
            library_id=library_id,
            claim_all_owned=False,
        )


def _finish_deletion(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
    journal: Path,
    manifest: dict[str, Any],
    stage_root: Path,
) -> None:
    """Main row is GONE: commit is irreversible; finish only known staged bytes."""
    if str(manifest["state"]) != "main_deleted":
        # Main row was already committed away before the journal reached its
        # terminal marker. This is safe only if every original is staged.
        for item in manifest["files"]:
            source = _safe_central_file(central_root, str(item["relative"]))
            staged = stage_root / str(item["relative"])
            if source.exists() or source.is_symlink() or not _verify_journal_file(staged, item):
                raise BackupDeletionError(
                    "Hauptdatensatz fehlt, aber die gestagten Dateien sind unvollständig. Manuelle Prüfung nötig."
                )
        manifest["state"] = "main_deleted"
        _write_journal(journal, manifest)

    _check_staging_contents(stage_root, manifest["files"])
    # The deletion marker is durable BEFORE touching the staged file tree.
    for library in manifest["libraries"]:
        library_id = str(library.get("library_id") or MAIN_LIBRARY_ID)
        remove_source_backup(registry_path, f"{library_id}:{manifest['job_id']}")
    if stage_root.exists():
        shutil.rmtree(stage_root, ignore_errors=False)
        _sync_dir(stage_root.parent)
    journal.unlink()
    _sync_dir(journal.parent)
    try:
        (central_root / ".deleting").rmdir()
    except OSError:
        pass


def _recover_one_deletion(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
    journal: Path,
) -> str:
    manifest = _read_journal(journal, central_root)
    job_id = str(manifest["job_id"])
    if Path(str(manifest["main_database"])).resolve(strict=False) != main_database.resolve(strict=False):
        raise BackupDeletionError("Löschjournal gehört zu einer anderen Hauptdatenbank.")
    if Path(str(manifest["registry_database"])).resolve(strict=False) != registry_path.resolve(strict=False):
        raise BackupDeletionError("Löschjournal gehört zu einer anderen Registry.")
    if not main_database.exists():
        raise BackupDeletionError("Hauptdatenbank für die Wiederherstellung fehlt.")
    _, stage_root = _deletion_paths(central_root, job_id)
    with database_connection(main_database) as connection:
        exists = connection.execute("SELECT 1 FROM jobs WHERE id=?", (job_id,)).fetchone() is not None
    if not exists:
        _finish_deletion(main_database, registry_path, central_root, journal, manifest, stage_root)
        return "completed"

    if manifest["state"] == "main_deleted":
        raise BackupDeletionError(
            "Löschjournal meldet irreversible Löschung, aber der Hauptdatensatz existiert."
        )
    _check_staging_contents(stage_root, manifest["files"])
    # Preflight ALL sources/staged files before restoring even the first file.
    for item in manifest["files"]:
        relative = str(item["relative"])
        source = _safe_central_file(central_root, relative)
        staged = stage_root / relative
        source_ok = _verify_journal_file(source, item)
        staged_ok = _verify_journal_file(staged, item)
        if source_ok == staged_ok:
            raise BackupDeletionError(
                "Lösch-Rückbau uneindeutig (Quelle/Staging fehlen oder existieren doppelt): " + relative
            )
    for item in reversed(manifest["files"]):
        relative = str(item["relative"])
        source = _safe_central_file(central_root, relative)
        staged = stage_root / relative
        if staged.is_file():
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, source)
            _sync_dir(source.parent)
            _sync_dir(staged.parent)

    _restore_library_projections(main_database, registry_path, job_id, manifest["libraries"])
    _check_staging_contents(stage_root, manifest["files"])
    if stage_root.exists():
        shutil.rmtree(stage_root)
        _sync_dir(stage_root.parent)
    journal.unlink()
    _sync_dir(journal.parent)
    try:
        (central_root / ".deleting").rmdir()
    except OSError:
        pass
    return "rolled_back"


def recover_backup_deletions(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
) -> dict[str, Any]:
    """Recover durable delete journals. Unsafe/ambiguous cases remain untouched."""
    directory = central_root / ".deleting-journals"
    result: dict[str, Any] = {"completed": 0, "rolled_back": 0, "blocked": 0, "errors": []}
    if not directory.exists():
        return result
    if directory.is_symlink() or not directory.is_dir():
        raise BackupDeletionError("Löschjournal-Verzeichnis ist ungültig.")
    for journal in sorted(directory.glob("*.json")):
        try:
            disposition = _recover_one_deletion(main_database, registry_path, central_root, journal)
            result[disposition] += 1
        except Exception as error:
            result["blocked"] += 1
            result["errors"].append(journal.name + ": " + str(error))
    return result


def delete_backup(
    main_database: Path,
    registry_path: Path,
    central_root: Path,
    job_id: str,
) -> dict[str, Any]:
    """Durable two-phase deletion: prepare -> stage -> commit -> purge.

    Before the irreversible main-row deletion, crash recovery rolls BACK all
    physical moves and secondary projections. Afterwards it only completes
    the safe staging purge, even across a process restart.
    """
    job_id = _validate_backup_job_id(job_id)
    journal, staging_root = _deletion_paths(central_root, job_id)
    if journal.exists() or journal.is_symlink() or staging_root.exists() or staging_root.is_symlink():
        raise BackupDeletionError(
            "Für diese Sicherung existiert bereits ein Löschauftrag. "
            "Bitte zuerst die Wiederherstellung abschließen."
        )
    status = backup_deletion_status(main_database, registry_path, central_root, job_id)
    if not status.get("allowed"):
        raise BackupDeletionError(str(status.get("reason") or "Sicherung ist nicht löschbar."))

    files = _main_file_rows(main_database, job_id)
    verified: list[tuple[dict[str, Any], Path]] = []
    entries: list[dict[str, Any]] = []
    for row in files:
        relative = str(row["current_relative_path"])
        if relative.startswith(".deleting"):
            raise BackupDeletionError("Sicherung verweist auf einen internen Löschbereich.")
        path = _safe_central_file(central_root, relative)
        digest = str(row["sha256"]).lower()
        record = {"relative": relative, "bytes": int(row["size_bytes"]), "sha256": digest}
        if not _verify_journal_file(path, record):
            raise BackupDeletionError("Datei fehlt vor dem Löschen: " + relative)
        entries.append(record)
        verified.append((row, path))

    library_rows = _library_rows(registry_path, main_database)
    manifest: dict[str, Any] = {
        "format": 1, "job_id": job_id,
        "central_root": str(central_root.resolve(strict=False)),
        "main_database": str(main_database.resolve(strict=False)),
        "registry_database": str(registry_path.resolve(strict=False)),
        "libraries": library_rows,
        "files": entries, "state": "prepared",
    }
    _write_journal(journal, manifest, new=True)
    try:
        staging_root.mkdir(parents=True, exist_ok=False)
        _sync_dir(staging_root.parent)
        for row, source in verified:
            relative = Path(str(row["current_relative_path"]))
            staged = staging_root / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, staged)
            _sync_dir(source.parent)
            _sync_dir(staged.parent)
        _check_staging_contents(staging_root, entries)
        for item in entries:
            if not _verify_journal_file(staging_root / item["relative"], item):
                raise BackupDeletionError("Gestagte Datei unvollständig: " + item["relative"])

        manifest["state"] = "files_staged"
        _write_journal(journal, manifest)
        main_resolved = main_database.resolve(strict=False)
        for library in library_rows:
            db_value = str(library.get("database_path") or "")
            if not db_value:
                continue
            db_path = Path(db_value)
            if db_path.resolve(strict=False) == main_resolved:
                continue
            if db_path.exists():
                _delete_job_row(db_path, job_id)
        # Commit point: from here the deleted job must NEVER be resurrected.
        if not _delete_job_row(main_database, job_id):
            raise BackupDeletionError("Hauptdatensatz konnte nicht gelöscht werden.")
        _finish_deletion(
            main_database, registry_path, central_root, journal,
            manifest, staging_root,
        )
    except Exception as error:
        # Do not hide recovery failures or delete staged files on rollback
        # failure. The durable journal remains available after process death.
        try:
            _recover_one_deletion(main_database, registry_path, central_root, journal)
        except Exception as recovery_error:
            raise BackupDeletionError(
                "Löschung unterbrochen; Löschjournal bleibt zur manuellen "
                "oder nächsten automatischen Wiederherstellung erhalten: "
                + str(recovery_error)
            ) from error
        raise BackupDeletionError(str(error)) from error

    for _, source in verified:
        _remove_empty_parents(source.parent, central_root)
    return {
        "job_id": job_id,
        "deleted_file_count": len(entries),
        "deleted_size_bytes": sum(int(row["size_bytes"]) for row, _ in verified),
    }
