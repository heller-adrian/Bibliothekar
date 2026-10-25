"""Safely stage previously unknown trash files for the regular camera import worker.

The original trash files remain until a completed, SHA-verified import confirms
their successful transfer. The manifest is OUTSIDE the import source tree.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import uuid

from app.database import create_job, get_job, database_connection
from app.source_filter import should_ignore_source_relative
from app.storage_config import storage_paths
from app.trash import TrashError, _sha256_file, trash_root, serialized_trash_operation
from app.trash_restore import _relative, _source


def stage_parent(workspace_root: Path) -> Path:
    root = storage_paths(workspace_root)["metadata_root"]
    parent = root / ".trash-import"
    if parent.is_symlink():
        raise TrashError("Unsicherer Import-Staging-Ordner.")
    parent.mkdir(parents=True, exist_ok=True)
    return parent.resolve(strict=True)


def _manifest(parent: Path, job_id: str) -> Path:
    if not job_id.startswith("TRASH_IMPORT_") or "/" in job_id:
        raise TrashError("Ungültiger Papierkorbauftrag.")
    return parent / (job_id + ".json")


@serialized_trash_operation("workspace_root")
def stage_trash_import(
    database_path: Path,
    workspace_root: Path,
    relative_paths: list[str],
) -> dict:
    if not relative_paths or len(relative_paths) != len(set(relative_paths)):
        raise TrashError("Ungültige Papierkorb-Auswahl.")
    if set(_relative(v).as_posix() for v in relative_paths).intersection(protected_trash_paths(None, workspace_root)):
        raise TrashError("Diese Dateien werden bereits wiederhergestellt.")
    root = trash_root(workspace_root)
    from app.trash_restore import assert_restore_paths_available
    assert_restore_paths_available(workspace_root,relative_paths)
    parent = stage_parent(workspace_root)
    # Avoid two live imports of the same file if a user clicks twice.
    wanted = set(relative_paths)
    for manifest in parent.glob("TRASH_IMPORT_*.json"):
        try:
            state = json.loads(manifest.read_text(encoding="utf-8"))
            job = get_job(database_path, str(state.get("job_id") or ""))
            if job and job.get("state") not in {"completed", "failed", "cancelled"}:
                if wanted.intersection(state.get("relative_paths") or []):
                    raise TrashError("Diese Dateien werden bereits wiederhergestellt.")
        except (OSError, ValueError, json.JSONDecodeError):
            raise TrashError("Ein Papierkorb-Importjournal ist nicht lesbar.")
    job_id = "TRASH_IMPORT_" + datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:12].upper()
    stage = parent / job_id
    stage.mkdir(mode=0o700)
    copies = []
    try:
        for value in sorted(wanted):
            rel = _relative(value)
            if should_ignore_source_relative(rel):
                raise TrashError("Verwaltungsdatei kann nicht als Aufnahme importiert werden: " + value)
            source = _source(root, rel)
            before = source.stat()
            digest = _sha256_file(source)
            target = stage / rel
            current = stage
            for part in rel.parts[:-1]:
                current = current / part
                current.mkdir(exist_ok=True)
                if current.is_symlink():
                    raise TrashError("Unsicherer Import-Zielpfad.")
            with source.open("rb") as inp, target.open("xb") as out:
                shutil.copyfileobj(inp, out, 1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
            after = source.stat()
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
            ) or target.stat().st_size != before.st_size or _sha256_file(target) != digest:
                raise TrashError("Datei während der Vorbereitung verändert: " + value)
            copies.append({"relative_path":value,"sha256":digest,"size_bytes":before.st_size})
        record = {"job_id":job_id,"relative_paths":sorted(wanted),"files":copies}
        from app.trash_selective import _atomic_json, _sync_dir
        _atomic_json(_manifest(parent,job_id), record)
        _sync_dir(parent.parent)
        job = create_job(
            database_path, job_id=job_id, kind="sd_import", trigger_type="manual",
            source_path=str(stage), working_path=str(storage_paths(workspace_root)["backup_root"]),
            operation="trash_import", source_volume_label="Aus Papierkorb",
        )
        return {"job_id":job_id,"queued_file_count":len(copies),"job":job}
    except Exception as error:
        if _manifest(parent,job_id).exists():
            raise TrashError("Wiederherstellung unterbrochen; Reservierungsjournal und Originale bleiben zur Klärung erhalten.") from error
        shutil.rmtree(stage, ignore_errors=True)
        raise


@serialized_trash_operation("workspace_root")
def cleanup_successful_trash_import(
    workspace_root: Path,
    job_id: str,
    imported_entries: list[dict],
) -> dict:
    """Remove source originals ONLY for imported and verified files.

    On an interrupted cleanup the manifest is retained for audit, and the
    remainder is still in the trash. Never delete unimported or altered files.
    """
    parent = stage_parent(workspace_root)
    record_path = _manifest(parent, job_id)
    if not record_path.is_file() or record_path.is_symlink():
        raise TrashError("Papierkorb-Importjournal fehlt.")
    data = json.loads(record_path.read_text(encoding="utf-8"))
    if str(data.get("job_id")) != job_id:
        raise TrashError("Papierkorb-Importjournal passt nicht zum Auftrag.")
    from app.trash_restore import assert_restore_paths_available
    assert_restore_paths_available(workspace_root,[str(item['relative_path']) for item in data.get('files') or []])
    imported = {
        (str(item.get("relative_path") or ""),str(item.get("sha256") or ""))
        for item in imported_entries
    }
    root = trash_root(workspace_root)
    removed = 0
    skipped = []
    for item in data.get("files") or []:
        rel = str(item["relative_path"])
        checksum = str(item["sha256"])
        if (rel,checksum) not in imported:
            skipped.append(rel)
            continue
        try:
            original = _source(root,_relative(rel))
            if original.stat().st_size != int(item["size_bytes"]) or _sha256_file(original) != checksum:
                skipped.append(rel)
                continue
            original.unlink()
            removed += 1
        except (OSError,TrashError):
            skipped.append(rel)
    from app.trash_selective import _atomic_json
    _atomic_json(record_path, {**data,"cleanup_completed":True,"skipped":skipped})
    shutil.rmtree(parent / job_id,ignore_errors=True)
    return {"removed_file_count":removed,"skipped":skipped}


@serialized_trash_operation("workspace_root")
def queue_trash_restore(
    database_path: Path, workspace_root: Path, relative_paths: list[str],
) -> dict:
    """Accept a durable restore request without hashing/copying its contents.

    Both known and unknown camera files use this queue. All actual mutation is
    performed by the import worker, never by the HTTP request.
    """
    if (not isinstance(relative_paths,list) or not relative_paths
        or any(not isinstance(v,str) for v in relative_paths)
        or len(relative_paths)!=len(set(relative_paths))):
        raise TrashError("Ungültige Papierkorb-Auswahl.")
    from app.trash_restore import assert_restore_paths_available
    assert_restore_paths_available(workspace_root,relative_paths)
    parent=stage_parent(workspace_root)
    root=trash_root(workspace_root)
    selected=sorted(relative_paths)
    for value in selected:
        rel=_relative(value)
        _source(root,rel)  # validates containment, regular file, no symlinks
        if should_ignore_source_relative(rel):
            raise TrashError("Verwaltungsdatei kann nicht als Aufnahme wiederhergestellt werden: "+value)
    selected = sorted(_relative(v).as_posix() for v in selected)
    if len(selected) != len(set(selected)):
        raise TrashError("Auswahl enthält denselben Dateipfad mehrfach.")
    if set(selected).intersection(protected_trash_paths(None, workspace_root)):
        raise TrashError("Diese Dateien werden bereits wiederhergestellt oder benötigen manuelle Klärung.")
    job_id="TRASH_IMPORT_"+datetime.now().strftime("%Y%m%d_%H%M%S_")+uuid.uuid4().hex[:12].upper()
    record={"job_id":job_id,"relative_paths":selected,"files":[],
            "status":"queued","schema_version":2}
    journal=_manifest(parent,job_id)
    from app.trash_selective import _atomic_json, _sync_dir
    try:
        # Durable intent precedes the independent SQLite commit. An orphaned
        # intent after a crash is protective evidence, never an empty claim.
        _atomic_json(journal, record)
        _sync_dir(parent.parent)
        job=create_job(
            database_path,job_id=job_id,kind="sd_import",trigger_type="manual",
            source_path=str(parent/job_id),
            working_path=str(storage_paths(workspace_root)["backup_root"]),
            operation="trash_import",source_volume_label="Aus Papierkorb",
        )
    except Exception as error:
        if journal.exists() or journal.is_symlink():
            raise TrashError("Wiederherstellungsauftrag unterbrochen; Reservierungsjournal und Originale bleiben zur Klärung erhalten.") from error
        raise
    return {"job_id":job_id,"queued_file_count":len(selected),"job":job}


@serialized_trash_operation("workspace_root")
def prepare_queued_trash_restore(
    database_path: Path,
    all_databases: list[Path],
    workspace_root: Path,
    job_id: str,
) -> dict:
    """Stage files inside the worker and restore known files in place.

    For every new file, the original is retained until successful media import.
    Known files retain their existing family and backup provenance.
    """
    parent=stage_parent(workspace_root)
    journal=_manifest(parent,job_id)
    if not journal.is_file() or journal.is_symlink():
        raise TrashError("Papierkorb-Importjournal fehlt.")
    data=json.loads(journal.read_text(encoding="utf-8"))
    if data.get("job_id")!=job_id or not isinstance(data.get("relative_paths"),list):
        raise TrashError("Ungültiges Papierkorb-Importjournal.")
    if data.get("status") == "known_restored":
        _finish_known_restore(workspace_root, job_id)
        return {"unknown_file_count":len(data.get("files") or []), "known_restored_count":int(data.get("known_restored_count") or 0), "known_paths":list(data.get("known_paths") or [])}
    if data.get("status") == "staged":
        from app.trash_restore import restore_trash_files
        from app.trash_selective import _atomic_json
        known = list(data.get("known_paths") or [])
        restored = restore_trash_files(sorted(all_databases), workspace_root, relative_paths=known, operation_id=job_id) if known else {"restored_file_count":0}
        data.update(status="known_restored", known_restored_count=restored["restored_file_count"])
        _atomic_json(journal, data)
        _finish_known_restore(workspace_root, job_id)
        return {"unknown_file_count":len(data.get("files") or []), "known_restored_count":restored["restored_file_count"], "known_paths":known}
    root=trash_root(workspace_root)
    known=[]
    unknown=[]
    for value in data["relative_paths"]:
        rel=_relative(value)
        _source(root,rel)
        if should_ignore_source_relative(rel):
            raise TrashError("Verwaltungsdatei im Wiederherstellungsauftrag.")
        linked=False
        for db in all_databases:
            with database_connection(db) as conn:
                if conn.execute(
                    "SELECT 1 FROM files WHERE current_root_kind='trash' "
                    "AND current_relative_path=? LIMIT 1",(value,)
                ).fetchone():
                    linked=True
                    break
        (known if linked else unknown).append(value)
    stage=parent/job_id
    if stage.exists():
        if stage.is_symlink() or not stage.is_dir():
            raise TrashError("Ungültiger Papierkorb-Zwischenbestand.")
    else:
        stage.mkdir(mode=0o700)
    copies=[]
    for value in unknown:
        rel=_relative(value)
        source=_source(root,rel)
        before=source.stat()
        digest=_sha256_file(source)
        target=stage/rel
        current=stage
        for part in rel.parts[:-1]:
            current=current/part
            current.mkdir(exist_ok=True)
            if current.is_symlink():
                raise TrashError("Unsicherer Zwischenbestand.")
        if target.exists() or target.is_symlink():
            if (target.is_symlink() or not target.is_file()
                or target.stat().st_size!=before.st_size
                or _sha256_file(target)!=digest):
                raise TrashError("Konflikt im Papierkorb-Zwischenbestand.")
        else:
            with source.open("rb") as inp,target.open("xb") as out:
                shutil.copyfileobj(inp,out,1024*1024)
                out.flush()
                os.fsync(out.fileno())
        after=source.stat()
        if ((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
            != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
            or _sha256_file(target)!=digest):
            raise TrashError("Datei wurde während der Vorbereitung verändert: "+value)
        copies.append({"relative_path":value,"sha256":digest,
                       "size_bytes":before.st_size})
    # Persist what has been staged before the known moves; any interrupted
    # attempt still has its original unknown files for a safe audit.
    data={**data,"files":copies,"known_paths":known,
          "status":"staged"}
    from app.trash_selective import _atomic_json
    _atomic_json(journal, data)
    restored={"restored_file_count":0,"restored_paths":[]}
    if known:
        from app.trash_restore import restore_trash_files
        restored=restore_trash_files(
            sorted(all_databases),workspace_root,relative_paths=known,operation_id=job_id
        )
    data={**data,"known_restored_count":int(restored.get("restored_file_count",0)),
          "status":"known_restored"}
    from app.trash_selective import _atomic_json
    _atomic_json(journal, data)
    _finish_known_restore(workspace_root, job_id)
    return {"unknown_file_count":len(unknown),
            "known_restored_count":int(restored.get("restored_file_count",0)),
            "known_paths":known}


def _finish_known_restore(workspace_root: Path, job_id: str) -> None:
    from app.trash_restore import _restore_journal
    from app.trash_selective import _sync_dir
    path = _restore_journal(workspace_root, job_id)
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text()).get('state') != 'completed':
            raise TrashError('Unvollständiges Restore-Journal bleibt erhalten.')
        path.unlink()
        _sync_dir(path.parent)


def _completed_cleanup(database_path: Path | None, workspace_root: Path, job_id: str, skipped: list[str]) -> bool:
    from contextlib import closing
    import sqlite3
    databases = {Path(database_path)} if database_path is not None else set()
    registry = Path(os.environ.get("KAMERA_REGISTRY_DATABASE",
        str(Path(os.environ.get("KAMERA_DATABASE_DIR", "/database"))/"bibliothekar-global.sqlite3")))
    if registry.is_file():
        try:
            with closing(sqlite3.connect(registry.absolute().as_uri()+"?mode=ro", uri=True)) as connection:
                rows = connection.execute("SELECT database_path,workspace_root FROM libraries WHERE COALESCE(is_registered,1)=1").fetchall()
            databases.update(Path(db) for db, workspace in rows
                             if Path(workspace).resolve() == workspace_root.resolve())
        except (OSError, sqlite3.Error, ValueError, TypeError):
            return False
    found = False
    for database in databases:
        # Never create a missing database while deciding whether to release.
        if not database.is_file():
            return False
        try:
            with closing(sqlite3.connect(database.absolute().as_uri()+"?mode=ro", uri=True)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute("SELECT operation,state,source_path,result_json FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                continue
            result = json.loads(row["result_json"] or "{}")
            cleanup = result.get("trash_source_cleanup", {}) if isinstance(result, dict) else {}
            if not isinstance(cleanup, dict):
                return False
            if (row["operation"] != "trash_import" or row["state"] != "completed"
                    or row["source_path"] != str(stage_parent(workspace_root)/job_id)
                    or cleanup.get("skipped") != skipped or "warning" in cleanup):
                return False
            found = True
        except (OSError, sqlite3.Error, ValueError, TypeError):
            return False
    return found


@serialized_trash_operation("workspace_root")
def protected_trash_paths(database_path: Path | None, workspace_root: Path, *, ignore_job_id: str | None = None) -> set[str]:
    """Return files reserved by queued/running restores, including staging."""
    from app.trash_restore import restore_reservations
    protected={path for record in restore_reservations(workspace_root, exclude=ignore_job_id) for path in record['relative_paths']}
    for journal in stage_parent(workspace_root).glob("TRASH_IMPORT_*.json"):
        if journal.is_symlink() or not journal.is_file():
            raise TrashError("Unsicheres Papierkorb-Importjournal.")
        try:
            data=json.loads(journal.read_text(encoding="utf-8"))
            paths=data["relative_paths"]
            if data.get("job_id") != journal.stem or not isinstance(paths,list) or not paths:
                raise ValueError("Ungültiger Reservierungsnachweis")
            canonical={_relative(p).as_posix() for p in paths}
            completed = data.get("cleanup_completed") is True
            known_done = data.get("status") == "known_restored"
            if completed or (known_done and data.get("files") == []):
                # Release only a complete partition of the original intent.
                # Missing cleanup fields are uncertainty, never an empty claim.
                files = data["files"]
                known = data.get("known_paths", []) if known_done else []
                if not isinstance(files, list) or not isinstance(known, list):
                    raise ValueError("Unvollständiger Abschlussnachweis")
                staged = {_relative(item["relative_path"]).as_posix() for item in files}
                restored = {_relative(p).as_posix() for p in known}
                if staged.intersection(restored) or staged | restored != canonical:
                    raise ValueError("Abschluss deckt Reservierung nicht vollständig ab")
                if completed:
                    skipped = data["skipped"]
                    if not isinstance(skipped, list):
                        raise ValueError("Unvollständiger Bereinigungsnachweis")
                    canonical = {_relative(p).as_posix() for p in skipped}
                    if not canonical.issubset(staged):
                        raise ValueError("Unbekannter Bereinigungsrest")
                    if _completed_cleanup(database_path, workspace_root, journal.stem, skipped):
                        canonical = set()
                else:
                    canonical = set()
            if journal.stem != ignore_job_id:
                protected.update(canonical)
        except (OSError,ValueError,KeyError,TypeError) as error:
            raise TrashError("Ein Papierkorb-Reservierungsjournal ist nicht eindeutig lesbar; Löschung gesperrt.") from error
    return protected


@serialized_trash_operation("workspace_root")
def resume_safe_queued_trash_restores(database_path: Path, workspace_root: Path) -> int:
    """Requeue only jobs interrupted before they modified any catalogue rows.

    Work begun inside the import pipeline is kept interrupted for manual audit;
    source originals remain in the trash. Do not auto-repeat a partial import.
    """
    parent=stage_parent(workspace_root)
    revived=0
    with database_connection(database_path) as conn:
        rows=conn.execute(
            "SELECT id FROM jobs WHERE operation='trash_import' AND state='interrupted'"
        ).fetchall()
        for row in rows:
            jid=str(row["id"])
            path=_manifest(parent,jid)
            if not path.is_file() or path.is_symlink():
                continue
            data=json.loads(path.read_text(encoding="utf-8"))
            from app.trash_restore import restore_reservations
            if any(item['operation_id']==jid and item['state']=='conflict' for item in restore_reservations(workspace_root)):
                continue
            if data.get("status") not in {"queued", "staged", "known_restored"}:
                continue
            if conn.execute("SELECT 1 FROM files WHERE job_id=? LIMIT 1",(jid,)).fetchone():
                continue
            if (storage_paths(workspace_root)["backup_root"]/".incoming"/jid).exists():
                continue
            conn.execute(
                "UPDATE jobs SET state='queued',stage='queued',error_message=NULL,"
                "finished_at=NULL,progress_message='Papierkorb-Wiederherstellung wartet auf Fortsetzung.' "
                "WHERE id=? AND state='interrupted'",(jid,)
            )
            revived+=1
        conn.commit()
    return revived
