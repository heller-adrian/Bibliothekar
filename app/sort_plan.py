from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
import hashlib
import json
import os

from app.database import database_connection
from app.event_access import event_file_rows
from app.event_layout import (
    ensure_event_layout_snapshot,
    leaf_layout_directories,
    layout_role_paths,
)
from app.event_inventory import _filename_family_source
from app.filename_collisions import export_collision_base_stem
from app.metadata import classify_media
from app.job_readiness import job_sort_readiness
from app.workspace_layout import (
    WorkspaceLayoutError,
    backup_root as workspace_backup_root,
    shared_work_root,
)


class SortPlanError(ValueError):
    """Raised when a sort plan cannot be calculated safely."""


PLANNABLE_EVENT_STATUSES = {
    "draft",
    "planned",
}

ALLOWED_FAMILY_STATUSES = {
    "detected",
    "complete",
}

def _layout_directories_at_leaf(leaf: PurePosixPath, layout_state: dict[str, Any]) -> set[str]:
    return {
        str(leaf / PurePosixPath(relative))
        for relative in leaf_layout_directories(layout_state)
    }


def _observed_organization_path(
    inventory_file: dict[str, Any],
    *,
    child_folder_names: set[str],
) -> PurePosixPath:
    """Return the user-controlled path between the structural leaf and filename."""
    raw = str(inventory_file.get("event_relative_path") or "").replace("\\", "/").strip("/")
    if not raw:
        return PurePosixPath()
    parts = list(PurePosixPath(raw).parts[:-1])
    if parts and parts[0] in child_folder_names:
        parts.pop(0)
    if parts and len(parts[0]) == 10 and parts[0][4:5] == "-" and parts[0][7:8] == "-":
        parts.pop(0)
    return PurePosixPath(*parts) if parts else PurePosixPath()


def _tree_text_from_directories(
    year: str,
    parent_folder: str,
    directories: set[str],
) -> str:
    root = PurePosixPath(year, parent_folder)
    rels: list[PurePosixPath] = []
    for value in directories:
        path = PurePosixPath(value)
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if rel.parts:
            rels.append(rel)
    tree: dict[str, Any] = {}
    for rel in sorted(set(rels), key=lambda p: (len(p.parts), p.as_posix().casefold())):
        cursor = tree
        for part in rel.parts:
            cursor = cursor.setdefault(part, {})
    lines = [year, f"└── {parent_folder}"]
    def walk(node: dict[str, Any], prefix: str) -> None:
        items = list(node.items())
        for index, (name, children) in enumerate(items):
            last = index == len(items) - 1
            lines.append(prefix + ("└── " if last else "├── ") + name)
            walk(children, prefix + ("    " if last else "│   "))
    walk(tree, "    ")
    return "\n".join(lines)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False



def _safe_relative_path(value: Any, field_name: str) -> PurePosixPath:
    raw = str(value or "").strip().replace("\\", "/")

    if not raw:
        raise SortPlanError(f"{field_name} fehlt.")

    path = PurePosixPath(raw)

    if path.is_absolute():
        raise SortPlanError(
            f"{field_name} darf kein absoluter Pfad sein."
        )

    if any(part in {"", ".", ".."} for part in path.parts):
        raise SortPlanError(
            f"{field_name} enthält einen unsicheren Pfadbestandteil."
        )

    return path



def _safe_component(value: Any, field_name: str) -> str:
    raw = str(value or "").strip()

    if not raw:
        raise SortPlanError(f"{field_name} fehlt.")

    if raw in {".", ".."} or any(
        character in raw for character in {"/", "\\", "\0"}
    ):
        raise SortPlanError(
            f"{field_name} enthält ein unzulässiges Zeichen."
        )

    return raw



def _resolve_workspace_root(workspace_path: Path) -> Path:
    root = workspace_path.expanduser().resolve(strict=False)

    if not root.exists() or not root.is_dir():
        raise SortPlanError(
            "Der SSD-Arbeitsbereich ist nicht verfügbar: "
            + str(root)
        )

    return root



def _resolve_job_root(
    job: dict[str, Any],
    workspace_root: Path,
) -> tuple[Path, str]:
    candidates = [
        ("working_path", job.get("working_path")),
        ("source_path", job.get("source_path")),
    ]

    for source_field, value in candidates:
        if not value:
            continue

        root = Path(str(value)).expanduser().resolve(strict=False)

        if not _is_relative_to(root, workspace_root):
            continue

        if not root.exists() or not root.is_dir():
            raise SortPlanError(
                "Der Arbeitsbestandspfad existiert nicht: "
                + str(root)
            )

        return root, source_field

    configured = [
        str(value)
        for _, value in candidates
        if value
    ]

    if configured:
        raise SortPlanError(
            "Der Auftrag verweist nicht auf einen Bestand innerhalb "
            "des SSD-Arbeitsbereichs: "
            + ", ".join(configured)
        )

    raise SortPlanError(
        "Der Auftrag besitzt noch keinen Arbeitsbestandspfad."
    )



def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()



def _path_has_symlink(path: Path, stop_at: Path) -> bool:
    current = path

    while True:
        if current.exists() and current.is_symlink():
            return True

        if current == stop_at:
            return False

        if current.parent == current:
            return False

        current = current.parent



