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

    status = str(cr.get("status") or "")
    preparation_required = bool(description.get("required"))
    target_root = str(description.get("target_root") or "")
    helper_root = str(description.get("prepared_structure_path") or "")
    missing = list(description.get("missing_directories") or [])

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

    # Wenn Struktur fehlt, ist ein Merge des vorbereiteten Ereignis-Inhalts die
    # effizienteste Finder-Handlung. Die Detailkarte nennt trotzdem exakt, was fehlt.
    if missing:
        operations.append({
            "kind": "merge_helper",
            "title": "Vorbereitete Struktur in das Ereignis übernehmen",
            "source": f"Arbeitsbereich/{STAGING_DIRECTORY_NAME}/{target_root}",
            "target": f"Kamerabibliothek/{target_root}",
            "file_count": len(workspace_rows),
            "missing_directories": missing,
            "detail": (
                f"{len(missing)} fehlende Ordner ergänzen"
                + (f" und {len(workspace_rows)} neue Dateien übernehmen" if workspace_rows else "")
                + "."
            ),
        })
    elif workspace_rows:
        grouped_workspace: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in workspace_rows:
            source = _parent_dir(
                row.get("workspace_staging_path")
                or f"{STAGING_DIRECTORY_NAME}/{row.get('new_path') or ''}"
            )
            target = _parent_dir(row.get("new_path"))
            grouped_workspace.setdefault((source, target), []).append(row)
        for (source, target), members in sorted(grouped_workspace.items()):
            operations.append({
                "kind": "copy_files",
                "title": "Neue Dateien in den vorhandenen Archivordner übernehmen",
                "source": f"Arbeitsbereich/{source}",
                "target": f"Kamerabibliothek/{target}",
                "file_count": len(members),
                "detail": f"{len(members)} Datei" + ("" if len(members) == 1 else "en") + " übernehmen.",
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
            "file_count": len(members),
            "detail": f"{len(members)} Datei" + ("" if len(members) == 1 else "en") + " verschieben.",
        })

    if status == "aenderbar_vorschlagen" and preparation_required:
        phase = "prepare"
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
            "summary": (
                f"{int(description.get('incoming_file_count') or 0)} neue Dateien · "
                f"{len(missing)} fehlende Ordner"
            ),
        },
        "operations": operations,
        "target_structure": {
            "root": f"Kamerabibliothek/{target_root}",
            "lines": _tree_lines(
                target_root,
                list(description.get("desired_directories") or []),
            ),
        },
        "technical_file_count": len(rows),
    }
