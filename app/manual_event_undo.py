"""Undo pending physical manual Applied event edits without altering event definitions.

Missing empty folders, dissolved subevents and ordinary relocations are restored
through explicit, hash-verified paths. Camera archives remain strictly read-only.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.database import database_connection
from app.event_inventory import scan_event_inventory
from app.event_structure_changes import (
    EventStructureChangeError, _event_state, _snapshot_from_inventory,
    detect_event_structure_change,
)
from app.manual_structure_undo import undo_empty_folder_change, restore_applied_event_directories
from app.manual_subevent_restoration import restore_applied_subevents, _checked_path
from app.safe_transfer import move_verified_no_overwrite, sha256_file, SafeTransferError
from app.workspace_layout import shared_work_root


def undo_manual_applied_change(db: Path, workspace: Path, change_id: str) -> dict[str, Any]:
    with database_connection(db) as conn:
        row = conn.execute(
            "SELECT * FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()
        if row is None or str(row["status"]) not in {"pending","blocked"} or row["root_kind"] != "shared_workspace":
            raise EventStructureChangeError("No pending Applied manual edit can be undone.")
        row = dict(row)
        snapshot = json.loads(str(row["detected_json"] or "{}"))
        event_id,job_id = str(row["event_id"]),str(row["job_id"])
    if snapshot.get("semantic_change_candidates"):
        return restore_applied_subevents(db,workspace,change_id)
    if (snapshot.get("directory_removed") and not any(snapshot.get(key) for key in (
        "directory_added","file_moves","root_rename","child_renames",
        "missing_file_ids","duplicate_file_ids","unclassified_directories",
        "placement_conflicts"
    ))):
        return undo_empty_folder_change(db,shared_work_root(workspace),change_id)

    if any(snapshot.get(key) for key in (
        "missing_file_ids","duplicate_file_ids","unclassified_directories",
        "placement_conflicts","inconsistent_leaf_layouts"
    )):
        raise EventStructureChangeError("The edit includes missing or ambiguous camera originals. Undo is blocked.")
    root = shared_work_root(workspace).resolve(strict=True)
    scan_event_inventory(db,root,job_id,event_id,root_kind="shared_workspace",
                         persist=True,fast_refresh=False)
    with database_connection(db) as conn:
        event,layout = _event_state(conn,event_id)
        if event["status"] != "applied":
            raise EventStructureChangeError("Only an Applied event can be restored automatically.")
        current = _snapshot_from_inventory(conn,event,layout,"shared_workspace")
        if current.get("signature") != snapshot.get("signature"):
            raise EventStructureChangeError("Physical state changed. Reload the manual change task.")
        file_paths = {
            int(r["known_file_id"]):dict(r) for r in conn.execute(
                """SELECT known_file_id,relative_path,sha256,size_bytes
                   FROM event_inventory_files
                   WHERE event_id=? AND root_kind='shared_workspace'
                     AND known_file_id IS NOT NULL""",(event_id,)
            ).fetchall()
        }
    renames = []
    root_change = snapshot.get("root_rename") or {}
    if root_change:
        renames.append((str(root_change["new_path"]),str(root_change["old_path"])))
    for child in snapshot.get("child_renames") or []:
        folder=str(event["start_datetime"])[:4]+"/"+str(event["folder_name"])+"/"
        renames.append((folder+str(child["new_folder"]),folder+str(child["old_folder"])))
    moved_files = snapshot.get("file_moves") or []
    if renames and moved_files:
        raise EventStructureChangeError(
            "Renamed event folders combined with individual file moves require manual reversal."
        )
    moves = []
    for move in moved_files:
        file_id=int(move["file_id"])
        observed=file_paths.get(file_id)
        if not observed or str(observed["relative_path"])!=str(move["new_path"]):
            raise EventStructureChangeError("A file has changed since the saved proposal.")
        src=_checked_path(root,str(move["new_path"]))
        dst=_checked_path(root,str(move["old_path"]))
        digest=str(move.get("sha256") or observed.get("sha256") or "")
        size=int(observed["size_bytes"] or 0)
        if (not digest or not src.is_file() or src.is_symlink()
            or src.stat().st_size!=size or sha256_file(src)!=digest
            or dst.exists() or dst.is_symlink()):
            raise EventStructureChangeError("A file cannot safely return to its original location.")
        moves.append((src,dst,size,digest))
    directory_renames=[]
    for source_rel,target_rel in renames:
        src=_checked_path(root,source_rel)
        dst=_checked_path(root,target_rel)
        if not src.is_dir() or src.is_symlink() or dst.exists() or dst.is_symlink():
            raise EventStructureChangeError("Original folder destination is occupied or missing.")
        directory_renames.append((src,dst))
    added = []
    prefix=str(event["start_datetime"])[:4]+"/"+str(event["folder_name"])+"/"
    for value in snapshot.get("directory_added") or []:
        path=_checked_path(root,prefix+str(value))
        if path.exists() and not path.is_dir():
            raise EventStructureChangeError("Added directory is not a directory.")
        added.append(path)
    # Reserve destinations and make no mutations before all file SHA checks.
    for src,dst,_,_ in moves:
        if not dst.parent.resolve(strict=False).is_relative_to(root):
            raise EventStructureChangeError("Destination leaves the writable workspace.")
    completed_files=[]
    completed_renames=[]
    try:
        for src,dst in directory_renames:
            dst.parent.mkdir(parents=True,exist_ok=True)
            os.rename(src,dst)
            completed_renames.append((src,dst))
        for src,dst,size,digest in moves:
            dst.parent.mkdir(parents=True,exist_ok=True)
            move_verified_no_overwrite(src,dst,expected_size=size,expected_sha256=digest)
            completed_files.append((src,dst,size,digest))
        for directory in sorted(added,key=lambda d:len(d.parts),reverse=True):
            if directory.exists():
                directory.rmdir()  # only actually empty folders are removable
        missing = set(snapshot.get("directory_removed") or [])
        if missing and not directory_renames:
            restore_applied_event_directories(
                db,root,[event_id],only_relative={event_id:missing}
            )
    except (OSError,SafeTransferError,EventStructureChangeError) as error:
        failures=[]
        for src,dst,size,digest in reversed(completed_files):
            try: move_verified_no_overwrite(dst,src,expected_size=size,expected_sha256=digest)
            except Exception as exc: failures.append(str(exc))
        for src,dst in reversed(completed_renames):
            try: os.rename(dst,src)
            except Exception as exc: failures.append(str(exc))
        raise EventStructureChangeError(
            "Undo failed; physical state must be reviewed. "+str(error)+
            (" Rollback incomplete: "+"; ".join(failures) if failures else "")
        ) from error
    scan_event_inventory(db,root,job_id,event_id,root_kind="shared_workspace",
                         persist=True,fast_refresh=False)
    pending=detect_event_structure_change(db,event_id)
    if pending:
        raise EventStructureChangeError(
            "The filesystem was reverted, but a manual structure task is still open. Review it."
        )
    return {"status":"restored","restored_files":len(completed_files),
            "restored_folders":len(completed_renames)+len(snapshot.get("directory_removed") or []),
            "archive_read_only":True}
