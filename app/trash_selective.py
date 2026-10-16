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
import stat
from pathlib import Path
import threading
import uuid
from typing import Iterable

from app.database import database_connection
from app.storage_config import storage_paths
from app.trash import TrashError, _physical_entries, _sha256_file, trash_root
from app.trash_restore import _relative, _source, _ensure_target_parent
from app.trash_path_safety import ACTIVE, DirectoryTree, identity, digest_fd, rename_exclusive


_RECOVERY_LOCK = threading.RLock()
_HELD_LOCKS = threading.local()


@contextmanager
def _operation_lock(workspace: Path):
    with _RECOVERY_LOCK:
        active = ACTIVE.get()
        if active is not None and active.workspace == Path(os.path.abspath(workspace)):
            active.verify()
            yield
            return
        with DirectoryTree(workspace) as tree:
            token = ACTIVE.set(tree)
            try:
                path = _parent(workspace) / '.lock'
                parent, name = tree.parent_fd(path)
                fd = os.open(name, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=parent)
                try:
                    info = os.fstat(fd)
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
                        raise TrashError('Unsicherer Besitzer der Papierkorbsperre.')
                    fcntl.flock(fd, fcntl.LOCK_EX)
                    tree.verify()
                    yield
                finally:
                    os.close(fd)
            finally:
                ACTIVE.reset(token)


_PURGE_SNAPSHOTS: ContextVar[dict] = ContextVar("trash_purge_snapshots", default={})


def _sync_dir(path: Path) -> None:
    tree = ACTIVE.get()
    if tree is not None and Path(os.path.abspath(path)).is_relative_to(tree.workspace):
        os.fsync(tree.directory(path))
        return
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
    tree = ACTIVE.get()
    if tree is None:
        raise TrashError('Dateiübernahme ohne gebundenen Workspace verweigert.')
    tree.verify()
    item = tree.item(source, target)
    source_fd = tree.open_file(source, expected=item.get('source_identity'))
    if digest_fd(source_fd) != sha256:
        raise TrashError('Original vor der Übernahme verändert.')
    src_parent, src_name = tree.parent_fd(source)
    dst_parent, dst_name = tree.parent_fd(target, create=True)
    tree.check_private(dst_parent)
    if os.fstat(source_fd).st_dev != os.fstat(dst_parent).st_dev:
        raise TrashError('Dateisystemgrenze erlaubt keine atomare Löschübernahme; Original bleibt erhalten.')
    # Retain the historical link checkpoint, but never make the permanent
    # staging snapshot an alias writable through an external source handle.
    temporary = target.with_name('.link-' + uuid.uuid4().hex)
    item['link_path'] = temporary.relative_to(tree.private_root / tree.record['id']).as_posix()
    _atomic_json(tree.journal, tree.record)
    linked = False
    try:
        tree.link(src_name, temporary.name, src_dir_fd=src_parent, dst_dir_fd=dst_parent, follow_symlinks=False)
        linked = True
        if identity(tree.info(temporary)) != identity(os.fstat(source_fd)):
            raise TrashError('Fremder Hardlink im Zwischenbestand; keine Bereinigung.')
    except OSError as error:
        if error.errno not in {errno.EXDEV, errno.EPERM}:
            raise
    tree.copy(source_fd, dst_name, dst_parent)
    if tree.sha(target) != sha256:
        raise TrashError('Prüfsummenfehler im Lösch-Zwischenbestand.')
    item['staged_identity'] = identity(tree.info(target))
    if linked:
        tree.unlink_private(temporary, expected=identity(os.fstat(source_fd)))
    _sync_parents(target.parent, durable_root)
    _atomic_json(tree.journal, tree.record)
    capture = tree.private_root / tree.record['id'] / '.captured' / _relative(item['path'])
    capture_parent, capture_name = tree.parent_fd(capture, create=True)
    tree.check_private(capture_parent)
    tree.verify()
    rename_exclusive(src_parent, src_name, capture_parent, capture_name)
    os.fsync(src_parent)
    os.fsync(capture_parent)
    if identity(tree.info(capture)) != identity(os.fstat(source_fd)):
        # Return an inadvertently captured replacement without overwriting any
        # newer name. If that is impossible, retain it and the journal as-is.
        try:
            rename_exclusive(capture_parent, capture_name, src_parent, src_name)
            os.fsync(src_parent)
            os.fsync(capture_parent)
        except OSError:
            pass
        raise TrashError('Quellname wurde gleichzeitig ersetzt; fremde Datei bleibt erhalten.')
    tree.verify()
    if tree.sha(capture, expected=item['source_identity']) != sha256:
        raise TrashError('Original während der atomaren Übernahme verändert.')
    # Keep the original inode/ownership/timestamps until the durable DB commit.
    # Prepared recovery returns it before discarding the independent snapshot.
    _sync_dir(source.parent)


