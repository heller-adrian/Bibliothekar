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
from app.event_inventory import scan_event_inventory, EventInventoryError
from app.event_layout import get_event_layout, layout_paths, layout_role_paths, update_event_layout
from app.event_document import build_event_document_from_db, EVENT_DOCUMENT_FILENAME
from app.external_changes import record_notice
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


def _snapshot_from_inventory(
    connection: Any,
    event: dict[str, Any],
    layout_state: dict[str, Any],
    root_kind: str,
) -> dict[str, Any]:
    event_id = str(event["id"])
    leaves = _leaf_prefixes(connection, event)
    dir_rows = connection.execute(
        """SELECT event_relative_path FROM event_inventory_directories
           WHERE event_id=? AND root_kind=? ORDER BY event_relative_path""",
        (event_id, root_kind),
    ).fetchall()
    observed_dirs = [_safe_rel(row["event_relative_path"]) for row in dir_rows]

    known_rows = connection.execute(
        """SELECT known_file_id,family_id,relative_path,event_relative_path,filename,
                  size_bytes,sha256,asset_kind
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

    file_moves = []
    for file_id, observed in observed_known.items():
        expected = expected_files.get(file_id)
        if expected is None:
            continue
        old = _safe_rel(expected.get("current_relative_path"))
        new = _safe_rel(observed.get("relative_path"))
        if old != new:
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
    for directory in observed_dirs:
        if directory in structural_leaf_dirs:
            continue
        split = _split_org_path(directory, leaves)
        if split is None:
            unclassified.append(directory)
            continue
        leaf, rest = split
        if rest:
            by_leaf.setdefault(leaf, set()).add(rest)

    nonempty_sets = [paths for paths in by_leaf.values()]
    canonical_sets = {tuple(sorted(paths)) for paths in nonempty_sets}
    inconsistent = len(canonical_sets) > 1
    proposed_paths = sorted(next(iter(canonical_sets), ())) if not inconsistent else []
    preserved_roles = {
        "export": set(layout_role_paths(layout_state["layout"], "export")),
    }
    proposed_layout = _layout_from_paths(
        proposed_paths,
        role_paths=preserved_roles,
    )

    expected_org = set(layout_paths(layout_state["layout"])) if layout_state.get("structure_enabled") else set()
    expected_dirs: set[str] = set()
    for leaf in leaves:
        if leaf:
            expected_dirs.add(leaf)
        for org in expected_org:
            value = PurePosixPath(*(PurePosixPath(leaf).parts if leaf else ()), *PurePosixPath(org).parts)
            expected_dirs.add(value.as_posix())
    directory_added = sorted(set(observed_dirs) - expected_dirs)
    directory_removed = sorted(expected_dirs - set(observed_dirs))

    blocked = bool(missing_ids or duplicate_ids or unclassified or inconsistent)
    changed = bool(file_moves or directory_added or directory_removed)
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
        "file_moves": file_moves,
        "missing_file_ids": missing_ids,
        "duplicate_file_ids": duplicate_ids,
        "unclassified_directories": unclassified,
        "inconsistent_leaf_layouts": inconsistent,
        "proposed_layout": proposed_layout,
        "proposed_structure_enabled": bool(proposed_paths),
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
        else:
            from app.physical_state import reconcile_missing_files
            reconcile_missing_files(connection, event, root_kind, [], now=now)

        # Reine Dateibewegungen innerhalb der bereits bekannten Ordnerstruktur
        # sind normaler Benutzer-IST-Zustand. Sie werden ohne Aufgabe in SQLite
        # nachgeführt; nur echte Ordner-/Strukturänderungen benötigen den
        # manuellen Strukturworkflow.
        placement_only = bool(snapshot.get("file_moves")) and not any((
            snapshot.get("directory_added"),
            snapshot.get("directory_removed"),
            snapshot.get("missing_file_ids"),
            snapshot.get("duplicate_file_ids"),
            snapshot.get("unclassified_directories"),
            snapshot.get("inconsistent_leaf_layouts"),
        ))
        if placement_only:
            from app.physical_state import sync_placement_moves
            sync_placement_moves(
                connection,
                event,
                layout_state,
                root_kind,
                list(snapshot.get("file_moves") or []),
                now=now,
            )
            if current is not None and str(current["status"]) in {"pending", "blocked"}:
                connection.execute(
                    """UPDATE event_structure_changes
                       SET status='cancelled',updated_at=?,completed_at=?
                       WHERE id=?""",
                    (now, now, current["id"]),
                )
            return None

        if not snapshot["changed"]:
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


def detect_all_event_structure_changes(database_path: Path) -> dict[str, Any]:
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
) -> dict[str, Any]:
    detected = json.loads(str(row["detected_json"] or "{}"))
    if detected.get("blocked"):
        raise EventStructureChangeError("Die erkannte Struktur besitzt Blocker und kann nicht übernommen werden.")
    layout = json.loads(str(row["proposed_layout_json"] or "{}"))
    structure_enabled, clean_input = _validated_structure_input(
        detected, layout, input_path
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
    }


def confirm_applied_structure_change(
    database_path: Path,
    workspace_path: Path,
    change_id: str,
    *,
    input_path: str,
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
                connection, row, input_path=input_path, now=now
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
        "structure_enabled": bool(detected.get("proposed_structure_enabled")),
        "input_path": clean_input,
        "layout": layout,
        "revision": int((document.get("folder_layout") or {}).get("revision") or 1) + 1,
    }
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
