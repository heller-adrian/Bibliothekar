from __future__ import annotations

"""Variabler Dreischritt-Assistent für manuelle Archivänderungen."""

from pathlib import Path, PurePosixPath
from typing import Any

from app.archive_staging import (
    BRANCHES,
    STAGING_DIRECTORY_NAME,
    describe_archive_change_staging_for_request,
)
from app.event_change_request import get_event_change_files, get_event_change_request
from app.archive_release_stock import describe_archive_release_stock


class ArchiveChangeAssistantError(RuntimeError):
    pass


def _parent_dir(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        return ""
    return PurePosixPath(raw).parent.as_posix()


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


def _minimal_roots(paths: list[str], event_root: str) -> list[str]:
    root = PurePosixPath(event_root)
    candidates = sorted(
        {PurePosixPath(value) for value in paths if value},
        key=lambda path: (len(path.parts), path.as_posix()),
    )
    result: list[PurePosixPath] = []
    for path in candidates:
        if path == root:
            continue
        if any(_path_is_under(path.as_posix(), parent.as_posix()) for parent in result):
            continue
        result.append(path)
    return [path.as_posix() for path in result]


def _basename(value: Any) -> str:
    raw = str(value or "").replace("\\", "/").strip("/")
    return PurePosixPath(raw).name if raw else ""


def build_archive_change_assistant(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise ArchiveChangeAssistantError("Änderungsauftrag wurde nicht gefunden.")

    rows = get_event_change_files(database_path, cr_id)
    description = describe_archive_change_staging_for_request(
        database_path, archive_root, cr_id
    )
    release_stock = describe_archive_release_stock(database_path, cr_id)

    status = str(cr.get("status") or "")
    preparation_required = bool(
        description.get("required") or release_stock.get("required")
    )
    target_root = str(description.get("target_root") or "")
    helper_root = str(description.get("prepared_structure_path") or "")
    missing = list(description.get("missing_directories") or [])
    obsolete = list(description.get("obsolete_directories") or [])

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

    operations: list[dict[str, Any]] = []

    new_roots = _minimal_roots(missing, target_root)
    covered_workspace_ids: set[int] = set()
    grouped_roots: dict[str, list[str]] = {}
    for root_value in new_roots:
        parent = PurePosixPath(root_value).parent.as_posix()
        grouped_roots.setdefault(parent, []).append(root_value)
        for row in workspace_rows:
            file_id = row.get("file_id")
            if file_id is not None and _path_is_under(
                str(row.get("new_path") or ""), root_value
            ):
                covered_workspace_ids.add(int(file_id))

    for parent, roots in sorted(grouped_roots.items()):
        names = [_basename(value) for value in roots]
        operations.append({
            "kind": "copy_helper_folders",
            "title": (
                f"Ordner {names[0]} ins Archiv übernehmen"
                if len(names) == 1
                else f"{len(names)} vorbereitete Ordner ins Archiv übernehmen"
            ),
            "sources": [
                f"Arbeitsbereich/{STAGING_DIRECTORY_NAME}/{value}"
                for value in roots
            ],
            "items": names,
            "target": f"Kamerabibliothek/{parent}",
            "detail": (
                f"Den vorbereiteten Ordner „{names[0]}“ vollständig übernehmen."
                if len(names) == 1
                else "Diese vorbereiteten Ordner vollständig übernehmen: "
                + ", ".join(names) + "."
            ),
        })

    remaining_workspace = [
        row for row in workspace_rows
        if row.get("file_id") is None
        or int(row["file_id"]) not in covered_workspace_ids
    ]
    grouped_workspace: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in remaining_workspace:
        source = _parent_dir(
            row.get("workspace_staging_path")
            or f"{STAGING_DIRECTORY_NAME}/{row.get('new_path') or ''}"
        )
        target = _parent_dir(row.get("new_path"))
        grouped_workspace.setdefault((source, target), []).append(row)
    for (source, target), members in sorted(grouped_workspace.items()):
        operations.append({
            "kind": "copy_files",
            "title": "Neue Dateien in einen vorhandenen Archivordner übernehmen",
            "source": f"Arbeitsbereich/{source}",
            "target": f"Kamerabibliothek/{target}",
            "items": [_basename(row.get("new_path")) for row in members],
            "file_count": len(members),
            "detail": (
                f"{len(members)} Datei" + ("" if len(members) == 1 else "en")
                + " in den vorhandenen Zielordner übernehmen."
            ),
        })

    grouped_archive: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in archive_rows:
        source = _parent_dir(row.get("old_path"))
        target = _parent_dir(row.get("new_path"))
        if source == target:
            continue
        grouped_archive.setdefault((source, target), []).append(row)
    for (source, target), members in sorted(grouped_archive.items()):
        operations.append({
            "kind": "move_archive_files",
            "title": "Dateien innerhalb der Kamerabibliothek verschieben",
            "source": f"Kamerabibliothek/{source}",
            "target": f"Kamerabibliothek/{target}",
            "items": [_basename(row.get("old_path")) for row in members],
            "file_count": len(members),
            "detail": (
                f"{len(members)} Datei" + ("" if len(members) == 1 else "en")
                + " in den angegebenen Zielordner verschieben."
            ),
        })

    if obsolete:
        operations.append({
            "kind": "remove_directories",
            "title": "Nicht mehr benötigte alte Ordner entfernen",
            "items": [_basename(value) for value in obsolete],
            "paths": [f"Kamerabibliothek/{value}" for value in obsolete],
            "detail": (
                "Diese alten Ordner müssen nach den Verschiebungen leer sein "
                "und können dann entfernt werden."
            ),
        })

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
        "preparation": {
            "helper_root": f"Arbeitsbereich/{helper_root}" if helper_root else "",
            "incoming_file_count": int(description.get("incoming_file_count") or 0),
            "missing_directories": missing,
            "helper_directories": list(description.get("helper_directories") or []),
            "release_file_count": int(release_stock.get("file_count") or 0),
            "release_segment_count": len(release_stock.get("segments") or []),
            "summary": (
                f"{int(description.get('incoming_file_count') or 0)} neue Dateien · "
                f"{len(missing)} fehlende Ordner · "
                f"{int(release_stock.get('file_count') or 0)} freigewordene Archivdateien"
            ),
        },
        "release_stock": release_stock,
        "operations": operations,
        "target_structure": {
            "root": f"Kamerabibliothek/{target_root}",
            "lines": _tree_lines(
                target_root,
                list(description.get("desired_directories") or []),
            ),
        },
        "obsolete_directories": obsolete,
        "technical_file_count": len(rows),
    }
