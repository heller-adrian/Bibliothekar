"""Crash-recoverable selected-file trash deletion (no symlink traversal)."""
from __future__ import annotations

from datetime import datetime, timezone
from contextlib import contextmanager
from contextvars import ContextVar
import errno
import fcntl
import hashlib
import json
import os
import shutil
from pathlib import Path
import threading
import uuid
from typing import Iterable

from app.database import database_connection
from app.storage_config import storage_paths
from app.trash import TrashError, _physical_entries, _sha256_file, trash_root
from app.trash_restore import _relative, _source, _ensure_target_parent


_RECOVERY_LOCK = threading.RLock()
_HELD_LOCKS = threading.local()


@contextmanager
def _operation_lock(workspace: Path, *, blocking: bool = True):
    # Inventory recovery must not roll back a live deletion. flock also covers
    # a second web process; the OS releases it when a process dies.
    if not _RECOVERY_LOCK.acquire(blocking=blocking):
        raise TrashError("Eine Papierkorboperation läuft bereits; bitte erneut versuchen.")
    try:
        path = _parent(workspace) / ".lock"
        held = getattr(_HELD_LOCKS, "paths", set())
        if path in held:
            yield
            return
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            except BlockingIOError as error:
                raise TrashError("Eine Papierkorboperation läuft bereits; bitte erneut versuchen.") from error
            _HELD_LOCKS.paths = held | {path}
            yield
        finally:
            _HELD_LOCKS.paths = held
            os.close(fd)
    finally:
        _RECOVERY_LOCK.release()


_PURGE_SNAPSHOTS: ContextVar[dict] = ContextVar("trash_purge_snapshots", default={})


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _sync_parents(path: Path, root: Path) -> None:
    current = path
    while True:
        _sync_dir(current)
        if current == root:
            return
        if current == current.parent:
            raise TrashError("Zwischenbestand liegt außerhalb des Journalordners.")
        current = current.parent


def _move_checked(source: Path, target: Path, sha256: str, *, durable_root: Path) -> None:
    # Publish and sync the staged copy BEFORE unlinking the trash entry.
    # A stop between link and unlink leaves two verified copies for recovery.
    try:
        os.link(source, target, follow_symlinks=False)
    except OSError as error:
        if error.errno != errno.EXDEV:
            raise
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o640)
        with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
    if _sha256_file(target) != sha256:
        raise TrashError("Prüfsummenfehler im Lösch-Zwischenbestand.")
    with target.open("rb") as staged_file:
        os.fsync(staged_file.fileno())
    # Include all new nested directory entries and the DELETE_* directory.
    _sync_parents(target.parent, durable_root)
    source.unlink()
    _sync_dir(source.parent)


def _return_checked(source: Path, target: Path, sha256: str, root: Path) -> None:
    if _sha256_file(source) != sha256:
        raise TrashError("Zwischenbestand während der Wiederherstellung verändert.")
    if target.exists():
        if target.is_symlink() or _sha256_file(target) != sha256:
            raise TrashError("Ziel während der Wiederherstellung verändert.")
        # Both copies were verified in the all-file recovery preflight.
        # Sync the surviving copy before removing the staging link.
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        _sync_parents(target.parent, root)
        source.unlink()
        _sync_dir(source.parent)
    else:
        _move_checked(source, target, sha256, durable_root=root)

