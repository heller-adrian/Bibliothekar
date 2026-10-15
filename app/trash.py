from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature

from app.database import database_connection
from app.external_changes import resolve_notice_key
from app.storage_config import load_storage_settings, storage_paths
from app.library_runtime import get_current_library
from app.workspace_layout import WorkspaceLayoutError, shared_work_root


TRASH_CONFIRMATION = "PAPIERKORB ENDGÜLTIG LEEREN"


class TrashError(RuntimeError):
    pass


def serialized_trash_operation(workspace_argument: str):
    """All reservation, inventory and worker mutations share the existing lock."""
    def decorate(function):
        parameters = signature(function)
        @wraps(function)
        def locked(*args, **kwargs):
            workspace = parameters.bind(*args, **kwargs).arguments[workspace_argument]
            from app.trash_selective import _operation_lock
            with _operation_lock(workspace):
                return function(*args, **kwargs)
        return locked
    return decorate


_EMPTY_DATABASES = ContextVar("trash_empty_databases", default=None)


@contextmanager
def trash_empty_databases(databases):
    """Supply catalogue scope without changing the established filesystem hook."""
    token = _EMPTY_DATABASES.set(tuple(databases))
    try:
        yield
    finally:
        _EMPTY_DATABASES.reset(token)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def trash_root(workspace_root: Path, *, create: bool = True) -> Path:
    workspace = workspace_root.expanduser().resolve(strict=False)
    # Request-scoped legacy compatibility roots contain symlinks and live
    # under /tmp. The trash always belongs to the original shared RW mount,
    # never to the temporary per-library compatibility directory.
    context = get_current_library()
    if (
        context is not None
        and workspace.parent == Path("/tmp/bibliothekar-library-workspaces")
    ):
        workspace = context.workspace_root.expanduser().resolve(strict=False)
    raw = workspace / load_storage_settings()["trash_directory_name"]
    # Check the unresolved entry: Path.resolve() would hide a malicious
    # Finder-created symlink to another dataset before this security check.
    if raw.is_symlink():
        raise TrashError("Der verwaltete Papierkorb darf kein symbolischer Link sein.")
    if raw.exists() and not raw.is_dir():
        raise TrashError("Der konfigurierte Papierkorb ist kein Ordner: " + str(raw))
    if create and not raw.exists():
        raw.mkdir(parents=True, exist_ok=True)
    if raw.exists() and not os.access(raw, os.R_OK | os.W_OK | os.X_OK):
        raise TrashError("Der Papierkorb ist nicht vollständig zugreifbar: " + str(raw))
    return raw.resolve(strict=False)


def _physical_entries(workspace_root: Path) -> tuple[Path, list[dict[str, Any]], int]:
    root = trash_root(workspace_root)
    entries: list[dict[str, Any]] = []
    directory_count = 0
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        directory = Path(dirpath)
        safe_dirs: list[str] = []
        for name in sorted(dirnames, key=str.casefold):
            candidate = directory / name
            try:
                info = os.lstat(candidate)
            except OSError:
                continue
            directory_count += 1
            if stat.S_ISLNK(info.st_mode):
                entries.append({
                    "relative_path": candidate.relative_to(root).as_posix(),
                    "filename": candidate.name,
                    "size_bytes": 0,
                    "entry_type": "symlink",
                    "tracked": False,
                })
            elif stat.S_ISDIR(info.st_mode):
                safe_dirs.append(name)
        dirnames[:] = safe_dirs
        if directory != root:
            entries.append({
                "relative_path": directory.relative_to(root).as_posix(),
                "filename": directory.name,
                "size_bytes": 0,
                "entry_type": "directory",
                "tracked": False,
            })

        for filename in sorted(filenames, key=str.casefold):
            path = directory / filename
            try:
                info = os.lstat(path)
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode):
                entries.append({
                    "relative_path": relative,
                    "filename": filename,
                    "size_bytes": 0,
                    "entry_type": "symlink",
                    "tracked": False,
                })
                continue
            if not stat.S_ISREG(info.st_mode):
                entries.append({
                    "relative_path": relative,
                    "filename": filename,
                    "size_bytes": int(info.st_size),
                    "entry_type": "other",
                    "tracked": False,
                })
                continue
            entries.append({
                "relative_path": relative,
                "filename": filename,
                "size_bytes": int(info.st_size),
                "entry_type": "file",
                "tracked": False,
                "_absolute_path": path,
                "_sha256": None,
            })
    return root, entries, directory_count


