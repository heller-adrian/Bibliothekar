"""Detect and reconcile manual filesystem organization changes for 0.28.0.

The filesystem is observational IST.  A detected difference becomes a durable
task.  Applied events can be accepted in-place after user confirmation.
Archived events remain read-only: Bibliothekar prepares a replacement event.json
under Später zuordnen and only commits SQLite after that exact document appears
in the archive and the live inventory still matches.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import uuid

from app.database import database_connection
from app.event_access import event_file_rows
from app.event_leaf_layouts import leaf_descriptors, stored_leaf_layouts, validate_leaf_choices, save_leaf_layouts
from app.event_inventory import scan_event_inventory, EventInventoryError
from app.event_layout import get_event_layout, layout_paths, layout_role_paths, update_event_layout
from app.event_document import build_event_document_from_db, EVENT_DOCUMENT_FILENAME
from app.external_changes import record_notice, resolve_notice_key
from app.workspace_layout import WORK_DIRECTORY_NAME


class EventStructureChangeError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_rel(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        return ""
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise EventStructureChangeError("Unsicherer relativer Strukturpfad: " + raw)
    return path.as_posix()


def _layout_from_paths(
    paths: list[str],
    *,
    role_paths: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for raw in sorted({_safe_rel(value) for value in paths if _safe_rel(value)}):
        cursor = tree
        for part in PurePosixPath(raw).parts:
            cursor = cursor.setdefault(part, {})
    def nodes(node: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[dict[str, Any]]:
        result = []
        for name, children in sorted(node.items(), key=lambda item: item[0].casefold()):
            path = PurePosixPath(*prefix, name).as_posix()
            node_id = "fs-" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
            item = {
                "id": node_id,
                "name": name,
                "children": nodes(children, (*prefix, name)),
            }
            for role, configured_paths in (role_paths or {}).items():
                if path in configured_paths:
                    item["role"] = role
            result.append(item)
        return result
    return {"version": 1, "nodes": nodes(tree)}


def _tree_text(directories: list[str]) -> str:
    tree: dict[str, Any] = {}
    for raw in sorted({_safe_rel(value) for value in directories if _safe_rel(value)}):
        cursor = tree
        for part in PurePosixPath(raw).parts:
            cursor = cursor.setdefault(part, {})
    lines: list[str] = []
    def walk(node: dict[str, Any], prefix: str = "") -> None:
        items = list(node.items())
        for index, (name, children) in enumerate(items):
            last = index == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name)
            walk(children, prefix + ("    " if last else "│   "))
    walk(tree)
    return "\n".join(lines)


def _event_state(connection: Any, event_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    event = connection.execute(
        "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
        (event_id,),
    ).fetchone()
    if event is None:
        raise EventStructureChangeError("Ereignis wurde nicht gefunden.")
    if str(event["status"]) not in {"applied", "archived"}:
        raise EventStructureChangeError("Nur angewendete oder archivierte Ereignisse besitzen einen beobachtbaren Endbestand.")
    return dict(event), get_event_layout(connection, event_id)


def _in_flight(connection: Any, event: dict[str, Any]) -> bool:
    event_id = str(event["id"])
    anchor_job = str(event["job_id"])
    if connection.execute(
        """SELECT 1 FROM event_mutations
           WHERE anchor_event_id=? AND status IN ('pending_reassignment','pending_apply','manual_archive')
           LIMIT 1""",
        (event_id,),
    ).fetchone():
        return True
    if connection.execute(
        """SELECT 1 FROM sort_runs
           WHERE event_id=? AND status IN ('queued','verifying','moving','finalizing','rolling_back','interrupted')
           LIMIT 1""",
        (event_id,),
    ).fetchone():
        return True
    if connection.execute(
        """SELECT 1 FROM event_change_requests
           WHERE event_id=? AND status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')
           LIMIT 1""",
        (event_id,),
    ).fetchone():
        return True
    if connection.execute(
        """SELECT 1 FROM event_ssd_releases
           WHERE event_id=?
             AND status IN ('verifying','deleting','finalizing','interrupted')
           LIMIT 1""",
        (event_id,),
    ).fetchone():
        return True
    return False


def assert_no_open_structure_change(connection: Any, event_id: str) -> None:
    row = connection.execute(
        """SELECT id,status FROM event_structure_changes
           WHERE event_id=? AND status IN ('pending','prepared','verified','blocked')
           ORDER BY created_at DESC LIMIT 1""",
        (event_id,),
    ).fetchone()
    if row is not None:
        raise EventStructureChangeError(
            "Für dieses Ereignis wurde eine manuelle Dateisystemänderung erkannt. "
            "Bitte zuerst die Aufgabe „Manuelle Ereignisänderung“ abschließen."
        )


def _leaf_prefixes(connection: Any, event: dict[str, Any]) -> list[str]:
    event_id = str(event["id"])
    preserve = bool(event.get("preserve_day_folders"))
    rows = connection.execute(
        """SELECT assigned.id AS assigned_event_id, assigned.parent_event_id,
                  assigned.folder_name, ff.selected_capture_time
           FROM event_assignments ea
           JOIN events assigned ON assigned.id=ea.event_id
           LEFT JOIN file_families ff ON ff.id=ea.family_id
           WHERE ea.family_id IS NOT NULL
             AND (assigned.id=? OR assigned.parent_event_id=?)
           ORDER BY assigned.start_datetime,ff.selected_capture_time""",
        (event_id, event_id),
    ).fetchall()
    prefixes: set[str] = set()
    for row in rows:
        parts: list[str] = []
        if row["parent_event_id"] is not None:
            parts.append(str(row["folder_name"]))
        if preserve:
            day = str(row["selected_capture_time"] or "")[:10]
            if len(day) == 10:
                parts.append(day)
        prefixes.add(PurePosixPath(*parts).as_posix() if parts else "")
    children = connection.execute(
        "SELECT folder_name FROM events WHERE parent_event_id=? ORDER BY start_datetime,id",
        (event_id,),
    ).fetchall()
    for child in children:
        folder = str(child["folder_name"] or "")
        if folder and not any(prefix == folder or prefix.startswith(folder + "/") for prefix in prefixes):
            prefixes.add(folder)
    if not prefixes:
        prefixes.add("")
    return sorted(prefixes, key=lambda value: (-len(PurePosixPath(value).parts), value))


def _split_org_path(relative: str, leaves: list[str]) -> tuple[str, str] | None:
    path = PurePosixPath(relative)
    for leaf in leaves:
        leaf_path = PurePosixPath(leaf) if leaf else PurePosixPath()
        if not leaf:
            return "", path.as_posix()
        try:
            rest = path.relative_to(leaf_path)
        except ValueError:
            continue
        return leaf, rest.as_posix() if rest.parts else ""
    return None


def _is_within_prefix(
    relative_path: str,
    prefix: str,
) -> bool:
    path = PurePosixPath(_safe_rel(relative_path))
    expected = PurePosixPath(_safe_rel(prefix))
    try:
        path.relative_to(expected)
        return True
    except ValueError:
        return False


def _expected_file_prefix(
    connection: Any,
    event: dict[str, Any],
    file_id: int,
) -> str:
    """Return the fachlich erlaubte strukturelle Wurzel einer Kameradatei.

    Organisationsordner (Input/Export/Unterordnerlayout) dürfen sich innerhalb
    dieser Wurzel ändern. Ein Wechsel in einen anderen Tag, ein anderes
    Unterereignis oder ein anderes Ereignis ist dagegen eine echte
    Zuordnungsabweichung.
    """
    event_id = str(event["id"])
    file_row = connection.execute(
        """SELECT f.family_id,ff.selected_capture_time
           FROM files f
           LEFT JOIN file_families ff ON ff.id=f.family_id
           WHERE f.id=?""",
        (int(file_id),),
    ).fetchone()
    if file_row is None:
        return ""

    family_id = (
        int(file_row["family_id"])
        if file_row["family_id"] is not None
        else None
    )
    assignment = connection.execute(
        """SELECT assigned.id,assigned.parent_event_id,assigned.folder_name
           FROM event_assignments ea
           JOIN events assigned ON assigned.id=ea.event_id
           WHERE (
                 ea.file_id=?
                 OR (
                     ea.file_id IS NULL
                     AND ea.family_id=?
                 )
               )
             AND COALESCE(assigned.parent_event_id,assigned.id)=?
           ORDER BY CASE WHEN ea.file_id=? THEN 0 ELSE 1 END,
                    assigned.start_datetime,assigned.id
           LIMIT 1""",
        (
            int(file_id),
            family_id,
            event_id,
            int(file_id),
        ),
    ).fetchone()

    start = str(event.get("start_datetime") or "")
    year = start[:4]
    folder = str(event.get("folder_name") or "").strip()
    parts: list[str] = []
    if len(year) == 4 and year.isdigit():
        parts.append(year)
    if folder:
        parts.append(folder)

    if assignment is not None and assignment["parent_event_id"] is not None:
        child = str(assignment["folder_name"] or "").strip()
        if child:
            parts.append(child)

    if bool(event.get("preserve_day_folders")):
        day = str(file_row["selected_capture_time"] or "")[:10]
        if len(day) == 10:
            parts.append(day)

    return PurePosixPath(*parts).as_posix() if parts else ""


def _open_placement_expected_path(
    connection: Any,
    file_id: int,
) -> str | None:
    row = connection.execute(
        """SELECT details_json FROM external_change_notices
           WHERE notice_key=? AND status='open'
           LIMIT 1""",
        (f"placement:{int(file_id)}",),
    ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row["details_json"] or "{}"))
    except Exception:
        return None
    value = str(payload.get("expected_relative_path") or "").strip()
    return value or None


def _snapshot_from_inventory(
    connection: Any,
    event: dict[str, Any],
    layout_state: dict[str, Any],
    root_kind: str,
) -> dict[str, Any]:
    event_id = str(event["id"])
    leaves = _leaf_prefixes(connection, event)
    leaf_defs = leaf_descriptors(connection, event, leaves)
    stored_leaves = stored_leaf_layouts(connection, event_id)
    dir_rows = connection.execute(
        """SELECT event_relative_path FROM event_inventory_directories
           WHERE event_id=? AND root_kind=? ORDER BY event_relative_path""",
        (event_id, root_kind),
    ).fetchall()
    observed_dirs = [_safe_rel(row["event_relative_path"]) for row in dir_rows]

    known_rows = connection.execute(
        """SELECT known_file_id,family_id,relative_path,event_relative_path,filename,
                  size_bytes,sha256,asset_kind,selected_capture_time
           FROM event_inventory_files
           WHERE event_id=? AND root_kind=?
           ORDER BY event_relative_path""",
        (event_id, root_kind),
    ).fetchall()
    known_counts: dict[int, int] = {}
    observed_known: dict[int, dict[str, Any]] = {}
    assets: list[dict[str, Any]] = []
    for raw in known_rows:
        row = dict(raw)
        if row["known_file_id"] is not None:
            file_id = int(row["known_file_id"])
            known_counts[file_id] = known_counts.get(file_id, 0) + 1
            observed_known[file_id] = row
        else:
            assets.append(row)

    expected_files = {int(row["id"]): row for row in event_file_rows(connection, event_id)}
    missing_ids = sorted(set(expected_files) - set(observed_known))
    duplicate_ids = sorted(file_id for file_id, count in known_counts.items() if count != 1)

    expected_year = str(event.get("start_datetime") or "")[:4]
    expected_folder = str(event.get("folder_name") or "").strip()
    expected_root = (
        PurePosixPath(expected_year, expected_folder).as_posix()
        if expected_year and expected_folder
        else ""
    )

    # Eine komplette manuelle Umbenennung des Ereignisordners wird durch den
    # beim Inventarscan beobachteten gemeinsamen Root erkannt. event_inventory
    # liefert den realen Prefix, event.json liefert zuvor die stabile Event-ID.
    observed_roots: set[str] = set()
    for observed in observed_known.values():
        full = PurePosixPath(_safe_rel(observed.get("relative_path")))
        rel = PurePosixPath(_safe_rel(observed.get("event_relative_path")))
        if rel.parts and len(full.parts) > len(rel.parts):
            prefix_parts = full.parts[:-len(rel.parts)]
            if prefix_parts:
                observed_roots.add(PurePosixPath(*prefix_parts).as_posix())

    root_rename: dict[str, Any] | None = None
    if len(observed_roots) == 1 and expected_root:
        observed_root = next(iter(observed_roots))
        observed_parts = PurePosixPath(observed_root).parts
        expected_parts = PurePosixPath(expected_root).parts
        if (
            observed_root != expected_root
            and len(observed_parts) == len(expected_parts) == 2
            and observed_parts[0] == expected_parts[0]
        ):
            root_rename = {
                "old_path": expected_root,
                "new_path": observed_root,
                "old_folder": expected_parts[-1],
                "new_folder": observed_parts[-1],
            }

    # Unterereignisse besitzen einen eigenen ersten Pfadbestandteil. Wenn alle
    # bekannten Dateien eines Unterereignisses geschlossen unter genau einem
    # neuen, bisher nicht belegten Prefix wiedergefunden werden, ist dies eine
    # eindeutige Ordnerumbenennung und keine Serie falscher Dateizuordnungen.
    child_rows = [
        dict(row)
        for row in connection.execute(
            """SELECT DISTINCT f.id AS file_id,
                      assigned.id AS child_event_id,
                      assigned.folder_name AS child_folder
               FROM event_assignments ea
               JOIN events assigned ON assigned.id=ea.event_id
               JOIN files f
                 ON (
                    ea.file_id=f.id
                    OR (
                        ea.file_id IS NULL
                        AND ea.family_id=f.family_id
                    )
                 )
               WHERE assigned.parent_event_id=?
               ORDER BY assigned.start_datetime,assigned.id,f.id""",
            (event_id,),
        ).fetchall()
    ]
    existing_child_folders = {
        str(row["folder_name"] or "")
        for row in connection.execute(
            "SELECT folder_name FROM events WHERE parent_event_id=?",
            (event_id,),
        ).fetchall()
        if str(row["folder_name"] or "")
    }
    child_groups: dict[str, dict[str, Any]] = {}
    for row in child_rows:
        child_id = str(row["child_event_id"])
        group = child_groups.setdefault(
            child_id,
            {
                "child_event_id": child_id,
                "old_folder": str(row["child_folder"] or ""),
                "file_ids": [],
            },
        )
        group["file_ids"].append(int(row["file_id"]))

    child_renames: list[dict[str, Any]] = []
    semantic_change_candidates: list[dict[str, Any]] = []
    child_rename_by_file: dict[int, tuple[str, str]] = {}
    child_directory_map: dict[str, str] = {}
    for group in child_groups.values():
        old_folder = str(group["old_folder"] or "")
        file_ids = [int(value) for value in group["file_ids"]]
        if not old_folder or not file_ids or any(fid not in observed_known for fid in file_ids):
            continue
        candidates: set[str] = set()
        valid = True
        for file_id in file_ids:
            parts = PurePosixPath(
                _safe_rel(observed_known[file_id].get("event_relative_path"))
            ).parts
            if not parts:
                valid = False
                break
            candidates.add(parts[0])
        if not valid or len(candidates) != 1:
            continue
        new_folder = next(iter(candidates))
        if (
            new_folder == old_folder
            or new_folder in existing_child_folders
            or not new_folder
        ):
            continue
        # Moving an entire child's contents into the parent's input is NOT
        # a rename of the child to "All". This needs an explicit event edit.
        if new_folder in set(layout_paths(layout_state["layout"])) or new_folder in {
            "Alle", "All", "Sortiert", "Sorted", "Export"
        }:
            semantic_change_candidates.append({
                "child_event_id": str(group["child_event_id"]),
                "old_folder": old_folder,
                "new_parent_folder": new_folder,
                "file_ids": file_ids,
            })
            continue
        child_renames.append({
            "child_event_id": str(group["child_event_id"]),
            "old_folder": old_folder,
            "new_folder": new_folder,
        })
        child_directory_map[new_folder] = old_folder
        for file_id in file_ids:
            child_rename_by_file[file_id] = (new_folder, old_folder)

    def normalize_event_relative(file_id: int, value: Any) -> str:
        raw = _safe_rel(value)
        parts = list(PurePosixPath(raw).parts)
        mapping = child_rename_by_file.get(int(file_id))
        if mapping and parts and parts[0] == mapping[0]:
            parts[0] = mapping[1]
        return PurePosixPath(*parts).as_posix() if parts else ""

    def normalize_directory(value: str) -> str:
        raw = _safe_rel(value)
        parts = list(PurePosixPath(raw).parts)
        if parts and parts[0] in child_directory_map:
            parts[0] = child_directory_map[parts[0]]
        return PurePosixPath(*parts).as_posix() if parts else ""

    normalized_dirs = [normalize_directory(value) for value in observed_dirs]

    file_moves = []
    placement_conflicts = []
    # A child's stored assignment alone is not sufficient: the observed
    # capture time must also be within the child's actual temporal bounds.
    child_intervals: dict[int, tuple[str, str]] = {}
    for assignment in connection.execute(
        """SELECT f.id AS file_id, assigned.start_datetime,assigned.end_datetime
           FROM event_assignments ea
           JOIN events assigned ON assigned.id=ea.event_id
           JOIN files f ON (
             ea.file_id=f.id OR (
               ea.file_id IS NULL AND ea.family_id=f.family_id
             )
           )
           WHERE assigned.parent_event_id=?
           ORDER BY CASE WHEN ea.file_id IS NULL THEN 1 ELSE 0 END""",
        (event_id,),
    ).fetchall():
        child_intervals[int(assignment["file_id"])] = (
            str(assignment["start_datetime"] or "")[:19],
            str(assignment["end_datetime"] or "")[:19],
        )

    for file_id, observed in observed_known.items():
        expected = expected_files.get(file_id)
        if expected is None:
            continue
        old = _safe_rel(expected.get("current_relative_path"))
        new = _safe_rel(observed.get("relative_path"))
        normalized_rel = normalize_event_relative(
            file_id,
            observed.get("event_relative_path"),
        )
        normalized_new = (
            PurePosixPath(expected_root, normalized_rel).as_posix()
            if expected_root and normalized_rel
            else new
        )
        expected_prefix = _expected_file_prefix(
            connection,
            event,
            file_id,
        )
        capture = str(observed.get("selected_capture_time") or "")[:19]
        child_bounds = child_intervals.get(int(file_id))
        outside_child_time = bool(
            child_bounds and capture and
            not (child_bounds[0] <= capture <= child_bounds[1])
        )
        if (expected_prefix and not _is_within_prefix(
            normalized_new,
            expected_prefix,
        )) or outside_child_time:
            placement_conflicts.append({
                "reason": "capture_outside_subevent" if outside_child_time else "wrong_location",
                "capture_time": capture,
                "file_id": file_id,
                "family_id": observed.get("family_id"),
                "old_path": old,
                "new_path": new,
                "expected_prefix": expected_prefix,
                "sha256": str(observed.get("sha256") or ""),
                "size_bytes": int(observed.get("size_bytes") or 0),
            })
        # Reine Root-/Unterereignis-Renames werden nicht zusätzlich als viele
        # einzelne Dateibewegungen dargestellt. Echte Organisationsbewegungen
        # innerhalb des Blatts bleiben dagegen sichtbar.
        if old != new and old != normalized_new:
            file_moves.append({
                "file_id": file_id,
                "family_id": observed.get("family_id"),
                "old_path": old,
                "new_path": new,
                "sha256": str(observed.get("sha256") or ""),
            })

    structural_leaf_dirs: set[str] = set()
    for leaf in leaves:
        if not leaf:
            continue
        parts = PurePosixPath(leaf).parts
        for index in range(1, len(parts) + 1):
            structural_leaf_dirs.add(PurePosixPath(*parts[:index]).as_posix())
    by_leaf: dict[str, set[str]] = {leaf: set() for leaf in leaves}
    unclassified: list[str] = []
    for directory in normalized_dirs:
        if directory in structural_leaf_dirs:
            continue
        split = _split_org_path(directory, leaves)
        if split is None:
            unclassified.append(directory)
            continue
        leaf, rest = split
        if rest:
            by_leaf.setdefault(leaf, set()).add(rest)

    # Each parent/child/day leaf may have its own organization folders and
    # input folder. Do not collapse distinct leaf layouts into a global one.
    leaf_layouts: list[dict[str, Any]] = []
    for leaf in leaf_defs:
        prefix = leaf["leaf_prefix"]
        paths = sorted(by_leaf.get(prefix, set()))
        old_leaf = stored_leaves.get(leaf["leaf_key"])
        prior_layout = old_leaf["layout"] if old_leaf else layout_state["layout"]
        prior_input = str(
            (old_leaf or layout_state).get("input_path") or ""
        )
        prior_export = set(layout_role_paths(prior_layout, "export"))
        proposed_leaf_layout = _layout_from_paths(
            paths, role_paths={"export": prior_export}
        )
        leaf_layouts.append({
            **leaf,
            "layout": proposed_leaf_layout,
            "structure_enabled": bool(paths),
            "input_path": prior_input if prior_input in paths else "",
            "input_options": paths,
        })

    root_leaf = next(
        (leaf for leaf in leaf_layouts if leaf["leaf_prefix"] == ""), None
    )
    proposed_layout = (
        root_leaf["layout"] if root_leaf is not None
        else layout_state["layout"]
    )
    proposed_paths = layout_paths(proposed_layout)
    inconsistent = False  # Different leaves are explicitly supported.

    expected_dirs: set[str] = set()
    for leaf in leaf_defs:
        prefix = leaf["leaf_prefix"]
        if prefix:
            expected_dirs.add(prefix)
        old_leaf = stored_leaves.get(leaf["leaf_key"])
        effective = old_leaf if old_leaf is not None else layout_state
        expected_org = (
            layout_paths(effective["layout"])
            if effective.get("structure_enabled") else []
        )
        for org in expected_org:
            value = PurePosixPath(
                *(PurePosixPath(prefix).parts if prefix else ()),
                *PurePosixPath(org).parts,
            )
            expected_dirs.add(value.as_posix())
    directory_added = sorted(set(normalized_dirs) - expected_dirs)
    directory_removed = sorted(expected_dirs - set(normalized_dirs))

    blocked = bool(missing_ids or duplicate_ids or unclassified or semantic_change_candidates)
    changed = bool(
        file_moves
        or directory_added
        or directory_removed
        or root_rename
        or child_renames
        or semantic_change_candidates
    )
    signature_payload = {
        "observed_dirs": observed_dirs,
        "files": [
            [int(row["known_file_id"]) if row["known_file_id"] is not None else None,
             str(row["event_relative_path"]), int(row["size_bytes"] or 0), str(row["sha256"] or "")]
            for row in map(dict, known_rows)
        ],
    }
    signature = hashlib.sha256(
        json.dumps(signature_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "event_id": event_id,
        "job_id": str(event["job_id"]),
        "event_name": str(event["name"]),
        "status": str(event["status"]),
        "root_kind": root_kind,
        "signature": signature,
        "leaves": leaves,
        "observed_directories": observed_dirs,
        "expected_directories": sorted(expected_dirs),
        "directory_added": directory_added,
        "directory_removed": directory_removed,
        "root_rename": root_rename,
        "child_renames": child_renames,
        "file_moves": file_moves,
        "placement_conflicts": placement_conflicts,
        "missing_file_ids": missing_ids,
        "duplicate_file_ids": duplicate_ids,
        "unclassified_directories": unclassified,
        "inconsistent_leaf_layouts": inconsistent,
        "semantic_change_candidates": semantic_change_candidates,
        "leaf_layouts": leaf_layouts,
        "proposed_layout": proposed_layout,
        "proposed_structure_enabled": bool(root_leaf["structure_enabled"]) if root_leaf else bool(layout_state["structure_enabled"]),
        "input_options": ["", *layout_paths(proposed_layout)],
        "current_input_path": str(layout_state.get("input_path") or ""),
        "changed": changed,
        "blocked": blocked,
    }

def detect_event_structure_change(
    database_path: Path,
    event_id: str,
) -> dict[str, Any] | None:
    now = _now()
    with database_connection(database_path) as connection:
        event, layout_state = _event_state(connection, event_id)
        if _in_flight(connection, event):
            return None
        root_kind = "camera_archive" if str(event["status"]) == "archived" else "shared_workspace"
        snapshot = _snapshot_from_inventory(connection, event, layout_state, root_kind)
        current = connection.execute(
            """SELECT * FROM event_structure_changes
               WHERE event_id=? AND root_kind=?
                 AND status IN ('pending','prepared','verified','blocked')
               ORDER BY created_at DESC LIMIT 1""",
            (event_id, root_kind),
        ).fetchone()

        # 0.28.2: Ein fehlendes Original ist keine Strukturänderung. Erst zwei
        # aufeinanderfolgende vollständige Scans bestätigen eine manuelle
        # Löschung. Bis dahin wird kein Benutzerauftrag erzeugt.
        if snapshot.get("missing_file_ids"):
            # Preserve physical locations before reconcile_missing_files removes
            # confirmed-deleted rows. Only directories containing those removed
            # files may be treated as an intentional partial deletion.
            missing_ids = [int(v) for v in snapshot["missing_file_ids"]]
            placeholders = ",".join("?" for _ in missing_ids)
            missing_previous_paths = {
                int(row["id"]): str(row["current_relative_path"] or "")
                for row in connection.execute(
                    f"SELECT id,current_relative_path FROM files WHERE id IN ({placeholders})",
                    tuple(missing_ids),
                ).fetchall()
            }
            from app.physical_state import reconcile_missing_files
            missing_state = reconcile_missing_files(
                connection,
                event,
                root_kind,
                list(snapshot.get("missing_file_ids") or []),
                now=now,
            )
            if missing_state["pending"]:
                if current is not None and str(current["status"]) in {"pending", "blocked"}:
                    connection.execute(
                        """UPDATE event_structure_changes
                           SET status='cancelled',updated_at=?,completed_at=?
                           WHERE id=?""",
                        (now, now, current["id"]),
                    )
                return None
            if missing_state["confirmed_deleted"]:
                remaining_inventory = int(
                    connection.execute(
                        """SELECT COUNT(*) FROM event_inventory_files
                           WHERE event_id=? AND root_kind=?""",
                        (event_id, root_kind),
                    ).fetchone()[0]
                    or 0
                )
                remaining_directories = int(
                    connection.execute(
                        """SELECT COUNT(*) FROM event_inventory_directories
                           WHERE event_id=? AND root_kind=?""",
                        (event_id, root_kind),
                    ).fetchone()[0]
                    or 0
                )
                remaining_assignments = int(
                    connection.execute(
                        """SELECT COUNT(*) FROM event_assignments ea
                           JOIN events assigned ON assigned.id=ea.event_id
                           WHERE COALESCE(assigned.parent_event_id,assigned.id)=?""",
                        (event_id,),
                    ).fetchone()[0]
                    or 0
                )
                if (
                    remaining_inventory == 0
                    and remaining_directories == 0
                    and remaining_assignments == 0
                ):
                    record_notice(
                        connection,
                        notice_key=f"event-root-deleted:{event_id}",
                        kind="event_root_deleted",
                        root_kind=root_kind,
                        title="Ereignisordner extern gelöscht",
                        detail=(
                            f"„{event.get('name') or event_id}“ wurde außerhalb "
                            "von Bibliothekar vollständig entfernt und aus dem "
                            "aktiven Bestand übernommen."
                        ),
                        job_id=str(event.get("job_id") or ""),
                        event_id=event_id,
                        relative_path=str(event.get("folder_name") or ""),
                        repairable=False,
                        action_required=False,
                        group_key="deletion_notice",
                        details={
                            "event_name": str(event.get("name") or ""),
                            "folder_name": str(event.get("folder_name") or ""),
                            "deleted_file_count": len(
                                missing_state["confirmed_deleted"]
                            ),
                        },
                        now=now,
                    )
                    connection.execute(
                        "DELETE FROM events WHERE id=?",
                        (event_id,),
                    )
                    return None
                snapshot = _snapshot_from_inventory(
                    connection,
                    event,
                    layout_state,
                    root_kind,
                )
                # Removing a populated *subdirectory* is not, by itself,
                # a request to change the configured event folder layout.
                # Persist the observed deletion as the same dismissible
                # external-change notice used for removed full event roots.
                event_prefix = (
                    str(event.get("start_datetime") or "")[:4]
                    + "/"
                    + str(event.get("folder_name") or "")
                    + "/"
                )
                deleted_ancestors: set[str] = set()
                for deleted_id in missing_state["confirmed_deleted"]:
                    old_path = missing_previous_paths.get(int(deleted_id), "")
                    if not old_path.startswith(event_prefix):
                        continue
                    parts = PurePosixPath(old_path[len(event_prefix):]).parts
                    for depth in range(1, len(parts)):
                        deleted_ancestors.add(
                            PurePosixPath(*parts[:depth]).as_posix()
                        )
                removed_dirs = [
                    directory
                    for directory in snapshot.get("directory_removed") or []
                    if directory in deleted_ancestors
                ]
                if removed_dirs:
                    record_notice(
                        connection,
                        notice_key=f"event-directory-deleted:{event_id}:{now[:19]}",
                        kind="event_directory_deleted",
                        root_kind=root_kind,
                        title="Ereignis-Unterordner extern gelöscht",
                        detail=(
                            f"Im Ereignis „{event.get('name') or event_id}“ wurden "
                            f"{len(removed_dirs)} Unterordner und "
                            f"{len(missing_state['confirmed_deleted'])} Dateien "
                            "außerhalb von Bibliothekar entfernt."
                        ),
                        job_id=str(event.get("job_id") or ""),
                        event_id=event_id,
                        relative_path=str(event.get("folder_name") or ""),
                        repairable=False,
                        action_required=False,
                        group_key="deletion_notice",
                        details={
                            "directories": removed_dirs,
                            "deleted_file_count": len(
                                missing_state["confirmed_deleted"]
                            ),
                        },
                        now=now,
                    )
        else:
            from app.physical_state import reconcile_missing_files
            reconcile_missing_files(connection, event, root_kind, [], now=now)

        # Previously acknowledged partial directory deletions remain valid
        # physical IST observations across reloads. Only the subdirectories
        # proven to have contained deleted files are ignored here; unrelated
        # structural changes still use the ordinary structure-change workflow.
        deleted_directory_notices = connection.execute(
            """SELECT details_json FROM external_change_notices
               WHERE event_id=? AND root_kind=?
                 AND kind='event_directory_deleted'
                 AND status IN ('open','dismissed')""",
            (event_id, root_kind),
        ).fetchall()
        accepted_deleted_dirs: set[str] = set()
        for deleted_notice in deleted_directory_notices:
            try:
                payload = json.loads(str(deleted_notice["details_json"] or "{}"))
                accepted_deleted_dirs.update(
                    str(value) for value in (payload.get("directories") or [])
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        if accepted_deleted_dirs:
            snapshot["directory_removed"] = [
                directory
                for directory in snapshot.get("directory_removed") or []
                if directory not in accepted_deleted_dirs
            ]

        # Bekannte Kameradateien dürfen innerhalb ihres fachlich erlaubten
        # Ereignis-/Unterereignis-/Tagesblatts frei in Organisationsordnern
        # verschoben werden. Ein Wechsel über diese Grenze bleibt dagegen als
        # eine gebündelte Konsistenzaufgabe offen.
        conflicts_by_id = {
            int(item["file_id"]): item
            for item in (snapshot.get("placement_conflicts") or [])
        }
        moves = list(snapshot.get("file_moves") or [])

        for item in snapshot.get("placement_conflicts") or []:
            file_id = int(item["file_id"])
            observed = str(item.get("new_path") or "")
            expected_path = (
                _open_placement_expected_path(
                    connection,
                    file_id,
                )
                or str(item.get("old_path") or "")
            )
            file_row = connection.execute(
                """SELECT f.job_id,f.original_filename,f.size_bytes,
                          COALESCE(f.sha256_current,f.sha256_original,'') AS sha256
                   FROM files f WHERE f.id=?""",
                (file_id,),
            ).fetchone()
            if file_row is None:
                continue
            detail = (
                f"{file_row['original_filename']} liegt unter „{observed}“. "
                f"Die fachliche Zuordnung erlaubt nur „{item.get('expected_prefix') or ''} …“."
            )
            if item.get("reason") == "capture_outside_subevent":
                detail += (
                    " Die tatsächliche Aufnahmezeit liegt außerhalb des "
                    "Zeitfensters des zugeordneten Unterereignisses."
                )
            if root_kind == "camera_archive":
                detail += (
                    " Das Archiv ist schreibgeschützt; bitte die Datei manuell "
                    "in den passenden Ereignis-/Unterereignisbereich zurückverschieben."
                )
            record_notice(
                connection,
                notice_key=f"placement:{file_id}",
                kind="placement_conflict",
                root_kind=root_kind,
                title="Datei falsch zugeordnet",
                detail=detail,
                job_id=str(file_row["job_id"]),
                event_id=event_id,
                file_id=file_id,
                relative_path=observed,
                repairable=root_kind == "shared_workspace" and item.get("reason") != "capture_outside_subevent",
                action_required=True,
                group_key="placement_conflict",
                details={
                    "expected_root_kind": root_kind,
                    "observed_root_kind": root_kind,
                    "expected_relative_path": expected_path,
                    "observed_relative_path": observed,
                    "expected_prefix": str(item.get("expected_prefix") or ""),
                    "reason": str(item.get("reason") or ""),
                    "capture_time": str(item.get("capture_time") or ""),
                    "size_bytes": int(file_row["size_bytes"] or 0),
                    "sha256": str(file_row["sha256"] or ""),
                },
                now=now,
            )

        # SQLite bildet den tatsächlich beobachteten Pfad ab. Das fachliche
        # SOLL bleibt bei falscher Ablage separat in external_change_notices.
        if moves:
            from app.physical_state import sync_placement_moves
            sync_placement_moves(
                connection,
                event,
                layout_state,
                root_kind,
                moves,
                now=now,
            )

        observed_file_ids = {
            int(row["known_file_id"])
            for row in connection.execute(
                """SELECT known_file_id FROM event_inventory_files
                   WHERE event_id=? AND root_kind=?
                     AND known_file_id IS NOT NULL""",
                (event_id, root_kind),
            ).fetchall()
        }
        for file_id in observed_file_ids - set(conflicts_by_id):
            resolve_notice_key(
                connection,
                f"placement:{file_id}",
                now=now,
            )

        # Nur fachlich falsche Platzierungen werden aus dem normalen
        # Strukturworkflow herausgehalten. Legitime Dateibewegungen, die zu
        # einer echten Ordneränderung gehören (z. B. Ordner umbenannt), bleiben
        # Teil des erkannten Strukturzustands und werden wie bisher übernommen.
        snapshot["file_moves"] = [
            move
            for move in moves
            if int(move["file_id"]) not in conflicts_by_id
        ]
        structural_changed = any((
            snapshot.get("directory_added"),
            snapshot.get("directory_removed"),
            snapshot.get("root_rename"),
            snapshot.get("child_renames"),
            snapshot.get("duplicate_file_ids"),
            snapshot.get("unclassified_directories"),
            snapshot.get("inconsistent_leaf_layouts"),
            snapshot.get("semantic_change_candidates"),
        ))
        snapshot["changed"] = bool(structural_changed)

        if not snapshot["changed"]:
            # Pure physical movements within an allowed leaf are accepted
            # without a manual structure task. Queue a durable event.json
            # projection in the same transaction as the observed SQLite paths.
            if moves and root_kind == "shared_workspace" and not conflicts_by_id:
                from app.event_document_sync import queue_event_document_sync
                connection.execute(
                    "UPDATE events SET revision=revision+1,updated_at=?,edited_at=? WHERE id=?",
                    (now, now, event_id),
                )
                revision = connection.execute(
                    "SELECT revision FROM events WHERE id=?", (event_id,)
                ).fetchone()[0]
                queue_event_document_sync(
                    connection, str(event["job_id"]), event_id,
                    int(revision), now=now,
                )
            if current is not None and str(current["status"]) in {"pending", "blocked"}:
                connection.execute(
                    """UPDATE event_structure_changes
                       SET status='cancelled',updated_at=?,completed_at=?
                       WHERE id=?""",
                    (now, now, current["id"]),
                )
            return None

        status = "blocked" if snapshot["blocked"] else "pending"
        detected_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
        proposed_json = json.dumps(snapshot["proposed_layout"], ensure_ascii=False, sort_keys=True)
        if current is not None:
            try:
                prior = json.loads(str(current["detected_json"] or "{}"))
            except Exception:
                prior = {}
            if (
                str(prior.get("signature") or "") == snapshot["signature"]
                and str(current["status"]) in {"prepared", "verified"}
            ):
                return {**dict(current), "detected": snapshot}
            connection.execute(
                """UPDATE event_structure_changes
                   SET status=?,detected_json=?,proposed_layout_json=?,
                       error_message=?,updated_at=?
                   WHERE id=?""",
                (
                    status,
                    detected_json,
                    proposed_json,
                    "Die reale Struktur ist nicht eindeutig und kann nicht sicher übernommen werden."
                    if snapshot["blocked"] else None,
                    now,
                    current["id"],
                ),
            )
            change_id = str(current["id"])
        else:
            change_id = "STRUCT_" + uuid.uuid4().hex.upper()
            connection.execute(
                """INSERT INTO event_structure_changes(
                       id,event_id,job_id,root_kind,status,detected_json,
                       proposed_layout_json,proposed_input_path,error_message,
                       created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    change_id,
                    event_id,
                    str(event["job_id"]),
                    root_kind,
                    status,
                    detected_json,
                    proposed_json,
                    "",
                    "Die reale Struktur ist nicht eindeutig und kann nicht sicher übernommen werden."
                    if snapshot["blocked"] else None,
                    now,
                    now,
                ),
            )
        return {
            "id": change_id,
            "event_id": event_id,
            "job_id": str(event["job_id"]),
            "root_kind": root_kind,
            "status": status,
            "detected": snapshot,
        }