def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _catalogue_snapshot(connection, paths: list[str]) -> dict:
    """Capture ONLY rows deleted/cascaded or SET NULL by these selected files.

    No database image is restored: independent jobs and edits remain intact.
    The same closure is rechecked under the purge's BEGIN IMMEDIATE lock.
    """
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )]
    keys = {}
    references = {}
    for table in tables:
        keys[table] = [r[1] for r in sorted(connection.execute(
            "PRAGMA table_info(" + _quote(table) + ")"
        ), key=lambda r: r[5]) if r[5]]
        for fk in connection.execute("PRAGMA foreign_key_list(" + _quote(table) + ")"):
            references.setdefault((table, fk[0]), []).append(tuple(fk))
    deleted = {}
    updates = {}
    queue = []

    def identity(table, row):
        if not keys[table]:
            raise TrashError("Katalogtabelle ohne eindeutigen Schlüssel: " + table)
        return table, tuple(row[k] for k in keys[table])

    def add(table, row):
        row = dict(row)
        key = identity(table, row)
        if key not in deleted:
            deleted[key] = row
            queue.append((table, row))

    for path in paths:
        for row in connection.execute(
            "SELECT * FROM files WHERE current_root_kind='trash' AND current_relative_path=?", (path,)
        ):
            add("files", row)
    family_ids = {row["family_id"] for (table, _), row in deleted.items()
                  if table == "files" and row["family_id"] is not None}
    for fid in family_ids:
        members = connection.execute("SELECT * FROM files WHERE family_id=?", (fid,)).fetchall()
        if all(identity("files", row) in deleted for row in members):
            row = connection.execute("SELECT * FROM file_families WHERE id=?", (fid,)).fetchone()
            if row is not None:
                add("file_families", row)
    while queue:
        parent, row = queue.pop()
        for (child, _), group in references.items():
            group.sort(key=lambda fk: fk[1])
            if group[0][2] != parent:
                continue
            action = group[0][6]
            if action not in {"CASCADE", "SET NULL", "SET DEFAULT"}:
                continue
            if action == "SET DEFAULT":
                raise TrashError("Unbekannte Katalog-Löschabhängigkeit: " + child)
            columns = [fk[3] for fk in group]
            parent_columns = [fk[4] or keys[parent][i] for i, fk in enumerate(group)]
            values = tuple(row[c] for c in parent_columns)
            matches = connection.execute(
                "SELECT * FROM " + _quote(child) + " WHERE "
                + " AND ".join(_quote(c) + "=?" for c in columns), values,
            ).fetchall()
            for match in matches:
                if action == "CASCADE":
                    add(child, match)
                else:
                    key = identity(child, match)
                    update = updates.setdefault(key, {"row": dict(match), "columns": set()})
                    update["columns"].update(columns)
    schema = "\n".join(str(r[0]) for r in connection.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
    ))
    return {
        "schema_sha256": hashlib.sha256(schema.encode()).hexdigest(),
        "keys": keys,
        "deleted": [{"table": table, "row": row} for (table, _), row in sorted(deleted.items(), key=lambda x: repr(x[0]))],
        "updates": [{"table": table, "row": value["row"], "columns": sorted(value["columns"])}
                    for (table, key), value in sorted(updates.items(), key=lambda x: repr(x[0]))
                    if (table, key) not in deleted],
    }


