"""0.52.0: verified, no-overwrite restoration of an already dissolved Applied child.

The archive path is intentionally excluded: physical restoration there is Finder
work and must be re-scanned through the normal read-only archive verifier.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from app.database import database_connection
from app.event_inventory import scan_event_inventory
from app.event_structure_changes import (
    EventStructureChangeError, _event_state, _snapshot_from_inventory, _safe_rel,
    detect_event_structure_change,
)
from app.safe_transfer import move_verified_no_overwrite, sha256_file, SafeTransferError
from app.workspace_layout import shared_work_root


def _checked_path(root: Path, relative: str) -> Path:
    clean = _safe_rel(relative)
    if not clean:
        raise EventStructureChangeError("Empty restoration path is not permitted.")
    value = root.joinpath(*PurePosixPath(clean).parts)
    if not value.resolve(strict=False).is_relative_to(root):
        raise EventStructureChangeError("A restoration path leaves the workspace.")
    node = root
    for part in PurePosixPath(clean).parts:
        node = node / part
        if node.is_symlink():
            raise EventStructureChangeError("Symbolic links are not allowed during restoration.")
    return value


def restore_applied_subevents(database_path: Path, workspace_path: Path, change_id: str) -> dict:
    """Undo a complete manual dissolution; verify *all* inputs before writes.

    This does not modify the archive. A failed or interrupted multi-file
    restoration leaves the durable task open so a subsequent scan can report
    exactly which files still need physical correction.
    """
    with database_connection(database_path) as conn:
        row = conn.execute(
            "SELECT * FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()
        if row is None or row["status"] != "blocked" or row["root_kind"] != "shared_workspace":
            raise EventStructureChangeError("No pending Applied subevent dissolution to restore.")
        row = dict(row)
        detected = json.loads(str(row["detected_json"] or "{}"))
        candidates = list(detected.get("semantic_change_candidates") or [])
        if not candidates or any(detected.get(key) for key in (
            "root_rename", "child_renames", "missing_file_ids",
            "duplicate_file_ids", "unclassified_directories"
        )):
            raise EventStructureChangeError("The subevent restoration is not unambiguous.")
        event, layout = _event_state(conn, str(row["event_id"]))
        if event["status"] != "applied":
            raise EventStructureChangeError("Automatic restoration is restricted to Applied events.")
        origin_paths = {int(k): str(v) for k,v in
                        (detected.get("restore_original_paths") or {}).items()}
        selected = {int(fid) for c in candidates for fid in c.get("file_ids") or []}
        if not selected or selected != set(origin_paths):
            raise EventStructureChangeError("The original camera-file paths are not fully recorded.")
        if any(not c.get("former_tree_physically_absent") for c in candidates):
            raise EventStructureChangeError("The former child tree was not fully removed.")
        original_children = {
            str(c["child_event_id"]): str(c["old_folder"]) for c in candidates
        }
        for cid, folder in original_children.items():
            child = conn.execute(
                "SELECT folder_name FROM events WHERE id=? AND parent_event_id=?",
                (cid, row["event_id"]),
            ).fetchone()
            if child is None or str(child["folder_name"]) != folder:
                raise EventStructureChangeError("The subevent definition has changed.")
        initial_signature = str(detected.get("signature") or "")
        job_id = str(row["job_id"])
        event_id = str(row["event_id"])
        event_prefix = str(event["start_datetime"])[:4] + "/" + str(event["folder_name"]) + "/"

    root = shared_work_root(workspace_path).resolve(strict=True)
    # Full SHA scan before the first filesystem write. Never trust a fast-size
    # cache when the user has explicitly requested physical restoration.
    scan_event_inventory(database_path, root, job_id, event_id,
                         root_kind="shared_workspace", persist=True, fast_refresh=False)
    with database_connection(database_path) as conn:
        event, layout = _event_state(conn, event_id)
        current = _snapshot_from_inventory(conn, event, layout, "shared_workspace")
        if str(current.get("signature") or "") != initial_signature:
            raise EventStructureChangeError(
                "The physical inventory changed after the proposal. Reload and review it."
            )
        if current.get("semantic_change_candidates") != candidates:
            raise EventStructureChangeError("The proposed subevent change is no longer valid.")
        inventory = {
            int(r["known_file_id"]): dict(r) for r in conn.execute(
                """SELECT known_file_id,relative_path,sha256,size_bytes
                     FROM event_inventory_files
                    WHERE event_id=? AND root_kind='shared_workspace'
                      AND known_file_id IS NOT NULL""",
                (event_id,),
            ).fetchall()
        }
        folders_to_restore = set()
        for folder in original_children.values():
            if any(d == folder or d.startswith(folder + "/")
                   for d in current.get("observed_directories") or []):
                raise EventStructureChangeError("The former child tree already exists.")
            folders_to_restore.add(event_prefix + folder)
            for expected in detected.get("expected_directories") or []:
                if expected == folder or expected.startswith(folder + "/"):
                    folders_to_restore.add(event_prefix + str(expected))

    moves = []
    for candidate in candidates:
        child_id = str(candidate["child_event_id"])
        folder = original_children[child_id]
        for fid in candidate.get("file_ids") or []:
            file_id = int(fid)
            info = inventory.get(file_id)
            if info is None:
                raise EventStructureChangeError("An original file is missing from the current inventory.")
            new_rel = str(info["relative_path"])
            old_rel = origin_paths[file_id]
            if not old_rel.startswith(event_prefix + folder + "/"):
                raise EventStructureChangeError("A recorded original path is not in its former child.")
            if new_rel.startswith(event_prefix + folder + "/"):
                raise EventStructureChangeError("The file was not moved out of its former child.")
            source = _checked_path(root, new_rel)
            target = _checked_path(root, old_rel)
            if not source.is_file() or target.exists() or target.is_symlink():
                raise EventStructureChangeError("A restoration source is missing or its target is occupied.")
            expected_sha = str(info.get("sha256") or "")
            size = int(info.get("size_bytes") or 0)
            if not expected_sha or source.stat().st_size != size or sha256_file(source) != expected_sha:
                raise EventStructureChangeError("A camera file failed the size/SHA-256 preflight.")
            moves.append((source, target, size, expected_sha))

    # Also ensure every directory is safe before performing the first move.
    directory_paths = sorted((_checked_path(root, d) for d in folders_to_restore),
                             key=lambda d: (len(d.parts), str(d)))
    for path in directory_paths:
        if path.exists() and not path.is_dir():
            raise EventStructureChangeError("A required folder path is occupied by a file.")

    completed = []
    try:
        for folder in directory_paths:
            folder.mkdir(parents=True, exist_ok=True)
        for source, target, size, digest in moves:
            move_verified_no_overwrite(source, target, expected_size=size, expected_sha256=digest)
            completed.append(target)
    except (OSError, SafeTransferError) as exc:
        raise EventStructureChangeError(
            "Restoration interrupted after " + str(len(completed)) +
            " files. No files were overwritten. Review the physical state before retrying: " + str(exc)
        ) from exc

    scan_event_inventory(database_path, root, job_id, event_id,
                         root_kind="shared_workspace", persist=True, fast_refresh=False)
    task = detect_event_structure_change(database_path, event_id)
    if task is not None and (task.get("detected") or {}).get("semantic_change_candidates"):
        raise EventStructureChangeError("Physical restoration finished, but the subevent conflict remains.")
    from app.event_document_sync import recover_event_document_sync_tasks
    recover_event_document_sync_tasks(database_path, workspace_path)
    with database_connection(database_path) as conn:
        conn.execute(
            """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'manual_subevent_restored','event',?,?,datetime('now'))""",
            (job_id, event_id, json.dumps({
                "change_id":change_id, "file_count":len(completed),
                "restored_folders":sorted(folders_to_restore),
            }, ensure_ascii=False, sort_keys=True)),
        )
    return {"status":"restored", "event_id":event_id, "file_count":len(completed),
            "restored_directories":len(folders_to_restore), "archive_read_only":True}