def detect_all_event_structure_changes(
    database_path: Path, workspace_path: Path | None = None,
) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        ids = [
            str(row["id"])
            for row in connection.execute(
                """SELECT id FROM events
                   WHERE parent_event_id IS NULL
                     AND COALESCE(TRIM(linkage_kind),'')=''
                     AND status IN ('applied','archived')
                   ORDER BY updated_at"""
            ).fetchall()
        ]
    detected = []
    errors = []
    for event_id in ids:
        try:
            item = detect_event_structure_change(database_path, event_id)
            if item is not None:
                detected.append(item)
        except (EventStructureChangeError, EventInventoryError, OSError) as error:
            errors.append({"event_id": event_id, "message": str(error)})
    if workspace_path is not None:
        from app.event_document_sync import recover_event_document_sync_tasks
        try:
            recover_event_document_sync_tasks(database_path, workspace_path)
        except OSError as error:
            errors.append({"event_id": "", "message": str(error)})
    return {"detected": detected, "errors": errors}


def get_structure_change(database_path: Path, change_id: str) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM event_structure_changes WHERE id=?",
            (change_id,),
        ).fetchone()
        if row is None:
            raise EventStructureChangeError("Strukturänderung wurde nicht gefunden.")
        result = dict(row)
        result["detected"] = json.loads(str(row["detected_json"] or "{}"))
        result["proposed_layout"] = json.loads(str(row["proposed_layout_json"] or "{}"))
        result.pop("detected_json", None)
        result.pop("proposed_layout_json", None)
        return result