def _return_checked(source: Path, target: Path, sha256: str, root: Path) -> None:
    tree = ACTIVE.get()
    tree.verify()
    item = tree.item(source, target)
    source_info = tree.info(source)
    if tree.sha(source) != sha256:
        raise TrashError('Zwischenbestand während der Wiederherstellung verändert.')
    target_info = tree.info(target)
    if target_info is not None:
        allowed = [item.get('source_identity'), item.get('staged_identity'), identity(source_info)]
        if not stat.S_ISREG(target_info.st_mode) or identity(target_info) not in allowed or tree.sha(target) != sha256:
            raise TrashError('Fremdes Restore-Ziel bleibt unverändert; Journal bleibt erhalten.')
        fd = tree.open_file(target, expected=identity(target_info))
        os.fsync(fd)
        _sync_parents(target.parent, root)
        tree.unlink_private(source, expected=identity(source_info))
    else:
        src_parent, src_name = tree.private_path(source)
        dst_parent, dst_name = tree.parent_fd(target, create=True)
        tree.verify()
        rename_exclusive(src_parent, src_name, dst_parent, dst_name)
        os.fsync(src_parent)
        os.fsync(dst_parent)
        if tree.sha(target, expected=identity(source_info)) != sha256:
            raise TrashError('Restore-Datei wurde nach der Veröffentlichung verändert.')


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
    from app.storage_config import load_storage_settings
    tree = ACTIVE.get()
    if tree is None:
        with DirectoryTree(workspace) as temporary:
            root = temporary.workspace / load_storage_settings()['metadata_directory_name'] / '.trash-deletions'
            temporary.directory(root, create=True, private=True)
            return root
    root = tree.workspace / load_storage_settings()['metadata_directory_name'] / '.trash-deletions'
    tree.directory(root, create=True, private=True)
    tree.private_root = root
    return root


