from __future__ import annotations

"""SSD-Hilfsstruktur fuer manuelle Aenderungen archivierter Ereignisse.

Die Kamerabibliothek wird von diesem Modul niemals beschrieben. Komplexe
Archiv-Aenderungen erhalten unter Arbeitsbereich/Später zuordnen eine
vorbereitete Zielhuelle. Neue freie SSD-Dateien werden dort als Hardlinks in
ihrer kuenftigen Struktur bereitgestellt; das Original bleibt bis zur
erfolgreichen Archivpruefung unangetastet.
"""

from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import os

from app.database import database_connection
from app.workspace_layout import shared_work_root


STAGING_DIRECTORY_NAME = "Später zuordnen"
BRANCHES = ("Alle", "Sortiert", "Export")


class ArchiveStagingError(RuntimeError):
    pass


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_relative(value: Any) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(raw)
    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArchiveStagingError("Unsicherer relativer Arbeitsbereichspfad: " + raw)
    return path


def _safe_component(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if (
        not text
        or text in {".", ".."}
        or "/" in text
        or "\\" in text
        or "\x00" in text
    ):
        raise ArchiveStagingError(f"Ungültiger {label}: {text}")
    return text


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _suffix_after_event_root(value: Any) -> tuple[str, ...]:
    parts = PurePosixPath(str(value or "").replace("\\", "/").strip("/")).parts
    return tuple(parts[2:]) if len(parts) >= 2 else tuple(parts)


def _preview_child_folders(preview: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for segment in list(preview.get("subevents") or preview.get("child_segments") or []):
        folder = str(segment.get("folder_name") or segment.get("folder") or "").strip()
        if not folder:
            start = str(segment.get("start_datetime") or segment.get("start_time") or "")
            end = str(segment.get("end_datetime") or segment.get("end_time") or "")
            start_time = start[11:16] if "T" in start else start[:5]
            end_time = end[11:16] if "T" in end else end[:5]
            name = str(segment.get("name") or "Unterereignis").strip()
            if start_time and end_time:
                folder = (
                    f"{start_time.replace(':','-')} - "
                    f"{end_time.replace(':','-')} - {name}"
                )
        if folder:
            result.append(_safe_component(folder, "Unterereignisordner"))
    child_folder = str(preview.get("child_folder") or "").strip()
    if child_folder and child_folder not in result:
        result.append(_safe_component(child_folder, "Unterereignisordner"))
    return result


def _target_root(preview: dict[str, Any]) -> PurePosixPath:
    year = _safe_component(str(preview.get("start_date") or "")[:4], "Jahr")
    parent = _safe_component(preview.get("parent_folder"), "Ereignisordner")
    return PurePosixPath(year, parent)


def _desired_directory_plan(
    preview: dict[str, Any],
    plan: dict[str, Any],
    *,
    moves_only: bool = False,
) -> set[PurePosixPath]:
    """Canonical SOLL directories implied by the final target files."""
    root = _target_root(preview)
    directories: set[PurePosixPath] = {root}
    items = [
        *(plan.get("families_with_plans") or []),
        *(plan.get("assets_with_plans") or []),
    ]
    for item in items:
        action = str(item.get("action") or "")
        if action in {"delete", "unresolved"}:
            continue
        if moves_only and action != "move":
            continue
        value = str(item.get("new_path") or "").strip()
        if not value:
            continue
        rel = _safe_relative(value)
        if len(rel.parts) < 2 or tuple(rel.parts[:2]) != tuple(root.parts):
            raise ArchiveStagingError(
                "Ein SOLL-Pfad liegt außerhalb des neuen Ereignisordners."
            )
        branch_index = next(
            (index for index, part in enumerate(rel.parts) if part in BRANCHES),
            None,
        )
        if branch_index is None:
            directories.add(rel.parent)
            continue
        container = PurePosixPath(*rel.parts[:branch_index])
        directories.add(container)
        for branch in BRANCHES:
            directories.add(container / branch)
    return directories


def _current_event_root(database_path: Path, event_id: str) -> PurePosixPath:
    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT start_datetime,folder_name FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
    if event is None:
        raise ArchiveStagingError("Archiviertes Ereignis wurde nicht gefunden.")
    return PurePosixPath(
        _safe_component(str(event["start_datetime"] or "")[:4], "Archivjahr"),
        _safe_component(str(event["folder_name"] or ""), "Archiv-Ereignisordner"),
    )


def _existing_suffixes(
    archive_root: Path,
    current_root: PurePosixPath,
) -> set[tuple[str, ...]]:
    root = archive_root.expanduser().resolve(strict=False)
    event_root = root.joinpath(*current_root.parts).resolve(strict=False)
    if not _inside(event_root, root) or not event_root.exists() or not event_root.is_dir():
        raise ArchiveStagingError(
            "Der aktuelle Ereignisordner wurde in der Kamerabibliothek nicht gefunden."
        )
    result: set[tuple[str, ...]] = {()}
    for current, directories, _ in os.walk(event_root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe: list[str] = []
        for name in directories:
            child = current_path / name
            if child.is_symlink():
                raise ArchiveStagingError(
                    "Symlink im archivierten Ereignis ist für eine Strukturänderung nicht zulässig: "
                    + str(child)
                )
            if child.is_dir():
                safe.append(name)
                result.add(tuple(child.relative_to(event_root).parts))
        directories[:] = safe
    return result


def _obsolete_directories_from_plan(
    database_path: Path,
    event_id: str,
    preview: dict[str, Any],
    plan: dict[str, Any],
    *,
    delete_event: bool = False,
) -> list[str]:
    """Old archive directories made obsolete by this concrete move plan."""
    current_root = _current_event_root(database_path, event_id)
    items = [
        *[
            item for item in (plan.get("families_with_plans") or [])
            if str(item.get("source_root_kind") or "camera_archive") != "shared_workspace"
        ],
        *(plan.get("assets_with_plans") or []),
    ]
    released_family_ids = {
        int(item["family_id"])
        for item in (plan.get("families_with_plans") or [])
        if str(item.get("action") or "") == "delete"
        and item.get("family_id") is not None
    }
    affected_items = [
        item for item in items
        if str(item.get("old_path") or "").strip()
        and (
            str(item.get("action") or "") in {"move", "delete"}
            or (
                str(item.get("action") or "") == "unresolved"
                and item.get("family_id") is not None
                and int(item["family_id"]) in released_family_ids
            )
        )
    ]
    if not affected_items:
        return []
    if delete_event:
        return [current_root.as_posix()]
    try:
        target_root = _target_root(preview)
    except ArchiveStagingError:
        return []
    if current_root != target_root:
        return [current_root.as_posix()]

    desired_directories = _desired_directory_plan(preview, plan)
    affected_containers: set[PurePosixPath] = set()
    affected_branches: dict[PurePosixPath, set[str]] = {}
    for item in affected_items:
        old_rel = _safe_relative(item.get("old_path"))
        if tuple(old_rel.parts[:2]) != tuple(current_root.parts):
            continue
        branch_index = next(
            (index for index, part in enumerate(old_rel.parts) if part in BRANCHES),
            None,
        )
        container = (
            PurePosixPath(*old_rel.parts[:branch_index])
            if branch_index is not None
            else old_rel.parent
        )
        affected_containers.add(container)
        if branch_index is not None:
            affected_branches.setdefault(container, set()).add(
                str(old_rel.parts[branch_index])
            )

    obsolete: set[PurePosixPath] = set()
    for container in affected_containers:
        if container != current_root and container not in desired_directories:
            obsolete.add(container)
            continue
        # Sobald ein alter Container strukturell berührt wird, müssen auch
        # leere Schwesterzweige berücksichtigt werden. Sonst blieben z.B.
        # Sortiert/Export nach dem Wechsel auf Tagesordner unsichtbar zurück.
        for branch in BRANCHES:
            branch_path = container / branch
            if branch_path not in desired_directories:
                obsolete.add(branch_path)
    return sorted(path.as_posix() for path in obsolete)


def _path_under(path: PurePosixPath, root: PurePosixPath) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def required_obsolete_directories_for_request(
    database_path: Path,
    cr_id: str,
) -> list[str]:
    cr, preview, plan = _request_preview_and_plan(database_path, cr_id)
    try:
        return _obsolete_directories_from_plan(
            database_path,
            str(cr["event_id"]),
            preview,
            plan,
            delete_event=bool(cr.get("delete_event") or 0),
        )
    except ArchiveStagingError:
        return []


def describe_archive_change_staging(
    database_path: Path,
    archive_root: Path,
    event_id: str,
    preview: dict[str, Any],
    plan: dict[str, Any],
    *,
    delete_event: bool = False,
) -> dict[str, Any]:
    """Compute Später zuordnen as SOLL minus the real IST archive structure."""
    current_root = _current_event_root(database_path, event_id)
    if delete_event:
        return {
            "required": False,
            "target_root": current_root.as_posix(),
            "current_root": current_root.as_posix(),
            "desired_directories": [],
            "missing_directories": [],
            "helper_directories": [],
            "obsolete_directories": [current_root.as_posix()],
            "incoming_file_count": 0,
            "prepared_structure_path": "",
        }
    target_root = _target_root(preview)
    # Für das SOLL zählt die tatsächlich bereits vorhandene Zielstruktur.
    # Bei einer Umbenennung darf die alte Ereignisstruktur nicht so behandelt
    # werden, als läge sie schon im neuen Zielordner.
    try:
        existing_suffixes = _existing_suffixes(archive_root, target_root)
    except ArchiveStagingError:
        existing_suffixes = set()
    desired = _desired_directory_plan(preview, plan)
    touched = _desired_directory_plan(preview, plan, moves_only=True)

    missing: set[PurePosixPath] = set()
    for directory in touched:
        if tuple(directory.parts[2:]) not in existing_suffixes:
            missing.add(directory)

    incoming = [
        item for item in (plan.get("families_with_plans") or [])
        if str(item.get("source_root_kind") or "camera_archive") == "shared_workspace"
        and str(item.get("action") or "") == "move"
        and str(item.get("new_path") or "").strip()
    ]
    helper_directories = set(missing)
    for item in incoming:
        helper_directories.add(_safe_relative(item["new_path"]).parent)
    helper_directories = {
        directory for directory in helper_directories
        if tuple(directory.parts[:2]) == tuple(target_root.parts)
    }

    obsolete = _obsolete_directories_from_plan(
        database_path, event_id, preview, plan, delete_event=delete_event
    )

    required = bool(helper_directories or incoming)

    return {
        "required": required,
        "target_root": target_root.as_posix(),
        "current_root": current_root.as_posix(),
        "desired_directories": sorted(path.as_posix() for path in desired),
        "missing_directories": sorted(path.as_posix() for path in missing),
        "helper_directories": sorted(path.as_posix() for path in helper_directories),
        "obsolete_directories": list(obsolete),
        "incoming_file_count": len(incoming),
        "prepared_structure_path": (
            (PurePosixPath(STAGING_DIRECTORY_NAME) / target_root).as_posix()
            if required else ""
        ),
    }


def _request_preview_and_plan(
    database_path: Path,
    cr_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    import json
    with database_connection(database_path) as connection:
        cr_row = connection.execute(
            "SELECT * FROM event_change_requests WHERE id=?",
            (cr_id,),
        ).fetchone()
        if cr_row is None:
            raise ArchiveStagingError("Änderungsauftrag wurde nicht gefunden.")
        camera = [dict(row) for row in connection.execute(
            "SELECT * FROM event_change_file_reviews WHERE change_request_id=? ORDER BY id",
            (cr_id,),
        ).fetchall()]
        assets = [dict(row) for row in connection.execute(
            "SELECT * FROM event_change_asset_reviews WHERE change_request_id=? ORDER BY id",
            (cr_id,),
        ).fetchall()]
    cr = dict(cr_row)
    try:
        subevents = json.loads(cr.get("child_segments_json") or "[]")
    except Exception:
        subevents = []
    preview = {
        "event_kind": str(cr.get("event_kind") or "event"),
        "parent_folder": str(cr.get("parent_folder") or ""),
        "child_folder": cr.get("child_folder"),
        "preserve_day_folders": bool(cr.get("preserve_day_folders")),
        "start_date": str(cr.get("start_date") or ""),
        "end_date": str(cr.get("end_date") or ""),
        "start_time": cr.get("start_time"),
        "end_time": cr.get("end_time"),
        "subevents": subevents,
    }
    plan = {
        "families_with_plans": [
            {**row, "source_root_kind": str(row.get("source_root_kind") or "camera_archive")}
            for row in camera
        ],
        "assets_with_plans": [
            {**row, "source_root_kind": "camera_archive"}
            for row in assets
        ],
    }
    return cr, preview, plan


def describe_archive_change_staging_for_request(
    database_path: Path,
    archive_root: Path,
    cr_id: str,
) -> dict[str, Any]:
    cr, preview, plan = _request_preview_and_plan(database_path, cr_id)
    description = describe_archive_change_staging(
        database_path,
        archive_root,
        str(cr["event_id"]),
        preview,
        plan,
        delete_event=bool(cr.get("delete_event") or 0),
    )
    from app.archive_change_document import projected_archive_event_document_spec
    event_document = projected_archive_event_document_spec(database_path, cr_id)
    if event_document is not None:
        description = {
            **description,
            "required": True,
            "event_document": {
                key: value
                for key, value in event_document.items()
                if key != "payload"
            },
        }
    else:
        description = {**description, "event_document": None}
    return description


def required_event_document_for_request(
    database_path: Path,
    cr_id: str,
) -> dict[str, Any] | None:
    from app.archive_change_document import projected_archive_event_document_spec
    spec = projected_archive_event_document_spec(database_path, cr_id)
    if spec is None:
        return None
    return {key: value for key, value in spec.items() if key != "payload"}


def required_target_directories_for_request(
    database_path: Path,
    cr_id: str,
) -> list[str]:
    """Directories whose existence is part of this concrete event change.

    Reassignment destinations outside the edited event are separate workflows
    and must not be validated against the source event's SOLL structure.
    """
    cr, preview, plan = _request_preview_and_plan(database_path, cr_id)
    if bool(cr.get("delete_event") or 0):
        return []
    try:
        root = _target_root(preview)
    except ArchiveStagingError:
        # Legacy/minimal requests without a complete structural target retain
        # their historical file-only verification semantics.
        return []

    touched: set[PurePosixPath] = set()
    items = [
        *(plan.get("families_with_plans") or []),
        *(plan.get("assets_with_plans") or []),
    ]
    for item in items:
        if str(item.get("action") or "") != "move":
            continue
        value = str(item.get("new_path") or "").strip()
        if not value:
            continue
        try:
            rel = _safe_relative(value)
        except ArchiveStagingError:
            continue
        if len(rel.parts) < 2 or tuple(rel.parts[:2]) != tuple(root.parts):
            # E.g. a family released from the edited event and reassigned into
            # a different archived event.
            continue
        touched.add(root)
        branch_index = next(
            (index for index, part in enumerate(rel.parts) if part in BRANCHES),
            None,
        )
        if branch_index is None:
            touched.add(rel.parent)
            continue
        container = PurePosixPath(*rel.parts[:branch_index])
        touched.add(container)
        for branch in BRANCHES:
            touched.add(container / branch)

    return sorted(path.as_posix() for path in touched)


def prepare_archive_change_staging_for_request(
    database_path: Path,
    workspace_path: Path,
    archive_root: Path,
    cr_id: str,
) -> dict[str, Any]:
    """Materialize only the missing helper structure and incoming SSD hardlinks."""
    cr, preview, plan = _request_preview_and_plan(database_path, cr_id)
    description = describe_archive_change_staging(
        database_path,
        archive_root,
        str(cr["event_id"]),
        preview,
        plan,
        delete_event=bool(cr.get("delete_event") or 0),
    )
    from app.archive_change_document import projected_archive_event_document_spec
    event_document = projected_archive_event_document_spec(database_path, cr_id)
    description = {
        **description,
        "required": bool(description.get("required") or event_document is not None),
        "event_document": (
            {key: value for key, value in event_document.items() if key != "payload"}
            if event_document is not None else None
        ),
    }
    if not description["required"]:
        return {
            **description,
            "prepared_structure_path": "",
            "staged_file_count": 0,
            "staging_by_file_id": {},
            "created_directories": [],
        }

    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_base = (work_root / STAGING_DIRECTORY_NAME).resolve(strict=False)
    if not _inside(staging_base, work_root):
        raise ArchiveStagingError("Der Archiv-Hilfsbereich verlässt den Arbeitsbereich.")

    directories = {
        _safe_relative(value)
        for value in description.get("helper_directories") or []
    }
    event_relative_root = _safe_relative(description["target_root"])
    prepared_rel = PurePosixPath(STAGING_DIRECTORY_NAME) / event_relative_root
    prepared_root = work_root.joinpath(*prepared_rel.parts).resolve(strict=False)
    if not _inside(prepared_root, staging_base):
        raise ArchiveStagingError("Die vorbereitete Archivstruktur ist unsicher.")

    created_dirs: list[Path] = []
    staged_paths: list[Path] = []
    staging_by_file_id: dict[int, str] = {}

    try:
        staging_base.mkdir(parents=True, exist_ok=True)
        for relative in sorted(directories, key=lambda value: (len(value.parts), value.as_posix())):
            target = staging_base.joinpath(*relative.parts).resolve(strict=False)
            if not _inside(target, staging_base):
                raise ArchiveStagingError("Ein vorbereiteter Ordner verlässt den Hilfsbereich.")
            if target.exists() and not target.is_dir():
                raise ArchiveStagingError("Ein vorbereiteter Strukturpfad ist bereits als Datei belegt: " + str(target))
            if not target.exists():
                target.mkdir(parents=True)
                created_dirs.append(target)

        for item in plan.get("families_with_plans") or []:
            if str(item.get("source_root_kind") or "camera_archive") != "shared_workspace":
                continue
            file_id = int(item["file_id"])
            source_rel = _safe_relative(item.get("workspace_original_path") or item.get("old_path"))
            target_rel = _safe_relative(item.get("new_path"))
            source = work_root.joinpath(*source_rel.parts).resolve(strict=False)
            staged_rel = PurePosixPath(STAGING_DIRECTORY_NAME) / target_rel
            staged = work_root.joinpath(*staged_rel.parts).resolve(strict=False)

            if not _inside(source, work_root) or not _inside(staged, staging_base):
                raise ArchiveStagingError("Eine SSD-Zuführung verlässt den Arbeitsbereich.")
            if not source.exists() or not source.is_file() or source.is_symlink():
                raise ArchiveStagingError("SSD-Quelldatei fehlt oder ist unsicher: " + str(source))
            expected_size = int(item.get("expected_size_bytes") or 0)
            expected_sha = str(item.get("expected_sha256") or "").strip()
            if int(source.stat().st_size) != expected_size:
                raise ArchiveStagingError("SSD-Quelldatei hat eine abweichende Größe: " + str(source))
            if not expected_sha or _sha256_file(source) != expected_sha:
                raise ArchiveStagingError("SSD-Quelldatei hat eine abweichende SHA-256-Summe: " + str(source))

            staged.parent.mkdir(parents=True, exist_ok=True)
            if staged.exists() or staged.is_symlink():
                if staged.is_file():
                    src_stat = source.stat()
                    dst_stat = staged.stat()
                    if (
                        int(src_stat.st_dev) == int(dst_stat.st_dev)
                        and int(src_stat.st_ino) == int(dst_stat.st_ino)
                    ):
                        staging_by_file_id[file_id] = staged_rel.as_posix()
                        continue
                raise ArchiveStagingError(
                    "Der vorbereitete SSD-Zielpfad ist bereits belegt: " + str(staged)
                )
            os.link(source, staged, follow_symlinks=False)
            staged_paths.append(staged)
            src_stat = source.stat()
            dst_stat = staged.stat()
            if (
                int(src_stat.st_dev) != int(dst_stat.st_dev)
                or int(src_stat.st_ino) != int(dst_stat.st_ino)
                or _sha256_file(staged) != expected_sha
            ):
                raise ArchiveStagingError("Der SSD-Hardlink konnte nicht sicher bestätigt werden: " + str(staged))
            staging_by_file_id[file_id] = staged_rel.as_posix()

        staged_event_document = ""
        if event_document is not None:
            document_rel = (
                PurePosixPath(STAGING_DIRECTORY_NAME)
                / PurePosixPath(str(event_document["target_relative_path"]))
            )
            document_path = work_root.joinpath(*document_rel.parts).resolve(strict=False)
            if not _inside(document_path, staging_base):
                raise ArchiveStagingError("Der vorbereitete event.json-Pfad ist unsicher.")
            document_path.parent.mkdir(parents=True, exist_ok=True)
            encoded = str(event_document["payload"]).encode("utf-8")
            if document_path.exists() or document_path.is_symlink():
                if (
                    not document_path.is_file()
                    or document_path.is_symlink()
                    or int(document_path.stat().st_size) != int(event_document["size_bytes"])
                    or _sha256_file(document_path) != str(event_document["sha256"])
                ):
                    raise ArchiveStagingError(
                        "Die vorbereitete event.json ist bereits mit abweichendem Inhalt vorhanden."
                    )
            else:
                tmp = document_path.with_name("event.json.tmp")
                tmp.write_bytes(encoded)
                os.replace(tmp, document_path)
                staged_paths.append(document_path)
            staged_event_document = document_rel.as_posix()

        return {
            **description,
            "prepared_structure_path": prepared_rel.as_posix(),
            "staged_file_count": len(staging_by_file_id),
            "staging_by_file_id": staging_by_file_id,
            "staged_event_document": staged_event_document,
            "created_directories": [
                path.relative_to(work_root).as_posix() for path in created_dirs
            ],
        }
    except Exception:
        for staged in reversed(staged_paths):
            try:
                staged.unlink(missing_ok=True)
            except OSError:
                pass
        for directory in sorted(created_dirs, key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise


def cleanup_archive_change_staging(
    database_path: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    remove_originals: bool,
    event_document_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove only known helper links and, after verification, their SSD originals."""
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_base = (work_root / STAGING_DIRECTORY_NAME).resolve(strict=False)
    removed_staged = 0
    removed_originals = 0
    removed_empty_source_directories = 0
    warnings: list[str] = []

    with database_connection(database_path) as connection:
        cr = connection.execute(
            "SELECT prepared_structure_path FROM event_change_requests WHERE id=?",
            (cr_id,),
        ).fetchone()
        rows = connection.execute(
            """SELECT file_id,old_path,workspace_original_path,workspace_staging_path,
                      expected_size_bytes,expected_sha256
               FROM event_change_file_reviews
               WHERE change_request_id=? AND source_root_kind='shared_workspace'
               ORDER BY id""",
            (cr_id,),
        ).fetchall()

    def remove_known(relative_value: str, expected_size: int, expected_sha: str, label: str) -> bool:
        if not relative_value:
            return False
        try:
            rel = _safe_relative(relative_value)
            path = work_root.joinpath(*rel.parts).resolve(strict=False)
            if not _inside(path, work_root):
                raise ArchiveStagingError("Pfad verlässt den Arbeitsbereich.")
            if not path.exists():
                return False
            if not path.is_file() or path.is_symlink():
                raise ArchiveStagingError("Pfad ist keine reguläre Datei.")
            if int(path.stat().st_size) != int(expected_size):
                raise ArchiveStagingError("Dateigröße stimmt nicht.")
            if not expected_sha or _sha256_file(path) != expected_sha:
                raise ArchiveStagingError("SHA-256 stimmt nicht.")
            path.unlink()
            return True
        except Exception as exc:
            warnings.append(f"{label}: {relative_value}: {exc}")
            return False

    for row in rows:
        expected_size = int(row["expected_size_bytes"] or 0)
        expected_sha = str(row["expected_sha256"] or "")
        staging_rel = str(row["workspace_staging_path"] or "")
        original_rel = str(row["workspace_original_path"] or row["old_path"] or "")
        if remove_known(staging_rel, expected_size, expected_sha, "Staging konnte nicht entfernt werden"):
            removed_staged += 1
        if remove_originals and original_rel != staging_rel:
            if remove_known(original_rel, expected_size, expected_sha, "SSD-Original konnte nicht freigegeben werden"):
                removed_originals += 1
                try:
                    original_path = work_root.joinpath(*_safe_relative(original_rel).parts).resolve(strict=False)
                    current = original_path.parent
                    while _inside(current, work_root) and current != work_root and current.parent != work_root:
                        try:
                            current.rmdir()
                            removed_empty_source_directories += 1
                        except OSError:
                            break
                        current = current.parent
                except Exception as exc:
                    warnings.append(
                        "Leerer SSD-Quellordner konnte nicht vollständig aufgeräumt werden: "
                        + str(exc)
                    )

    try:
        if event_document_spec is None:
            from app.archive_change_document import projected_archive_event_document_spec
            event_document = projected_archive_event_document_spec(database_path, cr_id)
        else:
            event_document = event_document_spec
        if event_document is not None:
            document_rel = (
                PurePosixPath(STAGING_DIRECTORY_NAME)
                / PurePosixPath(str(event_document["target_relative_path"]))
            )
            document_path = work_root.joinpath(*document_rel.parts).resolve(strict=False)
            if document_path.exists():
                if (
                    document_path.is_file()
                    and not document_path.is_symlink()
                    and int(document_path.stat().st_size) == int(event_document["size_bytes"])
                    and _sha256_file(document_path) == str(event_document["sha256"])
                ):
                    document_path.unlink()
                else:
                    warnings.append(
                        "Vorbereitete event.json wurde wegen abweichendem Inhalt nicht entfernt: "
                        + document_rel.as_posix()
                    )
    except Exception as exc:
        warnings.append("Vorbereitete event.json konnte nicht aufgeräumt werden: " + str(exc))

    prepared = str(cr["prepared_structure_path"] or "") if cr is not None else ""
    if prepared:
        try:
            prepared_rel = _safe_relative(prepared)
            prepared_root = work_root.joinpath(*prepared_rel.parts).resolve(strict=False)
            if _inside(prepared_root, staging_base) and prepared_root.exists() and prepared_root.is_dir():
                directories = [p for p in prepared_root.rglob("*") if p.is_dir()]
                directories.append(prepared_root)
                for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
                current = prepared_root.parent
                while _inside(current, staging_base) and current != work_root and current != staging_base:
                    try:
                        current.rmdir()
                    except OSError:
                        break
                    current = current.parent
        except Exception as exc:
            warnings.append("Leere vorbereitete Struktur konnte nicht vollständig entfernt werden: " + str(exc))

    reversal_root = staging_base / "Rückänderung" / cr_id
    if reversal_root.exists() and reversal_root.is_dir():
        # Nur bekannte Rückänderungs-Hilfsdateien werden entfernt. Der komplette
        # Baum gehört ausschließlich zu diesem Change Request.
        import shutil
        try:
            shutil.rmtree(reversal_root)
            parent = reversal_root.parent
            if parent != staging_base:
                try:
                    parent.rmdir()
                except OSError:
                    pass
        except OSError as exc:
            warnings.append("Rückänderungs-Hilfsbereich konnte nicht vollständig entfernt werden: " + str(exc))

    try:
        staging_base.mkdir(parents=True, exist_ok=True)
        empty_candidates = [
            path for path in staging_base.rglob("*")
            if path.is_dir() and not path.is_symlink()
        ]
        for directory in sorted(
            empty_candidates,
            key=lambda path: len(path.parts),
            reverse=True,
        ):
            try:
                directory.rmdir()
                removed_empty_source_directories += 1
            except OSError:
                pass
    except OSError as exc:
        warnings.append("Stammordner „Später zuordnen“ konnte nicht erhalten werden: " + str(exc))

    return {
        "removed_staging_file_count": removed_staged,
        "removed_original_file_count": removed_originals,
        "removed_empty_source_directory_count": removed_empty_source_directories,
        "warnings": warnings,
    }
