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
import errno
import hashlib
import os

from app.database import database_connection
from app.workspace_layout import backup_root, shared_work_root


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


def _workspace_source_path(
    workspace_path: Path,
    relative_value: Any,
) -> tuple[Path, Path]:
    """Resolve one SSD source without confusing central stock and work root."""
    rel = _safe_relative(relative_value)
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    central_root = backup_root(workspace_path).resolve(strict=False)
    work_candidate = work_root.joinpath(*rel.parts).resolve(strict=False)
    central_candidate = central_root.joinpath(*rel.parts).resolve(strict=False)

    work_exists = work_candidate.exists() or work_candidate.is_symlink()
    central_exists = central_candidate.exists() or central_candidate.is_symlink()

    # Freigewordene Archivdateien gehören definitionsgemäß zum globalen
    # Zentralbestand, auch wenn ein gleichnamiger Legacy-Pfad im Arbeitsbereich
    # existieren sollte.
    if rel.parts and rel.parts[0] == "Freigewordene Archivdateien":
        return central_candidate, central_root

    if central_exists and not work_exists:
        return central_candidate, central_root
    if work_exists and not central_exists:
        return work_candidate, work_root
    if central_exists and work_exists:
        raise ArchiveStagingError(
            "SSD-Quelle ist mehrdeutig vorhanden (Zentralbestand und "
            "Bibliotheks-Arbeitsbereich): " + rel.as_posix()
        )

    # Der anschließende Existenzcheck liefert die konkrete Fehlermeldung.
    return work_candidate, work_root


def _stage_verified_source(
    source: Path,
    staged: Path,
    *,
    expected_size: int,
    expected_sha: str,
) -> bool:
    """Create one no-overwrite helper link/copy and verify its identity."""
    if staged.exists() or staged.is_symlink():
        if staged.is_file() and not staged.is_symlink():
            src_stat = source.stat()
            dst_stat = staged.stat()
            if (
                int(src_stat.st_dev) == int(dst_stat.st_dev)
                and int(src_stat.st_ino) == int(dst_stat.st_ino)
                and _sha256_file(staged) == expected_sha
            ):
                return False
        raise ArchiveStagingError(
            "Der vorbereitete SSD-Zielpfad ist bereits belegt: " + str(staged)
        )

    staged.parent.mkdir(parents=True, exist_ok=True)
    copied = False
    try:
        try:
            os.link(source, staged, follow_symlinks=False)
        except OSError as exc:
            if exc.errno != errno.EXDEV:
                raise
            copied = True
            with source.open("rb") as src, staged.open("xb") as dst:
                while True:
                    block = src.read(1024 * 1024)
                    if not block:
                        break
                    dst.write(block)
                dst.flush()
                os.fsync(dst.fileno())

        if (
            not staged.is_file()
            or staged.is_symlink()
            or int(staged.stat().st_size) != int(expected_size)
            or _sha256_file(staged) != expected_sha
        ):
            raise ArchiveStagingError(
                "Die vorbereitete SSD-Datei konnte nicht sicher bestätigt werden: "
                + str(staged)
            )
        if not copied:
            src_stat = source.stat()
            dst_stat = staged.stat()
            if (
                int(src_stat.st_dev) != int(dst_stat.st_dev)
                or int(src_stat.st_ino) != int(dst_stat.st_ino)
            ):
                raise ArchiveStagingError(
                    "Der SSD-Hardlink konnte nicht sicher bestätigt werden: "
                    + str(staged)
                )
        return True
    except Exception:
        try:
            if staged.exists() and staged.is_file() and not staged.is_symlink():
                staged.unlink()
        except OSError:
            pass
        raise


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