def _atomic_json(path: Path, value: dict) -> None:
    if ACTIVE.get() is not None:
        ACTIVE.get().atomic_json(path, value)
        return
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
    from app.storage_config import load_storage_settings
    tree = ACTIVE.get()
    root = tree.workspace / load_storage_settings()['trash_directory_name']
    tree.directory(root, create=True)
    recovered = []
    for journal in sorted(parent / name for name in os.listdir(tree.directory(parent)) if name.startswith("DELETE_") and name.endswith(".json")):
        if journal.is_symlink():
            raise TrashError("Unsicheres Löschjournal.")
        tree.qualify_filesystem(tree.directory(parent))
        tree.enable_confinement()
        data = tree.read_json(journal)
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
        tree.record, tree.journal = data, journal
        if data.get("format") == 3:
            bindings = data.get("directory_identities")
            if not isinstance(bindings, dict) or "." not in bindings:
                raise TrashError("Löschjournal enthält keine belastbare Workspace-Bindung.")
            for relative, expected_id in bindings.items():
                bound = tree.workspace if relative == "." else tree.workspace / _relative(relative)
                if bound.is_relative_to(staged) and tree.info(bound) is None:
                    continue  # interrupted cleanup may already remove private dirs
                if identity(os.fstat(tree.directory(bound))) != expected_id:
                    raise TrashError("Verzeichnisidentität des Löschjournals wurde verändert.")
        for name in expected:
            _relative(name)
        if staged.is_symlink():
            raise TrashError("Unsicherer Lösch-Zwischenbestand.")
        if staged.exists():
            tree.directory(staged, private=True)
            for p, info in tree.walk(staged):
                relative = p.relative_to(staged).as_posix()
                capture_name = relative.removeprefix(".captured/")
                link_names = {item.get("link_path") for item in expected.values()}
                if stat.S_ISLNK(info.st_mode) or (not stat.S_ISDIR(info.st_mode) and (not stat.S_ISREG(info.st_mode) or (relative not in expected and relative not in link_names and not (relative.startswith(".captured/") and capture_name in expected)))):
                    raise TrashError("Fremder Eintrag im Lösch-Zwischenbestand.")
        if data.get("format") not in {2, 3} and data["state"] == "prepared":
            raise TrashError("Altes Löschjournal ohne Katalogsicherung erfordert manuelle Prüfung.")
        # Check ALL bytes before any database or filesystem recovery mutation.
        for name, item in expected.items():
            rel = _relative(name)
            candidates = [(staged, staged / rel)]
            if data.get("format") == 3:
                candidates.append((staged, staged / ".captured" / rel))
                if item.get("link_path"):
                    candidates.append((staged, staged / _relative(item["link_path"])))
            if data["state"] == "prepared":
                candidates.append((root, root / rel))
            found = 0
            for candidate_root, candidate in candidates:
                if candidate.exists() or candidate.is_symlink():
                    info = tree.info(candidate)
                    if not stat.S_ISREG(info.st_mode):
                        raise TrashError("Nicht reguläre Datei im Löschjournal.")
                    expected_identity = item.get("source_identity") if candidate.is_relative_to(root) or ".captured" in candidate.parts or candidate.name.startswith(".link-") else item.get("staged_identity")
                    allowed_identities = [item.get("source_identity"), item.get("staged_identity")] if candidate.is_relative_to(root) else [expected_identity]
                    if expected_identity is not None and identity(info) not in allowed_identities:
                        raise TrashError("Fremde Datei im Löschjournal; bleibt erhalten: " + name)
                    if tree.sha(candidate) != item["sha256"]:
                        raise TrashError("Veränderte Datei im Löschjournal: " + name)
                    found += 1
            if data.get("format") == 2 and data["state"] == "prepared":
                original_info, staged_info = tree.info(root / rel), tree.info(staged / rel)
                if original_info is not None and staged_info is not None and identity(original_info) != identity(staged_info):
                    raise TrashError("Altes Journal mit unklarer Doppelkopie; beide Dateien bleiben erhalten.")
            if data.get("format") == 3 and data["state"] == "prepared" and tree.info(root / rel) is None and tree.info(staged / ".captured" / rel) is None:
                raise TrashError("Originalidentität fehlt; unabhängige Sicherung und Journal bleiben erhalten.")
            if not found and data["state"] == "prepared":
                raise TrashError("Original und Zwischenbestand fehlen: " + name)
        if data.get("state") == "committed":
            # Also covers an interrupted/failed fsync after atomic replacement.
            # Never destroy originals until this observed commit fence is durable.
            os.fsync(tree.open_file(journal))
            _sync_dir(parent)
            for name in expected:
                capture = staged / ".captured" / _relative(name)
                if tree.info(capture) is not None:
                    tree.unlink_private(capture, expected=expected[name].get("source_identity"))
                link = expected[name].get("link_path")
                if link and tree.info(staged / _relative(link)) is not None:
                    tree.unlink_private(staged / _relative(link), expected=expected[name].get("source_identity"))
                path = staged / _relative(name)
                if tree.info(path) is not None:
                    tree.unlink_private(path, expected=expected[name].get("staged_identity"))
            _remove_empty_staging(staged)
            tree.unlink_private(journal)
            _sync_dir(parent)
            continue
        for database in databases:
            _restore_catalogue(database, ident)
        for item in reversed(data.get("files") or []):
            rel = _relative(str(item["path"]))
            src = staged / rel
            dst = root / rel
            capture = staged / ".captured" / rel
            if tree.info(capture) is not None:
                tree.parent_fd(dst, create=True)
                _return_checked(capture, dst, str(item["sha256"]), root)
            link = item.get("link_path")
            if link and tree.info(staged / _relative(link)) is not None:
                tree.parent_fd(dst, create=True)
                _return_checked(staged / _relative(link), dst, str(item["sha256"]), root)
            if tree.info(src) is not None:
                tree.parent_fd(dst, create=True)
                _sync_parents((root / rel).parent, root)
                _return_checked(src, dst, str(item["sha256"]), root)
                recovered.append(rel.as_posix())
        _remove_empty_staging(staged)
        tree.unlink_private(journal)
        _sync_dir(parent)
    return {"recovered_paths":recovered}