def _build_family_target_groups(
    entries: list[dict[str, Any]],
    asset_entries: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Group the complete per-file plan by family and destination directory.

    The original file entries remain unchanged and complete. These groups are
    an additional presentation and safety layer for large camera imports.
    """

    families_by_key: dict[str, dict[str, Any]] = {}

    for entry in entries:
        family_id = entry.get("family_id")
        file_id = int(entry["file_id"])
        source_relative = PurePosixPath(
            str(entry["source_relative_path"])
        )
        destination_relative = PurePosixPath(
            str(entry["destination_relative_path"])
        )

        if family_id is None:
            group_key = f"direct-file:{file_id}"
            display_name = source_relative.stem
        else:
            group_key = f"family:{int(family_id)}"
            display_name = str(
                source_relative.stem
                or entry.get("family_key")
                or f"Familie {family_id}"
            )

        family = families_by_key.setdefault(
            group_key,
            {
                "group_key": group_key,
                "family_id": (
                    int(family_id)
                    if family_id is not None
                    else None
                ),
                "family_key": entry.get("family_key"),
                "display_name": display_name,
                "family_status": str(
                    entry.get("family_status") or "detected"
                ),
                "file_count": 0,
                "total_size_bytes": 0,
                "media_types": set(),
                "target_directories": set(),
                "move_count": 0,
                "already_at_target_count": 0,
                "blocked_file_count": 0,
                "file_ids": [],
                "source_paths": [],
                "asset_source_paths": [],
            },
        )

        family["file_count"] += 1
        family["total_size_bytes"] += int(
            entry.get("expected_size_bytes") or 0
        )
        family["media_types"].add(
            str(entry.get("media_type") or "other")
        )
        family["target_directories"].add(
            str(destination_relative.parent)
        )
        family["file_ids"].append(file_id)
        family["source_paths"].append(
            str(source_relative)
        )

        status = str(entry.get("status") or "")

        if status == "move":
            family["move_count"] += 1
        elif status == "already_at_target":
            family["already_at_target_count"] += 1
        elif status.startswith("blocked_"):
            family["blocked_file_count"] += 1

    for asset in asset_entries or []:
        family_id = asset.get("family_id")
        if family_id is None:
            continue
        family = families_by_key.get(f"family:{int(family_id)}")
        if family is None:
            continue
        family["file_count"] += 1
        family["total_size_bytes"] += int(asset.get("expected_size_bytes") or 0)
        family["media_types"].add(str(asset.get("asset_kind") or "other"))
        family["asset_source_paths"].append(str(asset.get("source_relative_path") or ""))
        status = str(asset.get("status") or "")
        if status == "move":
            family["move_count"] += 1
        elif status == "already_at_target":
            family["already_at_target_count"] += 1
        elif status.startswith("blocked_"):
            family["blocked_file_count"] += 1

    families: list[dict[str, Any]] = []

    for family in families_by_key.values():
        target_directories = sorted(
            str(value)
            for value in family.pop("target_directories")
        )
        media_types = sorted(
            str(value)
            for value in family.pop("media_types")
        )
        file_pairs = sorted(
            zip(
                family.pop("source_paths"),
                family["file_ids"],
                strict=True,
            ),
            key=lambda item: (str(item[0]), int(item[1])),
        )

        family["file_ids"] = [
            int(file_id)
            for _, file_id in file_pairs
        ]
        family["target_directories"] = target_directories
        family["media_types"] = media_types
        family["split_across_targets"] = (
            len(target_directories) != 1
        )
        family["target_relative_path"] = (
            target_directories[0]
            if len(target_directories) == 1
            else None
        )
        family["ready"] = (
            not family["split_across_targets"]
            and int(family["blocked_file_count"]) == 0
        )
        families.append(family)

    families.sort(
        key=lambda item: (
            str(item.get("target_relative_path") or "~"),
            str(item.get("display_name") or ""),
            str(item.get("group_key") or ""),
        )
    )

    targets_by_path: dict[str, dict[str, Any]] = {}

    for family in families:
        split = bool(family["split_across_targets"])
        target_relative_path = family.get("target_relative_path")
        target_key = (
            str(target_relative_path)
            if target_relative_path
            else "__split_families__"
        )

        target = targets_by_path.setdefault(
            target_key,
            {
                "target_key": target_key,
                "target_relative_path": target_relative_path,
                "display_name": (
                    str(target_relative_path)
                    if target_relative_path
                    else "Mehrere Ziele – Blocker"
                ),
                "family_count": 0,
                "file_count": 0,
                "total_size_bytes": 0,
                "blocked_family_count": 0,
                "media_types": set(),
                "family_group_keys": [],
            },
        )

        target["family_count"] += 1
        target["file_count"] += int(family["file_count"])
        target["total_size_bytes"] += int(
            family["total_size_bytes"]
        )
        target["media_types"].update(family["media_types"])
        target["family_group_keys"].append(
            str(family["group_key"])
        )

        if split or not family["ready"]:
            target["blocked_family_count"] += 1

    target_groups: list[dict[str, Any]] = []

    for target in targets_by_path.values():
        target["media_types"] = sorted(
            str(value)
            for value in target["media_types"]
        )
        target["family_group_keys"] = list(
            target["family_group_keys"]
        )
        target["ready"] = int(target["blocked_family_count"]) == 0
        target_groups.append(target)

    target_groups.sort(
        key=lambda item: (
            item.get("target_relative_path") is None,
            str(item.get("target_relative_path") or ""),
        )
    )

    return families, target_groups



def _reapply_physical_event_prefix(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> PurePosixPath | None:
    """Return the still-physical event root before an applied edit.

    Applied edits persist their SOLL definition before files are moved.  The
    mutation snapshot therefore remains the authoritative source for the old
    physical event folder until the confirmed reapply has finished.
    """
    with database_connection(database_path) as connection:
        rows = connection.execute(
            """SELECT original_state_json
               FROM event_mutations
               WHERE job_id=?
                 AND status IN ('pending_reassignment','pending_apply')
               ORDER BY created_at DESC,id DESC""",
            (job_id,),
        ).fetchall()

        for row in rows:
            try:
                state = json.loads(str(row["original_state_json"] or "{}"))
            except json.JSONDecodeError:
                continue
            for old_event in state.get("events") or []:
                if (
                    str(old_event.get("id") or "") != str(event_id)
                    or old_event.get("parent_event_id")
                ):
                    continue
                start = str(old_event.get("start_datetime") or "")
                folder = str(old_event.get("folder_name") or "").strip()
                year = start[:4]
                if len(year) == 4 and year.isdigit() and folder:
                    return _safe_relative_path(
                        PurePosixPath(year, folder).as_posix(),
                        "Bisheriger Ereignisordner",
                    )

        current = connection.execute(
            """SELECT start_datetime,folder_name
               FROM events
               WHERE id=? AND job_id=? AND parent_event_id IS NULL""",
            (event_id, job_id),
        ).fetchone()
        if current is None:
            return None
        year = str(current["start_datetime"] or "")[:4]
        folder = str(current["folder_name"] or "").strip()
        if len(year) == 4 and year.isdigit() and folder:
            return _safe_relative_path(
                PurePosixPath(year, folder).as_posix(),
                "Ereignisordner",
            )
    return None


def _build_plan_token(
    job_id: str,
    event: dict[str, Any],
    source_root: Path,
    target_root: Path,
    central_stock_root: Path,
    entries: list[dict[str, Any]],
    asset_entries: list[dict[str, Any]],
    directory_rows: list[dict[str, Any]],
) -> str:
    payload = {
        "job_id": job_id,
        "event_id": str(event["id"]),
        "event_revision": int(event.get("revision") or 1),
        "event_status": str(event.get("status") or ""),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "central_stock_root": str(central_stock_root),
        "files": [
            {
                "file_id": int(entry["file_id"]),
                "family_id": entry.get("family_id"),
                "source": str(entry["source_relative_path"]),
                "destination": str(entry["destination_relative_path"]),
                "destination_root_kind": str(entry.get("destination_root_kind") or "target_root"),
                "size": int(entry["expected_size_bytes"]),
                "sha256": str(entry.get("stored_sha256") or ""),
                "source_device": entry.get("source_device"),
                "source_inode": entry.get("source_inode"),
                "source_mtime_ns": entry.get("source_mtime_ns"),
                "status": str(entry.get("status") or ""),
            }
            for entry in sorted(
                entries,
                key=lambda item: int(item["file_id"]),
            )
        ],
        "assets": [
            {
                "asset_kind": str(entry.get("asset_kind") or "other"),
                "family_id": entry.get("family_id"),
                "source_file_id": entry.get("source_file_id"),
                "source": str(entry["source_relative_path"]),
                "source_root_kind": str(entry.get("source_root_kind") or "shared_workspace"),
                "released_archive_asset_id": entry.get("released_archive_asset_id"),
                "destination": str(entry["destination_relative_path"]),
                "destination_root_kind": str(entry.get("destination_root_kind") or "target_root"),
                "size": int(entry["expected_size_bytes"]),
                "sha256": str(entry.get("stored_sha256") or ""),
                "source_device": entry.get("source_device"),
                "source_inode": entry.get("source_inode"),
                "source_mtime_ns": entry.get("source_mtime_ns"),
                "status": str(entry.get("status") or ""),
            }
            for entry in sorted(
                asset_entries,
                key=lambda item: str(item["source_relative_path"]),
            )
        ],
        "directories": [
            str(row["relative_path"])
            for row in sorted(
                directory_rows,
                key=lambda item: str(item["relative_path"]),
            )
        ],
    }

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()

def build_event_sort_plan(
    database_path: Path,
    job_id: str,
    event_id: str,
    workspace_path: Path,
    *,
    verify_sha256: bool = False,
    verification_callback: (
        Callable[[int, int], None] | None
    ) = None,
    asset_verification_callback: (
        Callable[[str, int], None] | None
    ) = None,
    allow_reapply: bool = False,
) -> dict[str, Any]:
    """
    Calculate a read-only file-system sort plan for one parent event.

    The function never creates, moves, renames, changes, or deletes a file,
    directory, database row, or checksum. Optional SHA-256 verification only
    reads source files.

    With ``allow_reapply=True`` the plan describes the re-sort of an
    already applied, not yet archived event: the files live in the shared
    work area and the plan only ever moves them inside that area.
    """

    workspace_root = _resolve_workspace_root(workspace_path)

    # 0.28.0: Sicherung ist Herkunft, nicht Ereignisidentität. Alte
    # /api/jobs/...-Routen bleiben als Kompatibilität erhalten, aber der
    # technische Anchor wird immer aus dem Ereignis selbst abgeleitet.
    with database_connection(database_path) as anchor_connection:
        anchor_row = anchor_connection.execute(
            "SELECT job_id FROM events WHERE id=? AND parent_event_id IS NULL",
            (event_id,),
        ).fetchone()
    if anchor_row is None:
        raise SortPlanError("Ereignis wurde nicht gefunden.")
    job_id = str(anchor_row["job_id"])

    reapply_inventory: dict[str, Any] | None = None
    if allow_reapply:
        try:
            inventory_root = shared_work_root(workspace_root)
        except WorkspaceLayoutError as error:
            raise SortPlanError(str(error)) from error
        physical_prefix = _reapply_physical_event_prefix(
            database_path,
            job_id,
            event_id,
        )
        try:
            from app.event_inventory import EventInventoryError, scan_event_inventory

            reapply_inventory = scan_event_inventory(
                database_path,
                inventory_root,
                job_id,
                event_id,
                root_kind="shared_workspace",
                persist=False,
                update_known_file_locations=False,
                event_prefix_override=physical_prefix,
            )
        except EventInventoryError as error:
            raise SortPlanError(str(error)) from error

    with database_connection(database_path) as connection:
        job_row = connection.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        if job_row is None:
            raise SortPlanError("Sicherung wurde nicht gefunden.")

        event_row = connection.execute(
            """
            SELECT *
            FROM events
            WHERE id = ?
              AND job_id = ?
            """,
            (event_id, job_id),
        ).fetchone()

        if event_row is None:
            raise SortPlanError("Ereignis wurde nicht gefunden.")

        event = dict(event_row)

        if event.get("event_level") != "parent":
            raise SortPlanError(
                "Ein Sortierplan kann nur für ein Hauptereignis "
                "erstellt werden."
            )

        if allow_reapply:
            if (
                str(event.get("status")) != "applied"
                or not event.get("applied_at")
                or event.get("archived_at")
            ):
                raise SortPlanError(
                    "Eine Nachsortierung ist nur für ein angewendetes "
                    "und noch nicht archiviertes Ereignis möglich."
                )
        else:
            if str(event.get("status")) not in PLANNABLE_EVENT_STATUSES:
                raise SortPlanError(
                    "Nur noch nicht angewendete Planungen können geprüft werden."
                )

            if event.get("applied_at") or event.get("archived_at"):
                raise SortPlanError(
                    "Dieses Ereignis wurde bereits angewendet oder archiviert."
                )

        child_definition_rows = connection.execute(
            """SELECT id,folder_name,start_datetime,end_datetime
               FROM events
               WHERE parent_event_id=?
               ORDER BY start_datetime,id""",
            (event_id,),
        ).fetchall()
        child_definitions = [dict(row) for row in child_definition_rows]

        assignment_rows = connection.execute(
            """
            SELECT
                ea.family_id,
                ea.file_id,
                assigned.id AS assigned_event_id,
                assigned.parent_event_id,
                assigned.folder_name AS assigned_folder_name,
                COALESCE(ff.selected_capture_time, direct_ff.selected_capture_time)
                    AS assignment_capture_time

            FROM event_assignments AS ea

            JOIN events AS assigned
                ON assigned.id = ea.event_id
            LEFT JOIN file_families AS ff
                ON ff.id = ea.family_id
            LEFT JOIN files AS direct_file
                ON direct_file.id = ea.file_id
            LEFT JOIN file_families AS direct_ff
                ON direct_ff.id = direct_file.family_id

            WHERE (
                    assigned.id = ?
                    OR assigned.parent_event_id = ?
                  )

            ORDER BY
                assigned.start_datetime,
                assigned.id,
                ea.family_id,
                ea.file_id
            """,
            (event_id, event_id),
        ).fetchall()

        family_assignments: dict[int, dict[str, Any]] = {}
        direct_file_assignments: list[int] = []
        removed_family_ids: set[int] = set()
        removed_targets: dict[int, dict[str, Any]] = {}
        child_assignment_days: dict[str, set[str]] = defaultdict(set)

        for row in assignment_rows:
            if row["family_id"] is not None:
                family_assignments[int(row["family_id"])] = dict(row)
            elif row["file_id"] is not None:
                direct_file_assignments.append(int(row["file_id"]))
            if row["parent_event_id"] is not None:
                day_key = str(row["assignment_capture_time"] or "")[:10]
                if len(day_key) == 10:
                    child_assignment_days[str(row["assigned_event_id"])].add(day_key)

        if allow_reapply:
            removed_rows = connection.execute(
                """SELECT family_id, target_event_id, target_status, target_kind,
                          target_name, target_folder_name, target_preserve_day_folders,
                          target_linkage_kind
                   FROM event_reapply_removed_families
                   WHERE event_id = ?
                     AND COALESCE(target_kind,'') <> 'released_free'""",
                (event_id,),
            ).fetchall()
            removed_family_ids = {int(row["family_id"]) for row in removed_rows}
            removed_targets = {int(row["family_id"]): dict(row) for row in removed_rows}

        if not family_assignments and not direct_file_assignments and not removed_family_ids:
            raise SortPlanError(
                "Dem Ereignis sind keine Dateien oder Dateifamilien zugeordnet."
            )

        family_ids = sorted(set(family_assignments) | removed_family_ids)
        family_placeholders = ",".join("?" for _ in family_ids)

        file_rows: list[Any] = []

        if family_ids:
            file_rows.extend(
                connection.execute(
                    f"""
                    SELECT
                        f.*,
                        ff.family_key,
                        ff.status AS family_status,
                        ff.selected_capture_time AS family_capture_time,
                        ff.capture_time_confidence AS family_confidence

                    FROM files AS f

                    JOIN file_families AS ff
                        ON ff.id = f.family_id

                    WHERE f.family_id IN ({family_placeholders})

                    ORDER BY
                        ff.selected_capture_time,
                        ff.id,
                        f.original_relative_path
                    """,
                    tuple(family_ids),
                ).fetchall()
            )

        if direct_file_assignments:
            file_placeholders = ",".join(
                "?" for _ in direct_file_assignments
            )
            file_rows.extend(
                connection.execute(
                    f"""
                    SELECT
                        f.*,
                        ff.family_key,
                        ff.status AS family_status,
                        ff.selected_capture_time AS family_capture_time,
                        ff.capture_time_confidence AS family_confidence

                    FROM files AS f

                    LEFT JOIN file_families AS ff
                        ON ff.id = f.family_id

                    WHERE f.id IN ({file_placeholders})

                    ORDER BY f.original_relative_path
                    """,
                    tuple(direct_file_assignments),
                ).fetchall()
            )

        from app.free_stock_layout import (
            affected_days_for_event,
            canonical_free_directory,
            free_file_rows,
            released_origin_directory,
        )
        affected_days = affected_days_for_event(connection, event_id)
        known_file_ids = {int(row["id"]) for row in file_rows}
        for free_row in free_file_rows(
            connection,
            affected_days,
            job_id=job_id,
            shared_library=allow_reapply,
        ):
            if int(free_row["id"]) not in known_file_ids:
                file_rows.append(free_row)
        normalized_file_rows: list[dict[str, Any]] = []
        for raw_file_row in file_rows:
            record = dict(raw_file_row)
            record_family_id = (
                int(record["family_id"])
                if record.get("family_id") is not None
                else None
            )
            removed_target = removed_targets.get(record_family_id)
            if record.get("_free_stock") or (
                removed_target is not None
                and not removed_target.get("target_event_id")
            ):
                record["_free_stock"] = True
                capture_value = str(
                    record.get("family_capture_time")
                    or record.get("selected_capture_time")
                    or ""
                )
                released_directory = (
                    released_origin_directory(
                        connection,
                        record_family_id,
                        capture_value,
                        physical=True,
                    )
                    if record_family_id is not None
                    else None
                )
                record["_free_directory"] = str(
                    released_directory
                    or canonical_free_directory(
                        connection,
                        capture_value,
                        physical=True,
                        include_event_ids=(event_id,) if not allow_reapply else (),
                    )
                )
            normalized_file_rows.append(record)
        file_rows = normalized_file_rows
        file_rows_by_id = {
            int(row["id"]): dict(row)
            for row in file_rows
        }

        assigned_family_set = set(family_ids)
        assigned_source_rows = [
            row for row in file_rows
            if row.get("family_id") is not None
            and int(row["family_id"]) in assigned_family_set
        ]
        released_workspace_source = bool(assigned_family_set) and not allow_reapply and not direct_file_assignments
        if released_workspace_source:
            covered_family_ids = {
                int(row["family_id"]) for row in assigned_source_rows
                if row.get("family_id") is not None
            }
            released_workspace_source = (
                covered_family_ids == assigned_family_set
                and bool(assigned_source_rows)
                and all(
                    str(row.get("current_root_kind") or "") == "shared_workspace"
                    and str(row.get("current_relative_path") or "").replace("\\", "/").startswith(
                        "Freigewordene Archivdateien/"
                    )
                    for row in assigned_source_rows
                )
            )

    job = dict(job_row)

    try:
        target_root = shared_work_root(workspace_root)
    except WorkspaceLayoutError as error:
        raise SortPlanError(str(error)) from error

    shared_workspace_source = bool(file_rows) and all(
        str(dict(row).get("current_root_kind") or "") == "shared_workspace"
        for row in file_rows
    )
    try:
        central_stock_root = workspace_backup_root(workspace_root)
    except WorkspaceLayoutError as error:
        raise SortPlanError(str(error)) from error

    central_stock_source = bool(file_rows) and all(
        (
            central_stock_root
            / str(
                dict(row).get("current_relative_path")
                or dict(row).get("original_relative_path")
                or ""
            )
        ).is_file()
        for row in file_rows
    )

    if allow_reapply:
        # Applied/Reapply bleibt vollständig innerhalb des Arbeitsbereichs
        # der aktuell gewählten Bibliothek.
        source_root = target_root
        source_root_field = "shared_workspace"
    elif central_stock_source:
        # 0.31.1: Freie und nur geplante Aufnahmen liegen physisch im
        # zentralen Tagesbestand. Erst Anwenden überführt sie in die Bibliothek.
        source_root = central_stock_root
        source_root_field = "central_stock"
    elif released_workspace_source:
        # Kompatibilitätsweg für einen noch nicht migrierten Altbestand.
        source_root = target_root
        source_root_field = "released_archive_workspace"
    elif shared_workspace_source:
        # Kompatibilitätsweg für den Main-Bestand vor der 0.31.1-Migration.
        source_root = target_root
        source_root_field = "shared_workspace"
    else:
        source_root, source_root_field = _resolve_job_root(
            job,
            workspace_root,
        )

    year = str(event.get("start_datetime") or "")[:4]

    if len(year) != 4 or not year.isdigit():
        raise SortPlanError(
            "Aus dem Ereignisbeginn konnte kein Jahr ermittelt werden."
        )

    parent_folder = _safe_component(
        event.get("folder_name"),
        "Ereignisordner",
    )

    preserve_day_folders = bool(
        event.get("preserve_day_folders")
    )

    with database_connection(database_path) as connection:
        collision_row = connection.execute(
            """
            SELECT id, job_id, status
            FROM events
            WHERE parent_event_id IS NULL
              AND folder_name = ?
              AND id <> ?
              AND status IN ('planned', 'applied', 'archived')
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (parent_folder, event_id),
        ).fetchone()

    collision_redirected = collision_row is not None
    job_token = _safe_component(job_id[-12:], "Auftragskennung")
    linkage_kind = str(event.get("linkage_kind") or "")
    if allow_reapply:
        # Die Nachsortierung nutzt ausschließlich die aktuelle Ereignisstruktur.
        # Eine Umlenkung nach „Später zuordnen“ fand beim ursprünglichen
        # Anwenden statt und darf hier nicht erneut greifen.
        physical_parent_parts = [parent_folder]
    elif linkage_kind == "planned_extension" and str(event.get("event_kind") or "") == "no_event":
        # Beiträge aus unterschiedlichen Sicherungen dürfen denselben monatlichen
        # „Ohne Ereignis“-Ordner ergänzen. Technisch nutzen wir den bestehenden
        # Follow-up-Typ, semantisch bleibt es eine gemeinsame Monatssammlung.
        physical_parent_parts = [parent_folder]
        collision_redirected = False
    elif linkage_kind == "planned_extension":
        physical_parent_parts = ["Ergänzungen", f"{parent_folder} - {job_token}"]
    elif linkage_kind == "applied_followup":
        physical_parent_parts = ["Nachträge", f"{parent_folder} - {job_token}"]
    elif linkage_kind == "archived_manual":
        # 0.27.0: Die manuelle Archiv-Erweiterung liegt unter der kanonischen
        # Ereignishülle. Mehrere Nachtraege duerfen dort zusammenlaufen; echte
        # Dateikollisionen bleiben durch den No-Overwrite-Plan blockiert.
        physical_parent_parts = ["Später zuordnen", parent_folder]
    else:
        physical_parent_parts = (
            ["Später zuordnen", f"{parent_folder} - {job_token}"]
            if collision_redirected
            else [parent_folder]
        )

    with database_connection(database_path) as connection:
        try:
            layout_state = ensure_event_layout_snapshot(
                connection, event_id, now=datetime.now(timezone.utc).isoformat()
            )
        except Exception as error:
            raise SortPlanError("Ereignis-Unterordnerstruktur ist ungültig: " + str(error)) from error
    layout_input_path = PurePosixPath(str(layout_state.get("input_path") or ""))
    layout_export_paths = (
        layout_role_paths(layout_state["layout"], "export")
        if bool(layout_state.get("structure_enabled"))
        else []
    )
    child_folder_names = {
        str(child.get("folder_name") or "") for child in child_definitions
        if str(child.get("folder_name") or "")
    }

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    planned_directories: set[str] = set()
    family_statuses: dict[int, str] = {}
    pending_delete = bool(int(event.get("pending_delete") or 0))

    # During a confirmed delete the event hierarchy is source-only: the
    # complete event will disappear and only canonical free-stock directories
    # are valid targets. Do not recreate empty parent/child structure.
    if not (allow_reapply and pending_delete):
        # Organizational subevents always keep their own structure. With
        # "Tagesordner erhalten", however, a day directory represents actual
        # content and is created only for capture days that really land in this
        # subevent. An entirely empty subevent keeps the configured event
        # folder structure directly below its folder.
        for child in child_definitions:
            child_folder_name = _safe_component(
                child.get("folder_name"),
                "Unterereignisordner",
            )
            child_root = PurePosixPath(year, *physical_parent_parts, child_folder_name)
            assigned_days = sorted(
                child_assignment_days.get(str(child["id"]), set())
            )

            if preserve_day_folders and assigned_days:
                for day_key in assigned_days:
                    leaf = child_root / day_key
                    layout_dirs = _layout_directories_at_leaf(leaf, layout_state)
                    planned_directories.update(layout_dirs or {str(leaf)})

                start_day = datetime.fromisoformat(
                    str(child["start_datetime"])[:19]
                ).date()
                end_day = datetime.fromisoformat(
                    str(child["end_datetime"])[:19]
                ).date()
                from datetime import timedelta
                occupied_days = set(assigned_days)
                missing_days = []
                day = start_day
                while day <= end_day:
                    day_key = day.isoformat()
                    if day_key not in occupied_days:
                        missing_days.append(day_key)
                    day += timedelta(days=1)
                if missing_days:
                    warnings.append({
                        "code": "empty_subevent_days",
                        "message": (
                            "Unterereignis „"
                            + str(child.get("folder_name") or child.get("id"))
                            + "“ enthält an "
                            + ", ".join(missing_days)
                            + " keine Dateifamilien; für diese Tage werden "
                              "keine Tagesordner angelegt."
                        ),
                        "event_id": str(child["id"]),
                        "days": missing_days,
                    })
            else:
                layout_dirs = _layout_directories_at_leaf(child_root, layout_state)
                planned_directories.update(layout_dirs or {str(child_root)})

        assigned_child_ids = {
            str(row["assigned_event_id"])
            for row in assignment_rows
            if row["parent_event_id"] is not None
        }
        for child in child_definitions:
            if str(child["id"]) not in assigned_child_ids:
                warnings.append({
                    "code": "empty_subevent",
                    "message": (
                        "Unterereignis „" + str(child.get("folder_name") or child.get("id"))
                        + "“ enthält aktuell keine Dateifamilien; die leere Ordnerstruktur wird trotzdem angelegt."
                    ),
                    "event_id": str(child["id"]),
                })
    
    job_ready, job_blocker = job_sort_readiness(job)
    if not job_ready and not released_workspace_source and not shared_workspace_source:
        blockers.append({
            "code": "job_not_verified",
            "message": job_blocker,
        })
    elif released_workspace_source:
        warnings.append({
            "code": "released_archive_workspace_source",
            "message": (
                "Die ausgewählten Familien stammen aus dem verifizierten "
                "Rückkehrbestand „Freigewordene Archivdateien“. Die ursprüngliche "
                "Sicherung bleibt nur als Herkunft erhalten und wird nicht erneut "
                "als physische Sortierquelle benötigt."
            ),
        })
    elif shared_workspace_source and not job_ready:
        warnings.append({
            "code": "shared_workspace_source",
            "message": (
                "Die Dateien liegen bereits im gemeinsamen verifizierten "
                "Arbeitsbereich. Der technische Anchor-Job bleibt nur Workflow-"
                "Eigentümer und ist keine physische Sortierquelle."
            ),
        })

    if linkage_kind == "planned_extension":
        warnings.append({
            "code": "planned_event_extension",
            "message": (
                "Die Dateien ergänzen eine offene Planung aus einem anderen "
                "Sicherungsauftrag und werden bis zur gemeinsamen Archivprüfung "
                "eindeutig unter ‚Ergänzungen‘ bereitgestellt."
            ),
        })
    elif linkage_kind == "applied_followup":
        warnings.append({
            "code": "applied_event_followup",
            "message": (
                "Die Dateien sind ein bestätigter Nachtrag zu einem bereits "
                "angewendeten Ereignis und werden sicher unter ‚Nachträge‘ abgelegt."
            ),
        })
    elif linkage_kind == "archived_manual":
        warnings.append({
            "code": "archived_event_manual_followup",
            "message": (
                "Das passende Ereignis ist bereits archiviert. Die Dateien werden "
                "unter ‚Später zuordnen‘ für die manuelle Archiv-Ergänzung bereitgestellt."
            ),
        })
    elif collision_redirected:
        warnings.append({
            "code": "existing_event_folder_redirect",
            "message": (
                "Ein gleichnamiger Ereignisordner aus einem anderen "
                "Sicherungsauftrag existiert bereits. Die neuen Dateien "
                "werden sicher getrennt unter ‚Später zuordnen‘ abgelegt."
            ),
        })

    if direct_file_assignments:
        warnings.append({
            "code": "direct_file_assignments",
            "message": (
                f"{len(direct_file_assignments)} direkte Dateizuordnungen "
                "werden zusätzlich berücksichtigt."
            ),
        })

    reapply_inventory_by_file_id = {
        int(item["known_file_id"]): item
        for item in (reapply_inventory or {}).get("files", [])
        if item.get("known_file_id") is not None
    }

    seen_source_ids: set[int] = set()

    for row in file_rows:
        file_record = dict(row)
        file_id = int(file_record["id"])

        if file_id in seen_source_ids:
            continue

        seen_source_ids.add(file_id)

        family_id = (
            int(file_record["family_id"])
            if file_record.get("family_id") is not None
            else None
        )

        assignment = (
            family_assignments.get(family_id)
            if family_id is not None
            else None
        )

        child_folder: str | None = None

        if assignment and assignment.get("parent_event_id") is not None:
            child_folder = _safe_component(
                assignment.get("assigned_folder_name"),
                "Unterereignisordner",
            )

        branch_key = child_folder


        family_status = str(
            file_record.get("family_status") or "detected"
        )

        if family_id is not None:
            family_statuses[family_id] = family_status

        capture_time = (
            file_record.get("family_capture_time")
            or file_record.get("selected_capture_time")
        )
        day_key = str(capture_time or "")[:10]

        inventory_file = reapply_inventory_by_file_id.get(file_id)
        source_relative = _safe_relative_path(
            (
                inventory_file.get("relative_path")
                if inventory_file is not None
                else None
            )
            or file_record.get("current_relative_path")
            or file_record.get("original_relative_path"),
            "Aktueller relativer Dateipfad",
        )

        current_root_kind = (
            "shared_workspace"
            if inventory_file is not None
            else str(file_record.get("current_root_kind") or "job_root")
        )
        if current_root_kind not in {"job_root", "shared_workspace"}:
            blockers.append({
                "code": "source_root_kind_not_supported",
                "file_id": file_id,
                "message": "Unbekannter Quellbereich: " + current_root_kind,
            })

        filename = _safe_component(
            source_relative.name,
            "Dateiname",
        )

        reassignment = removed_targets.get(family_id) if family_id is not None else None
        is_free_stock = bool(file_record.get("_free_stock")) or bool(
            reassignment and not reassignment.get("target_event_id")
        )
        file_preserve_day_folders = preserve_day_folders
        if is_free_stock:
            free_directory = PurePosixPath(str(file_record["_free_directory"]))
            destination_parts = list(free_directory.parts)
            child_folder = None
            file_preserve_day_folders = False
        elif reassignment:
            target_folder = _safe_component(
                reassignment.get("target_folder_name") or "Später zuordnen",
                "Zielereignisordner",
            )
            target_linkage = str(reassignment.get("target_linkage_kind") or "")
            if target_linkage == "planned_extension" and str(reassignment.get("target_kind") or "") == "existing_no_event":
                destination_parts = [year, target_folder]
            elif target_linkage == "planned_extension":
                destination_parts = [year, "Ergänzungen", f"{target_folder} - {job_token}"]
            elif target_linkage == "applied_followup":
                destination_parts = [year, "Nachträge", f"{target_folder} - {job_token}"]
            elif target_linkage == "archived_manual" or str(reassignment.get("target_status") or "") == "archived":
                destination_parts = ["Später zuordnen", year, target_folder]
            else:
                destination_parts = [year, target_folder]
            file_preserve_day_folders = bool(reassignment.get("target_preserve_day_folders"))
            child_folder = None
        elif linkage_kind == "archived_manual" or collision_redirected:
            # "Später zuordnen" ist ein globaler technischer Bereich direkt
            # unter Arbeitsbereich. Die Jahresordner entstehen nur innerhalb
            # dieses Bereichs, damit die normalen Jahresordner auch langfristig
            # ausschließlich echte Ereignisse enthalten.
            destination_parts = ["Später zuordnen", year, *physical_parent_parts[1:]]
        else:
            destination_parts = [year, *physical_parent_parts]

        if child_folder:
            destination_parts.append(child_folder)

        if file_preserve_day_folders:
            if len(day_key) != 10:
                blockers.append({
                    "code": "missing_capture_day",
                    "file_id": file_id,
                    "message": (
                        "Für eine Datei fehlt das Aufnahmedatum, obwohl "
                        "Tagesordner erhalten bleiben sollen: "
                        + str(source_relative)
                    ),
                })
            else:
                destination_parts.append(day_key)

        structural_leaf = PurePosixPath(*destination_parts)
        if is_free_stock:
            destination_parts.append(filename)
        else:
            organization = PurePosixPath()
            if bool(layout_state.get("structure_enabled")):
                if allow_reapply and inventory_file is not None:
                    organization = _observed_organization_path(
                        inventory_file,
                        child_folder_names=child_folder_names,
                    )
                    if not organization.parts:
                        # 0.28.3: Nach einem flachen Zustand gibt es keine
                        # historische Platzierung mehr. Beim Wiedereinschalten
                        # der Struktur landen alle Dateien im aktuellen Input.
                        organization = layout_input_path
                else:
                    organization = layout_input_path
            if organization.parts:
                destination_parts.extend(organization.parts)
            destination_parts.append(filename)
            # Count only files that remain in this event itself. Families sent
            # to free stock or to another reassignment target do not justify an
            # empty parent structure in this event.

        destination_relative = PurePosixPath(*destination_parts)
        source_base = (
            target_root
            if allow_reapply and current_root_kind == "shared_workspace"
            else source_root
        )
        destination_root_kind = (
            "central_stock" if is_free_stock else "target_root"
        )
        destination_base = (
            central_stock_root
            if destination_root_kind == "central_stock"
            else target_root
        )
        source_absolute = (
            source_base.joinpath(*source_relative.parts).resolve(
                strict=False
            )
        )
        destination_absolute = (
            destination_base.joinpath(*destination_relative.parts).resolve(
                strict=False
            )
        )

        if not _is_relative_to(source_absolute, source_base):
            blockers.append({
                "code": "source_outside_root",
                "file_id": file_id,
                "message": (
                    "Ein Quellpfad verlässt den Arbeitsbestand: "
                    + str(source_relative)
                ),
            })

        if not _is_relative_to(destination_absolute, destination_base):
            blockers.append({
                "code": "target_outside_root",
                "file_id": file_id,
                "message": (
                    "Ein Zielpfad verlässt den Arbeitsbestand: "
                    + str(destination_relative)
                ),
            })

        source_exists = source_absolute.exists()
        source_is_file = source_absolute.is_file() if source_exists else False
        source_is_symlink = source_absolute.is_symlink() if source_exists else False
        source_readable = (
            os.access(source_absolute, os.R_OK)
            if source_exists
            else False
        )
        source_stat = (
            source_absolute.stat(follow_symlinks=False)
            if source_is_file and not source_is_symlink
            else None
        )
        source_size = (
            int(source_stat.st_size)
            if source_stat is not None
            else None
        )
        expected_size = int(file_record.get("size_bytes") or 0)
        size_matches = source_size == expected_size
        same_path = source_absolute == destination_absolute
        target_exists = destination_absolute.exists()
        target_is_directory = (
            destination_absolute.is_dir()
            if target_exists
            else False
        )
        target_conflict = target_exists and not same_path

        checksum_expected = str(
            file_record.get("sha256_current")
            or file_record.get("sha256_original")
            or ""
        ).strip()
        checksum_actual: str | None = None
        checksum_matches: bool | None = None

        if (
            verify_sha256
            and source_is_file
            and not source_is_symlink
            and source_readable
        ):
            checksum_actual = _sha256_file(source_absolute)
            checksum_matches = (
                bool(checksum_expected)
                and checksum_actual == checksum_expected
            )

            if verification_callback is not None:
                verification_callback(
                    file_id,
                    expected_size,
                )

        if not source_exists:
            blockers.append({
                "code": "source_missing",
                "file_id": file_id,
                "message": "Quelldatei fehlt: " + str(source_relative),
            })
        elif not source_is_file or source_is_symlink:
            blockers.append({
                "code": "source_not_regular_file",
                "file_id": file_id,
                "message": (
                    "Quelle ist keine reguläre Datei: "
                    + str(source_relative)
                ),
            })
        elif not source_readable:
            blockers.append({
                "code": "source_not_readable",
                "file_id": file_id,
                "message": "Quelldatei ist nicht lesbar: " + str(source_relative),
            })

        if source_is_file and not size_matches:
            blockers.append({
                "code": "source_size_mismatch",
                "file_id": file_id,
                "message": (
                    "Dateigröße weicht von SQLite ab: "
                    + str(source_relative)
                ),
            })

        if not checksum_expected:
            blockers.append({
                "code": "checksum_missing",
                "file_id": file_id,
                "message": (
                    "Für eine Quelldatei fehlt die gespeicherte SHA-256-Summe: "
                    + str(source_relative)
                ),
            })
        elif verify_sha256 and checksum_matches is False:
            blockers.append({
                "code": "checksum_mismatch",
                "file_id": file_id,
                "message": (
                    "SHA-256-Prüfung fehlgeschlagen: "
                    + str(source_relative)
                ),
            })

        if target_conflict:
            blockers.append({
                "code": "target_exists",
                "file_id": file_id,
                "message": (
                    "Am Ziel existiert bereits ein anderer Eintrag: "
                    + str(destination_relative)
                ),
            })

        if _path_has_symlink(source_absolute, source_base):
            blockers.append({
                "code": "source_symlink_component",
                "file_id": file_id,
                "message": (
                    "Der Quellpfad enthält einen symbolischen Link: "
                    + str(source_relative)
                ),
            })

        if _path_has_symlink(destination_absolute.parent, target_root):
            blockers.append({
                "code": "target_symlink_component",
                "file_id": file_id,
                "message": (
                    "Der Zielpfad enthält einen symbolischen Link: "
                    + str(destination_relative.parent)
                ),
            })

        if is_free_stock:
            # Zentrale Tagesordner werden von der Transferphase aus dem
            # absoluten Zielpfad erzeugt und gehören nicht zur Ereignisstruktur.
            pass
        else:
            layout_dirs = _layout_directories_at_leaf(structural_leaf, layout_state)
            planned_directories.update(layout_dirs or {str(structural_leaf)})
            planned_directories.add(str(destination_relative.parent))

        entry_status = "move"

        if same_path:
            entry_status = "already_at_target"
        elif not source_exists:
            entry_status = "blocked_missing_source"
        elif target_conflict:
            entry_status = "blocked_target_exists"
        elif source_is_file and not size_matches:
            entry_status = "blocked_size_mismatch"
        elif verify_sha256 and checksum_matches is False:
            entry_status = "blocked_checksum_mismatch"

        entries.append({
            "file_id": file_id,
            "family_id": family_id,
            "family_key": file_record.get("family_key"),
            "family_status": family_status,
            "media_type": str(file_record.get("media_type") or "other"),
            "current_root_kind": current_root_kind,
            "source_relative_path": str(source_relative),
            "source_absolute_path": str(source_absolute),
            "destination_relative_path": str(destination_relative),
            "destination_root_kind": destination_root_kind,
            "structural_leaf_relative_path": str(structural_leaf),
            "free_stock": is_free_stock,
            "destination_absolute_path": str(destination_absolute),
            "expected_size_bytes": expected_size,
            "source_size_bytes": source_size,
            "source_device": (
                int(source_stat.st_dev)
                if source_stat is not None
                else None
            ),
            "source_inode": (
                int(source_stat.st_ino)
                if source_stat is not None
                else None
            ),
            "source_mtime_ns": (
                int(source_stat.st_mtime_ns)
                if source_stat is not None
                else None
            ),
            "size_matches": size_matches,
            "stored_sha256": checksum_expected or None,
            "sha256_verified_now": verify_sha256,
            "calculated_sha256": checksum_actual,
            "sha256_matches": checksum_matches,
            "source_exists": source_exists,
            "source_readable": source_readable,
            "source_is_regular_file": source_is_file and not source_is_symlink,
            "target_exists": target_exists,
            "target_is_directory": target_is_directory,
            "same_path": same_path,
            "status": entry_status,
        })

    asset_entries: list[dict[str, Any]] = []

    # TrueNAS-/SMB-sicher: Zielnamen werden für Kollisionen grundsätzlich
    # case-insensitiv betrachtet. Besonders beim Abschalten der Unterordner
    # können Kamera-JPEG und Export-JPEG denselben Stamm besitzen und sich nur
    # durch .JPG/.jpg unterscheiden. Auf case-insensitiven Datasets ist das
    # derselbe Pfad. Kameraoriginale behalten immer ihren Namen; nur ein Export
    # erhält bei Bedarf einen transparenten Suffix.
    reserved_destination_keys: set[str] = {
        str(PurePosixPath(entry["destination_relative_path"])).casefold()
        for entry in entries
    }

    def reserve_asset_destination(
        candidate: PurePosixPath,
        *,
        asset_kind: str,
    ) -> PurePosixPath:
        key = candidate.as_posix().casefold()
        if key not in reserved_destination_keys:
            reserved_destination_keys.add(key)
            return candidate
        if asset_kind != "export":
            # Für XMP/sonstige Sidecars ist eine Namensänderung fachlich nicht
            # automatisch sicher. Die spätere Duplikatprüfung blockiert diesen
            # seltenen Sonderfall weiterhin.
            return candidate

        parent = candidate.parent
        suffix = candidate.suffix
        stem = candidate.name[:-len(suffix)] if suffix else candidate.name
        base = f"{stem}_Export"
        index = 0
        while True:
            name = (
                f"{base}{suffix}"
                if index == 0
                else f"{base}_{index:03d}{suffix}"
            )
            proposed = parent / name
            proposed_key = proposed.as_posix().casefold()
            if proposed_key not in reserved_destination_keys:
                reserved_destination_keys.add(proposed_key)
                return proposed
            index += 1

    # Zusatzdateien, die mit einer archivierten Familie in den Rückkehrbestand
    # gelangt sind, werden beim nächsten normalen Anwenden wieder über dieselbe
    # sichere Asset-Pipeline mitgeführt.
    if family_ids and not allow_reapply:
        with database_connection(database_path) as connection:
            released_archive_asset_rows = [
                dict(row)
                for row in connection.execute(
                    f"""SELECT *
                        FROM released_archive_assets
                        WHERE family_id IN ({family_placeholders})
                        ORDER BY family_id,current_relative_path,id""",
                    tuple(family_ids),
                ).fetchall()
            ]

        camera_entries_by_family: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            if entry.get("family_id") is not None:
                camera_entries_by_family[int(entry["family_id"])].append(entry)

        for asset in released_archive_asset_rows:
            family_id = (
                int(asset["family_id"])
                if asset.get("family_id") is not None
                else None
            )
            if family_id is None:
                blockers.append({
                    "code": "released_asset_family_missing",
                    "path": str(asset.get("current_relative_path") or ""),
                    "message": "Eine freigewordene Zusatzdatei besitzt keine Dateifamilie.",
                })
                continue

            candidates = camera_entries_by_family.get(family_id, [])
            target_leaves = {
                str(candidate.get("structural_leaf_relative_path") or "")
                for candidate in candidates
                if str(candidate.get("structural_leaf_relative_path") or "")
            }
            if not candidates or len(target_leaves) != 1:
                blockers.append({
                    "code": "released_asset_target_ambiguous",
                    "family_id": family_id,
                    "path": str(asset.get("current_relative_path") or ""),
                    "message": (
                        "Das strukturelle Ziel einer freigewordenen Zusatzdatei "
                        "ist innerhalb ihrer Kamerafamilie nicht eindeutig."
                    ),
                })
                continue

            source_relative = _safe_relative_path(
                asset.get("current_relative_path"),
                "Freigewordene Zusatzdatei",
            )
            source_absolute = central_stock_root.joinpath(*source_relative.parts).resolve(
                strict=False
            )
            structural_leaf = PurePosixPath(next(iter(target_leaves)))
            filename = _safe_component(source_relative.name, "Zusatzdateiname")
            released_asset_kind = str(asset.get("asset_kind") or "other")
            destination_container = structural_leaf
            if bool(layout_state.get("structure_enabled")):
                organization = layout_input_path
                if released_asset_kind == "export" and layout_export_paths:
                    organization = PurePosixPath(layout_export_paths[0])
                if organization.parts:
                    destination_container = destination_container / organization
            destination_relative = reserve_asset_destination(
                destination_container / filename,
                asset_kind=released_asset_kind,
            )
            destination_base = target_root
            destination_absolute = destination_base.joinpath(
                *destination_relative.parts
            ).resolve(strict=False)

            if not _is_relative_to(source_absolute, central_stock_root):
                blockers.append({
                    "code": "released_asset_source_outside_root",
                    "path": str(source_relative),
                    "message": "Eine freigewordene Zusatzdatei verlässt den Arbeitsbereich.",
                })
            if not _is_relative_to(destination_absolute, destination_base):
                blockers.append({
                    "code": "released_asset_target_outside_root",
                    "path": str(destination_relative),
                    "message": "Das Ziel einer freigewordenen Zusatzdatei verlässt den Arbeitsbereich.",
                })

            source_exists = source_absolute.exists()
            source_is_symlink = source_absolute.is_symlink() if source_exists else False
            source_is_file = source_absolute.is_file() if source_exists else False
            source_readable = os.access(source_absolute, os.R_OK) if source_exists else False
            source_stat = (
                source_absolute.stat(follow_symlinks=False)
                if source_is_file and not source_is_symlink
                else None
            )
            source_size = int(source_stat.st_size) if source_stat is not None else None
            expected_size = int(asset.get("size_bytes") or 0)
            expected_sha256 = str(asset.get("sha256") or "").strip()
            same_path = source_absolute == destination_absolute
            target_exists = destination_absolute.exists()
            target_conflict = target_exists and not same_path
            checksum_actual = None
            checksum_matches = None

            if verify_sha256 and source_is_file and not source_is_symlink and source_readable:
                checksum_actual = _sha256_file(source_absolute)
                checksum_matches = bool(expected_sha256) and checksum_actual == expected_sha256
                if asset_verification_callback is not None:
                    asset_verification_callback(str(source_relative), expected_size)

            if not source_exists:
                blockers.append({
                    "code": "released_asset_source_missing",
                    "path": str(source_relative),
                    "message": "Freigewordene Zusatzdatei fehlt: " + str(source_relative),
                })
            elif not source_is_file or source_is_symlink:
                blockers.append({
                    "code": "released_asset_source_not_regular",
                    "path": str(source_relative),
                    "message": "Freigewordene Zusatzdatei ist keine reguläre Datei.",
                })
            elif not source_readable:
                blockers.append({
                    "code": "released_asset_source_not_readable",
                    "path": str(source_relative),
                    "message": "Freigewordene Zusatzdatei ist nicht lesbar.",
                })
            if source_is_file and source_size != expected_size:
                blockers.append({
                    "code": "released_asset_source_size_mismatch",
                    "path": str(source_relative),
                    "message": "Freigewordene Zusatzdatei hat eine abweichende Größe.",
                })
            if not expected_sha256:
                blockers.append({
                    "code": "released_asset_checksum_missing",
                    "path": str(source_relative),
                    "message": "Für eine freigewordene Zusatzdatei fehlt die SHA-256-Summe.",
                })
            elif verify_sha256 and checksum_matches is False:
                blockers.append({
                    "code": "released_asset_checksum_mismatch",
                    "path": str(source_relative),
                    "message": "SHA-256-Prüfung einer freigewordenen Zusatzdatei ist fehlgeschlagen.",
                })
            if target_conflict:
                blockers.append({
                    "code": "released_asset_target_exists",
                    "path": str(destination_relative),
                    "message": "Am Ziel einer freigewordenen Zusatzdatei existiert bereits ein anderer Eintrag.",
                })
            if _path_has_symlink(source_absolute, central_stock_root):
                blockers.append({
                    "code": "released_asset_source_symlink_component",
                    "path": str(source_relative),
                    "message": "Der Quellpfad einer freigewordenen Zusatzdatei enthält einen symbolischen Link.",
                })
            if _path_has_symlink(destination_absolute.parent, destination_base):
                blockers.append({
                    "code": "released_asset_target_symlink_component",
                    "path": str(destination_relative),
                    "message": "Der Zielpfad einer freigewordenen Zusatzdatei enthält einen symbolischen Link.",
                })

            status = "move"
            if same_path:
                status = "already_at_target"
            elif not source_exists:
                status = "blocked_missing_source"
            elif target_conflict:
                status = "blocked_target_exists"
            elif source_is_file and source_size != expected_size:
                status = "blocked_size_mismatch"
            elif verify_sha256 and checksum_matches is False:
                status = "blocked_checksum_mismatch"

            planned_directories.add(str(destination_relative.parent))
            asset_entries.append({
                "released_archive_asset_id": int(asset["id"]),
                "asset_kind": released_asset_kind,
                "family_id": family_id,
                "source_file_id": asset.get("source_file_id"),
                "source_root_kind": "shared_workspace",
                "current_root_kind": "shared_workspace",
                "source_relative_path": str(source_relative),
                "source_absolute_path": str(source_absolute),
                "destination_relative_path": str(destination_relative),
                "destination_root_kind": "target_root",
                "destination_absolute_path": str(destination_absolute),
                "expected_size_bytes": expected_size,
                "source_size_bytes": source_size,
                "source_device": int(source_stat.st_dev) if source_stat is not None else None,
                "source_inode": int(source_stat.st_ino) if source_stat is not None else None,
                "source_mtime_ns": int(source_stat.st_mtime_ns) if source_stat is not None else None,
                "stored_sha256": expected_sha256 or None,
                "sha256_verified_now": verify_sha256,
                "calculated_sha256": checksum_actual,
                "sha256_matches": checksum_matches,
                "source_exists": source_exists,
                "source_readable": source_readable,
                "source_is_regular_file": source_is_file and not source_is_symlink,
                "target_exists": target_exists,
                "same_path": same_path,
                "status": status,
            })
            reserved_destination_keys.add(
                str(destination_relative).casefold()
            )

    # XMP-/Exportdateien können auch erst nach dem SD-Import im freien
    # Tagesbestand entstehen (z. B. durch Lightroom). Solche Dateien stehen
    # noch nicht in SQLite. Vor dem ersten Anwenden werden deshalb ausschließlich
    # eindeutig zuordenbare Sidecars/Exports direkt neben bekannten
    # Kameradateien konservativ erkannt und in denselben sicheren Sortierlauf
    # aufgenommen. Beliebige Fremddateien bleiben unangetastet.
    if family_ids and not allow_reapply:
        camera_entries_by_family = defaultdict(list)
        for entry in entries:
            if entry.get("family_id") is not None:
                camera_entries_by_family[int(entry["family_id"])].append(entry)

        known_match_rows = []
        for row in file_rows:
            record = dict(row)
            if record.get("family_id") is None:
                continue
            if int(record["family_id"]) not in set(family_ids):
                continue
            known_match_rows.append({
                **record,
                "file_id": int(record["id"]),
            })

        known_source_files = {
            Path(str(entry["source_absolute_path"])).resolve(strict=False)
            for entry in entries
        }
        tracked_asset_sources = {
            Path(str(entry["source_absolute_path"])).resolve(strict=False)
            for entry in asset_entries
        }
        scan_directories = {
            Path(str(entry["source_absolute_path"])).parent.resolve(strict=False)
            for entry in entries
            if entry.get("family_id") is not None
            and int(entry["family_id"]) in set(family_ids)
            and not bool(file_rows_by_id.get(int(entry["file_id"]), {}).get("_free_stock"))
        }
        # Auch normaler freier Tagesbestand ist zulässig; die obige
        # _free_stock-Markierung wird nur für Zielberechnung benutzt. Daher
        # zusätzlich alle physischen Quellordner der zugeordneten Familien
        # einbeziehen.
        scan_directories.update(
            Path(str(entry["source_absolute_path"])).parent.resolve(strict=False)
            for entry in entries
            if entry.get("family_id") is not None
            and int(entry["family_id"]) in set(family_ids)
        )

        for source_directory in sorted(scan_directories, key=lambda p: str(p)):
            if not source_directory.is_dir():
                continue
            for loose_path in sorted(source_directory.iterdir(), key=lambda p: p.name.casefold()):
                loose_path = loose_path.resolve(strict=False)
                if (
                    loose_path in known_source_files
                    or loose_path in tracked_asset_sources
                    or not loose_path.is_file()
                    or loose_path.is_symlink()
                ):
                    continue

                media_type = classify_media(loose_path)
                if media_type == "xmp":
                    asset_kind = "xmp"
                elif (
                    media_type in {"jpeg", "image"}
                    and export_collision_base_stem(loose_path.stem) is not None
                ):
                    asset_kind = "export"
                else:
                    continue

                family_source = _filename_family_source(
                    loose_path.name,
                    known_match_rows,
                )
                if family_source is None or family_source.get("family_id") is None:
                    continue
                loose_family_id = int(family_source["family_id"])
                if loose_family_id not in set(family_ids):
                    continue

                candidates = camera_entries_by_family.get(loose_family_id, [])
                same_source_candidates = [
                    candidate
                    for candidate in candidates
                    if Path(str(candidate["source_absolute_path"])).parent.resolve(strict=False)
                    == source_directory
                ]
                if same_source_candidates:
                    candidates = same_source_candidates
                target_leaves = {
                    str(candidate.get("structural_leaf_relative_path") or "")
                    for candidate in candidates
                    if str(candidate.get("structural_leaf_relative_path") or "")
                }
                if not candidates or len(target_leaves) != 1:
                    blockers.append({
                        "code": "loose_asset_target_ambiguous",
                        "family_id": loose_family_id,
                        "path": str(loose_path),
                        "message": (
                            "Eine neu entstandene XMP-/Exportdatei konnte keinem "
                            "eindeutigen Ziel innerhalb ihrer Kamerafamilie zugeordnet werden."
                        ),
                    })
                    continue

                source_candidate = candidates[0]
                source_relative = (
                    PurePosixPath(str(source_candidate["source_relative_path"])).parent
                    / loose_path.name
                )
                structural_leaf = PurePosixPath(next(iter(target_leaves)))
                destination_container = structural_leaf
                target_is_free_stock = all(
                    bool(candidate.get("free_stock")) for candidate in candidates
                )
                if (
                    not target_is_free_stock
                    and bool(layout_state.get("structure_enabled"))
                ):
                    organization = layout_input_path
                    if asset_kind == "export" and layout_export_paths:
                        organization = PurePosixPath(layout_export_paths[0])
                    if organization.parts:
                        destination_container = destination_container / organization
                destination_relative = reserve_asset_destination(
                    destination_container / loose_path.name,
                    asset_kind=asset_kind,
                )
                destination_root_kind = (
                    "central_stock" if target_is_free_stock else "target_root"
                )
                destination_base = (
                    central_stock_root
                    if destination_root_kind == "central_stock"
                    else target_root
                )
                destination_absolute = destination_base.joinpath(
                    *destination_relative.parts
                ).resolve(strict=False)

                source_stat = loose_path.stat(follow_symlinks=False)
                expected_size = int(source_stat.st_size)
                expected_sha256 = _sha256_file(loose_path)
                same_path = loose_path == destination_absolute
                target_exists = destination_absolute.exists()
                target_conflict = target_exists and not same_path
                checksum_actual = expected_sha256 if verify_sha256 else None
                checksum_matches = True if verify_sha256 else None

                if target_conflict:
                    blockers.append({
                        "code": "loose_asset_target_exists",
                        "family_id": loose_family_id,
                        "path": str(destination_relative),
                        "message": (
                            "Am Ziel einer neu erkannten XMP-/Exportdatei existiert "
                            "bereits ein anderer Eintrag."
                        ),
                    })
                if _path_has_symlink(
                    destination_absolute.parent,
                    destination_base,
                ):
                    blockers.append({
                        "code": "loose_asset_target_symlink_component",
                        "family_id": loose_family_id,
                        "path": str(destination_relative),
                        "message": (
                            "Der Zielpfad einer neu erkannten XMP-/Exportdatei "
                            "enthält einen symbolischen Link."
                        ),
                    })

                status = "already_at_target" if same_path else (
                    "blocked_target_exists" if target_conflict else "move"
                )
                if destination_root_kind == "target_root":
                    planned_directories.add(str(destination_relative.parent))
                asset_entries.append({
                    "asset_kind": asset_kind,
                    "family_id": loose_family_id,
                    "source_file_id": int(source_candidate["file_id"]),
                    "source_root_kind": str(
                        source_candidate.get("current_root_kind") or "shared_workspace"
                    ),
                    "current_root_kind": str(
                        source_candidate.get("current_root_kind") or "shared_workspace"
                    ),
                    "source_relative_path": str(source_relative),
                    "source_absolute_path": str(loose_path),
                    "destination_relative_path": str(destination_relative),
                    "destination_root_kind": destination_root_kind,
                    "destination_absolute_path": str(destination_absolute),
                    "expected_size_bytes": expected_size,
                    "source_size_bytes": expected_size,
                    "source_device": int(source_stat.st_dev),
                    "source_inode": int(source_stat.st_ino),
                    "source_mtime_ns": int(source_stat.st_mtime_ns),
                    "stored_sha256": expected_sha256,
                    "sha256_verified_now": verify_sha256,
                    "calculated_sha256": checksum_actual,
                    "sha256_matches": checksum_matches,
                    "source_exists": True,
                    "source_readable": os.access(loose_path, os.R_OK),
                    "source_is_regular_file": True,
                    "target_exists": target_exists,
                    "same_path": same_path,
                    "status": status,
                })
                tracked_asset_sources.add(loose_path)
                if (
                    verify_sha256
                    and asset_verification_callback is not None
                ):
                    asset_verification_callback(
                        str(source_relative),
                        expected_size,
                    )

    if allow_reapply and reapply_inventory is not None:
        camera_entries_by_file = {
            int(entry["file_id"]): entry
            for entry in entries
        }
        camera_entries_by_family: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for entry in entries:
            if entry.get("family_id") is not None:
                camera_entries_by_family[int(entry["family_id"])].append(entry)

        for asset in reapply_inventory.get("files", []):
            if asset.get("known_file_id") is not None:
                continue
            asset_kind = str(asset.get("asset_kind") or "")
            if asset_kind not in {"xmp", "export"}:
                continue

            source_relative = _safe_relative_path(
                asset.get("relative_path"),
                "XMP-Quellpfad",
            )
            source_absolute = target_root.joinpath(*source_relative.parts).resolve(
                strict=False
            )
            family_id = (
                int(asset["family_id"])
                if asset.get("family_id") is not None
                else None
            )
            source_file_id = (
                int(asset["source_file_id"])
                if asset.get("source_file_id") is not None
                else None
            )

            if family_id is None:
                blockers.append({
                    "code": "xmp_family_unresolved",
                    "path": str(source_relative),
                    "message": (
                        "Eine XMP-/Exportdatei konnte keiner Kamerafamilie eindeutig "
                        "zugeordnet werden: " + str(source_relative)
                    ),
                })
                continue

            candidates: list[dict[str, Any]] = []
            if source_file_id is not None and source_file_id in camera_entries_by_file:
                candidates = [camera_entries_by_file[source_file_id]]
            if not candidates:
                candidates = list(camera_entries_by_family.get(family_id, []))

            target_leaves = {
                str(candidate.get("structural_leaf_relative_path") or "")
                for candidate in candidates
                if str(candidate.get("structural_leaf_relative_path") or "")
            }
            if not candidates or len(target_leaves) != 1:
                blockers.append({
                    "code": "asset_target_ambiguous",
                    "family_id": family_id,
                    "path": str(source_relative),
                    "message": (
                        "Das strukturelle Ziel einer XMP-/Exportdatei ist innerhalb "
                        "ihrer Kamerafamilie nicht eindeutig: " + str(source_relative)
                    ),
                })
                continue

            destination_parent = PurePosixPath(next(iter(target_leaves)))
            target_is_free_stock = all(
                bool(candidate.get("free_stock")) for candidate in candidates
            )
            if (
                not target_is_free_stock
                and bool(layout_state.get("structure_enabled"))
            ):
                observed_organization = _observed_organization_path(
                    asset,
                    child_folder_names=child_folder_names,
                )
                organization = (
                    observed_organization
                    if observed_organization.parts
                    else layout_input_path
                )
                if organization.parts:
                    destination_parent = destination_parent / organization
            filename = _safe_component(
                source_relative.name,
                "Export-Dateiname" if asset_kind == "export" else "XMP-Dateiname",
            )
            destination_relative = reserve_asset_destination(
                destination_parent / filename,
                asset_kind=asset_kind,
            )
            destination_root_kind = (
                "central_stock" if target_is_free_stock else "target_root"
            )
            destination_base = (
                central_stock_root
                if destination_root_kind == "central_stock"
                else target_root
            )
            destination_absolute = destination_base.joinpath(
                *destination_relative.parts
            ).resolve(strict=False)

            if not _is_relative_to(source_absolute, target_root):
                blockers.append({
                    "code": "xmp_source_outside_root",
                    "path": str(source_relative),
                    "message": "XMP-Quelle verlässt den Arbeitsbereich.",
                })
            if not _is_relative_to(destination_absolute, target_root):
                blockers.append({
                    "code": "xmp_target_outside_root",
                    "path": str(destination_relative),
                    "message": "XMP-Ziel verlässt den Arbeitsbereich.",
                })

            source_exists = source_absolute.exists()
            source_is_symlink = source_absolute.is_symlink() if source_exists else False
            source_is_file = source_absolute.is_file() if source_exists else False
            source_readable = os.access(source_absolute, os.R_OK) if source_exists else False
            source_stat = (
                source_absolute.stat(follow_symlinks=False)
                if source_is_file and not source_is_symlink
                else None
            )
            source_size = int(source_stat.st_size) if source_stat is not None else None
            expected_size = int(asset.get("size_bytes") or 0)
            expected_sha256 = str(asset.get("sha256") or "").strip()
            same_path = source_absolute == destination_absolute
            target_exists = destination_absolute.exists()
            target_conflict = target_exists and not same_path

            if not source_exists:
                blockers.append({
                    "code": "xmp_source_missing",
                    "path": str(source_relative),
                    "message": "XMP-Datei fehlt: " + str(source_relative),
                })
            elif not source_is_file or source_is_symlink:
                blockers.append({
                    "code": "xmp_source_not_regular",
                    "path": str(source_relative),
                    "message": "XMP-Quelle ist keine reguläre Datei: " + str(source_relative),
                })
            elif not source_readable:
                blockers.append({
                    "code": "xmp_source_not_readable",
                    "path": str(source_relative),
                    "message": "XMP-Datei ist nicht lesbar: " + str(source_relative),
                })
            if source_is_file and source_size != expected_size:
                blockers.append({
                    "code": "xmp_source_size_mismatch",
                    "path": str(source_relative),
                    "message": "XMP-Dateigröße änderte sich während der Planung.",
                })
            if not expected_sha256:
                blockers.append({
                    "code": "xmp_checksum_missing",
                    "path": str(source_relative),
                    "message": "Für die XMP-Datei fehlt die SHA-256-Summe.",
                })
            if target_conflict:
                blockers.append({
                    "code": "xmp_target_exists",
                    "path": str(destination_relative),
                    "message": (
                        "Am geplanten XMP-Ziel existiert bereits ein anderer "
                        "Eintrag: " + str(destination_relative)
                    ),
                })
            if _path_has_symlink(source_absolute, target_root):
                blockers.append({
                    "code": "xmp_source_symlink_component",
                    "path": str(source_relative),
                    "message": "Der XMP-Quellpfad enthält einen symbolischen Link.",
                })
            if _path_has_symlink(destination_absolute.parent, target_root):
                blockers.append({
                    "code": "xmp_target_symlink_component",
                    "path": str(destination_relative),
                    "message": "Der XMP-Zielpfad enthält einen symbolischen Link.",
                })

            status = "move"
            if same_path:
                status = "already_at_target"
            elif not source_exists:
                status = "blocked_missing_source"
            elif target_conflict:
                status = "blocked_target_exists"
            elif source_is_file and source_size != expected_size:
                status = "blocked_size_mismatch"

            if destination_root_kind == "target_root":
                planned_directories.add(str(destination_relative.parent))
            asset_entry = {
                "asset_kind": asset_kind,
                "family_id": family_id,
                "source_file_id": source_file_id,
                "source_relative_path": str(source_relative),
                "source_absolute_path": str(source_absolute),
                "destination_relative_path": str(destination_relative),
                "destination_root_kind": destination_root_kind,
                "destination_absolute_path": str(destination_absolute),
                "expected_size_bytes": expected_size,
                "source_size_bytes": source_size,
                "source_device": (
                    int(source_stat.st_dev) if source_stat is not None else None
                ),
                "source_inode": (
                    int(source_stat.st_ino) if source_stat is not None else None
                ),
                "source_mtime_ns": (
                    int(source_stat.st_mtime_ns) if source_stat is not None else None
                ),
                "stored_sha256": expected_sha256 or None,
                "source_exists": source_exists,
                "source_readable": source_readable,
                "source_is_regular_file": source_is_file and not source_is_symlink,
                "target_exists": target_exists,
                "same_path": same_path,
                "status": status,
            }
            asset_entries.append(asset_entry)
            reserved_destination_keys.add(
                str(destination_relative).casefold()
            )

            if (
                verify_sha256
                and status in {"move", "already_at_target"}
                and asset_verification_callback is not None
            ):
                asset_verification_callback(
                    str(source_relative),
                    expected_size,
                )

    if not entries:
        blockers.append({
            "code": "no_files",
            "message": "Für die Ereigniszuordnung wurden keine Dateien gefunden.",
        })

    for family_id, family_status in sorted(family_statuses.items()):
        if family_status not in ALLOWED_FAMILY_STATUSES:
            blockers.append({
                "code": "family_not_ready",
                "family_id": family_id,
                "message": (
                    f"Dateifamilie {family_id} ist noch nicht sortierbereit: "
                    + family_status
                ),
            })

    families, target_groups = _build_family_target_groups(
        entries,
        asset_entries,
    )

    for family in families:
        if not family["split_across_targets"] or allow_reapply:
            continue

        blockers.append({
            "code": "family_split_target",
            "family_id": family.get("family_id"),
            "family_key": family.get("family_key"),
            "message": (
                "Eine Dateifamilie würde auf mehrere Zielordner "
                "aufgeteilt und darf deshalb nicht sortiert werden: "
                + str(family["display_name"])
                + " → "
                + ", ".join(family["target_directories"])
            ),
        })

    destinations_by_casefold: dict[str, list[str]] = defaultdict(list)
    for entry in [*entries, *asset_entries]:
        destination = str(entry["destination_relative_path"])
        destinations_by_casefold[destination.casefold()].append(destination)

    duplicate_destinations = [
        sorted(set(paths))
        for paths in destinations_by_casefold.values()
        if len(paths) > 1
    ]
    duplicate_destinations.sort(key=lambda paths: paths[0].casefold())

    for paths in duplicate_destinations:
        blockers.append({
            "code": "duplicate_destination",
            "message": (
                "Mehrere Quelldateien würden denselben Zielpfad verwenden "
                "(Groß-/Kleinschreibung zählt auf dem NAS nicht als Unterschied): "
                + " / ".join(paths)
            ),
        })

    target_device = int(target_root.stat().st_dev)
    central_device = int(central_stock_root.stat().st_dev)
    target_available = int(
        os.statvfs(target_root).f_bavail * os.statvfs(target_root).f_frsize
    )
    central_available = int(
        os.statvfs(central_stock_root).f_bavail
        * os.statvfs(central_stock_root).f_frsize
    )
    required_target_bytes = 0
    required_central_bytes = 0
    for entry in [*entries, *asset_entries]:
        if entry.get("same_path") or entry.get("status") != "move":
            continue
        source_device = entry.get("source_device")
        destination_kind = str(
            entry.get("destination_root_kind") or "target_root"
        )
        destination_device = (
            central_device
            if destination_kind == "central_stock"
            else target_device
        )
        if source_device is None or int(source_device) == destination_device:
            continue
        if destination_kind == "central_stock":
            required_central_bytes += int(entry["expected_size_bytes"])
        else:
            required_target_bytes += int(entry["expected_size_bytes"])

    required_extra_bytes = required_target_bytes + required_central_bytes
    same_filesystem = required_extra_bytes == 0
    available_bytes = min(target_available, central_available)

    if required_target_bytes > target_available:
        blockers.append({
            "code": "insufficient_space",
            "message": "Im Bibliotheks-Arbeitsbereich reicht der freie Speicher für den geprüften Transfer nicht aus.",
        })
    if required_central_bytes > central_available:
        blockers.append({
            "code": "insufficient_central_stock_space",
            "message": "Im zentralen Aufnahmebestand reicht der freie Speicher für den geprüften Rücktransfer nicht aus.",
        })
    if required_extra_bytes:
        warnings.append({
            "code": "cross_filesystem_copy_verify",
            "message": (
                "Mindestens eine Datei wechselt das Dateisystem. Bibliothekar "
                "verwendet dafür Copy → SHA-256-Prüfung → Quelllöschung."
            ),
        })

    if not verify_sha256:
        warnings.append({
            "code": "checksums_not_recomputed",
            "message": (
                "Die gespeicherten SHA-256-Summen sind vorhanden, wurden für "
                "diese schnelle Vorschau aber nicht erneut über alle Dateien "
                "berechnet. Die erneute Prüfsummenprüfung gehört zum späteren "
                "bestätigten Anwenden."
            ),
        })

    directory_rows = []

    for relative in sorted(planned_directories):
        relative_path = _safe_relative_path(relative, "Geplanter Ordner")
        absolute = target_root.joinpath(*relative_path.parts).resolve(
            strict=False
        )
        directory_rows.append({
            "relative_path": str(relative_path),
            "absolute_path": str(absolute),
            "exists": absolute.exists(),
            "is_directory": absolute.is_dir() if absolute.exists() else False,
        })

        if absolute.exists() and not absolute.is_dir():
            blockers.append({
                "code": "directory_path_occupied",
                "message": (
                    "Ein geplanter Ordnerpfad ist bereits durch eine Datei belegt: "
                    + str(relative_path)
                ),
            })

    structure_text = _tree_text_from_directories(
        year,
        parent_folder,
        planned_directories,
    )

    blocker_codes = Counter(
        str(blocker.get("code"))
        for blocker in blockers
    )

    summary = {
        "ready": len(blockers) == 0,
        "family_count": len(families),
        "target_group_count": len(target_groups),
        "file_count": len(entries) + len(asset_entries),
        "camera_file_count": len(entries),
        "asset_count": len(asset_entries),
        "xmp_count": sum(
            entry.get("asset_kind") == "xmp" for entry in asset_entries
        ),
        "move_count": sum(
            entry["status"] == "move" for entry in [*entries, *asset_entries]
        ),
        "already_at_target_count": sum(
            entry["status"] == "already_at_target"
            for entry in [*entries, *asset_entries]
        ),
        "directory_count": len(directory_rows),
        "directory_create_count": sum(
            not row["exists"] for row in directory_rows
        ),
        "total_size_bytes": sum(
            int(entry["expected_size_bytes"])
            for entry in [*entries, *asset_entries]
        ),
        "available_bytes": available_bytes,
        "required_extra_bytes": required_extra_bytes,
        "same_filesystem": same_filesystem,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "missing_source_count": blocker_codes.get("source_missing", 0),
        "size_mismatch_count": blocker_codes.get("source_size_mismatch", 0),
        "checksum_mismatch_count": blocker_codes.get("checksum_mismatch", 0),
        "target_conflict_count": blocker_codes.get("target_exists", 0),
        "duplicate_destination_count": blocker_codes.get(
            "duplicate_destination", 0
        ),
        "family_issue_count": blocker_codes.get("family_not_ready", 0),
        "family_split_count": blocker_codes.get(
            "family_split_target", 0
        ),
    }

    plan_token = _build_plan_token(
        job_id,
        event,
        source_root,
        target_root,
        central_stock_root,
        entries,
        asset_entries,
        directory_rows,
    )

    return {
        "mode": "read_only_sort_plan",
        "plan_token": plan_token,
        "apply_confirmation_phrase": "SORTIERUNG ANWENDEN",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "files_changed": False,
        "folders_changed": False,
        "database_changed": False,
        "sha256_recomputed": verify_sha256,
        "job": {
            "id": str(job["id"]),
            "kind": str(job.get("kind") or ""),
            "operation": str(job.get("operation") or ""),
            "state": str(job.get("state") or ""),
            "stage": str(job.get("stage") or ""),
            "source_root_field": source_root_field,
        },
        "event": {
            "id": str(event["id"]),
            "name": str(event["name"]),
            "folder_name": parent_folder,
            "physical_folder_parts": physical_parent_parts,
            "collision_redirected": collision_redirected,
            "status": str(event["status"]),
            "event_kind": str(event.get("event_kind") or "event"),
            "preserve_day_folders": preserve_day_folders,
            "start_datetime": str(event["start_datetime"]),
            "end_datetime": str(event["end_datetime"]),
        },
        "workspace_root": str(workspace_root),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "structure_text": structure_text,
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "directories": directory_rows,
        "target_groups": target_groups,
        "families": families,
        "files": entries,
        "assets": asset_entries,
    }
