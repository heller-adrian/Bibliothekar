"""Detect and reconcile manual filesystem organization changes for 0.28.0.

The filesystem is observational IST.  A detected difference becomes a durable
task.  Applied events can be accepted in-place after user confirmation.
Archived events remain read-only: Bibliothekar prepares a replacement event.json
under Später zuordnen and only commits SQLite after that exact document appears
in the archive and the live inventory still matches.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat
import uuid

from app.database import database_connection
from app.event_access import event_file_rows, event_source_jobs
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
    original = str(value or "").replace("\\", "/")
    if not original:
        return ""
    # Never silently strip an absolute root before checking it. PurePosixPath
    # also normalizes repeated separators and "." components, so inspect the
    # original components before constructing the path.
    if original.startswith("/") or any(
        part in {"", ".", ".."} for part in original.split("/")
    ):
        raise EventStructureChangeError(
            "Unsicherer relativer Strukturpfad: " + original
        )
    path = PurePosixPath(original)
    if path.is_absolute():
        raise EventStructureChangeError(
            "Unsicherer relativer Strukturpfad: " + original
        )
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


def validate_guided_structure_edit(
    connection: Any,
    event_id: str,
    change_id: str,
    preview: dict[str, Any],
    *,
    expected_root_kind: str | None = None,
) -> dict[str, Any]:
    """0.52.1: never interpret physical Finder moves as event reassignment.

    The normal editor can still change event ownership through its own fully
    validated workflow, but a manual folder deletion is not an authorization
    to dissolve a time-bounded subevent or silently rewrite SQL assignments.
    """
    raise EventStructureChangeError(
        "Automatic dissolution of subevents from Finder moves is disabled. "
        "Restore the original folders and use the normal event editor for changes."
    )
    row = connection.execute(
        """SELECT * FROM event_structure_changes
           WHERE id=? AND event_id=? AND status='blocked'""",
        (str(change_id), str(event_id)),
    ).fetchone()
    if row is None:
        raise EventStructureChangeError("The manual change task is no longer active.")
    row = dict(row)
    if expected_root_kind is not None and row["root_kind"] != expected_root_kind:
        raise EventStructureChangeError("The manual change belongs to another storage area.")
    try:
        detected = json.loads(str(row["detected_json"] or "{}"))
    except (TypeError, ValueError) as exc:
        raise EventStructureChangeError("The observed structure is invalid.") from exc
    candidates = detected.get("semantic_change_candidates") or []
    # A front-end task is not an authorization token on its own: re-evaluate
    # the current complete inventory in the same transaction and reject any
    # snapshot that changed since the user reviewed it.
    current_event, current_layout = _event_state(connection, event_id)
    current = _snapshot_from_inventory(
        connection, current_event, current_layout, str(row["root_kind"])
    )
    if (
        str(current.get("signature") or "") != str(detected.get("signature") or "")
        or current.get("semantic_change_candidates") != candidates
    ):
        raise EventStructureChangeError(
            "The filesystem inventory changed. Reload before accepting the edit."
        )
    if detected.get("root_rename") or detected.get("child_renames"):
        raise EventStructureChangeError(
            "Folder renames must be resolved separately before this edit."
        )
    actual_directories = set(current.get("observed_directories") or [])
    for candidate in candidates:
        folder = str(candidate.get("old_folder") or "")
        if not candidate.get("former_tree_physically_absent") or any(
            directory == folder or directory.startswith(folder + "/")
            for directory in actual_directories
        ):
            raise EventStructureChangeError(
                "The former subevent folder, including empty folders, must be fully absent."
            )
    candidate_file_ids = {
        int(fid) for candidate in candidates for fid in candidate.get("file_ids") or []
    }
    unresolved = [
        item for item in current.get("placement_conflicts") or []
        if int(item["file_id"]) not in candidate_file_ids
    ]
    if unresolved:
        raise EventStructureChangeError("An unrelated file-placement conflict is still open.")
    if not candidates or any(
        (detected.get(key) or []) for key in (
            "missing_file_ids", "duplicate_file_ids", "unclassified_directories",
        )
    ):
        raise EventStructureChangeError("Manual structure changes are not unambiguous.")
    event = connection.execute(
        "SELECT * FROM events WHERE id=? AND parent_event_id IS NULL",
        (event_id,),
    ).fetchone()
    if event is None or str(event["event_kind"]) != "event":
        raise EventStructureChangeError("Only normal parent events support this transition.")
    event = dict(event)
    if str(preview.get("parent_folder") or "") != str(event["folder_name"]):
        raise EventStructureChangeError("Changing the parent folder requires a separate edit.")
    if (
        str(preview.get("start_date") or "") != str(event["start_datetime"])[:10]
        or str(preview.get("end_date") or "") != str(event["end_datetime"])[:10]
    ):
        raise EventStructureChangeError("Changing the parent period requires a separate edit.")
    # The physical arrangement was already performed. A guided dissolution
    # MUST NOT smuggle in changes requiring a new sort or new folder creation.
    if bool(preview.get("preserve_day_folders")) != bool(event["preserve_day_folders"]):
        raise EventStructureChangeError(
            "Day-folder settings must be edited separately from a manual dissolution."
        )
    if bool(preview.get("uses_time_range")):
        proposed_start = str(preview.get("start_time") or "")[:5]
        proposed_end = str(preview.get("end_time") or "")[:5]
        if (
            proposed_start != str(event["start_datetime"])[11:16]
            or proposed_end != str(event["end_datetime"])[11:16]
        ):
            raise EventStructureChangeError(
                "Changing parent time boundaries requires a separate edit."
            )
    elif (
        str(event["start_datetime"])[11:19] != "00:00:00"
        or str(event["end_datetime"])[11:19] != "23:59:59"
    ):
        raise EventStructureChangeError(
            "The parent time boundaries may not change in this guided edit."
        )
    new_layout = preview.get("folder_layout")
    if isinstance(new_layout, dict) and any((
        bool(new_layout.get("structure_enabled")) != bool(current_layout["structure_enabled"]),
        str(new_layout.get("input_path") or "") != str(current_layout.get("input_path") or ""),
        new_layout.get("layout") != current_layout.get("layout"),
    )):
        raise EventStructureChangeError(
            "Changing the parent folder layout requires a separate edit."
        )
    children = [
        dict(child) for child in connection.execute(
            "SELECT id,name,start_datetime,end_datetime FROM events WHERE parent_event_id=?",
            (event_id,),
        ).fetchall()
    ]
    old_by_id = {str(child["id"]): child for child in children}
    candidate_ids = {str(c["child_event_id"]) for c in candidates}
    if not candidate_ids or not candidate_ids <= set(old_by_id):
        raise EventStructureChangeError("A referenced subevent no longer exists.")
    new_children = list(preview.get("subevents") or [])
    remaining_ids = {str(c.get("id") or "") for c in new_children}
    if (
        len(remaining_ids) != len(new_children)
        or any(not cid or cid not in old_by_id for cid in remaining_ids)
        or remaining_ids != set(old_by_id) - candidate_ids
    ):
        raise EventStructureChangeError(
            "Only the physically dissolved subevents may be removed in this guided edit."
        )
    for c in new_children:
        old = old_by_id[str(c["id"])]
        if (
            str(c.get("name") or "") != str(old["name"])
            or str(c.get("folder_name") or "") != str(old["folder_name"])
            or str(c.get("start_datetime") or "")[:19] != str(old["start_datetime"])[:19]
            or str(c.get("end_datetime") or "")[:19] != str(old["end_datetime"])[:19]
        ):
            raise EventStructureChangeError("Other subevents must remain unchanged.")

    known_ids = set()
    parent_layout = current_layout["layout"]
    allowed_parent_paths = set(layout_paths(parent_layout))
    allowed_top_levels = {
        str(PurePosixPath(path).parts[0])
        for path in allowed_parent_paths if PurePosixPath(path).parts
    }
    if not allowed_top_levels:
        raise EventStructureChangeError(
            "A verified parent organization destination is required."
        )
    for item in candidates:
        if str(item.get("new_parent_folder") or "") not in allowed_top_levels:
            raise EventStructureChangeError(
                "The files must all be inside a known parent organization folder."
            )
        known_ids.update(int(v) for v in item.get("file_ids") or [])
    if not known_ids:
        raise EventStructureChangeError("No files were verified for the dissolved subevent.")
    # Every original file and family of each child must be in the proposed
    # relocation. Partial moves are placement conflicts, never dissolutions.
    for candidate in candidates:
        old_id = str(candidate["child_event_id"])
        expected_child_ids = {
            int(row["id"]) for row in connection.execute(
                """SELECT DISTINCT f.id FROM files f
                   JOIN event_assignments ea
                      ON ea.file_id=f.id OR (ea.file_id IS NULL AND ea.family_id=f.family_id)
                   WHERE ea.event_id=?""",
                (old_id,),
            ).fetchall()
        }
        if not expected_child_ids or expected_child_ids != {
            int(value) for value in candidate.get("file_ids") or []
        }:
            raise EventStructureChangeError(
                "Only a complete relocation of every known subevent file may be accepted."
            )
    inventory = connection.execute(
        """SELECT known_file_id,event_relative_path,sha256,size_bytes
           FROM event_inventory_files
           WHERE event_id=? AND root_kind=? AND known_file_id IS NOT NULL""",
        (event_id, row["root_kind"]),
    ).fetchall()
    from collections import Counter
    occurrences = Counter(int(v["known_file_id"]) for v in inventory)
    if any(occurrences[file_id] != 1 for file_id in known_ids):
        raise EventStructureChangeError("The moved files must each occur exactly once.")
    for file_id in known_ids:
        file_row = connection.execute(
            """SELECT f.selected_capture_time,ff.selected_capture_time AS family_time
               FROM files f LEFT JOIN file_families ff ON ff.id=f.family_id
               WHERE f.id=?""",
            (file_id,),
        ).fetchone()
        if file_row is None:
            raise EventStructureChangeError("A moved file disappeared from the database.")
        capture = str(file_row["selected_capture_time"] or file_row["family_time"] or "")[:19]
        if not capture or not (
            str(event["start_datetime"])[:19] <= capture <= str(event["end_datetime"])[:19]
        ):
            raise EventStructureChangeError("A moved photo is outside the parent event's time interval.")
    # Preserve parent family ownership: changing family selection, root folder
    # layouts or unrelated siblings must use the ordinary reviewed editor.
    current_families = {
        int(v["family_id"]) for v in connection.execute(
            """SELECT DISTINCT ea.family_id FROM event_assignments ea
               JOIN events e ON e.id=ea.event_id
               WHERE COALESCE(e.parent_event_id,e.id)=? AND ea.family_id IS NOT NULL""",
            (event_id,),
        ).fetchall()
    }
    if {int(v) for v in preview.get("selected_family_ids") or []} != current_families:
        raise EventStructureChangeError("Manual guided edits cannot add or remove families.")
    return {"change_id": row["id"], "removed_child_ids": sorted(candidate_ids)}


def assert_no_open_structure_change(
    connection: Any, event_id: str, *,
    guided_change_id: str | None = None,
    preview: dict[str, Any] | None = None,
) -> None:
    row = connection.execute(
        """SELECT id,status FROM event_structure_changes
           WHERE event_id=? AND status IN ('pending','prepared','verified','blocked')
           ORDER BY created_at DESC LIMIT 1""",
        (event_id,),
    ).fetchone()
    if row is not None:
        if (
            guided_change_id and preview is not None
            and str(row["id"]) == str(guided_change_id)
        ):
            validate_guided_structure_edit(
                connection, event_id, guided_change_id, preview,
                expected_root_kind="shared_workspace",
            )
            return
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
        # 0.52.0: moving all known files is not a dissolution if any part of
        # the former child tree still exists (including empty Export folders).
        # Neither an empty child shell nor remaining unknown assets may be
        # silently reclassified as a deleted subevent.
        former_tree_remains = any(
            directory == old_folder or directory.startswith(old_folder + "/")
            for directory in observed_dirs
        ) or any(
            str(item.get("event_relative_path") or "").startswith(old_folder + "/")
            for item in assets
        )
        if former_tree_remains:
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
                "file_ids": sorted(set(file_ids)),
                "former_tree_physically_absent": True,
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
        child_intervals.setdefault(int(assignment["file_id"]), (
            str(assignment["start_datetime"] or "")[:19],
            str(assignment["end_datetime"] or "")[:19],
        ))

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
    # Preserve original path evidence in the task so the complete physical
    # tree can be restored, even after SQLite follows an observed Finder move.
    dissolve_ids = {
        int(fid) for candidate in semantic_change_candidates
        for fid in (candidate.get("file_ids") or [])
    }
    restore_original_paths = {
        str(item["file_id"]): str(item["old_path"])
        for item in file_moves
        if int(item["file_id"]) in dissolve_ids
    }
    restore_observed_paths = {
        str(file_id): str(observed_known[file_id].get("relative_path") or "")
        for file_id in dissolve_ids if file_id in observed_known
    }
    # A user may move the files, trigger Refresh (creating ordinary placement
    # notices), and only afterwards delete the empty child directory.
    # SQLite already follows IST by then: recover the original SOLL location
    # from the persistent placement notice, never from the new SQLite path.
    for candidate in semantic_change_candidates:
        child_folder = str(candidate.get("old_folder") or "")
        for fid in candidate.get("file_ids") or []:
            file_id = int(fid)
            if str(file_id) in restore_original_paths:
                continue
            old_path = _open_placement_expected_path(connection, file_id)
            expected_prefix = expected_root + "/" + child_folder + "/"
            if old_path and old_path.startswith(expected_prefix):
                restore_original_paths[str(file_id)] = old_path
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
        "restore_original_paths": restore_original_paths,
        "restore_observed_paths": restore_observed_paths,
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
            # If an entire child leaf vanished together with confirmed-lost
            # originals, its formerly empty Export / Sorted descendants are
            # part of the SAME loss, not a second user-approved layout edit.
            # Keep unrelated missing directories as real structure tasks.
            snapshot["directory_removed"] = [
                directory
                for directory in snapshot.get("directory_removed") or []
                if not any(
                    directory == deleted or directory.startswith(deleted + "/")
                    for deleted in accepted_deleted_dirs
                )
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
                and prior.get("semantic_change_candidates") == snapshot.get("semantic_change_candidates")
            ):
                # The already accepted physical IST path replaces files.current_relative_path.
                # Never erase the first captured original locations on a second scan.
                for fid, previous_path in (prior.get("restore_original_paths") or {}).items():
                    snapshot["restore_original_paths"].setdefault(str(fid), str(previous_path))
                for fid, previous_path in (prior.get("restore_observed_paths") or {}).items():
                    snapshot["restore_observed_paths"].setdefault(str(fid), str(previous_path))
                detected_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True)
                if str(current["status"]) in {"prepared", "verified"}:
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


def _renamed_display_name(event: Any, new_folder: str) -> str:
    name = str(event["name"])
    old_folder = str(event["folder_name"])
    if name and old_folder.endswith(name):
        prefix = old_folder[:-len(name)]
        if new_folder.startswith(prefix) and new_folder[len(prefix):].strip():
            return new_folder[len(prefix):].strip()
    # A non-standard folder name is itself the explicit new title. Never
    # guess a date prefix from an unrelated arbitrary naming convention.
    return new_folder


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
        # A child folder may have been renamed physically. Keep the stable
        # leaf key while updating the portable leaf prefix to the new folder.
        child_prefix_renames = {
            str(rename["old_folder"]): str(rename["new_folder"])
            for rename in (detected.get("child_renames") or [])
        }
        for leaf in selected_leaves:
            parts = str(leaf["leaf_prefix"]).split("/")
            if parts and parts[0] in child_prefix_renames:
                parts[0] = child_prefix_renames[parts[0]]
                leaf["leaf_prefix"] = "/".join(parts)
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
        previous = connection.execute(
            "SELECT name,folder_name FROM events WHERE id=?", (row["event_id"],)
        ).fetchone()
        connection.execute(
            """UPDATE events
               SET folder_name=?,name=?,updated_at=?,edited_at=?
               WHERE id=? AND parent_event_id IS NULL""",
            (new_folder, _renamed_display_name(previous, new_folder), now, now, row["event_id"]),
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
    """Atomically stage only an event's own document, never a foreign file."""
    expected_event_id = str((document.get("event") or {}).get("id") or "")
    if not expected_event_id:
        raise EventStructureChangeError("Die vorzubereitende event.json besitzt keine Ereignis-ID.")
    # Symlinks below the staging root could redirect the new file to a
    # different event or an external volume. The trusted root itself may be
    # a historical compatibility symlink, hence check only year/event leaves.
    if path.parent.is_symlink() or path.parent.parent.is_symlink() or path.is_symlink():
        raise EventStructureChangeError("Die event.json-Hilfsstruktur enthält einen symbolischen Link.")
    if path.exists():
        if not path.is_file():
            raise EventStructureChangeError("Das event.json-Hilfsziel ist keine reguläre Datei.")
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError, OSError) as exc:
            raise EventStructureChangeError("Fremde oder beschädigte vorbereitete event.json bleibt unverändert.") from exc
        if (
            not isinstance(previous, dict)
            or str(previous.get("source") or "") != "kamera-automatisierung"
            or str((previous.get("event") or {}).get("id") or "") != expected_event_id
        ):
            raise EventStructureChangeError("Vorhandene event.json gehört einem anderen Ereignis.")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    tmp = path.with_name(path.name + ".tmp." + digest[:12])
    if tmp.exists() or tmp.is_symlink():
        # A crash may leave our deterministic temporary file behind. Reuse
        # only exact bytes for this document; never overwrite a foreign file.
        if (
            tmp.is_symlink() or not tmp.is_file()
            or hashlib.sha256(tmp.read_bytes()).hexdigest() != digest
        ):
            raise EventStructureChangeError(
                "Fremde oder abweichende temporäre event.json bleibt erhalten."
            )
    else:
        with tmp.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    try:
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return digest