def _remove_empty_staging(staged: Path) -> None:
    tree = ACTIVE.get()
    if tree.info(staged) is None:
        return
    for path, info in sorted(tree.walk(staged), key=lambda item: len(item[0].parts), reverse=True):
        if stat.S_ISDIR(info.st_mode):
            tree.rmdir(path)
    tree.rmdir(staged)


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
    ACTIVE.get().qualify_filesystem(ACTIVE.get().directory(_parent(workspace)))
    ACTIVE.get().enable_confinement()
    _recover_trash_deletions(workspace, allowed_databases=databases)
    root, entries, _ = _physical_entries(workspace)
    physical = {str(e["relative_path"]) for e in entries if e["entry_type"] == "file"}
    candidates = []
    for path in sorted(relative_paths):
        rel = _relative(path)
        if path not in physical:
            raise TrashError("Datei ist nicht mehr im Papierkorb: " + path)
        source = root / rel
        tree = ACTIVE.get()
        fd = tree.open_file(source)
        candidates.append({"path":path,"sha256":digest_fd(fd),"source_identity":identity(os.fstat(fd))})
    parent = _parent(workspace)
    op_id = "DELETE_" + uuid.uuid4().hex.upper()
    staging = parent / op_id
    ACTIVE.get().directory(staging, create=True, private=True)
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
    record = {"format":3,"id":op_id,"state":"prepared","files":candidates,"databases":snapshots}
    tree = ACTIVE.get()
    record["directory_identities"] = {
        path.relative_to(tree.workspace).as_posix(): identity(os.fstat(fd))
        for path, fd in tree.directories.items() if path.is_relative_to(tree.workspace)
    }
    tree.record, tree.journal = record, journal
    _atomic_json(journal,record)
    token = _PURGE_SNAPSHOTS.set({db["path"]: db["snapshot"] for db in snapshots})
    try:
        for item in candidates:
            rel = _relative(item["path"])
            target = staging / rel
            ACTIVE.get().parent_fd(target, create=True)
            source = root / rel
            if ACTIVE.get().sha(source, expected=item["source_identity"]) != item["sha256"]:
                raise TrashError("Datei vor dem Löschen verändert: " + item["path"])
            _move_checked(source,target,item["sha256"],durable_root=parent)
        for db in databases:
            ACTIVE.get().verify()
            for item in candidates:
                rel = _relative(item["path"])
                if ACTIVE.get().sha(staging / rel, expected=item["staged_identity"]) != item["sha256"] or ACTIVE.get().sha(staging / ".captured" / rel, expected=item["source_identity"]) != item["sha256"]:
                    raise TrashError("Dateiversion vor Datenbankabschluss verändert; weitere Löschung gesperrt.")
            _purge_selected(Path(db),[item["path"] for item in candidates])
        # Once the DB no longer references the files, the deletion is durable.
        record["state"] = "committed"
        _atomic_json(journal,record)
        _recover_trash_deletions(workspace, allowed_databases=databases)
        # Public empty parent names remain externally mutable. Never rmdir a
        # name based on a previous check; harmless empty directories remain.
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