def _validated_structure_input(
    detected: dict[str, Any],
    layout: dict[str, Any],
    input_path: str,
) -> tuple[bool, str]:
    """Kanonischen Input liefern oder eine ungültige Struktur sicher ablehnen."""
    structure_enabled = bool(detected.get("proposed_structure_enabled"))
    clean_input = _safe_rel(input_path)
    valid_paths = set(layout_paths(layout))
    if structure_enabled:
        if not clean_input:
            raise EventStructureChangeError(
                "Bitte einen Input-Ordner wählen. Bei aktiver Unterordnerstruktur "
                "muss immer genau ein vorhandener Ordner als Input festgelegt sein."
            )
        if clean_input not in valid_paths:
            raise EventStructureChangeError(
                "Der gewählte Input-Ordner gehört nicht zur erkannten Struktur."
            )
    else:
        clean_input = ""
    return structure_enabled, clean_input


def _apply_confirmed_state(
    connection: Any,
    row: dict[str, Any],
    *,
    input_path: str,
    now: str,
    input_paths: dict[str, str] | None = None,
) -> dict[str, Any]:
    detected = json.loads(str(row["detected_json"] or "{}"))
    if detected.get("blocked"):
        raise EventStructureChangeError("Die erkannte Struktur besitzt Blocker und kann nicht übernommen werden.")
    layout = json.loads(str(row["proposed_layout_json"] or "{}"))
    leaves = list(detected.get("leaf_layouts") or [])
    if len(leaves) > 1 or (leaves and leaves[0]["leaf_prefix"]):
        selected_leaves = validate_leaf_choices(leaves, input_paths, input_path)
        root_leaf = next(
            (leaf for leaf in selected_leaves if leaf["leaf_prefix"] == ""), None
        )
        if root_leaf is None:
            structure_enabled = bool(get_event_layout(connection, str(row["event_id"]))["structure_enabled"])
            clean_input = str(get_event_layout(connection, str(row["event_id"]))["input_path"])
        else:
            structure_enabled = bool(root_leaf["structure_enabled"])
            clean_input = str(root_leaf["input_path"])
            layout = root_leaf["layout"]
        save_leaf_layouts(
            connection, str(row["event_id"]), selected_leaves, now=now
        )
    else:
        structure_enabled, clean_input = _validated_structure_input(
            detected, layout, input_path
        )

    def _safe_single_folder(value: Any, label: str) -> str:
        clean = str(value or "").strip()
        path = PurePosixPath(clean)
        if (
            not clean
            or path.is_absolute()
            or len(path.parts) != 1
            or path.parts[0] in {".", ".."}
        ):
            raise EventStructureChangeError(
                f"{label} ist kein sicherer einzelner Ordnername."
            )
        return clean

    root_rename = detected.get("root_rename") or None
    if root_rename:
        new_folder = _safe_single_folder(
            root_rename.get("new_folder"),
            "Neuer Ereignisordner",
        )
        connection.execute(
            """UPDATE events
               SET folder_name=?,updated_at=?,edited_at=?
               WHERE id=? AND parent_event_id IS NULL""",
            (new_folder, now, now, row["event_id"]),
        )

    for child_rename in detected.get("child_renames") or []:
        child_id = str(child_rename.get("child_event_id") or "")
        new_folder = _safe_single_folder(
            child_rename.get("new_folder"),
            "Neuer Unterereignisordner",
        )
        child = connection.execute(
            """SELECT id FROM events
               WHERE id=? AND parent_event_id=?""",
            (child_id, row["event_id"]),
        ).fetchone()
        if child is None:
            raise EventStructureChangeError(
                "Das umbenannte Unterereignis gehört nicht mehr zu diesem Ereignis."
            )
        connection.execute(
            """UPDATE events
               SET folder_name=?,revision=revision+1,
                   updated_at=?,edited_at=?
               WHERE id=?""",
            (new_folder, now, now, child_id),
        )

    inventory = connection.execute(
        """SELECT known_file_id,relative_path FROM event_inventory_files
           WHERE event_id=? AND root_kind=? AND known_file_id IS NOT NULL""",
        (row["event_id"], row["root_kind"]),
    ).fetchall()
    seen: set[int] = set()
    for item in inventory:
        file_id = int(item["known_file_id"])
        if file_id in seen:
            raise EventStructureChangeError("Eine bekannte Kameradatei wurde mehrfach gefunden.")
        seen.add(file_id)
        connection.execute(
            """UPDATE files SET current_relative_path=?,current_root_kind=?,updated_at=?
               WHERE id=?""",
            (str(item["relative_path"]), str(row["root_kind"]), now, file_id),
        )
    update_event_layout(
        connection,
        str(row["event_id"]),
        structure_enabled=structure_enabled,
        input_path=clean_input,
        layout=layout,
        updated_at=now,
    )
    connection.execute(
        "UPDATE events SET revision=revision+1,updated_at=?,edited_at=? WHERE id=?",
        (now, now, row["event_id"]),
    )
    return {
        "structure_enabled": structure_enabled,
        "input_path": clean_input,
        "layout": layout,
        "leaf_layouts": selected_leaves if len(leaves) > 1 or (leaves and leaves[0]["leaf_prefix"]) else [],
    }