def _restore_catalogue(database: dict, operation_id: str) -> None:
    path = Path(database["path"])
    if not path.is_file() or path.is_symlink():
        raise TrashError("Katalog für Löschrücknahme fehlt: " + str(path))
    info = path.stat()
    if [info.st_dev, info.st_ino] != database["identity"]:
        raise TrashError("Katalog wurde seit dem Löschauftrag ersetzt: " + str(path))
    snapshot = database["snapshot"]
    with database_connection(path) as c:
        c.execute("BEGIN IMMEDIATE")
        c.execute("PRAGMA defer_foreign_keys=ON")
        current_schema = "\n".join(str(r[0]) for r in c.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type,name"
        ))
        if hashlib.sha256(current_schema.encode()).hexdigest() != snapshot["schema_sha256"]:
            raise TrashError("Katalogschema wurde seit dem Löschauftrag verändert.")
        for entry in snapshot["deleted"]:
            table, row = entry["table"], entry["row"]
            keys = snapshot["keys"][table]
            where = " AND ".join(_quote(k) + "=?" for k in keys)
            existing = c.execute("SELECT * FROM " + _quote(table) + " WHERE " + where,
                                 tuple(row[k] for k in keys)).fetchone()
            if existing is not None:
                if dict(existing) != row:
                    raise TrashError("Katalogkonflikt bei Löschrücknahme: " + table)
                continue
            columns = list(row)
            c.execute("INSERT INTO " + _quote(table) + " (" + ",".join(map(_quote, columns))
                      + ") VALUES (" + ",".join("?" for _ in columns) + ")", tuple(row.values()))
        for entry in snapshot["updates"]:
            table, row, columns = entry["table"], entry["row"], entry["columns"]
            keys = snapshot["keys"][table]
            where = " AND ".join(_quote(k) + "=?" for k in keys)
            values = tuple(row[k] for k in keys)
            existing = c.execute("SELECT * FROM " + _quote(table) + " WHERE " + where, values).fetchone()
            if existing is None or any(existing[k] not in (None, row[k]) for k in columns):
                raise TrashError("Katalogabhängigkeit kann nicht sicher zurückgenommen werden.")
            c.execute("UPDATE " + _quote(table) + " SET " + ",".join(_quote(k) + "=?" for k in columns)
                      + " WHERE " + where, tuple(row[k] for k in columns) + values)
        if c.execute("PRAGMA foreign_key_check").fetchall():
            raise TrashError("Fremdschlüsselkonflikt bei Löschrücknahme.")
        details = json.dumps({"operation_id": operation_id}, sort_keys=True)
        c.execute("""INSERT INTO audit_log(action,entity_type,entity_id,details_json,created_at)
                     SELECT 'trash_deletion_rolled_back','trash_deletion',?,?,?
                     WHERE NOT EXISTS (SELECT 1 FROM audit_log
                       WHERE action='trash_deletion_rolled_back' AND entity_id=?)""",
                  (operation_id, details, datetime.now(timezone.utc).isoformat(), operation_id))


