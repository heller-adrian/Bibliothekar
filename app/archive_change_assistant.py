from __future__ import annotations

"""Variabler Dreischritt-Assistent für manuelle Archivänderungen."""

from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import os

from app.archive_staging import (
    BRANCHES,
    staging_directory_name,
    describe_archive_change_staging_for_request,
)
from app.event_change_request import get_event_change_files, get_event_change_request
from app.archive_release_stock import describe_archive_release_stock
from app.workspace_layout import shared_work_root


from app.manual_file_operations import group_file_operations, topmost_directories, parent_directory as _parent_dir


class ArchiveChangeAssistantError(RuntimeError):
    pass


def _tree_lines(root: str, directories: list[str]) -> list[str]:
    root_path = PurePosixPath(root)
    tree: dict[str, dict] = {}
    for value in directories:
        path = PurePosixPath(value)
        try:
            suffix = path.relative_to(root_path)
        except ValueError:
            continue
        node = tree
        for part in suffix.parts:
            node = node.setdefault(part, {})

    lines = [root_path.parts[0], f"└── {root_path.parts[1]}"]

    def walk(node: dict[str, dict], indent: str) -> None:
        names = sorted(node, key=lambda name: (name in BRANCHES, name))
        for index, name in enumerate(names):
            last = index == len(names) - 1
            lines.append(f"{indent}{'└──' if last else '├──'} {name}")
            walk(node[name], indent + ("    " if last else "│   "))

    walk(tree, "    ")
    return lines


def _path_is_under(path_value: str, root_value: str) -> bool:
    try:
        PurePosixPath(path_value).relative_to(PurePosixPath(root_value))
        return True
    except ValueError:
        return False