def confirm_applied_structure_change(
    database_path: Path,
    workspace_path: Path,
    change_id: str,
    *,
    input_path: str,
    input_paths: dict[str, str] | None = None,
    app_version: str | None = None,
) -> dict[str, Any]:
    """Commit observed Applied state, then durably refresh event.json.

    The database transition is intentionally two-phase. If writing event.json
    fails after SQLite has accepted the already-existing Finder state, the task
    remains verified and can be retried without applying the structure twice.
    """
    now = _now()
    with database_connection(database_path) as connection:
        raw = connection.execute(
            "SELECT * FROM event_structure_changes WHERE id=?",
            (change_id,),
        ).fetchone()
        if raw is None or str(raw["root_kind"]) != "shared_workspace":
            raise EventStructureChangeError("Diese Applied-Strukturänderung wurde nicht gefunden.")
        row = dict(raw)
        state = str(row["status"])
        if state not in {"pending", "verified"}:
            raise EventStructureChangeError("Diese Applied-Strukturänderung ist nicht mehr offen.")

        if state == "pending":
            connection.execute("BEGIN IMMEDIATE")
            layout_state = _apply_confirmed_state(
                connection, row, input_path=input_path, input_paths=input_paths, now=now
            )
            connection.execute(
                """UPDATE event_structure_changes
                   SET status='verified',proposed_input_path=?,updated_at=?,error_message=NULL
                   WHERE id=?""",
                (_safe_rel(input_path), now, change_id),
            )
            connection.commit()
        else:
            layout_state = get_event_layout(connection, str(row["event_id"]))

    try:
        from app.event_document import write_event_document
        document = build_event_document_from_db(
            database_path, workspace_path, str(row["job_id"]), str(row["event_id"])
        )
        if document is None:
            raise EventStructureChangeError("Die neue event.json konnte nicht erzeugt werden.")
        event_json = write_event_document(workspace_path, document, app_version=app_version)
    except Exception as error:
        with database_connection(database_path) as connection:
            connection.execute(
                """UPDATE event_structure_changes
                   SET status='verified',error_message=?,updated_at=?
                   WHERE id=?""",
                ("event.json konnte noch nicht aktualisiert werden: " + str(error), _now(), change_id),
            )
        if isinstance(error, EventStructureChangeError):
            raise
        raise EventStructureChangeError(
            "SQLite wurde sicher aktualisiert, aber event.json konnte noch nicht geschrieben werden. "
            "Die Aufgabe bleibt offen und kann erneut ausgeführt werden: " + str(error)
        ) from error

    done = _now()
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE event_structure_changes
               SET status='completed',updated_at=?,completed_at=?,error_message=NULL
               WHERE id=?""",
            (done, done, change_id),
        )
    return {
        "status": "completed",
        "change_id": change_id,
        "event_id": str(row["event_id"]),
        "folder_layout": layout_state,
        "event_document_path": str(event_json),
    }


def _write_prepared_document(path: Path, document: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    tmp = path.with_name(path.name + ".tmp." + digest[:12])
    with tmp.open("wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return digest


def cleanup_completed_archived_structure_helpers(
    database_path: Path,
    workspace_path: Path,
    *,
    event_id: str | None = None,
    change_id: str | None = None,
) -> dict[str, Any]:
    """Remove only verified helper event.json files from completed archive tasks.

    Older 0.28.3 builds left the prepared event.json below Später zuordnen.
    That stale, app-owned helper could later collide with a newly projected
    archive event.json. Removal is deliberately narrow: only a completed
    camera-archive structure task, its recorded exact helper path and its
    recorded SHA-256 are accepted. Empty parent folders are then pruned up to,
    but never including, Später zuordnen.
    """
    staging_root = (
        Path(workspace_path)
        / WORK_DIRECTORY_NAME
        / "Später zuordnen"
    ).resolve(strict=False)
    removed_files = 0
    removed_directories = 0
    warnings: list[str] = []

    query = """SELECT id,event_id,detected_json
               FROM event_structure_changes
               WHERE root_kind='camera_archive' AND status='completed'"""
    params: list[Any] = []
    if change_id is not None:
        query += " AND id=?"
        params.append(str(change_id))
    if event_id is not None:
        query += " AND event_id=?"
        params.append(str(event_id))
    query += " ORDER BY completed_at,id"

    with database_connection(database_path) as connection:
        rows = [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]

    for row in rows:
        try:
            detected = json.loads(str(row.get("detected_json") or "{}"))
        except Exception:
            warnings.append(
                f"{row.get('id')}: gespeicherte Hilfsdatei-Information ist beschädigt."
            )
            continue
        raw_path = str(detected.get("prepared_event_json_path") or "").strip()
        expected_sha = str(detected.get("prepared_event_json_sha256") or "").strip()
        if not raw_path or not expected_sha:
            continue

        helper_path = Path(raw_path).expanduser().resolve(strict=False)
        if helper_path == staging_root or staging_root not in helper_path.parents:
            warnings.append(
                f"{row.get('id')}: gespeicherter Hilfsdateipfad liegt außerhalb von Später zuordnen."
            )
            continue

        if helper_path.exists() or helper_path.is_symlink():
            if not helper_path.is_file() or helper_path.is_symlink():
                warnings.append(
                    f"{row.get('id')}: Hilfsdateipfad ist keine reguläre Datei."
                )
                continue
            try:
                actual_sha = hashlib.sha256(helper_path.read_bytes()).hexdigest()
            except OSError as exc:
                warnings.append(f"{row.get('id')}: Hilfsdatei konnte nicht geprüft werden: {exc}")
                continue
            if actual_sha != expected_sha:
                warnings.append(
                    f"{row.get('id')}: Hilfsdatei wurde nicht entfernt, weil ihr Inhalt vom bestätigten Stand abweicht."
                )
                continue
            try:
                helper_path.unlink()
                removed_files += 1
            except OSError as exc:
                warnings.append(f"{row.get('id')}: Hilfsdatei konnte nicht entfernt werden: {exc}")
                continue

        current = helper_path.parent
        while current != staging_root and staging_root in current.parents:
            try:
                current.rmdir()
                removed_directories += 1
            except OSError:
                break
            current = current.parent

    return {
        "removed_file_count": removed_files,
        "removed_directory_count": removed_directories,
        "warnings": warnings,
    }


def prepare_archived_structure_change(
    database_path: Path,
    workspace_path: Path,
    change_id: str,
    *,
    input_path: str,
    input_paths: dict[str, str] | None = None,
    app_version: str | None = None,
) -> dict[str, Any]:
    now = _now()
    with database_connection(database_path) as connection:
        raw = connection.execute(
            "SELECT * FROM event_structure_changes WHERE id=?",
            (change_id,),
        ).fetchone()
        if raw is None or str(raw["status"]) not in {"pending", "prepared"} or str(raw["root_kind"]) != "camera_archive":
            raise EventStructureChangeError("Diese Archiv-Strukturänderung ist nicht mehr offen.")
        row = dict(raw)
        detected = json.loads(str(row["detected_json"] or "{}"))
        if detected.get("blocked"):
            raise EventStructureChangeError("Die erkannte Archivstruktur besitzt Blocker.")
        layout = json.loads(str(row["proposed_layout_json"] or "{}"))
        leaves = list(detected.get("leaf_layouts") or [])
        if len(leaves) > 1 or (leaves and leaves[0]["leaf_prefix"]):
            selected_leaves = validate_leaf_choices(leaves, input_paths, input_path)
            root_leaf = next(
                (leaf for leaf in selected_leaves if leaf["leaf_prefix"] == ""), None
            )
            clean_input = str(root_leaf["input_path"]) if root_leaf is not None else str(
                get_event_layout(connection, str(row["event_id"]))["input_path"]
            )
            if root_leaf is not None:
                layout = root_leaf["layout"]
        else:
            selected_leaves = []
            _structure_enabled, clean_input = _validated_structure_input(
                detected, layout, input_path
            )
        event = connection.execute(
            "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
            (row["event_id"],),
        ).fetchone()
        if event is None:
            raise EventStructureChangeError("Das archivierte Ereignis wurde nicht gefunden.")

    document = build_event_document_from_db(
        database_path,
        workspace_path,
        str(row["job_id"]),
        str(row["event_id"]),
        include_archived=True,
    )
    if document is None:
        raise EventStructureChangeError("Die neue Archiv-event.json konnte nicht erzeugt werden.")
    document = dict(document)
    document["folder_layout"] = {
        "structure_enabled": bool(root_leaf["structure_enabled"]) if selected_leaves and root_leaf is not None else bool(detected.get("proposed_structure_enabled")),
        "input_path": clean_input,
        "layout": layout,
        "revision": int((document.get("folder_layout") or {}).get("revision") or 1) + 1,
    }
    if selected_leaves:
        document["leaf_folder_layouts"] = selected_leaves
    document["structure"] = _tree_text(detected.get("observed_directories") or [])
    if app_version:
        document["source_app_version"] = app_version
        document["generated_at"] = now

    year = str(event["start_datetime"] or "")[:4]
    folder = str(event["folder_name"])
    prepared = (
        Path(workspace_path)
        / WORK_DIRECTORY_NAME
        / "Später zuordnen"
        / year
        / folder
        / EVENT_DOCUMENT_FILENAME
    )
    digest = _write_prepared_document(prepared, document)
    detected["prepared_event_json_path"] = str(prepared)
    detected["prepared_event_json_sha256"] = digest
    detected["selected_input_path"] = clean_input
    detected["selected_leaf_input_paths"] = {leaf["leaf_key"]: leaf["input_path"] for leaf in selected_leaves}
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE event_structure_changes
               SET status='prepared',detected_json=?,proposed_input_path=?,updated_at=?
               WHERE id=?""",
            (json.dumps(detected, ensure_ascii=False, sort_keys=True), clean_input, now, change_id),
        )
    return {
        "status": "prepared",
        "change_id": change_id,
        "event_id": str(row["event_id"]),
        "prepared_event_json_path": str(prepared),
        "prepared_event_json_sha256": digest,
        "archive_target_relative_path": f"{year}/{folder}/{EVENT_DOCUMENT_FILENAME}",
    }


