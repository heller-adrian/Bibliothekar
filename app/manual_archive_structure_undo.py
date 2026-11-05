"""Explicit read-only archive Undo for detected external structure changes.

The archive is NEVER modified here. An authorized user restores the original
folder/layout manually, then this module verifies the observed physical state
and closes the task. Only a byte-identical, app-owned staging event.json can
be removed when switching away from Accept.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path, PurePosixPath
from typing import Any

from app.database import database_connection
from app.event_inventory import scan_event_inventory
from app.root_operations import validate_active_roots
from app.event_structure_changes import (
    EventStructureChangeError, _now, _event_state, _snapshot_from_inventory,
    detect_event_structure_change, event_file_rows,
)


def _read_pending(db: Path, change_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    with database_connection(db) as conn:
        row = conn.execute(
            "SELECT * FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()
        if row is None or row["root_kind"] != "camera_archive" or row["status"] not in (
            "pending", "prepared", "blocked",
        ):
            raise EventStructureChangeError("No open archived manual structure change.")
        item = dict(row)
        detected = json.loads(str(row["detected_json"] or "{}"))
    return item, detected


def _discard_owned_helper(
    detected: dict[str, Any], *, workspace: Path, work_root: Path, event_id: str
) -> None:
    raw = str(detected.get("prepared_event_json_path") or "")
    digest = str(detected.get("prepared_event_json_sha256") or "")
    if not raw or not digest or len(digest) != 64:
        raise EventStructureChangeError("No verifiable staged event.json available for Undo.")
    target = Path(raw)
    # The recorded path may point to a legacy workspace alias. Require an
    # exact three-level staging path, never arbitrary workspace files.
    roots = [
        work_root / "Assign Later", work_root / "Später zuordnen",
        workspace / "Arbeitsbereich" / "Später zuordnen",
    ]
    qualified = False
    for allowed in roots:
        try:
            rel = target.absolute().relative_to(allowed.absolute())
        except ValueError:
            continue
        if (len(rel.parts) == 3
                and rel.parts[0].isdigit() and len(rel.parts[0]) == 4
                and rel.name == "event.json"):
            qualified = True
            break
    if not qualified:
        raise EventStructureChangeError("Staged event.json lies outside its recorded helper.")
    for p in (target, target.parent, target.parent.parent):
        if p.is_symlink():
            raise EventStructureChangeError("Symlink substitution in archive helper is forbidden.")
    if not target.exists():
        return   # A prior interrupted switch may have removed precisely this helper.
    st = target.stat(follow_symlinks=False)
    if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
        raise EventStructureChangeError("Staged event.json is not an independent regular file.")
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise EventStructureChangeError("Staged event.json differs from the verified helper.")
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise EventStructureChangeError("Staged event.json is not a valid event document.") from exc
    if not isinstance(payload, dict) or str(payload.get("source") or "") != "kamera-automatisierung":
        raise EventStructureChangeError("Staged event.json is not app-owned.")
    if str((payload.get("event") or {}).get("id") or "") != event_id:
        raise EventStructureChangeError("Staged event.json belongs to another event.")
    validate_active_roots()
    # No overwritten files, no archive writes and no directory-tree deletion.
    target.unlink()


def set_archived_structure_review_mode(
    db: Path, workspace: Path, work_root: Path, change_id: str, mode: str
) -> dict[str, Any]:
    if mode not in {"accept", "undo"}:
        raise EventStructureChangeError("Choose Accept Changes or Undo Changes.")
    validate_active_roots()
    with database_connection(db) as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()
        if (row is None or row["root_kind"] != "camera_archive"
                or row["status"] not in ("pending", "prepared", "blocked")):
            raise EventStructureChangeError("Archived structure task is no longer open.")
        detected = json.loads(str(row["detected_json"] or "{}"))
        if mode == "undo" and row["status"] == "prepared":
            _discard_owned_helper(
                detected, workspace=workspace, work_root=work_root,
                event_id=str(row["event_id"]),
            )
            detected.pop("prepared_event_json_path", None)
            detected.pop("prepared_event_json_sha256", None)
            detected.pop("selected_input_path", None)
            detected.pop("selected_leaf_input_paths", None)
        detected["review_mode"] = mode
        status = (
            "pending" if mode == "undo" and row["status"] == "prepared"
            else row["status"]
        )
        conn.execute(
            "UPDATE event_structure_changes SET status=?,detected_json=?,updated_at=? WHERE id=?",
            (status, json.dumps(detected, ensure_ascii=False, sort_keys=True),
             _now(), change_id),
        )
    return {"status": status, "review_mode": mode, "archive_read_only": True}


def verify_archived_structure_undo(
    db: Path, archive: Path, change_id: str
) -> dict[str, Any]:
    validate_active_roots()
    row, detected = _read_pending(db, change_id)
    if detected.get("review_mode") != "undo" or row["status"] != "pending":
        raise EventStructureChangeError("Select Undo Changes before verification.")
    with database_connection(db) as conn:
        event = conn.execute(
            "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
            (row["event_id"],),
        ).fetchone()
        if event is None or event["status"] != "archived":
            raise EventStructureChangeError("The archived event is no longer available.")
        year = str(event["start_datetime"])[:4]
        folder = str(event["folder_name"])
        event_name = str(event["name"])
    # These paths come from the stored event identity, not a user supplied path.
    root = archive.resolve(strict=True)
    event_dir = root / year / folder
    if any(p.is_symlink() for p in (root, root/year, event_dir)):
        raise EventStructureChangeError("Symlink in archive event path.")
    if not event_dir.is_dir():
        raise EventStructureChangeError("Restore the original event folder name before Verify.")
    original_document = event_dir / "event.json"
    if original_document.is_symlink() or not original_document.is_file():
        raise EventStructureChangeError("Restore the original event.json before Verify.")
    with original_document.open("rb") as stream:
        doc = json.loads(stream.read())
    meta = doc.get("event") if isinstance(doc, dict) else None
    if not isinstance(meta, dict) or str(meta.get("id") or "") != str(row["event_id"]):
        raise EventStructureChangeError("The event.json identity is not the archived event.")
    if (str(meta.get("folder_name") or "") != folder
            or str(meta.get("name") or "") != event_name):
        raise EventStructureChangeError("Restore the original event.json metadata before Verify.")
    scan_event_inventory(
        db, root, str(row["job_id"]), str(row["event_id"]),
        root_kind="camera_archive", persist=True,
        update_known_file_locations=False, fast_refresh=False,
    )
    with database_connection(db) as conn:
        event, layout = _event_state(conn, str(row["event_id"]))
        observed = _snapshot_from_inventory(conn, event, layout, "camera_archive")
        unresolved = (
            "directory_added", "directory_removed", "root_rename",
            "child_renames", "file_moves", "placement_conflicts",
            "missing_file_ids", "duplicate_file_ids", "unclassified_directories",
            "inconsistent_leaf_layouts", "semantic_change_candidates",
        )
        if any(observed.get(key) for key in unresolved):
            raise EventStructureChangeError("The archive has not yet been restored to the original layout.")
        expected_files = {
            int(f["id"]): (int(f["size_bytes"]), str(f["sha256_current"] or f["sha256_original"] or ""))
            for f in event_file_rows(conn, str(row["event_id"]))
        }
        physical = {}
        for f in conn.execute(
            "SELECT known_file_id,size_bytes,sha256 FROM event_inventory_files "
            "WHERE event_id=? AND root_kind='camera_archive' AND known_file_id IS NOT NULL",
            (str(row["event_id"]),),
        ).fetchall():
            fid = int(f["known_file_id"])
            if fid in physical:
                raise EventStructureChangeError("Duplicate known archive file detected.")
            physical[fid] = (int(f["size_bytes"]), str(f["sha256"] or ""))
        if not expected_files or physical != expected_files:
            raise EventStructureChangeError("Archive file identities are not fully restored.")
    # Existing detector closes only a genuinely restored physical state.
    pending = detect_event_structure_change(db, str(row["event_id"]))
    if pending is not None:
        raise EventStructureChangeError("The physical archive change is still present.")
    with database_connection(db) as conn:
        final = conn.execute(
            "SELECT status FROM event_structure_changes WHERE id=?",
            (change_id,),
        ).fetchone()
    if final is None or final["status"] != "cancelled":
        raise EventStructureChangeError("The restored task could not be closed safely.")
    return {"status": "restored", "archive_read_only": True, "change_id": change_id}