def _basename(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    return PurePosixPath(raw).name if raw else ""


def _safe_archive_path(archive_root: Path, relative: str) -> Path:
    root = archive_root.expanduser().resolve(strict=False)
    rel = PurePosixPath(str(relative or "").replace("\\", "/").strip("/"))
    if not rel.parts or rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ArchiveChangeAssistantError("Unsicherer Archivpfad: " + str(relative))
    target = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArchiveChangeAssistantError("Archivpfad verlässt die Kamerabibliothek.") from exc
    return target


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scan_live_locations(
    archive_root: Path,
    rows: list[dict[str, Any]],
    roots: list[str],
) -> dict[tuple[str, int], dict[str, Any]]:
    relevant = [
        row for row in rows
        if str(row.get("action") or "") == "move"
        and str(row.get("new_path") or "").strip()
        and str(row.get("expected_sha256") or "").strip()
    ]
    expected_by_size: dict[int, set[str]] = {}
    for row in relevant:
        expected_by_size.setdefault(int(row.get("expected_size_bytes") or 0), set()).add(
            str(row.get("expected_sha256") or "")
        )

    index: dict[tuple[int, str], list[str]] = {}
    root_abs = archive_root.expanduser().resolve(strict=False)
    scanned: set[Path] = set()
    for relative_root in roots:
        if not relative_root:
            continue
        try:
            base = _safe_archive_path(archive_root, relative_root)
        except ArchiveChangeAssistantError:
            continue
        if not base.is_dir() or base in scanned:
            continue
        scanned.add(base)
        for current, directories, filenames in os.walk(base, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name for name in directories
                if not (current_path / name).is_symlink()
            ]
            for name in filenames:
                path = current_path / name
                if path.is_symlink() or not path.is_file():
                    continue
                size = int(path.stat().st_size)
                hashes = expected_by_size.get(size)
                if not hashes:
                    continue
                sha = _sha256_file(path)
                if sha not in hashes:
                    continue
                relative = path.resolve(strict=False).relative_to(root_abs).as_posix()
                index.setdefault((size, sha), []).append(relative)

    states: dict[tuple[str, int], dict[str, Any]] = {}
    for row in relevant:
        key = (str(row.get("review_kind") or "camera"), int(row["id"]))
        size = int(row.get("expected_size_bytes") or 0)
        sha = str(row.get("expected_sha256") or "")
        target = str(row.get("new_path") or "")
        old = str(row.get("old_path") or "")
        matches = list(index.get((size, sha), []))
        if target in matches:
            states[key] = {
                "state": "done",
                "current_path": target,
                "at_target": True,
                "matches": matches,
            }
        elif old in matches:
            states[key] = {
                "state": "pending",
                "current_path": old,
                "at_target": False,
                "matches": matches,
            }
        elif len(matches) == 1:
            states[key] = {
                "state": "pending",
                "current_path": matches[0],
                "at_target": False,
                "matches": matches,
            }
        elif len(matches) > 1:
            states[key] = {
                "state": "ambiguous",
                "current_path": "",
                "at_target": False,
                "matches": sorted(matches),
            }
        else:
            states[key] = {
                "state": "missing",
                "current_path": "",
                "at_target": False,
                "matches": [],
            }
    return states


def build_archive_change_assistant(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    scan_live: bool = False,
    archive_display_root: str = "Kamerabibliothek",
    work_display_root: str = "Arbeitsbereich",
    backup_display_root: str = "SD-Kartensicherungen",
) -> dict[str, Any]:
    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise ArchiveChangeAssistantError("Änderungsauftrag wurde nicht gefunden.")

    rows = get_event_change_files(database_path, cr_id)
    description = describe_archive_change_staging_for_request(
        database_path, archive_root, cr_id
    )
    from app.archive_reversal import _manifest_path, _read_baseline
    from app.archive_staging import staging_without_renamed_folders
    renames = []
    if _manifest_path(workspace_path, cr_id).is_file():
        renames = _read_baseline(workspace_path, cr_id).get("directory_renames", [])
        description = staging_without_renamed_folders(description, renames)
    release_stock = describe_archive_release_stock(database_path, cr_id)
    from app.managed_directory_names import directory_name
    from app.workspace_layout import backup_root
    release_stock['release_directory_name']=directory_name(backup_root(workspace_path),"released_archive")

    status = str(cr.get("status") or "")
    delete_event = bool(cr.get("delete_event") or 0)
    preparation_required = bool(
        description.get("required") or release_stock.get("required")
    )
    target_root = str(description.get("target_root") or "")
    current_root = str(description.get("current_root") or "")
    helper_root = str(cr.get("prepared_structure_path") or description.get("prepared_structure_path") or "")
    # Use the physical workspace name, never the historical public constant.
    # A prepared request retains its persisted staging path across upgrades.
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_name = staging_directory_name(work_root)
    if helper_root:
        helper_path = PurePosixPath(helper_root.replace(chr(92), "/"))
        helper_parts = helper_path.parts
        if (
            helper_path.is_absolute()
            or ".." in helper_parts
            or len(helper_parts) < 3
            or helper_parts[0] not in {"Später zuordnen", "Assign Later"}
        ):
            raise ArchiveChangeAssistantError("Invalid persisted archive staging path.")
        persisted_name = helper_parts[0]
        persisted_root = work_root / persisted_name
        if persisted_root.is_symlink():
            raise ArchiveChangeAssistantError("Archive staging path must not be a symlink.")
        if persisted_root.is_dir():
            staging_name = persisted_name
        elif status == "aenderbar_bestaetigt":
            raise ArchiveChangeAssistantError(
                "The prepared archive staging folder no longer exists. "
                "Refresh and verify the request before following any Finder instructions."
            )
    missing = list(description.get("missing_directories") or [])
    obsolete = list(description.get("obsolete_directories") or [])
    event_document = description.get("event_document")

    archive_display_root = str(archive_display_root or "Kamerabibliothek").strip() or "Kamerabibliothek"
    work_display_root = str(work_display_root or "Arbeitsbereich").strip() or "Arbeitsbereich"
    backup_display_root = str(backup_display_root or "SD-Kartensicherungen").strip() or "SD-Kartensicherungen"

    actionable = [
        row for row in rows
        if str(row.get("action") or "") == "move"
        and str(row.get("new_path") or "").strip()
    ]
    workspace_rows = [
        row for row in actionable
        if str(row.get("source_root_kind") or "camera_archive") == "shared_workspace"
    ]
    archive_rows = [
        row for row in actionable
        if str(row.get("source_root_kind") or "camera_archive") != "shared_workspace"
    ]

    live_states: dict[tuple[str, int], dict[str, Any]] = {}
    if scan_live:
        live_states = _scan_live_locations(
            archive_root,
            rows,
            [current_root, target_root],
        )

    operations: list[dict[str, Any]] = []
    folder_removal = {"qualified":False}
    if delete_event and release_stock.get("copy_verified"):
        from app.archive_delete_guidance import qualify_event_folder
        folder_removal=qualify_event_folder(database_path,archive_root,workspace_path,cr_id,release_stock)

    if delete_event and folder_removal.get("qualified") and (
        not bool(release_stock.get("required"))
        or bool(release_stock.get("archive_removed"))
    ):
        old_root = str(description.get("current_root") or "")
        old_path = _safe_archive_path(archive_root, old_root)
        state = None
        if scan_live:
            state = "done" if not old_path.exists() else "pending"
        operations.append({
            "kind": "remove_deleted_event_root",
            "title": "Alten Ereignisordner vollständig entfernen",
            "paths": [f"{archive_display_root}/{old_root}"] if old_path.exists() else [],
            "all_paths": [f"{archive_display_root}/{old_root}"],
            "detail": (
                "Nachdem alle Archivdateien sicher auf die SSD zurückgeholt wurden, "
                "den bisherigen Ereignisordner einschließlich event.json vollständig entfernen."
            ),
            "state": state,
        })

    # Minimal user action: copy complete top-level prepared structures.
    # Bei Löschaufträgen gibt es bewusst keine neue SOLL-Struktur.
    if not delete_event:
        from app.archive_locations import ArchiveLocationError, archive_target_lookup
        from app.archive_rename_guidance import layout_rename_state

        for rename in renames:
            source, target = rename["source"], rename["target"]
            operations.append({
                "kind": "rename_archive_folder",
                "title": "Geprüften Ordner umbenennen",
                "source": f"{archive_display_root}/{source}",
                "target": f"{archive_display_root}/{target}",
                "detail": "Benenne den geprüften Ordner am angegebenen Ort um. Ersetze keinen vorhandenen Ordner.",
                "state": layout_rename_state(archive_root, rename),
            })
        obsolete = [path for path in obsolete if not any(path == rename["source"] for rename in renames)]
        archive_rows = [row for row in archive_rows if not any(
            _path_is_under(row["old_path"], rename["source"]) for rename in renames
        )]

        existing = archive_target_lookup(archive_root)
        copy_groups: dict[PurePosixPath, list[str]] = {}
        copy_roots = []
        for candidate in topmost_directories(missing):
            root_value = candidate.as_posix()
            try:
                occupied = existing(root_value) is not None
            except (ArchiveLocationError, OSError):
                occupied = True
            if occupied:
                operations.append({
                    "kind": "archive_conflict",
                    "title": "Zielordner ist belegt",
                    "protected_paths": [f"{archive_display_root}/{root_value}"],
                    "detail": "Das Ziel ist bereits belegt. Ersetze dort keine vorhandenen Dateien oder Ordner.",
                    "state": "blocked",
                })
                continue
            copy_groups.setdefault(candidate.parent, []).append(root_value)
            copy_roots.append(root_value)

        covered_workspace_rows = {
            (str(row.get("review_kind") or "camera"), int(row["id"]))
            for row in workspace_rows
            if any(_path_is_under(str(row.get("new_path") or ""), root) for root in copy_roots)
        }
        document_rel = str(event_document.get("target_relative_path") or "") if event_document else ""
        document_covered_by_root_copy = False
        for parent, paths in sorted(copy_groups.items()):
            sources = list(paths)
            if document_rel and document_rel.startswith(parent.as_posix() + "/"):
                document_parent = PurePosixPath(document_rel).parent
                if document_parent == parent:
                    sources.append(document_rel)
                    document_covered_by_root_copy = True
                elif document_parent.as_posix() in paths:
                    document_covered_by_root_copy = True
            operations.append({
                "kind": "copy_helper_folders",
                "title": "Vorbereitete Struktur ins Archiv übernehmen",
                "sources": [f"{work_display_root}/{staging_name}/{path}" for path in sources],
                "items": [_basename(path) for path in sources],
                "target": f"{archive_display_root}/{parent.as_posix()}",
                "detail": (
                    "Nur die genannten Ordner an das angegebene Ziel kopieren. Vorhandene Ordner nicht ersetzen."
                    if document_rel not in sources else
                    "Nur die genannten Ordner kopieren und die event.json durch die vorbereitete Fassung ersetzen."
                ),
                "state": "pending" if scan_live else None,
            })

        remaining_workspace = [
            row for row in workspace_rows
            if (
                str(row.get("review_kind") or "camera"),
                int(row["id"]),
            ) not in covered_workspace_rows
        ]
        grouped_workspace = group_file_operations(
            (row.get("workspace_staging_path") or f"{staging_name}/{row.get('new_path') or ''}",
             row.get("new_path"), row)
            for row in remaining_workspace
        )
        for (source, target), members in grouped_workspace:
            state = None
            pending_members = members
            if scan_live:
                pending_members = [
                    row for row in members
                    if not live_states.get(
                        (str(row.get("review_kind") or "camera"), int(row["id"])),
                        {},
                    ).get("at_target")
                ]
                state = "done" if not pending_members else "pending"
            shown_members = pending_members if scan_live and pending_members else members
            operations.append({
                "kind": "copy_files",
                "title": "Neue Dateien in einen vorhandenen Archivordner übernehmen",
                "source": f"{work_display_root}/{source}",
                "target": f"{archive_display_root}/{target}",
                "items": [_basename(row.get("new_path")) for row in shown_members],
                "file_count": len(shown_members),
                "detail": (
                    f"{len(shown_members)} Datei" + ("" if len(shown_members) == 1 else "en")
                    + " in den vorhandenen Zielordner übernehmen."
                ),
                "state": state,
            })

        if event_document and not document_covered_by_root_copy:
            target_rel = str(event_document.get("target_relative_path") or "")
            target_abs = _safe_archive_path(archive_root, target_rel)
            document_state = None
            if scan_live:
                if (
                    target_abs.is_file()
                    and not target_abs.is_symlink()
                    and int(target_abs.stat().st_size) == int(event_document.get("size_bytes") or 0)
                    and _sha256_file(target_abs) == str(event_document.get("sha256") or "")
                ):
                    document_state = "done"
                else:
                    document_state = "pending"
            operations.append({
                "kind": "replace_event_document",
                "title": "Aktuelle event.json ins Archiv übernehmen",
                "source": f"{work_display_root}/{staging_name}/{target_rel}",
                "target": f"{archive_display_root}/{target_rel}",
                "items": ["event.json"],
                "file_count": 1,
                "detail": (
                    "Die bestehende event.json im Archiv durch die vorbereitete neue "
                    "event.json ersetzen. Nicht daneben ablegen und keine zweite "
                    "event.json im Ereignisordner behalten."
                ),
                "state": document_state,
            })

        grouped_archive = group_file_operations(
            (row.get("old_path"), row.get("new_path"), row) for row in archive_rows
        )

        for (planned_source, target), members in grouped_archive:
            state = None
            shown_members = members
            source_dirs = [planned_source]
            if scan_live:
                pending: list[dict[str, Any]] = []
                current_dirs: set[str] = set()
                missing_count = 0
                ambiguous_count = 0
                for row in members:
                    live = live_states.get(
                        (str(row.get("review_kind") or "camera"), int(row["id"])),
                        {},
                    )
                    if live.get("at_target"):
                        continue
                    pending.append(row)
                    if live.get("current_path"):
                        current_dirs.add(_parent_dir(live["current_path"]))
                    elif live.get("state") == "ambiguous":
                        ambiguous_count += 1
                    else:
                        missing_count += 1
                if not pending:
                    state = "done"
                    shown_members = members
                else:
                    state = "pending"
                    shown_members = pending
                    source_dirs = sorted(current_dirs) or [planned_source]
                    if missing_count or ambiguous_count:
                        state = "attention"

            operations.append({
                "kind": "move_archive_files",
                "title": "Dateien innerhalb der Kamerabibliothek verschieben",
                "source": (
                    f"{archive_display_root}/{source_dirs[0]}"
                    if len(source_dirs) == 1 else ""
                ),
                "sources": (
                    [f"{archive_display_root}/{value}" for value in source_dirs]
                    if len(source_dirs) > 1 else []
                ),
                "target": f"{archive_display_root}/{target}",
                "items": [
                    _basename(
                        live_states.get(
                            (str(row.get("review_kind") or "camera"), int(row["id"])),
                            {},
                        ).get("current_path")
                        or row.get("old_path")
                    )
                    for row in shown_members
                ],
                "file_count": len(shown_members),
                "detail": (
                    f"{len(shown_members)} Datei" + ("" if len(shown_members) == 1 else "en")
                    + " in den angegebenen Zielordner verschieben."
                ),
                "state": state,
            })

        if obsolete:
            # Alte DB-/event.json-Strukturen können noch Verzeichnisse nennen,
            # die durch eine frühere manuelle Archivänderung bereits physisch
            # entfernt wurden. Finder-Arbeit entsteht nur für tatsächlich noch
            # vorhandene Ordner; die historische Soll-Differenz bleibt intern
            # weiterhin in obsolete_directories nachvollziehbar.
            pending_obsolete = [
                value for value in obsolete
                if _safe_archive_path(archive_root, value).exists()
            ]
            if pending_obsolete:
                operations.append({
                    "kind": "remove_directories",
                    "title": "Nicht mehr benötigte alte Ordner entfernen",
                    "items": [_basename(value) for value in pending_obsolete],
                    "paths": [f"{archive_display_root}/{value}" for value in pending_obsolete],
                    "all_paths": [f"{archive_display_root}/{value}" for value in obsolete],
                    "detail": (
                        "Diese alten Ordner müssen nach den Verschiebungen leer sein "
                        "und können dann entfernt werden."
                    ),
                    "state": "pending" if scan_live else None,
                })

    # Presentation only: keep the existing physical completion verification.
    if not renames and status != "aenderbar_vorschlagen" and not release_stock.get("required") and event_document:
        from app.archive_reversal import _read_baseline
        from app.archive_rename_guidance import qualify_rename
        try:
            baseline = _read_baseline(workspace_path, cr_id)
            compact = qualify_rename(
                archive_root, rows, current_document=baseline.get("event_json"),
                replacement=work_root / staging_name / str(event_document["target_relative_path"]),
                replacement_meta=event_document, document_target=event_document["target_relative_path"],
                archive_label=archive_display_root, work_root=work_root, work_label=work_display_root,
                known_directories=baseline.get("original_directories") or [],
            )
            if compact:
                operations = compact
        except (OSError, ValueError, KeyError, RuntimeError):
            pass  # Missing/ambiguous evidence retains the detailed instructions.

    if status == "aenderbar_bestaetigt":
        from app.archive_reversal import incoming_archive_conflicts
        conflicts = incoming_archive_conflicts(archive_root, workspace_path, cr_id, rows)
        if conflicts:
            operations = [{
                "kind": "archive_conflict",
                "title": "Archivdateien mit ungeklärter Herkunft",
                "protected_paths": [archive_display_root + "/" + path for path in conflicts],
                "detail": "Diese Pfade sind geschützt. Prüfe den Archivbestand vor einer erneuten Planung.",
                "state": "blocked",
            }]

    if status == "aenderbar_vorschlagen" and preparation_required:
        phase = "prepare"
    elif (
        bool(release_stock.get("required"))
        and not bool(release_stock.get("archive_removed"))
    ):
        phase = "finder"
    elif operations:
        phase = "finder"
    else:
        phase = "verify"

    return {
        "change_request_id": cr_id,
        "event_id": str(cr.get("event_id") or ""),
        "event_name": str(cr.get("event_name") or ""),
        "status": status,
        "phase": phase,
        "preparation_required": preparation_required,
        "prepared": status != "aenderbar_vorschlagen",
        "live_refreshed": bool(scan_live),
        "preparation": {
            "helper_root": f"{work_display_root}/{helper_root}" if helper_root else "",
            "staging_root": f"{work_display_root}/{staging_name}",
            "incoming_file_count": int(description.get("incoming_file_count") or 0),
            "missing_directories": missing,
            "helper_directories": list(description.get("helper_directories") or []),
            "event_document": event_document,
            "release_file_count": int(release_stock.get("file_count") or 0),
            "release_segment_count": len(release_stock.get("segments") or []),
            "summary": (
                f"{int(description.get('incoming_file_count') or 0)} neue Dateien · "
                f"{len(missing)} fehlende Ordner · "
                f"{int(release_stock.get('file_count') or 0)} freigewordene Archivdateien"
            ),
        },
        "release_stock": {**release_stock,"folder_removal":folder_removal},
        "path_labels": {
            "archive_root": archive_display_root,
            "work_root": work_display_root,
            "staging_root": f"{work_display_root}/{staging_name}",
            "backup_root": backup_display_root,
        },
        "operations": operations,
        "target_structure": (
            {
                "root": "",
                "lines": ["Ereignis wird vollständig aus der Kamerabibliothek entfernt."],
                "deleted": True,
            }
            if delete_event
            else {
                "root": f"{archive_display_root}/{target_root}",
                "lines": _tree_lines(
                    target_root,
                    list(description.get("desired_directories") or []),
                ),
                "deleted": False,
            }
        ),
        "obsolete_directories": obsolete,
        "technical_file_count": len(rows),
    }