def _remove_ignored_helper_metadata(directory: Path) -> int:
    """Remove only harmless OS metadata from app-owned helper directories."""
    removed = 0
    try:
        entries = list(directory.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if entry.is_symlink() or not entry.is_file():
            continue
        if entry.name != ".DS_Store" and not entry.name.startswith("._"):
            continue
        try:
            entry.unlink()
            removed += 1
        except OSError:
            pass
    return removed


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
    layout_state = preview.get("folder_layout")
    configured_layout_paths: list[PurePosixPath] = []
    if isinstance(layout_state, dict) and bool(layout_state.get("structure_enabled")):
        from app.event_layout import layout_paths
        configured_layout_paths = [
            PurePosixPath(value)
            for value in layout_paths(layout_state.get("layout") or {})
        ]
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
        if configured_layout_paths:
            parent = rel.parent
            matched = next(
                (
                    layout_path
                    for layout_path in sorted(
                        configured_layout_paths,
                        key=lambda value: len(value.parts),
                        reverse=True,
                    )
                    if len(parent.parts) >= len(layout_path.parts)
                    and tuple(parent.parts[-len(layout_path.parts):]) == layout_path.parts
                ),
                None,
            )
            container = (
                PurePosixPath(*parent.parts[:-len(matched.parts)])
                if matched is not None and matched.parts
                else parent
            )
            directories.add(container)
            for layout_path in configured_layout_paths:
                directories.add(container / layout_path)
            continue

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
        item
        for item in [
            *(plan.get("families_with_plans") or []),
            *(plan.get("assets_with_plans") or []),
        ]
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
        released_asset_sources = {
            (
                int(row["family_id"]) if row["family_id"] is not None else None,
                str(row["current_relative_path"] or ""),
            )
            for row in connection.execute(
                """SELECT family_id,current_relative_path
                   FROM released_archive_assets
                   ORDER BY id"""
            ).fetchall()
        }
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
    if cr.get("folder_layout_json") is not None:
        try:
            stored_layout = json.loads(str(cr.get("folder_layout_json") or "{}"))
        except Exception as exc:
            raise ArchiveStagingError("Die gespeicherte Archiv-Ordnerstruktur ist beschädigt.") from exc
        preview["folder_layout"] = {
            "structure_enabled": bool(cr.get("folder_structure_enabled")),
            "input_path": str(cr.get("folder_input_path") or ""),
            "layout": stored_layout,
        }
        preview["create_subfolders"] = bool(cr.get("folder_structure_enabled"))
    plan = {
        "families_with_plans": [
            {**row, "source_root_kind": str(row.get("source_root_kind") or "camera_archive")}
            for row in camera
        ],
        "assets_with_plans": [
            {
                **row,
                "source_root_kind": (
                    "shared_workspace"
                    if (
                        (
                            int(row["family_id"])
                            if row.get("family_id") is not None
                            else None
                        ),
                        str(row.get("old_path") or ""),
                    ) in released_asset_sources
                    else "camera_archive"
                ),
                "workspace_original_path": (
                    str(row.get("old_path") or "")
                    if (
                        (
                            int(row["family_id"])
                            if row.get("family_id") is not None
                            else None
                        ),
                        str(row.get("old_path") or ""),
                    ) in released_asset_sources
                    else ""
                ),
            }
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


def refresh_staged_event_document_after_verified_paths(
    database_path: Path,
    workspace_path: Path,
    cr_id: str,
    previous_spec: dict[str, Any],
) -> dict[str, Any]:
    """Refresh only an app-owned staged event.json after verified path aliases.

    A camera original may acquire a Finder/Windows collision suffix while the
    user performs the read-only archive work. The portable event.json must then
    describe that *actual* verified path. We may update the SSD helper, but
    never the archive itself. An existing helper is replaced only when it still
    matches the exact previously prepared size and SHA-256.
    """
    from app.archive_change_document import projected_archive_event_document_spec

    new_spec = projected_archive_event_document_spec(database_path, cr_id)
    if new_spec is None:
        return {"updated": False, "spec": None}

    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_base = (work_root / STAGING_DIRECTORY_NAME).resolve(strict=False)
    target_rel = _safe_relative(str(new_spec["target_relative_path"]))
    document_path = (
        staging_base.joinpath(*target_rel.parts).resolve(strict=False)
    )
    if not _inside(document_path, staging_base):
        raise ArchiveStagingError("Der aktualisierte event.json-Pfad ist unsicher.")

    previous_sha = str(previous_spec.get("sha256") or "")
    previous_size = int(previous_spec.get("size_bytes") or 0)
    if document_path.exists() or document_path.is_symlink():
        if (
            not document_path.is_file()
            or document_path.is_symlink()
            or int(document_path.stat().st_size) != previous_size
            or not previous_sha
            or _sha256_file(document_path) != previous_sha
        ):
            raise ArchiveStagingError(
                "Die vorbereitete event.json wurde außerhalb des aktuellen "
                "Archivauftrags verändert und deshalb nicht automatisch ersetzt."
            )

    document_path.parent.mkdir(parents=True, exist_ok=True)
    encoded = str(new_spec["payload"]).encode("utf-8")
    tmp = document_path.with_name("event.json.tmp.refresh")
    try:
        with tmp.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, document_path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass

    return {
        "updated": True,
        "spec": {key: value for key, value in new_spec.items() if key != "payload"},
        "staged_event_document": (
            PurePosixPath(STAGING_DIRECTORY_NAME) / target_rel
        ).as_posix(),
    }


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

    # 0.28.3: Frühere manuelle Archiv-Strukturaufgaben hinterließen ihre
    # verifizierte event.json unter Später zuordnen. Vor einer neuen
    # Archivänderung räumen wir ausschließlich solche nachweislich abgeschlossenen
    # und SHA-256-identischen Alt-Hilfen desselben Ereignisses weg.
    from app.event_structure_changes import cleanup_completed_archived_structure_helpers
    cleanup_completed_archived_structure_helpers(
        database_path,
        workspace_path,
        event_id=str(cr["event_id"]),
    )
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

        incoming_items = [
            item
            for item in [
                *(plan.get("families_with_plans") or []),
                *(plan.get("assets_with_plans") or []),
            ]
            if str(item.get("source_root_kind") or "camera_archive") == "shared_workspace"
            and str(item.get("action") or "") == "move"
            and str(item.get("new_path") or "").strip()
        ]
        staged_asset_count = 0
        for item in incoming_items:
            file_id = (
                int(item["file_id"])
                if item.get("file_id") is not None
                else None
            )
            source_rel = _safe_relative(
                item.get("workspace_original_path")
                or item.get("old_path")
            )
            target_rel = _safe_relative(item.get("new_path"))
            source, source_root = _workspace_source_path(
                workspace_path,
                source_rel,
            )
            staged_rel = PurePosixPath(STAGING_DIRECTORY_NAME) / target_rel
            staged = work_root.joinpath(*staged_rel.parts).resolve(strict=False)

            if not _inside(source, source_root) or not _inside(staged, staging_base):
                raise ArchiveStagingError(
                    "Eine SSD-Zuführung verlässt den zulässigen Bestand."
                )
            if not source.exists() or not source.is_file() or source.is_symlink():
                raise ArchiveStagingError(
                    "SSD-Quelldatei fehlt oder ist unsicher: " + str(source)
                )
            expected_size = int(item.get("expected_size_bytes") or 0)
            expected_sha = str(item.get("expected_sha256") or "").strip()
            if int(source.stat().st_size) != expected_size:
                raise ArchiveStagingError(
                    "SSD-Quelldatei hat eine abweichende Größe: " + str(source)
                )
            if not expected_sha or _sha256_file(source) != expected_sha:
                raise ArchiveStagingError(
                    "SSD-Quelldatei hat eine abweichende SHA-256-Summe: "
                    + str(source)
                )

            created = _stage_verified_source(
                source,
                staged,
                expected_size=expected_size,
                expected_sha=expected_sha,
            )
            if created:
                staged_paths.append(staged)
            if file_id is not None:
                staging_by_file_id[file_id] = staged_rel.as_posix()
            else:
                staged_asset_count += 1

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
            "staged_file_count": len(staging_by_file_id) + staged_asset_count,
            "staged_camera_file_count": len(staging_by_file_id),
            "staged_asset_count": staged_asset_count,
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

    central_root = backup_root(workspace_path).resolve(strict=False)
    release_root = (
        central_root / "Freigewordene Archivdateien"
    ).resolve(strict=False)

    with database_connection(database_path) as connection:
        cr = connection.execute(
            "SELECT prepared_structure_path FROM event_change_requests WHERE id=?",
            (cr_id,),
        ).fetchone()
        camera_rows = [
            {
                **dict(row),
                "review_kind": "camera",
                "released_asset_id": None,
                "staging_relative_path": str(
                    row["workspace_staging_path"] or ""
                ),
            }
            for row in connection.execute(
                """SELECT file_id,old_path,workspace_original_path,
                          workspace_staging_path,expected_size_bytes,
                          expected_sha256
                   FROM event_change_file_reviews
                   WHERE change_request_id=?
                     AND source_root_kind='shared_workspace'
                   ORDER BY id""",
                (cr_id,),
            ).fetchall()
        ]
        asset_rows = [
            {
                **dict(row),
                "review_kind": "asset",
                "workspace_original_path": str(row["old_path"] or ""),
                "staging_relative_path": (
                    (
                        PurePosixPath(STAGING_DIRECTORY_NAME)
                        / _safe_relative(str(row["new_path"] or ""))
                    ).as_posix()
                    if str(row["new_path"] or "").strip()
                    else ""
                ),
            }
            for row in connection.execute(
                """SELECT review.id,review.family_id,review.old_path,
                          review.new_path,review.expected_size_bytes,
                          review.expected_sha256,
                          released.id AS released_asset_id
                   FROM event_change_asset_reviews review
                   JOIN released_archive_assets released
                     ON released.family_id=review.family_id
                    AND released.current_relative_path=review.old_path
                   WHERE review.change_request_id=?
                     AND review.action='move'
                   ORDER BY review.id""",
                (cr_id,),
            ).fetchall()
        ]

    rows = camera_rows + asset_rows
    removed_released_asset_ids: list[int] = []

    def remove_known(
        relative_value: str,
        root: Path,
        expected_size: int,
        expected_sha: str,
        label: str,
    ) -> tuple[bool, Path | None]:
        if not relative_value:
            return False, None
        try:
            rel = _safe_relative(relative_value)
            path = root.joinpath(*rel.parts).resolve(strict=False)
            if not _inside(path, root):
                raise ArchiveStagingError("Pfad verlässt den zulässigen SSD-Bestand.")
            if not path.exists():
                return False, path
            if not path.is_file() or path.is_symlink():
                raise ArchiveStagingError("Pfad ist keine reguläre Datei.")
            if int(path.stat().st_size) != int(expected_size):
                raise ArchiveStagingError("Dateigröße stimmt nicht.")
            if not expected_sha or _sha256_file(path) != expected_sha:
                raise ArchiveStagingError("SHA-256 stimmt nicht.")
            path.unlink()
            return True, path
        except Exception as exc:
            warnings.append(f"{label}: {relative_value}: {exc}")
            return False, None

    def cleanup_empty_source_parents(path: Path, root: Path) -> None:
        nonlocal removed_empty_source_directories
        stop_root = root
        if _inside(path, release_root):
            stop_root = release_root
        current = path.parent
        while _inside(current, root) and current != stop_root:
            try:
                current.rmdir()
                removed_empty_source_directories += 1
            except OSError:
                break
            current = current.parent

    for row in rows:
        expected_size = int(row.get("expected_size_bytes") or 0)
        expected_sha = str(row.get("expected_sha256") or "")
        staging_rel = str(row.get("staging_relative_path") or "")
        original_rel = str(
            row.get("workspace_original_path")
            or row.get("old_path")
            or ""
        )

        removed_helper, _ = remove_known(
            staging_rel,
            work_root,
            expected_size,
            expected_sha,
            "Staging konnte nicht entfernt werden",
        )
        if removed_helper:
            removed_staged += 1

        if remove_originals and original_rel != staging_rel:
            try:
                original_path, source_root = _workspace_source_path(
                    workspace_path,
                    original_rel,
                )
            except Exception as exc:
                warnings.append(
                    "SSD-Original konnte nicht aufgelöst werden: "
                    + original_rel
                    + ": "
                    + str(exc)
                )
                continue
            try:
                rel = original_path.relative_to(source_root).as_posix()
            except ValueError:
                warnings.append(
                    "SSD-Original verlässt den zulässigen Bestand: "
                    + original_rel
                )
                continue
            removed_original, removed_path = remove_known(
                rel,
                source_root,
                expected_size,
                expected_sha,
                "SSD-Original konnte nicht freigegeben werden",
            )
            if removed_original and removed_path is not None:
                removed_originals += 1
                cleanup_empty_source_parents(removed_path, source_root)
                if row.get("released_asset_id") is not None:
                    removed_released_asset_ids.append(
                        int(row["released_asset_id"])
                    )

    if removed_released_asset_ids:
        with database_connection(database_path) as connection:
            placeholders = ",".join(
                "?" for _ in removed_released_asset_ids
            )
            connection.execute(
                f"""DELETE FROM released_archive_assets
                    WHERE id IN ({placeholders})""",
                tuple(sorted(set(removed_released_asset_ids))),
            )
            connection.commit()

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
                    _remove_ignored_helper_metadata(directory)
                    try:
                        directory.rmdir()
                    except OSError:
                        pass
                current = prepared_root.parent
                while _inside(current, staging_base) and current != work_root and current != staging_base:
                    _remove_ignored_helper_metadata(current)
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
        release_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        warnings.append(
            "Stammordner „Freigewordene Archivdateien“ konnte nicht erhalten werden: "
            + str(exc)
        )

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
            _remove_ignored_helper_metadata(directory)
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