def _parent(workspace: Path) -> Path:
    root = storage_paths(workspace)["metadata_root"] / ".trash-deletions"
    if root.is_symlink():
        raise TrashError("Papierkorb-Löschjournal darf kein Symlink sein.")
    root.mkdir(parents=True, exist_ok=True)
    _sync_dir(root.parent)
    return root.resolve(strict=True)


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_name("." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def recover_trash_deletions(workspace: Path, *, allowed_databases: Iterable[Path] | None = None) -> dict:
    """Return uncommitted staged originals without losing any data."""
    with _operation_lock(workspace):
        return _recover_trash_deletions(workspace, allowed_databases=allowed_databases)


def _recover_trash_deletions(workspace: Path, *, allowed_databases=None) -> dict:
    parent = _parent(workspace)
    root = trash_root(workspace)
    recovered = []
    for journal in sorted(parent.glob("DELETE_*.json")):
        if journal.is_symlink():
            raise TrashError("Unsicheres Löschjournal.")
        data = json.loads(journal.read_text(encoding="utf-8"))
        ident = str(data.get("id") or "")
        if ident != journal.stem or len(ident) != 39 or not ident.startswith("DELETE_") or any(c not in "0123456789ABCDEF" for c in ident[7:]):
            raise TrashError("Ungültige Löschjournal-ID.")
        if data.get("state") not in {"prepared", "committed"}:
            raise TrashError("Unbekannter Löschjournalzustand.")
        approved = {str(Path(p).resolve()) for p in allowed_databases} if allowed_databases is not None else None
        databases = data.get("databases", [])
        if approved is not None and any(db["path"] not in approved for db in databases):
            raise TrashError("Löschjournal verweist auf eine nicht registrierte Datenbank.")
        staged = parent / ident
        expected = {str(item["path"]): item for item in data["files"]}
        from app.trash_import import protected_trash_paths
        if set(expected).intersection(protected_trash_paths(None, workspace)):
            raise TrashError("Löschjournal überschneidet sich mit einer Wiederherstellungsreservierung; Bestand bleibt erhalten.")
        for name in expected:
            _relative(name)
        if staged.is_symlink():
            raise TrashError("Unsicherer Lösch-Zwischenbestand.")
        if staged.exists():
            for p in staged.rglob("*"):
                if p.is_symlink() or (p.is_file() and p.relative_to(staged).as_posix() not in expected):
                    raise TrashError("Fremder Eintrag im Lösch-Zwischenbestand.")
        if data.get("format") != 2 and data["state"] == "prepared":
            raise TrashError("Altes Löschjournal ohne Katalogsicherung erfordert manuelle Prüfung.")
        # Check ALL bytes before any database or filesystem recovery mutation.
        for name, item in expected.items():
            rel = _relative(name)
            candidates = [(staged, staged / rel)]
            if data["state"] == "prepared":
                candidates.append((root, root / rel))
            found = 0
            for candidate_root, candidate in candidates:
                if candidate.exists() or candidate.is_symlink():
                    _source(candidate_root, rel)
                    if _sha256_file(candidate) != item["sha256"]:
                        raise TrashError("Veränderte Datei im Löschjournal: " + name)
                    found += 1
            if not found and data["state"] == "prepared":
                raise TrashError("Original und Zwischenbestand fehlen: " + name)
        if data.get("state") == "committed":
            # Also covers an interrupted/failed fsync after atomic replacement.
            # Never destroy originals until this observed commit fence is durable.
            with journal.open("rb") as committed_journal:
                os.fsync(committed_journal.fileno())
            _sync_dir(parent)
            for name in expected:
                path = staged / _relative(name)
                if path.exists():
                    path.unlink()
                    _sync_dir(path.parent)
            _remove_empty_staging(staged)
            journal.unlink()
            _sync_dir(parent)
            continue
        for database in databases:
            _restore_catalogue(database, ident)
        for item in reversed(data.get("files") or []):
            rel = _relative(str(item["path"]))
            src = staged / rel
            dst = root / rel
            if src.exists():
                _ensure_target_parent(root,rel)
                _sync_parents((root / rel).parent, root)
                _return_checked(src, dst, str(item["sha256"]), root)
                recovered.append(rel.as_posix())
        _remove_empty_staging(staged)
        journal.unlink()
        _sync_dir(parent)
    return {"recovered_paths":recovered}


def _remove_empty_staging(staged: Path) -> None:
    if not staged.exists():
        return
    for p in sorted(staged.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if p.is_dir() and not p.is_symlink():
            p.rmdir()
    staged.rmdir()
    _sync_dir(staged.parent)


def _purge_selected(db: Path, paths: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        expected = _PURGE_SNAPSHOTS.get().get(str(db.resolve()))
        if expected is not None and _catalogue_snapshot(connection, paths) != expected:
            raise TrashError("Katalog wurde seit der Löschvorbereitung verändert.")
        for path in paths:
            rows = [dict(row) for row in connection.execute(
                """SELECT id,job_id,family_id,
                          COALESCE(sha256_current,sha256_original,'') AS sha256
                   FROM files WHERE current_root_kind='trash' AND current_relative_path=?""",
                (path,)
            ).fetchall()]
            for row in rows:
                connection.execute(
                    """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                       VALUES (?,'trash_file_permanently_deleted','file',?,?,?)""",
                    (row["job_id"],str(row["id"]),
                     json.dumps({"trash_relative_path":path,"sha256":row["sha256"]},
                                ensure_ascii=False),now)
                )
                connection.execute(
                    "DELETE FROM files WHERE id=? AND current_root_kind='trash'",
                    (int(row["id"]),)
                )
                if row["family_id"] is not None:
                    remaining = connection.execute(
                        "SELECT 1 FROM files WHERE family_id=? LIMIT 1",
                        (int(row["family_id"]),)
                    ).fetchone()
                    if remaining is None:
                        connection.execute(
                            "DELETE FROM file_families WHERE id=?",
                            (int(row["family_id"]),)
                        )
        connection.commit()


def delete_selected_trash_files(
    databases: Iterable[Path],
    workspace: Path,
    relative_paths: list[str],
) -> dict:
    with _operation_lock(workspace):
        return _delete_selected_trash_files(databases, workspace, relative_paths)


def _delete_selected_trash_files(databases, workspace, relative_paths) -> dict:
    if not isinstance(relative_paths,list) or not relative_paths or any(
        not isinstance(p,str) for p in relative_paths
    ) or len(set(relative_paths))!=len(relative_paths):
        raise TrashError("Ungültige Lösch-Auswahl.")
    databases = sorted({Path(p).resolve() for p in databases})
    from app.trash_import import protected_trash_paths
    selected = {_relative(p).as_posix() for p in relative_paths}
    if selected.intersection(protected_trash_paths(None, workspace)):
        raise TrashError("Ausgewählte Dateien gehören zu einer Wiederherstellungsreservierung.")
    _recover_trash_deletions(workspace, allowed_databases=databases)
    root, entries, _ = _physical_entries(workspace)
    physical = {str(e["relative_path"]) for e in entries if e["entry_type"] == "file"}
    candidates = []
    for path in sorted(relative_paths):
        rel = _relative(path)
        if path not in physical:
            raise TrashError("Datei ist nicht mehr im Papierkorb: " + path)
        source = _source(root,rel)
        candidates.append({"path":path,"sha256":_sha256_file(source)})
    parent = _parent(workspace)
    op_id = "DELETE_" + uuid.uuid4().hex.upper()
    staging = parent / op_id
    staging.mkdir(mode=0o700)
    journal = parent / (op_id + ".json")
    snapshots = []
    for db in databases:
        if not db.is_file() or db.is_symlink():
            raise TrashError("Bibliothekskatalog fehlt: " + str(db))
        with database_connection(db) as c:
            c.execute("BEGIN IMMEDIATE")
            snapshot = _catalogue_snapshot(c, relative_paths)
        info = db.stat()
        snapshots.append({"path": str(db), "identity": [info.st_dev, info.st_ino], "snapshot": snapshot})
    record = {"format":2,"id":op_id,"state":"prepared","files":candidates,"databases":snapshots}
    _atomic_json(journal,record)
    token = _PURGE_SNAPSHOTS.set({db["path"]: db["snapshot"] for db in snapshots})
    try:
        for item in candidates:
            rel = _relative(item["path"])
            target = staging / rel
            _ensure_target_parent(staging,rel)
            source = _source(root,rel)
            if _sha256_file(source) != item["sha256"]:
                raise TrashError("Datei vor dem Löschen verändert: " + item["path"])
            _move_checked(source,target,item["sha256"],durable_root=parent)
        for db in databases:
            _purge_selected(Path(db),[item["path"] for item in candidates])
        # Once the DB no longer references the files, the deletion is durable.
        record["state"] = "committed"
        _atomic_json(journal,record)
        _recover_trash_deletions(workspace, allowed_databases=databases)
        for item in candidates:
            parent_dir = (root / _relative(item["path"])).parent
            while parent_dir != root:
                try: parent_dir.rmdir()
                except OSError: break
                parent_dir = parent_dir.parent
        return {"deleted_file_count":len(candidates)}
    except Exception:
        # The journal enables safe restoration on the next operation, including
        # a process crash; never discard the staged originals in this branch.
        try:
            _recover_trash_deletions(workspace, allowed_databases=databases)
        except Exception as recovery_error:
            raise TrashError("Löschung unterbrochen; Originale und Journal bleiben zur Wiederherstellung erhalten: "
                             + str(recovery_error)) from recovery_error
        raise
    finally:
        _PURGE_SNAPSHOTS.reset(token)