def _candidate_still_present(workspace_root: Path, row: dict[str, Any]) -> bool:
    if str(row.get("current_root_kind") or "") != "shared_workspace":
        return False
    relative = str(row.get("current_relative_path") or "").strip().replace("\\", "/")
    if not relative:
        return False
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False

    roots: list[Path] = []
    try:
        roots.append(storage_paths(workspace_root)["backup_root"].resolve(strict=False))
    except Exception:
        pass
    try:
        work = shared_work_root(workspace_root).resolve(strict=False)
        if work not in roots:
            roots.append(work)
    except (WorkspaceLayoutError, OSError):
        pass

    for base in roots:
        physical = (base / candidate).resolve(strict=False)
        try:
            physical.relative_to(base)
        except ValueError:
            continue
        if physical.is_file():
            return True
    return False


@serialized_trash_operation("workspace_root")
def reconcile_trash_inventory(
    database_path: Path,
    workspace_root: Path,
    *,
    physical_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Synchronize one library DB with the physical shared trash."""
    root, scanned, directory_count = _physical_entries(workspace_root)
    entries = physical_entries if physical_entries is not None else scanned
    timestamp = _now()
    adopted = 0
    exact = 0
    ambiguous = 0

    with database_connection(database_path) as connection:
        for item in entries:
            if str(item.get("entry_type") or "file") != "file":
                continue
            relative = str(item.get("relative_path") or "")
            filename = str(item.get("filename") or Path(relative).name)
            size_bytes = int(item.get("size_bytes") or 0)

            known = connection.execute(
                """SELECT f.id AS file_id,f.job_id,f.family_id,f.original_filename,
                          f.current_relative_path,f.current_root_kind,f.size_bytes,
                          COALESCE(f.sha256_current,f.sha256_original,'') AS sha256
                   FROM files f
                   WHERE f.current_root_kind='trash'
                     AND f.current_relative_path=?
                   ORDER BY f.id
                   LIMIT 2""",
                (relative,),
            ).fetchall()
            selected: dict[str, Any] | None = None
            if len(known) == 1:
                selected = dict(known[0])
                exact += 1
            elif len(known) > 1:
                ambiguous += 1
                continue
            else:
                candidates = [
                    dict(row)
                    for row in connection.execute(
                        """SELECT f.id AS file_id,f.job_id,f.family_id,
                                  f.original_filename,f.current_relative_path,
                                  f.current_root_kind,f.size_bytes,
                                  COALESCE(f.sha256_current,f.sha256_original,'') AS sha256
                           FROM files f
                           WHERE f.size_bytes=?
                             AND COALESCE(f.current_root_kind,'shared_workspace')
                                 IN ('shared_workspace','trash')
                           ORDER BY
                             CASE WHEN f.original_filename=? THEN 0 ELSE 1 END,
                             f.id""",
                        (size_bytes, filename),
                    ).fetchall()
                ]
                candidates = [
                    row for row in candidates
                    if str(row.get("current_root_kind") or "") == "trash"
                    or not _candidate_still_present(workspace_root, row)
                ]
                if candidates:
                    digest = item.get("_sha256")
                    if not digest:
                        absolute = item.get("_absolute_path") or (root / relative)
                        digest = _sha256_file(Path(absolute))
                        item["_sha256"] = digest
                    matching = [
                        row for row in candidates
                        if str(row.get("sha256") or "") == str(digest)
                    ]
                    same_name = [
                        row for row in matching
                        if str(row.get("original_filename") or "") == filename
                    ]
                    pool = same_name or matching
                    if len(pool) == 1:
                        selected = pool[0]
                    elif len(pool) > 1:
                        ambiguous += 1
                        continue

            if selected is None:
                continue

            file_id = int(selected["file_id"])
            previous_root_kind = str(selected.get("current_root_kind") or "")
            previous_relative_path = str(selected.get("current_relative_path") or "")
            changed = previous_root_kind != "trash" or previous_relative_path != relative
            connection.execute(
                """UPDATE files
                   SET current_root_kind='trash',
                       current_relative_path=?,
                       updated_at=?
                   WHERE id=?""",
                (relative, timestamp, file_id),
            )
            connection.execute(
                "DELETE FROM central_missing_file_observations WHERE file_id=?",
                (file_id,),
            )
            connection.execute(
                "DELETE FROM event_missing_file_observations WHERE file_id=?",
                (file_id,),
            )
            resolve_notice_key(connection, f"placement:{file_id}", now=timestamp)
            item["tracked"] = True
            item["file_id"] = file_id
            item["family_id"] = (
                int(selected["family_id"]) if selected.get("family_id") is not None else None
            )
            if changed:
                adopted += 1
                connection.execute(
                    """INSERT INTO audit_log(
                           job_id,action,entity_type,entity_id,details_json,created_at)
                       VALUES (?,'trash_file_observed','file',?,?,?)""",
                    (
                        str(selected.get("job_id") or "") or None,
                        str(file_id),
                        json.dumps(
                            {
                                "previous_root_kind": previous_root_kind,
                                "previous_relative_path": previous_relative_path,
                                "trash_relative_path": relative,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        timestamp,
                    ),
                )
        connection.commit()

    public_entries = [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in entries
    ]
    return {
        "root": str(root),
        "folder_name": root.name,
        "file_count": sum(1 for item in entries if item.get("entry_type") == "file"),
        "entry_count": len(entries),
        "directory_count": directory_count,
        "total_size_bytes": sum(
            int(item.get("size_bytes") or 0)
            for item in entries
            if item.get("entry_type") == "file"
        ),
        "tracked_file_count": sum(
            1 for item in entries
            if item.get("entry_type") == "file" and item.get("tracked")
        ),
        "untracked_file_count": sum(
            1 for item in entries
            if item.get("entry_type") == "file" and not item.get("tracked")
        ),
        "adopted_file_count": adopted,
        "exact_file_count": exact,
        "ambiguous_file_count": ambiguous,
        "entries": public_entries,
    }


def purge_trash_database(database_path: Path) -> dict[str, int]:
    timestamp = _now()
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT id,job_id,family_id,current_relative_path,
                          COALESCE(sha256_current,sha256_original,'') AS sha256
                   FROM files
                   WHERE current_root_kind='trash'
                   ORDER BY id"""
            ).fetchall()
        ]
        family_ids = {
            int(row["family_id"]) for row in rows if row.get("family_id") is not None
        }
        for row in rows:
            connection.execute(
                """INSERT INTO audit_log(
                       job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'trash_file_permanently_deleted','file',?,?,?)""",
                (
                    str(row.get("job_id") or "") or None,
                    str(row["id"]),
                    json.dumps(
                        {
                            "trash_relative_path": str(row.get("current_relative_path") or ""),
                            "sha256": str(row.get("sha256") or ""),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
        connection.execute("DELETE FROM files WHERE current_root_kind='trash'")
        removed_families = 0
        for family_id in sorted(family_ids):
            remaining = connection.execute(
                "SELECT COUNT(*) FROM files WHERE family_id=?",
                (family_id,),
            ).fetchone()[0]
            if int(remaining or 0) == 0:
                connection.execute("DELETE FROM file_families WHERE id=?", (family_id,))
                removed_families += 1
        connection.commit()
    return {
        "deleted_file_rows": len(rows),
        "deleted_family_rows": removed_families,
    }


def _remove_tree_without_following_links(path: Path) -> None:
    info = os.lstat(path)
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        path.unlink()
        return
    for entry in os.scandir(path):
        _remove_tree_without_following_links(Path(entry.path))
    path.rmdir()


@serialized_trash_operation("workspace_root")
def empty_trash_filesystem(workspace_root: Path) -> dict[str, int]:
    # This check is inside the same process/thread lock as reservation
    # publication, not the advisory HTTP preflight. Keep it through cleanup.
    from app.trash_import import protected_trash_paths
    if protected_trash_paths(None, workspace_root):
        raise TrashError("Wiederherstellung reserviert Papierkorbdateien; Leeren gesperrt.")
    databases = _EMPTY_DATABASES.get()
    if databases is not None:
        from app.trash_selective import recover_trash_deletions, delete_selected_trash_files
        recover_trash_deletions(workspace_root, allowed_databases=databases)
        root, entries, _ = _physical_entries(workspace_root)
        # Do not route unknown special entries through regular-file journals.
        if any(e['entry_type'] not in {'file', 'directory'} for e in entries):
            raise TrashError("Papierkorb enthält Links oder spezielle Einträge; sichere manuelle Klärung erforderlich.")
        paths = [e['relative_path'] for e in entries if e['entry_type'] == 'file']
        for database in databases:
            with database_connection(database) as connection:
                missing = {str(row[0]) for row in connection.execute(
                    "SELECT current_relative_path FROM files WHERE current_root_kind='trash'"
                )} - set(paths)
            if missing:
                raise TrashError("Papierkorbkatalog enthält ungeklärte fehlende Dateien; Leeren gesperrt.")
        result = delete_selected_trash_files(databases, workspace_root, paths) if paths else {'deleted_file_count': 0}
        # Only remove empty directories. Never sweep a newly appeared file.
        for e in sorted((e for e in entries if e['entry_type'] == 'directory'), key=lambda e: len(Path(e['relative_path']).parts), reverse=True):
            try: (root / e['relative_path']).rmdir()
            except FileNotFoundError: pass
        if any(root.iterdir()):
            raise TrashError("Papierkorb ist nicht vollständig leer; übrige Einträge bleiben erhalten.")
        # The journalled purge already commits every selected row. Do not
        # introduce an unjournalled multi-database tail after that fence.
        return result
    root = trash_root(workspace_root)
    deleted_entries = 0
    for child in list(root.iterdir()):
        _remove_tree_without_following_links(child)
        deleted_entries += 1
    return {"deleted_top_level_entries": deleted_entries}