def _archive_structure_helper_root(
    workspace_path: Path, work_root: Path | None = None,
) -> Path:
    """Choose a staging directory without migrating any existing folders.

    The production caller supplies the selected library's real work_root.
    Legacy direct callers retain their historical compatibility location.
    Existing German staging directories always take precedence to avoid
    splitting already started archive changes across physical directories.
    """
    base = Path(work_root) if work_root is not None else (
        Path(workspace_path) / WORK_DIRECTORY_NAME
    )
    old = base / "Später zuordnen"
    if old.is_dir() and not old.is_symlink():
        return old
    new = base / "Assign Later"
    if new.is_dir() and not new.is_symlink():
        return new
    return new


def cleanup_completed_archived_structure_helpers(
    database_path: Path,
    workspace_path: Path,
    *,
    event_id: str | None = None,
    change_id: str | None = None,
    work_root: Path | None = None,
) -> dict[str, Any]:
    """Remove only verified helper event.json files from completed archive tasks.

    Older 0.28.3 builds left the prepared event.json below Später zuordnen.
    That stale, app-owned helper could later collide with a newly projected
    archive event.json. Removal is deliberately narrow: only a completed
    camera-archive structure task, its recorded exact helper path and its
    recorded SHA-256 are accepted. Empty parent folders are then pruned up to,
    but never including, Später zuordnen.
    """
    base = Path(work_root) if work_root is not None else (
        Path(workspace_path) / WORK_DIRECTORY_NAME
    )
    allowed_staging_roots = {
        (base / name).resolve(strict=False)
        for name in ("Später zuordnen", "Assign Later")
    }
    # Legacy records may have used the root compatibility alias even when
    # the configured library work_root now points elsewhere.
    allowed_staging_roots.add(
        (Path(workspace_path) / WORK_DIRECTORY_NAME / "Später zuordnen").resolve(strict=False)
    )
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
        staging_root = next(
            (root for root in allowed_staging_roots if root in helper_path.parents),
            None,
        )
        if staging_root is None:
            warnings.append(
                f"{row.get('id')}: Hilfsdatei liegt außerhalb des erlaubten Assign-Later-Bereichs."
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
    work_root: Path | None = None,
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
    if detected.get("root_rename"):
        document["event"] = {**document["event"], "folder_name": detected["root_rename"]["new_folder"],
                             "name": _renamed_display_name(event, detected["root_rename"]["new_folder"])}
    if app_version:
        document["source_app_version"] = app_version
        document["generated_at"] = now

    year = str(event["start_datetime"] or "")[:4]
    folder = str(event["folder_name"])
    prepared = (
        _archive_structure_helper_root(workspace_path, work_root)
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
        "archive_target_relative_path": str((detected.get("root_rename") or {}).get("new_path") or f"{year}/{folder}") + "/" + EVENT_DOCUMENT_FILENAME,
    }


@contextmanager
def _bound_archive_document(archive_root: Path, event: Any, detected: dict[str, Any]):
    """Bind the prepared, unique event document to no-follow directory FDs.

    Identity alone never authorizes adoption: the exact prepared document and
    the unchanged, hash-verified family inventory are required by the caller.
    Keep the bindings alive until its SQLite commit, rejecting replacements.
    """
    year = str(event["start_datetime"] or "")[:4]
    expected = _safe_rel((detected.get("root_rename") or {}).get("new_path")
                         or f"{year}/{event['folder_name']}")
    if len(PurePosixPath(expected).parts) != 2 or PurePosixPath(expected).parts[0] != year:
        raise EventStructureChangeError("Der vorbereitete Archivpfad ist ungültig.")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as stack:
        def opened(name: str, parent: int | None, directory: bool = True) -> int:
            fd = os.open(name, flags if directory else os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                         dir_fd=parent)
            stack.callback(os.close, fd)
            return fd

        bindings = []
        def bound(name: str, parent: int, directory: bool = True) -> int:
            fd = opened(name, parent, directory)
            bindings.append((parent, name, fd))
            return fd

        try:
            parent = opened("/", None)
            for part in Path(archive_root).absolute().parts[1:]:
                parent = bound(part, parent)
            year_fd = bound(year, parent)
            matches = []
            for name in os.listdir(year_fd):
                info = os.stat(name, dir_fd=year_fd, follow_symlinks=False)
                if not stat.S_ISDIR(info.st_mode):
                    continue
                # Close unrelated candidates immediately: a large archive
                # must not consume one open FD per event until commit.
                with ExitStack() as candidate:
                    candidate_fd = os.open(name, flags, dir_fd=year_fd)
                    candidate.callback(os.close, candidate_fd)
                    try:
                        doc_fd = os.open(EVENT_DOCUMENT_FILENAME, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                         dir_fd=candidate_fd)
                    except FileNotFoundError:
                        continue
                    candidate.callback(os.close, doc_fd)
                    info = os.fstat(doc_fd)
                    if not stat.S_ISREG(info.st_mode):
                        raise EventStructureChangeError("Die event.json ist keine reguläre Datei.")
                    with os.fdopen(os.dup(doc_fd), "rb") as stream:
                        content = stream.read()
                    try:
                        payload = json.loads(content)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if not isinstance(payload, dict) or not isinstance(payload.get("event"), dict):
                        continue
                    if str(payload["event"].get("id") or "") == str(event["id"]):
                        matches.append((name, candidate_fd, doc_fd, content, info))
                        stack.enter_context(candidate.pop_all())
            if not matches:
                raise EventStructureChangeError("Die event.json im Archiv entspricht noch nicht der vorbereiteten Datei.")
            if len(matches) != 1:
                raise EventStructureChangeError("Der Archiv-Ereignisordner ist nicht eindeutig nachgewiesen.")
            name, folder_fd, doc_fd, content, document_info = matches[0]
            prefix = f"{year}/{name}"
            if prefix != expected:
                raise EventStructureChangeError("Der Archivpfad hat sich seit der Vorschau verändert.")
            bindings.extend([(year_fd, name, folder_fd), (folder_fd, EVENT_DOCUMENT_FILENAME, doc_fd)])
            actual_sha = hashlib.sha256(content).hexdigest()
            if not detected.get("prepared_event_json_sha256") or actual_sha != detected["prepared_event_json_sha256"]:
                raise EventStructureChangeError("Die event.json im Archiv entspricht noch nicht der vorbereiteten Datei.")

            def validate_binding():
                for parent_fd, entry, fd in bindings:
                    actual = os.stat(entry, dir_fd=parent_fd, follow_symlinks=False)
                    held = os.fstat(fd)
                    if (actual.st_dev, actual.st_ino, actual.st_mode) != (held.st_dev, held.st_ino, held.st_mode):
                        raise EventStructureChangeError("Die Archiv-Pfadbindung wurde verändert.")
                after = os.fstat(doc_fd)
                if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (
                    document_info.st_size, document_info.st_mtime_ns, document_info.st_ctime_ns
                ):
                    raise EventStructureChangeError("Die event.json wurde während der Prüfung verändert.")
            validate_binding()
            yield prefix, actual_sha, validate_binding, json.loads(content)
        except OSError as error:
            raise EventStructureChangeError("Der Archivpfad ist nicht sicher lesbar: " + str(error)) from error


def verify_archived_structure_change(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    change_id: str,
    *,
    work_root: Path | None = None,
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
    with _bound_archive_document(archive_root, event, detected) as (prefix, actual_sha, validate_binding, document):
        inventory = scan_event_inventory(
            database_path,
            archive_root,
            str(row["job_id"]),
            str(row["event_id"]),
            root_kind="camera_archive",
            persist=True,
            update_known_file_locations=False,
            fast_refresh=False,
            event_prefix_override=prefix,
        )
        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            event_now, layout_now = _event_state(connection, str(row["event_id"]))
            current = _snapshot_from_inventory(connection, event_now, layout_now, "camera_archive")
            if str(current.get("signature") or "") != str(detected.get("signature") or ""):
                raise EventStructureChangeError(
                    "Der Archivbestand hat sich seit der Vorschau erneut verändert. Bitte die Aufgabe neu prüfen."
                )
            if current.get("blocked") or current.get("root_rename") != detected.get("root_rename"):
                raise EventStructureChangeError("Die Ereignisidentität oder Dateifamilien sind nicht mehr eindeutig.")
            owned = {int(item["id"]): (item["family_id"], str(item["sha256_current"] or item["sha256_original"] or ""))
                     for item in event_file_rows(connection, str(row["event_id"]))}
            documented = {int(item["known_file_id"]): (item.get("family_id"), str(item.get("sha256") or ""))
                          for item in document.get("files", []) if item.get("known_file_id") is not None}
            if not owned or owned != documented or {
                str(item["job_id"]) for item in event_source_jobs(connection, str(row["event_id"]))
            } != {str(item["job_id"]) for item in document.get("source_jobs", [])}:
                raise EventStructureChangeError("Herkunft oder Dateifamilien stimmen nicht mit der vorbereiteten event.json überein.")
            validate_binding()
            pending = connection.execute("SELECT status,detected_json FROM event_structure_changes WHERE id=?", (change_id,)).fetchone()
            if pending is None or pending["status"] != "prepared" or pending["detected_json"] != row["detected_json"]:
                raise EventStructureChangeError("Die Strukturänderung wurde inzwischen bearbeitet.")
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
            validate_binding()
            connection.commit()

    helper_cleanup = cleanup_completed_archived_structure_helpers(
        database_path,
        workspace_path,
        change_id=change_id,
        work_root=work_root,
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
