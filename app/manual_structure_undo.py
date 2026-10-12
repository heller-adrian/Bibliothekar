"""Restore the canonical directory skeleton after external Finder/SMB moves.

Only Applied workspaces are writable. The durable SQLite event layout is the
SOLL; neither the observed inventory nor event.json may invent destinations.
This module deliberately never opens a camera-archive path for writing.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from app.database import database_connection
from app.event_structure_changes import EventStructureChangeError, _event_state, _snapshot_from_inventory


def _safe_directory(root: Path, relative: str) -> Path:
    parts = PurePosixPath(str(relative)).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise EventStructureChangeError("Invalid restoration directory path.")
    if PurePosixPath(str(relative)).is_absolute():
        raise EventStructureChangeError("Absolute restoration directory is prohibited.")
    node = root
    for part in parts:
        node = node / part
        if node.is_symlink():
            raise EventStructureChangeError("Restoration may not cross symbolic links.")
        if node.exists() and not node.is_dir():
            raise EventStructureChangeError("A required directory is occupied by a file.")
    if not node.resolve(strict=False).is_relative_to(root):
        raise EventStructureChangeError("Restoration directory escapes the workspace.")
    return node


def restore_applied_event_directories(
    database_path: Path,
    library_work_root: Path,
    event_ids: Iterable[str],
    *,
    only_relative: dict[str, set[str]] | None = None,
) -> dict[str, list[str]]:
    """Recreate original empty folders *after* verified file restoration.

    Every path is checked before the first mkdir. Do not alter DB layouts,
    file assignments or any existing camera file. The optional only_relative
    scope is for an explicit empty-directory Undo action.
    """
    root = Path(library_work_root).resolve(strict=True)
    planned: list[tuple[str, str, Path]] = []
    with database_connection(database_path) as conn:
        for event_id in sorted({str(value) for value in event_ids if str(value)}):
            row = conn.execute(
                "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
                (event_id,),
            ).fetchone()
            if row is None or str(row["status"]) != "applied":
                raise EventStructureChangeError(
                    "Directory restoration is restricted to existing Applied root events."
                )
            event, layout = _event_state(conn, event_id)
            snapshot = _snapshot_from_inventory(conn, event, layout, "shared_workspace")
            expected = set(snapshot["expected_directories"])
            if only_relative is not None:
                selected = set(only_relative.get(event_id, set()))
                if not selected.issubset(expected):
                    raise EventStructureChangeError("Restoration changed since review.")
                expected = selected
            folder = str(event["folder_name"] or "")
            year = str(event["start_datetime"] or "")[:4]
            if not year.isdigit() or len(year) != 4 or not folder:
                raise EventStructureChangeError("The event root is not unambiguous.")
            for relative in sorted(expected):
                rel = PurePosixPath(year, folder, relative).as_posix()
                path = _safe_directory(root, rel)
                planned.append((event_id, relative, path))
    # Re-validate all destinations, including parents, immediately before writes.
    for _, _, path in planned:
        relative = path.relative_to(root).as_posix()
        _safe_directory(root, relative)
    result: dict[str, list[str]] = {}
    for event_id, relative, path in planned:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            result.setdefault(event_id, []).append(relative)
    return result


def undo_empty_folder_change(database_path: Path, library_work_root: Path, change_id: str) -> dict:
    """Undo only absent EMPTY organization folders, not unknown file loss."""
    from app.event_inventory import scan_event_inventory
    from app.event_structure_changes import detect_event_structure_change
    with database_connection(database_path) as conn:
        row = conn.execute(
            "SELECT * FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()
        if row is None or row["status"] != "pending" or row["root_kind"] != "shared_workspace":
            raise EventStructureChangeError("No pending Applied directory-only change.")
        event_id, job_id = str(row["event_id"]), str(row["job_id"])
        event, layout = _event_state(conn, event_id)
        from json import loads
        detected = loads(str(row["detected_json"] or "{}"))
        forbidden = (
            "directory_added", "file_moves", "placement_conflicts",
            "missing_file_ids", "duplicate_file_ids",
            "unclassified_directories", "child_renames",
            "semantic_change_candidates",
        )
        if any(detected.get(key) for key in forbidden) or detected.get("root_rename"):
            raise EventStructureChangeError(
                "Only an unchanged event with missing empty folders supports this undo."
            )
        missing = set(detected.get("directory_removed") or [])
        if not missing:
            raise EventStructureChangeError("No missing directory to restore.")
        old_signature = str(detected.get("signature") or "")
    root = Path(library_work_root).resolve(strict=True)
    scan_event_inventory(database_path, root, job_id, event_id,
                         root_kind="shared_workspace", persist=True, fast_refresh=False)
    with database_connection(database_path) as conn:
        event, layout = _event_state(conn, event_id)
        current = _snapshot_from_inventory(conn, event, layout, "shared_workspace")
        if current.get("signature") != old_signature:
            raise EventStructureChangeError("The physical state changed. Reload the task.")
    restored = restore_applied_event_directories(
        database_path, root, [event_id], only_relative={event_id: missing}
    )
    scan_event_inventory(database_path, root, job_id, event_id,
                         root_kind="shared_workspace", persist=True, fast_refresh=False)
    task = detect_event_structure_change(database_path, event_id)
    if task and (task.get("detected") or {}).get("directory_removed"):
        raise EventStructureChangeError("Some expected folders are still missing.")
    return {"event_id": event_id, "restored_directories": restored.get(event_id, []),
            "status": "restored"}