def verify_archived_structure_change(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    change_id: str,
) -> dict[str, Any]:
    now = _now()
    with database_connection(database_path) as connection:
        raw = connection.execute(
            "SELECT * FROM event_structure_changes WHERE id=?",
            (change_id,),
        ).fetchone()
        if raw is None or str(raw["status"]) != "prepared" or str(raw["root_kind"]) != "camera_archive":
            raise EventStructureChangeError("Diese Archiv-Strukturänderung wartet nicht auf Prüfung.")
        row = dict(raw)
        detected = json.loads(str(row["detected_json"] or "{}"))
        event = connection.execute(
            "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
            (row["event_id"],),
        ).fetchone()
        if event is None:
            raise EventStructureChangeError("Das archivierte Ereignis fehlt.")
    year = str(event["start_datetime"] or "")[:4]
    target = Path(archive_root) / year / str(event["folder_name"]) / EVENT_DOCUMENT_FILENAME
    if not target.is_file() or target.is_symlink():
        raise EventStructureChangeError("Die neue event.json wurde im Archiv noch nicht gefunden.")
    actual_sha = hashlib.sha256(target.read_bytes()).hexdigest()
    expected_sha = str(detected.get("prepared_event_json_sha256") or "")
    if not expected_sha or actual_sha != expected_sha:
        raise EventStructureChangeError("Die event.json im Archiv entspricht noch nicht der vorbereiteten Datei.")

    inventory = scan_event_inventory(
        database_path,
        archive_root,
        str(row["job_id"]),
        str(row["event_id"]),
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    with database_connection(database_path) as connection:
        event_now, layout_now = _event_state(connection, str(row["event_id"]))
        current = _snapshot_from_inventory(connection, event_now, layout_now, "camera_archive")
        if str(current.get("signature") or "") != str(detected.get("signature") or ""):
            raise EventStructureChangeError(
                "Der Archivbestand hat sich seit der Vorschau erneut verändert. Bitte die Aufgabe neu prüfen."
            )
        connection.execute("BEGIN IMMEDIATE")
        layout_state = _apply_confirmed_state(
            connection,
            row,
            input_path=str(row.get("proposed_input_path") or ""),
            input_paths=detected.get("selected_leaf_input_paths"),
            now=now,
        )
        connection.execute(
            """UPDATE event_structure_changes
               SET status='completed',updated_at=?,completed_at=?,error_message=NULL
               WHERE id=?""",
            (now, now, change_id),
        )
        connection.commit()

    helper_cleanup = cleanup_completed_archived_structure_helpers(
        database_path,
        workspace_path,
        change_id=change_id,
    )
    return {
        "status": "completed",
        "change_id": change_id,
        "event_id": str(row["event_id"]),
        "folder_layout": layout_state,
        "verified_event_json_sha256": actual_sha,
        "archive_read_only": True,
        "helper_cleanup": helper_cleanup,
    }
