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


def _needs_staging(
    database_path: Path,
    event_id: str,
    preview: dict[str, Any],
    plan: dict[str, Any],
) -> bool:
    """Pure event-folder renames need no helper shell; real structure changes do."""
    incoming = any(
        str(item.get("source_root_kind") or "camera_archive") == "shared_workspace"
        for item in plan.get("families_with_plans") or []
    )
    if incoming:
        return True

    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT start_datetime,preserve_day_folders FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
        children = connection.execute(
            "SELECT folder_name FROM events WHERE parent_event_id=? ORDER BY id",
            (event_id,),
        ).fetchall()
    if event is None:
        raise ArchiveStagingError("Archiviertes Ereignis wurde nicht gefunden.")

    if bool(event["preserve_day_folders"]) != bool(preview.get("preserve_day_folders")):
        return True

    old_children = sorted(str(row["folder_name"] or "") for row in children)
    new_children = sorted(_preview_child_folders(preview))
    if old_children != new_children:
        return True

    old_year = str(event["start_datetime"] or "")[:4]
    new_year = str(preview.get("start_date") or "")[:4]
    if old_year and new_year and old_year != new_year:
        return True

    for item in plan.get("families_with_plans") or []:
        if str(item.get("action") or "") != "move":
            continue
        if str(item.get("source_root_kind") or "camera_archive") != "camera_archive":
            return True
        old_path = str(item.get("old_path") or "")
        new_path = str(item.get("new_path") or "")
        old_parts = PurePosixPath(old_path).parts
        new_parts = PurePosixPath(new_path).parts
        if len(old_parts) < 2 or len(new_parts) < 2:
            return True
        if old_parts[0] != new_parts[0]:
            return True
        if _suffix_after_event_root(old_path) != _suffix_after_event_root(new_path):
            return True

    return False


def _directory_plan(
    preview: dict[str, Any],
    plan: dict[str, Any],
) -> set[PurePosixPath]:
    year = _safe_component(str(preview.get("start_date") or "")[:4], "Jahr")
    parent = _safe_component(preview.get("parent_folder"), "Ereignisordner")
    root = PurePosixPath(year, parent)
    directories: set[PurePosixPath] = {root}
    populated_children: set[str] = set()

    all_items = [
        *(plan.get("families_with_plans") or []),
        *(plan.get("assets_with_plans") or []),
    ]
    for item in all_items:
        action = str(item.get("action") or "")
        new_path = str(item.get("new_path") or "").strip()
        if action in {"delete", "unresolved"} or not new_path:
            continue
        rel = _safe_relative(new_path)
        parent_dir = rel.parent
        directories.add(parent_dir)
        if parent_dir.name in BRANCHES:
            container = parent_dir.parent
            for branch in BRANCHES:
                directories.add(container / branch)
        parts = rel.parts
        if len(parts) >= 3:
            first_inside_event = parts[2]
            if first_inside_event not in BRANCHES and not (
                len(first_inside_event) == 10
                and first_inside_event[4] == "-"
                and first_inside_event[7] == "-"
            ):
                populated_children.add(first_inside_event)

    for child in _preview_child_folders(preview):
        if child in populated_children:
            continue
        child_root = root / child
        directories.add(child_root)
        for branch in BRANCHES:
            directories.add(child_root / branch)

    return directories


def prepare_archive_change_staging(
    database_path: Path,
    workspace_path: Path,
    cr_id: str,
    event_id: str,
    preview: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Prepare the manual helper shell and incoming SSD hardlinks."""
    if not _needs_staging(database_path, event_id, preview, plan):
        return {
            "prepared_structure_path": "",
            "staged_file_count": 0,
            "staging_by_file_id": {},
            "created_directories": [],
        }

    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_base = (work_root / STAGING_DIRECTORY_NAME).resolve(strict=False)
    if not _inside(staging_base, work_root):
        raise ArchiveStagingError("Der Archiv-Hilfsbereich verlässt den Arbeitsbereich.")

    directories = _directory_plan(preview, plan)
    event_relative_root = min(directories, key=lambda value: len(value.parts))
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

        return {
            "prepared_structure_path": prepared_rel.as_posix(),
            "staged_file_count": len(staging_by_file_id),
            "staging_by_file_id": staging_by_file_id,
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
) -> dict[str, Any]:
    """Remove only known helper links and, after verification, their SSD originals."""
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    staging_base = (work_root / STAGING_DIRECTORY_NAME).resolve(strict=False)
    removed_staged = 0
    removed_originals = 0
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
                while _inside(current, staging_base) and current != work_root:
                    try:
                        current.rmdir()
                    except OSError:
                        break
                    if current == staging_base:
                        break
                    current = current.parent
        except Exception as exc:
            warnings.append("Leere vorbereitete Struktur konnte nicht vollständig entfernt werden: " + str(exc))

    return {
        "removed_staging_file_count": removed_staged,
        "removed_original_file_count": removed_originals,
        "warnings": warnings,
    }
