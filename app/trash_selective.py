"""Crash-recoverable selected-file trash deletion (no symlink traversal)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import uuid
from typing import Iterable

from app.database import database_connection
from app.storage_config import storage_paths
from app.trash import TrashError, _physical_entries, _sha256_file, trash_root
from app.trash_restore import _relative, _source, _move_checked, _ensure_target_parent


def _parent(workspace: Path) -> Path:
    root = storage_paths(workspace)["metadata_root"] / ".trash-deletions"
    if root.is_symlink():
        raise TrashError("Papierkorb-Löschjournal darf kein Symlink sein.")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve(strict=True)


def _atomic_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def recover_trash_deletions(workspace: Path) -> dict:
    """Return uncommitted staged originals without losing any data."""
    parent = _parent(workspace)
    root = trash_root(workspace)
    recovered = []
    for journal in sorted(parent.glob("DELETE_*.json")):
        if journal.is_symlink():
            raise TrashError("Unsicheres Löschjournal.")
        data = json.loads(journal.read_text(encoding="utf-8"))
        if data.get("state") == "committed":
            shutil.rmtree(parent / str(data["id"]), ignore_errors=True)
            journal.unlink()
            continue
        staged = parent / str(data["id"])
        for item in reversed(data.get("files") or []):
            rel = _relative(str(item["path"]))
            src = staged / rel
            dst = root / rel
            if src.exists():
                if src.is_symlink() or dst.exists() or dst.is_symlink():
                    raise TrashError("Löschjournal kann wegen Dateikonflikt nicht wiederhergestellt werden: " + rel.as_posix())
                _ensure_target_parent(root,rel)
                _move_checked(src,dst,str(item["sha256"]))
                recovered.append(rel.as_posix())
        shutil.rmtree(staged, ignore_errors=True)
        journal.unlink()
    return {"recovered_paths":recovered}


def _purge_selected(db: Path, paths: list[str]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
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
    if not isinstance(relative_paths,list) or not relative_paths or any(
        not isinstance(p,str) for p in relative_paths
    ) or len(set(relative_paths))!=len(relative_paths):
        raise TrashError("Ungültige Lösch-Auswahl.")
    recover_trash_deletions(workspace)
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
    record = {"id":op_id,"state":"prepared","files":candidates}
    _atomic_json(journal,record)
    moved = 0
    try:
        for item in candidates:
            rel = _relative(item["path"])
            target = staging / rel
            _ensure_target_parent(staging,rel)
            source = _source(root,rel)
            if _sha256_file(source) != item["sha256"]:
                raise TrashError("Datei vor dem Löschen verändert: " + item["path"])
            _move_checked(source,target,item["sha256"])
            moved += 1
        for db in databases:
            _purge_selected(Path(db),[item["path"] for item in candidates])
        # Once the DB no longer references the files, the deletion is durable.
        record["state"] = "committed"
        journal.unlink()
        _atomic_json(journal,record)
        shutil.rmtree(staging)
        journal.unlink(missing_ok=True)
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
            recover_trash_deletions(workspace)
        except Exception:
            pass
        raise
