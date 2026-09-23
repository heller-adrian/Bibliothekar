from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
import hashlib
import json
import os

from app.database import database_connection
from app.job_readiness import job_sort_readiness
from app.workspace_layout import (
    WorkspaceLayoutError,
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



def _tree_text(
    year: str,
    parent_folder: str,
    branches: list[dict[str, Any]],
) -> str:
    lines = [
        year,
        f"└── {parent_folder}",
    ]

    if not branches:
        return "\n".join(lines)

    for branch_index, branch in enumerate(branches):
        branch_name = branch.get("name")
        days = list(branch.get("days") or [])
        branch_is_last = branch_index == len(branches) - 1

        branch_indent = "    "

        if branch_name:
            branch_connector = "└──" if branch_is_last else "├──"
            lines.append(
                f"{branch_indent}{branch_connector} {branch_name}"
            )
            branch_indent += "    " if branch_is_last else "│   "

        if days:
            for day_index, day_key in enumerate(days):
                day_is_last = day_index == len(days) - 1
                day_connector = "└──" if day_is_last else "├──"
                lines.append(
                    f"{branch_indent}{day_connector} {day_key}"
                )
                leaf_indent = branch_indent + (
                    "    " if day_is_last else "│   "
                )
                lines.extend([
                    f"{leaf_indent}├── Alle",
                    f"{leaf_indent}├── Sortiert",
                    f"{leaf_indent}└── Export",
                ])
        else:
            lines.extend([
                f"{branch_indent}├── Alle",
                f"{branch_indent}├── Sortiert",
                f"{branch_indent}└── Export",
            ])

    return "\n".join(lines)




def _build_family_target_groups(
    entries: list[dict[str, Any]],
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
                entry.get("family_key")
                or source_relative.stem
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



def _build_plan_token(
    job_id: str,
    event: dict[str, Any],
    source_root: Path,
    target_root: Path,
    entries: list[dict[str, Any]],
    directory_rows: list[dict[str, Any]],
) -> str:
    payload = {
        "job_id": job_id,
        "event_id": str(event["id"]),
        "event_revision": int(event.get("revision") or 1),
        "event_status": str(event.get("status") or ""),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "files": [
            {
                "file_id": int(entry["file_id"]),
                "family_id": entry.get("family_id"),
                "source": str(entry["source_relative_path"]),
                "destination": str(entry["destination_relative_path"]),
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

        assignment_rows = connection.execute(
            """
            SELECT
                ea.family_id,
                ea.file_id,
                assigned.id AS assigned_event_id,
                assigned.parent_event_id,
                assigned.folder_name AS assigned_folder_name

            FROM event_assignments AS ea

            JOIN events AS assigned
                ON assigned.id = ea.event_id

            WHERE assigned.job_id = ?
              AND (
                    assigned.id = ?
                    OR assigned.parent_event_id = ?
                  )

            ORDER BY
                assigned.start_datetime,
                assigned.id,
                ea.family_id,
                ea.file_id
            """,
            (job_id, event_id, event_id),
        ).fetchall()

        family_assignments: dict[int, dict[str, Any]] = {}
        direct_file_assignments: list[int] = []
        removed_family_ids: set[int] = set()
        removed_targets: dict[int, dict[str, Any]] = {}

        for row in assignment_rows:
            if row["family_id"] is not None:
                family_assignments[int(row["family_id"])] = dict(row)
            elif row["file_id"] is not None:
                direct_file_assignments.append(int(row["file_id"]))

        if allow_reapply:
            removed_rows = connection.execute(
                """SELECT family_id, target_event_id, target_status, target_kind,
                          target_name, target_folder_name, target_preserve_day_folders,
                          target_linkage_kind
                   FROM event_reapply_removed_families
                   WHERE event_id = ? AND job_id = ?""",
                (event_id, job_id),
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

                    WHERE f.job_id = ?
                      AND f.family_id IN ({family_placeholders})

                    ORDER BY
                        ff.selected_capture_time,
                        ff.id,
                        f.original_relative_path
                    """,
                    (job_id, *family_ids),
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

                    WHERE f.job_id = ?
                      AND f.id IN ({file_placeholders})

                    ORDER BY f.original_relative_path
                    """,
                    (job_id, *direct_file_assignments),
                ).fetchall()
            )

        from app.free_stock_layout import (
            affected_days_for_event,
            canonical_free_directory,
            free_file_rows,
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
                record["_free_directory"] = str(
                    canonical_free_directory(
                        connection,
                        str(
                            record.get("family_capture_time")
                            or record.get("selected_capture_time")
                            or ""
                        ),
                        physical=True,
                        include_event_ids=(event_id,) if not allow_reapply else (),
                    )
                )
            normalized_file_rows.append(record)
        file_rows = normalized_file_rows

    job = dict(job_row)

    try:
        target_root = shared_work_root(workspace_root)
    except WorkspaceLayoutError as error:
        raise SortPlanError(str(error)) from error

    if allow_reapply:
        # In der Nachsortierung liegen die Dateien bereits im gemeinsamen
        # Arbeitsbereich; Quelle und Ziel sind derselbe Bereich.
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
              AND job_id <> ?
              AND status IN ('planned', 'applied', 'archived')
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (parent_folder, job_id),
        ).fetchone()

    collision_redirected = collision_row is not None
    job_token = _safe_component(job_id[-12:], "Auftragskennung")
    linkage_kind = str(event.get("linkage_kind") or "")
    if allow_reapply:
        # Die Nachsortierung nutzt ausschließlich die aktuelle Ereignisstruktur.
        # Eine Umlenkung nach „Später zuzuordnen“ fand beim ursprünglichen
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
        physical_parent_parts = ["Später zuzuordnen", f"{parent_folder} - {job_token}"]
    else:
        physical_parent_parts = (
            ["Später zuzuordnen", f"{parent_folder} - {job_token}"]
            if collision_redirected
            else [parent_folder]
        )

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    planned_directories: set[str] = set()
    branch_days: dict[str | None, set[str]] = defaultdict(set)
    branch_order: list[str | None] = []
    family_statuses: dict[int, str] = {}

    job_ready, job_blocker = job_sort_readiness(job)
    if not job_ready:
        blockers.append({
            "code": "job_not_verified",
            "message": job_blocker,
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
                "unter ‚Später zuzuordnen‘ für die manuelle Archiv-Ergänzung bereitgestellt."
            ),
        })
    elif collision_redirected:
        warnings.append({
            "code": "existing_event_folder_redirect",
            "message": (
                "Ein gleichnamiger Ereignisordner aus einem anderen "
                "Sicherungsauftrag existiert bereits. Die neuen Dateien "
                "werden sicher getrennt unter ‚Später zuzuordnen‘ abgelegt."
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

        if branch_key not in branch_order:
            branch_order.append(branch_key)

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

        source_relative = _safe_relative_path(
            file_record.get("current_relative_path")
            or file_record.get("original_relative_path"),
            "Aktueller relativer Dateipfad",
        )

        current_root_kind = str(
            file_record.get("current_root_kind")
            or "job_root"
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
                reassignment.get("target_folder_name") or "Später zuzuordnen",
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
                destination_parts = ["Später zuzuordnen", year, f"{target_folder} - {job_token}"]
            else:
                destination_parts = [year, target_folder]
            file_preserve_day_folders = bool(reassignment.get("target_preserve_day_folders"))
            child_folder = None
        elif linkage_kind == "archived_manual" or collision_redirected:
            # "Später zuzuordnen" ist ein globaler technischer Bereich direkt
            # unter Arbeitsbereich. Die Jahresordner entstehen nur innerhalb
            # dieses Bereichs, damit die normalen Jahresordner auch langfristig
            # ausschließlich echte Ereignisse enthalten.
            destination_parts = ["Später zuzuordnen", year, *physical_parent_parts[1:]]
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
                branch_days[branch_key].add(day_key)

        if is_free_stock:
            destination_parts.append(filename)
        else:
            destination_parts.extend(["Alle", filename])

        destination_relative = PurePosixPath(*destination_parts)
        source_base = target_root if current_root_kind == "shared_workspace" else source_root
        source_absolute = (
            source_base.joinpath(*source_relative.parts).resolve(
                strict=False
            )
        )
        destination_absolute = (
            target_root.joinpath(*destination_relative.parts).resolve(
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

        if not _is_relative_to(destination_absolute, target_root):
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

        leaf = destination_relative.parent
        planned_directories.add(str(leaf))
        if not is_free_stock:
            planned_directories.add(str(leaf.parent / "Sortiert"))
            planned_directories.add(str(leaf.parent / "Export"))

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

    families, target_groups = _build_family_target_groups(entries)

    for family in families:
        if not family["split_across_targets"]:
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

    destination_counts = Counter(
        entry["destination_relative_path"]
        for entry in entries
    )
    duplicate_destinations = sorted(
        destination
        for destination, count in destination_counts.items()
        if count > 1
    )

    for destination in duplicate_destinations:
        blockers.append({
            "code": "duplicate_destination",
            "message": (
                "Mehrere Quelldateien würden denselben Zielpfad verwenden: "
                + destination
            ),
        })

    source_device = int(source_root.stat().st_dev)
    target_device = int(target_root.stat().st_dev)
    same_filesystem = source_device == target_device

    if not same_filesystem:
        blockers.append({
            "code": "different_filesystem",
            "message": (
                "Quelle und Ziel liegen nicht auf demselben Dateisystem. "
                "Für diese Sortierung sind nur Verschiebungen innerhalb "
                "des SSD-Arbeitsbereichs zulässig."
            ),
        })

    statvfs = os.statvfs(target_root)
    available_bytes = int(statvfs.f_bavail * statvfs.f_frsize)
    total_bytes = sum(
        int(entry["expected_size_bytes"])
        for entry in entries
        if not entry["same_path"]
    )
    required_extra_bytes = 0 if same_filesystem else total_bytes

    if required_extra_bytes > available_bytes:
        blockers.append({
            "code": "insufficient_space",
            "message": (
                "Der freie Speicher reicht für die geplante Operation nicht aus."
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

    branches: list[dict[str, Any]] = []

    for branch_key in branch_order:
        branches.append({
            "name": branch_key,
            "days": sorted(branch_days.get(branch_key, set()))
            if preserve_day_folders
            else [],
        })

    structure_text = _tree_text(
        year,
        parent_folder,
        branches,
    )

    blocker_codes = Counter(
        str(blocker.get("code"))
        for blocker in blockers
    )

    summary = {
        "ready": len(blockers) == 0,
        "family_count": len(families),
        "target_group_count": len(target_groups),
        "file_count": len(entries),
        "move_count": sum(
            entry["status"] == "move" for entry in entries
        ),
        "already_at_target_count": sum(
            entry["status"] == "already_at_target" for entry in entries
        ),
        "directory_count": len(directory_rows),
        "directory_create_count": sum(
            not row["exists"] for row in directory_rows
        ),
        "total_size_bytes": sum(
            int(entry["expected_size_bytes"])
            for entry in entries
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
        entries,
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
    }
