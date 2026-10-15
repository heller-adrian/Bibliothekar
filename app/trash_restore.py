"""Sichere Wiederherstellung von Dateien aus dem gemeinsamen Papierkorb.

Die kanonischen Tagesordner werden mit derselben Zeitlogik berechnet
wie beim regulären zentralen Kamerabestand.
"""
from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
import stat
import uuid
from typing import Any, Iterable

from app.database import database_connection
from app.free_stock_layout import FreeStockLayoutError, canonical_free_directory
from app.storage_config import storage_paths
from app.trash import TrashError, _physical_entries, _sha256_file, reconcile_trash_inventory


def _relative(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TrashError("Ungültige Dateiauswahl.")
    path = Path(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise TrashError("Unsicherer Dateipfad.")
    return path


def _source(root: Path, relative: Path) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode):
            raise TrashError("Symbolische Links dürfen nicht wiederhergestellt werden.")
    if not stat.S_ISREG(os.lstat(current).st_mode):
        raise TrashError("Nur reguläre Dateien können wiederhergestellt werden.")
    return current


def _ensure_target_parent(root: Path, relative: Path) -> None:
    if not root.is_dir():
        raise TrashError("Der zentrale Tagesbestand ist nicht erreichbar.")
    current = root
    for part in relative.parent.parts:
        if part == ".":
            continue
        current = current / part
        if current.is_symlink():
            raise TrashError("Symbolischer Link im Zielpfad: " + str(current))
        current.mkdir(exist_ok=True)
        if not current.is_dir():
            raise TrashError("Ziel ist kein Verzeichnis: " + str(current))


def _move_checked(source: Path, target: Path, sha256: str) -> None:
    """No overwrite, SHA check before removing source; EXDEV copy is exclusive."""
    created = False
    try:
        try:
            os.link(source, target, follow_symlinks=False)
            created = True
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(target, flags, 0o640)
            created = True
            with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
        if _sha256_file(target) != sha256:
            raise TrashError("Prüfsummenfehler: " + source.name)
        with target.open("rb") as handle:
            os.fsync(handle.fileno())
        from app.trash_selective import _sync_parents, _sync_dir
        # Sync every new target ancestor before removing the trash entry.
        _sync_parents(target.parent, Path(os.path.commonpath((source, target))))
        source.unlink()
        _sync_dir(source.parent)
    except Exception:
        # A directory-fsync error can occur AFTER source.unlink(). Never
        # remove the surviving copy merely because the move raised.
        if created and source.is_file() and not source.is_symlink() and _sha256_file(source) == sha256:
            target.unlink(missing_ok=True)
        raise


def _databases(values: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for value in values:
        path = Path(value).resolve(strict=False)
        if path.is_file() and path not in result:
            result.append(path)
    if not result:
        raise TrashError("Keine Bibliotheksdatenbank erreichbar.")
    return result


# Selection and canonical-target validation follows below.

def _plan_restore(
    database_paths: Iterable[Path], workspace_root: Path,
    *, relative_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Restore all regular files or just selected paths to daily stock."""
    databases = _databases(database_paths)
    for database in databases:
        reconcile_trash_inventory(database, workspace_root)
    root, entries, _ = _physical_entries(workspace_root)
    files = {str(e["relative_path"]) for e in entries if e["entry_type"] == "file"}
    if relative_paths is None:
        selection = sorted(files)
    else:
        if not isinstance(relative_paths, list) or any(
            not isinstance(v, str) for v in relative_paths
        ) or len(set(relative_paths)) != len(relative_paths):
            raise TrashError("Ungültige oder doppelte Dateiauswahl.")
        selection = sorted(relative_paths)
    if not selection:
        raise TrashError("Keine Dateien zum Wiederherstellen vorhanden.")
    if len(selection) > 100000:
        raise TrashError("Zu viele Dateien in einem Vorgang.")

    central = storage_paths(workspace_root)["backup_root"]
    if not central.is_dir() or central.is_symlink():
        raise TrashError("Der zentrale Tagesbestand ist nicht sicher erreichbar.")
    plans: list[dict[str, Any]] = []
    targets: set[str] = set()
    for name in selection:
        rel = _relative(name)
        if name not in files:
            raise TrashError("Datei nicht mehr im Papierkorb: " + name)
        src = _source(root, rel)
        size, sha = src.stat().st_size, _sha256_file(src)
        goals: set[str] = set()
        identities: set[tuple[str, str]] = set()
        linked: list[tuple[Path, dict[str, Any]]] = []

        # Later stage
        for database in databases:
            with database_connection(database) as c:
                matches = [dict(r) for r in c.execute(
                    "SELECT f.id,f.job_id,f.family_id,f.original_relative_path,f.size_bytes,"
                    " COALESCE(f.sha256_current,f.sha256_original,'') AS sha256,"
                    " COALESCE(ff.selected_capture_time,f.selected_capture_time,'') AS capture_time"
                    " FROM files f LEFT JOIN file_families ff ON ff.id=f.family_id"
                    " WHERE f.current_root_kind='trash' AND f.current_relative_path=?",
                    (name,),
                ).fetchall()]
                if len(matches) > 1:
                    raise TrashError("Mehrdeutiger Katalogeintrag: " + name)
                if not matches:
                    continue
                row = matches[0]
                if size != int(row["size_bytes"]) or sha != str(row["sha256"]):
                    raise TrashError("Größe oder Prüfsumme abweichend: " + name)
                if row["family_id"] is None:
                    raise TrashError("Datei ohne Kamerafamilie: " + name)
                assigned = c.execute(
                    "SELECT 1 FROM event_assignments a JOIN events e ON e.id=a.event_id "
                    "WHERE a.family_id=? AND e.status IN "
                    "('draft','planned','applied','archived') LIMIT 1",
                    (row["family_id"],),
                ).fetchone()
                if assigned:
                    raise TrashError("Noch einem Ereignis zugeordnet: " + name)
                capture = str(row["capture_time"] or "")
                if not capture:
                    raise TrashError("Aufnahmezeit unbekannt: " + name)
                try:
                    directory = canonical_free_directory(c, capture, physical=True)
                except FreeStockLayoutError as error:
                    raise TrashError(str(error) + " (" + name + ")") from error
                goals.add((directory / src.name).as_posix())
                identities.add((str(row["job_id"]), str(row["original_relative_path"])))
                linked.append((database, row))

        if not linked:
            raise TrashError("Nicht katalogisierte Datei: " + name)
        if len(goals) != 1 or len(identities) != 1:
            raise TrashError("Bibliotheksübergreifend uneindeutige Zuordnung: " + name)
        target_relative = next(iter(goals))
        target = central / _relative(target_relative)
        if target_relative in targets:
            raise TrashError("Zwei Dateien mit demselben Tagesziel: " + target_relative)
        targets.add(target_relative)
        if target.exists() or target.is_symlink():
            raise TrashError("Zieldatei existiert bereits: " + target_relative)
        plans.append(dict(source=src, relative=name, target=target,
                          target_relative=target_relative, sha256=sha, rows=linked))

    return databases, root, central, plans


def _restore_parent(workspace: Path) -> Path:
    parent = storage_paths(workspace)["metadata_root"] / ".trash-restores"
    if parent.is_symlink():
        raise TrashError("Unsicherer Restore-Journalordner.")
    parent.mkdir(parents=True, exist_ok=True)
    return parent


def _restore_journal(workspace: Path, operation_id: str) -> Path:
    if not operation_id or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in operation_id):
        raise TrashError("Ungültige Restore-Identität.")
    return _restore_parent(workspace) / (operation_id + ".json")


def _load_restore(journal: Path, workspace: Path, databases: list[Path]):
    if journal.is_symlink() or not journal.is_file():
        raise TrashError("Unsicheres Restore-Journal.")
    data = json.loads(journal.read_text())
    root = storage_paths(workspace)["trash_root"]
    central = storage_paths(workspace)["backup_root"]
    if data.get("operation_id") not in {None, journal.stem}:
        raise TrashError("Restore-Journal besitzt eine falsche Identität.")
    if data.get("format") != 1 or data.get("state") not in {"prepared", "rolling_back", "completed"} or not data.get("plans"):
        raise TrashError("Ungültiger Restore-Plan.")
    allowed = {str(p.resolve()): p for p in databases}
    plans = []
    for item in data["plans"]:
        plan = dict(item)
        plan["source"] = root / _relative(plan["relative"])
        plan["target"] = central / _relative(plan["target_relative"])
        if len(plan["sha256"]) != 64:
            raise TrashError("Restore ohne Prüfsumme.")
        linked = []
        for db, row in plan["rows"]:
            if db not in allowed or not allowed[db].is_file():
                raise TrashError("Restore-Datenbank nicht registriert.")
            info = allowed[db].stat()
            if [info.st_dev, info.st_ino] != data["databases"][db]:
                raise TrashError("Restore-Datenbank wurde ersetzt.")
            linked.append((allowed[db], row))
        plan["rows"] = linked
        plans.append(plan)
    return data, root, central, plans


def _preflight_restore(plans, root, central):
    # Validate the ENTIRE plan and every catalogue before the first mutation.
    for plan in plans:
        found = False
        for base, rel in ((root, plan["relative"]), (central, plan["target_relative"])):
            path = base / _relative(rel)
            if path.exists() or path.is_symlink():
                path = _source(base, _relative(rel))
                if _sha256_file(path) != plan["sha256"]:
                    raise TrashError("Restore-Datei besitzt fremden Inhalt: " + rel)
                found = True
        if not found:
            raise TrashError("Restore ohne gesicherte Datei.")
        for database, row in plan["rows"]:
            with database_connection(database) as c:
                current = c.execute("SELECT *,COALESCE(sha256_current,sha256_original,'') AS expected_sha FROM files WHERE id=?", (row["id"],)).fetchone()
                if current is None or any(current[key] != row[key] for key in ("job_id", "family_id", "original_relative_path", "size_bytes")) or current["expected_sha"] != plan["sha256"] or (current["current_root_kind"], current["current_relative_path"]) not in {("trash", plan["relative"]), ("shared_workspace", plan["target_relative"])}:
                    raise TrashError("Restore-Katalog wurde verändert.")


def _rollback_restore(plans, root, central):
    _preflight_restore(plans, root, central)
    for plan in reversed(plans):
        if plan["target"].exists():
            if plan["source"].exists():
                plan["target"].unlink()
                from app.trash_selective import _sync_dir
                _sync_dir(plan["target"].parent)
            else:
                _ensure_target_parent(root, _relative(plan["relative"]))
                _move_checked(plan["target"], plan["source"], plan["sha256"])


def restore_trash_files(database_paths: Iterable[Path], workspace_root: Path, *,
                        relative_paths: list[str] | None = None,
                        operation_id: str | None = None) -> dict[str, Any]:
    from app.trash_selective import _operation_lock, _atomic_json, _sync_dir
    # Shared deletion/restore lock also protects cross-process recovery.
    with _operation_lock(workspace_root):
        databases = _databases(database_paths)
        from app.trash_import import protected_trash_paths
        reserved = protected_trash_paths(None, workspace_root, ignore_job_id=operation_id)
        selected = {_relative(p).as_posix() for p in relative_paths} if relative_paths is not None else reserved
        if reserved.intersection(selected):
            raise TrashError("Dateien gehören bereits zu einem anderen Wiederherstellungsauftrag.")
        journal = _restore_journal(workspace_root, operation_id or uuid.uuid4().hex)
        if not journal.exists():
            databases, root, central, plans = _plan_restore(databases, workspace_root, relative_paths=relative_paths)
            data = dict(format=1, state="prepared", operation_id=operation_id,
                        databases={str(db): [db.stat().st_dev, db.stat().st_ino] for db in databases},
                        plans=[{k: ([[str(db), row] for db, row in value] if k == "rows" else value)
                                for k, value in plan.items() if k not in {"source", "target"}}
                               for plan in plans])
            _atomic_json(journal, data)
            _sync_dir(journal.parent.parent)
        data, root, central, plans = _load_restore(journal, workspace_root, databases)
        if relative_paths is not None and sorted(relative_paths) != sorted(p["relative"] for p in plans):
            raise TrashError("Restore-Auswahl widerspricht dem Journal.")
        _preflight_restore(plans, root, central)
        if data["state"] == "rolling_back":
            _rollback_restore(plans, root, central)
            journal.unlink()
            _sync_dir(journal.parent)
            return restore_trash_files(databases, workspace_root, relative_paths=relative_paths, operation_id=operation_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        committed = []
        try:
            for plan in plans:
                _ensure_target_parent(central, _relative(plan["target_relative"]))
                if plan["source"].exists():
                    if plan["target"].exists():
                        # Interrupted link/unlink: both hashes passed preflight.
                        with plan["target"].open("rb") as h: os.fsync(h.fileno())
                        plan["source"].unlink()
                        _sync_dir(plan["source"].parent)
                    else:
                        _move_checked(plan["source"], plan["target"], plan["sha256"])
            for plan in plans:
                for database, row in plan["rows"]:
                    with database_connection(database) as c:
                        c.execute("BEGIN IMMEDIATE")
                        current = c.execute("SELECT current_root_kind,current_relative_path FROM files WHERE id=?", (row["id"],)).fetchone()
                        if tuple(current) == ("shared_workspace", plan["target_relative"]):
                            continue
                        changed = c.execute("UPDATE files SET current_root_kind='shared_workspace',current_relative_path=?,updated_at=? WHERE id=? AND current_root_kind='trash' AND current_relative_path=?", (plan["target_relative"], timestamp, row["id"], plan["relative"]))
                        if changed.rowcount != 1:
                            raise TrashError("Datei inzwischen geändert: " + plan["relative"])
                        c.execute("DELETE FROM central_missing_file_observations WHERE file_id=?", (row["id"],))
                        c.execute("DELETE FROM event_missing_file_observations WHERE file_id=?", (row["id"],))
                        c.execute("INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at) VALUES (?,'trash_file_restored','file',?,?,?)", (row["job_id"], str(row["id"]), json.dumps(dict(source=plan["relative"], target=plan["target_relative"], sha256=plan["sha256"]), ensure_ascii=False, sort_keys=True), timestamp))
                    committed.append((database, int(row["id"]), plan["relative"]))
            data["state"] = "completed"
            _atomic_json(journal, data)
        except Exception as error:
            # Keep committed work for forward replay. Before any DB commit, the
            # legacy exception rollback remains safe and is itself journalled.
            if not committed and not any(_catalogue_restored(p) for p in plans):
                data["state"] = "rolling_back"
                _atomic_json(journal, data)
                _rollback_restore(plans, root, central)
                journal.unlink()
                _sync_dir(journal.parent)
            raise TrashError("Wiederherstellung fehlgeschlagen; Journal zur Fortsetzung erhalten: " + str(error)) from error
        if operation_id is None:
            journal.unlink()
            _sync_dir(journal.parent)
        return {"restored_file_count": len(plans), "restored_paths": [p["target_relative"] for p in plans]}


def _catalogue_restored(plan):
    for database, row in plan["rows"]:
        with database_connection(database) as c:
            found = c.execute("SELECT current_root_kind FROM files WHERE id=?", (row["id"],)).fetchone()
            if found and found[0] == "shared_workspace": return True
    return False


def recover_trash_restores(workspace_root: Path, *, allowed_databases: set[Path]) -> int:
    from app.trash_selective import _operation_lock, _sync_dir
    recovered = 0
    with _operation_lock(workspace_root):
        for journal in sorted(_restore_parent(workspace_root).glob("*.json")):
            data, root, central, plans = _load_restore(journal, workspace_root, _databases(allowed_databases))
            if data["state"] == "completed" and data.get("operation_id"):
                from app.trash_import import stage_parent
                request = stage_parent(workspace_root) / (str(data["operation_id"]) + ".json")
                if request.is_symlink():
                    raise TrashError("Unsicheres Restore-Auftragsjournal.")
                if request.is_file() and json.loads(request.read_text()).get("status") == "known_restored":
                    journal.unlink(); _sync_dir(journal.parent)
                    continue
            if data["state"] == "rolling_back":
                _rollback_restore(plans, root, central)
                journal.unlink(); _sync_dir(journal.parent)
            else:
                restore_trash_files(allowed_databases, workspace_root, relative_paths=[p["relative"] for p in plans], operation_id=journal.stem)
                if not data.get("operation_id"):
                    journal.unlink(); _sync_dir(journal.parent)
            recovered += 1
    return recovered
