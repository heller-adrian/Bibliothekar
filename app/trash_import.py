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

from app.database import create_job, get_job
from app.source_filter import should_ignore_source_relative
from app.storage_config import storage_paths
from app.trash import TrashError, _sha256_file, trash_root
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


def stage_trash_import(
    database_path: Path,
    workspace_root: Path,
    relative_paths: list[str],
) -> dict:
    if not relative_paths or len(relative_paths) != len(set(relative_paths)):
        raise TrashError("Ungültige Papierkorb-Auswahl.")
    root = trash_root(workspace_root)
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
        _manifest(parent,job_id).write_text(json.dumps(record,ensure_ascii=False),encoding="utf-8")
        job = create_job(
            database_path, job_id=job_id, kind="sd_import", trigger_type="manual",
            source_path=str(stage), working_path=str(storage_paths(workspace_root)["backup_root"]),
            operation="trash_import", source_volume_label="Aus Papierkorb",
        )
        return {"job_id":job_id,"queued_file_count":len(copies),"job":job}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        _manifest(parent,job_id).unlink(missing_ok=True)
        raise


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
    record_path.write_text(json.dumps({**data,"cleanup_completed":True,"skipped":skipped},ensure_ascii=False),encoding="utf-8")
    shutil.rmtree(parent / job_id,ignore_errors=True)
    return {"removed_file_count":removed,"skipped":skipped}
