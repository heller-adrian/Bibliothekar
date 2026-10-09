from __future__ import annotations

"""Read-only-guided rollback for manual archive changes.

The app never writes to the camera archive.  It preserves only the original
folder skeleton and event.json below Arbeitsbereich/Später zuordnen.  Original
camera files are either found by SHA-256 inside the archive or, after a release
step, recovered from the already verified SSD return copy.
"""

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import shutil

from app.database import database_connection
from app.workspace_layout import backup_root, shared_work_root


REVERSAL_DIRECTORY_NAME = "Rückänderung"
REVERSAL_VERSION = 1


class ArchiveReversalError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: Any) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(raw)
    if not path.parts or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveReversalError("Unsicherer relativer Pfad: " + raw)
    return path


def _safe_archive_path(archive_root: Path, value: Any) -> Path:
    root = archive_root.expanduser().resolve(strict=False)
    rel = _safe_relative(value)
    target = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArchiveReversalError("Archivpfad verlässt die Kamerabibliothek.") from exc
    return target


def _work_root(workspace_path: Path) -> Path:
    return shared_work_root(workspace_path).resolve(strict=False)


def _central_root(workspace_path: Path) -> Path:
    return backup_root(workspace_path).resolve(strict=False)


def _base(workspace_path: Path, cr_id: str) -> Path:
    root = _work_root(workspace_path)
    value = (root / "Später zuordnen" / REVERSAL_DIRECTORY_NAME / cr_id).resolve(strict=False)
    try:
        value.relative_to(root)
    except ValueError as exc:
        raise ArchiveReversalError("Rückänderungsbereich verlässt den Arbeitsbereich.") from exc
    return value


def _manifest_path(workspace_path: Path, cr_id: str) -> Path:
    return _base(workspace_path, cr_id) / "baseline.json"


def _request_path(workspace_path: Path, cr_id: str) -> Path:
    return _base(workspace_path, cr_id) / "request.json"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ArchiveReversalError("Rückänderungsdaten sind nicht lesbar: " + str(path)) from exc


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _request_context(database_path: Path, cr_id: str) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    with database_connection(database_path) as connection:
        cr_row = connection.execute("SELECT * FROM event_change_requests WHERE id=?", (cr_id,)).fetchone()
        if cr_row is None:
            raise ArchiveReversalError("Änderungsauftrag wurde nicht gefunden.")
        cr = dict(cr_row)
        event_row = connection.execute(
            "SELECT * FROM events WHERE id=? AND job_id=?",
            (str(cr["event_id"]), str(cr["job_id"])),
        ).fetchone()
        if event_row is None:
            raise ArchiveReversalError("Das ursprüngliche Ereignis wurde nicht gefunden.")
        event = dict(event_row)
        camera = [
            {**dict(row), "review_kind": "camera"}
            for row in connection.execute(
                "SELECT * FROM event_change_file_reviews WHERE change_request_id=? ORDER BY id",
                (cr_id,),
            ).fetchall()
        ]
        assets = []
        for row in connection.execute(
            """SELECT review.*,
                      EXISTS (
                          SELECT 1
                          FROM released_archive_assets released
                          WHERE released.family_id=review.family_id
                            AND released.current_relative_path=review.old_path
                            AND released.size_bytes=review.expected_size_bytes
                            AND released.sha256=review.expected_sha256
                      ) AS from_released_stock
               FROM event_change_asset_reviews review
               WHERE review.change_request_id=?
                 AND review.action<>'advisory'
               ORDER BY review.id""",
            (cr_id,),
        ).fetchall():
            item = dict(row)
            item["review_kind"] = "asset"
            item["source_root_kind"] = (
                "shared_workspace"
                if bool(item.pop("from_released_stock", 0))
                else "camera_archive"
            )
            item["file_id"] = None
            assets.append(item)
    return cr, event, camera + assets


def _is_advisory_row(row: dict[str, Any]) -> bool:
    return bool(
        str(row.get("review_kind") or "") == "asset"
        and row.get("family_id") is None
        and str(row.get("asset_kind") or "other") != "export"
        and str(row.get("action") or "") == "keep"
        and str(row.get("old_path") or "") == str(row.get("new_path") or "")
    )


def prepare_reversal_baseline(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    manifest_path = _manifest_path(workspace_path, cr_id)
    if manifest_path.is_file():
        return _read_json(manifest_path)

    cr, event, request_rows = _request_context(database_path, cr_id)
    original_year = str(event.get("start_datetime") or cr.get("start_date") or "")[:4]
    original_folder = str(event.get("folder_name") or "").strip()
    if not original_year or not original_folder:
        raise ArchiveReversalError("Der ursprüngliche Ereignisordner ist nicht eindeutig.")
    original_root = PurePosixPath(original_year, original_folder).as_posix()
    original_abs = _safe_archive_path(archive_root, original_root)
    if not original_abs.is_dir() or original_abs.is_symlink():
        raise ArchiveReversalError("Der ursprüngliche Ereignisordner ist nicht sicher lesbar.")

    root_abs = archive_root.expanduser().resolve(strict=False)
    directories: list[str] = [original_root]
    original_file_paths: list[str] = []
    for current, names, files in os.walk(original_abs, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_names = []
        for name in names:
            child = current_path / name
            if child.is_symlink():
                raise ArchiveReversalError("Symlink im ursprünglichen Ereignisordner: " + str(child))
            safe_names.append(name)
            directories.append(child.resolve(strict=False).relative_to(root_abs).as_posix())
        names[:] = safe_names
        for name in files:
            child = current_path / name
            if child.is_symlink() or not child.is_file():
                raise ArchiveReversalError(
                    "Unsicherer Dateieintrag im ursprünglichen Ereignisordner: " + str(child)
                )
            original_file_paths.append(
                child.resolve(strict=False).relative_to(root_abs).as_posix()
            )

    base = _base(workspace_path, cr_id)
    original_stock = base / "Original"
    original_stock.mkdir(parents=True, exist_ok=True)
    event_json_rel = PurePosixPath(original_root, "event.json").as_posix()
    event_json = _safe_archive_path(archive_root, event_json_rel)
    event_json_meta = None
    if event_json.exists():
        if not event_json.is_file() or event_json.is_symlink():
            raise ArchiveReversalError("Die ursprüngliche event.json ist keine reguläre Datei.")
        backup = original_stock.joinpath(*PurePosixPath(event_json_rel).parts)
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(event_json, backup)
        event_json_meta = {
            "relative_path": event_json_rel,
            "backup_relative_path": backup.relative_to(_work_root(workspace_path)).as_posix(),
            "size_bytes": int(event_json.stat().st_size),
            "sha256": _sha256_file(event_json),
        }

    original_assets: list[dict[str, Any]] = []
    for row in request_rows:
        if str(row.get("review_kind") or "") != "asset" or _is_advisory_row(row):
            continue
        if str(row.get("source_root_kind") or "camera_archive") != "camera_archive":
            continue
        old_rel = str(row.get("old_path") or "").strip()
        if not old_rel:
            continue
        source = _safe_archive_path(archive_root, old_rel)
        expected_size = int(row.get("expected_size_bytes") or 0)
        expected_sha = str(row.get("expected_sha256") or "").strip()
        if not _matches(source, expected_size, expected_sha):
            continue
        backup = original_stock.joinpath(*_safe_relative(old_rel).parts)
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copyfile(source, backup)
        original_assets.append({
            "relative_path": old_rel,
            "backup_relative_path": backup.relative_to(_work_root(workspace_path)).as_posix(),
            "size_bytes": expected_size,
            "sha256": expected_sha,
        })

    target_year = str(cr.get("start_date") or original_year)[:4] or original_year
    target_root = PurePosixPath(target_year, str(cr.get("parent_folder") or original_folder)).as_posix()
    manifest = {
        "version": REVERSAL_VERSION,
        "change_request_id": cr_id,
        "event_id": str(cr["event_id"]),
        "original_root": original_root,
        "target_root": target_root,
        "original_directories": sorted(set(directories)),
        "original_file_paths": sorted(set(original_file_paths)),
        "original_assets": original_assets,
        "event_json": event_json_meta,
        "delete_event": bool(cr.get("delete_event") or 0),
        "created_at": _now(),
    }
    _write_json(manifest_path, manifest)
    return manifest


def reversal_active(workspace_path: Path, cr_id: str) -> bool:
    return _request_path(workspace_path, cr_id).is_file()


def begin_archive_reversal(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    manifest = prepare_reversal_baseline(database_path, archive_root, workspace_path, cr_id)
    request_path = _request_path(workspace_path, cr_id)
    if not request_path.exists():
        _write_json(request_path, {
            "version": REVERSAL_VERSION,
            "change_request_id": cr_id,
            "status": "requested",
            "created_at": _now(),
        })
    result = build_archive_reversal_assistant(database_path, archive_root, workspace_path, cr_id)
    result["baseline"] = manifest
    return result


def _matches(path: Path, size: int, sha: str) -> bool:
    return bool(
        path.is_file()
        and not path.is_symlink()
        and (not size or int(path.stat().st_size) == int(size))
        and sha
        and _sha256_file(path) == sha
    )


def _candidate_roots(manifest: dict[str, Any], archive_root: Path) -> list[Path]:
    roots = []
    for value in [manifest.get("original_root"), manifest.get("target_root")]:
        if not value:
            continue
        path = _safe_archive_path(archive_root, value)
        if path not in roots:
            roots.append(path)
    return roots


def _find_archive_location(
    archive_root: Path,
    manifest: dict[str, Any],
    old_path: str,
    new_path: str,
    size: int,
    sha: str,
) -> str | None:
    for rel in [old_path, new_path]:
        if not rel:
            continue
        path = _safe_archive_path(archive_root, rel)
        if _matches(path, size, sha):
            return _safe_relative(rel).as_posix()

    root_abs = archive_root.expanduser().resolve(strict=False)
    for root in _candidate_roots(manifest, archive_root):
        if not root.is_dir():
            continue
        for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            dirs[:] = [name for name in dirs if not (current_path / name).is_symlink()]
            for name in files:
                candidate = current_path / name
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                if size and int(candidate.stat().st_size) != size:
                    continue
                if _sha256_file(candidate) == sha:
                    return candidate.resolve(strict=False).relative_to(root_abs).as_posix()
    return None


def prepare_archive_reversal(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    archive_display_root: str = "Kamerabibliothek",
    work_display_root: str = "Arbeitsbereich",
) -> dict[str, Any]:
    manifest = prepare_reversal_baseline(database_path, archive_root, workspace_path, cr_id)
    request_path = _request_path(workspace_path, cr_id)
    if not request_path.exists():
        begin_archive_reversal(database_path, archive_root, workspace_path, cr_id)

    cr, _event, rows = _request_context(database_path, cr_id)
    base = _base(workspace_path, cr_id)
    restore_root = base / "Wiederherstellung"
    work_root = _work_root(workspace_path)
    central_root = _central_root(workspace_path)
    prepared_targets: list[tuple[Path, int, str]] = []
    for rel in manifest.get("original_directories") or []:
        restore_root.joinpath(*_safe_relative(rel).parts).mkdir(parents=True, exist_ok=True)

    for asset in manifest.get("original_assets") or []:
        source = work_root.joinpath(
            *_safe_relative(asset["backup_relative_path"]).parts
        )
        target = restore_root.joinpath(
            *_safe_relative(asset["relative_path"]).parts
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                os.link(source, target, follow_symlinks=False)
            except OSError:
                shutil.copyfile(source, target)
        prepared_targets.append((
            target,
            int(asset.get("size_bytes") or 0),
            str(asset.get("sha256") or ""),
        ))

    event_json = manifest.get("event_json")
    if event_json:
        source = work_root.joinpath(*_safe_relative(event_json["backup_relative_path"]).parts)
        target = restore_root.joinpath(*_safe_relative(event_json["relative_path"]).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                os.link(source, target, follow_symlinks=False)
            except OSError:
                shutil.copyfile(source, target)
        prepared_targets.append((
            target,
            int(event_json.get("size_bytes") or 0),
            str(event_json.get("sha256") or ""),
        ))

    missing_sources: list[str] = []
    for row in rows:
        if _is_advisory_row(row):
            continue
        if str(row.get("source_root_kind") or "camera_archive") != "camera_archive":
            continue
        old_path = str(row.get("old_path") or "").strip()
        if not old_path:
            continue
        size = int(row.get("expected_size_bytes") or 0)
        sha = str(row.get("expected_sha256") or "").strip()
        new_path = str(row.get("new_path") or "").strip()
        found = _find_archive_location(archive_root, manifest, old_path, new_path, size, sha)
        if found:
            continue
        staged = restore_root.joinpath(*_safe_relative(old_path).parts)
        if _matches(staged, size, sha):
            continue
        release_rel = str(row.get("workspace_release_path") or "").strip()
        if not release_rel:
            missing_sources.append(old_path)
            continue
        source = central_root.joinpath(*_safe_relative(release_rel).parts).resolve(strict=False)
        if not _matches(source, size, sha):
            missing_sources.append(old_path)
            continue
        target = restore_root.joinpath(*_safe_relative(old_path).parts).resolve(strict=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            try:
                os.link(source, target, follow_symlinks=False)
            except OSError:
                shutil.copyfile(source, target)
        if not _matches(target, size, sha):
            raise ArchiveReversalError("Rückkehrkopie konnte nicht sicher vorbereitet werden: " + old_path)
        prepared_targets.append((target, size, sha))

    if missing_sources:
        raise ArchiveReversalError(
            "Der ursprüngliche Bestand ist für folgende Archivdateien weder im Archiv noch im geprüften SSD-Bestand vorhanden: "
            + ", ".join(missing_sources[:5])
        )

    if not restore_root.is_dir():
        raise ArchiveReversalError(
            "Der Wiederherstellungsbereich konnte nicht materialisiert werden."
        )
    for target, size, sha in prepared_targets:
        if not sha or not _matches(target, size, sha):
            raise ArchiveReversalError(
                "Eine vorbereitete Rückänderungsdatei ist nicht vollständig verifiziert: "
                + str(target)
            )

    request = _read_json(request_path)
    request["status"] = "prepared"
    request["prepared_at"] = _now()
    _write_json(request_path, request)
    return build_archive_reversal_assistant(
        database_path,
        archive_root,
        workspace_path,
        cr_id,
        scan_live=True,
        archive_display_root=archive_display_root,
        work_display_root=work_display_root,
    )


def _planned_extra_directories(database_path: Path, cr_id: str, manifest: dict[str, Any]) -> list[str]:
    try:
        from app.archive_staging import describe_archive_change_staging_for_request
        # archive_root is required only for real existing suffixes; caller computes
        # final list separately where needed.
    except Exception:
        return []
    return []


def _extra_archive_files(
    archive_root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    original = {str(value) for value in (manifest.get("original_file_paths") or [])}
    extras: set[str] = set()
    root_abs = archive_root.expanduser().resolve(strict=False)
    for root in _candidate_roots(manifest, archive_root):
        if not root.is_dir():
            continue
        for current, directories, files in os.walk(root, topdown=True, followlinks=False):
            current_path = Path(current)
            directories[:] = [
                name for name in directories
                if not (current_path / name).is_symlink()
            ]
            for name in files:
                candidate = current_path / name
                if candidate.is_symlink() or not candidate.is_file():
                    continue
                rel = candidate.resolve(strict=False).relative_to(root_abs).as_posix()
                if rel not in original:
                    extras.add(rel)
    return sorted(extras)


def _extra_archive_directories(
    archive_root: Path,
    manifest: dict[str, Any],
) -> list[str]:
    original_root = str(manifest.get("original_root") or "")
    if not original_root:
        return []
    root = _safe_archive_path(archive_root, original_root)
    if not root.is_dir():
        return []
    root_abs = archive_root.expanduser().resolve(strict=False)
    original = {str(value) for value in (manifest.get("original_directories") or [])}
    extras: list[str] = []
    for current, directories, _files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_names = []
        for name in directories:
            child = current_path / name
            if child.is_symlink():
                continue
            safe_names.append(name)
            relative = child.resolve(strict=False).relative_to(root_abs).as_posix()
            if relative not in original:
                extras.append(relative)
        directories[:] = safe_names
    return sorted(set(extras), key=lambda value: (len(PurePosixPath(value).parts), value), reverse=True)


def _reversal_state(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    archive_display_root: str = "Kamerabibliothek",
    work_display_root: str = "Arbeitsbereich",
) -> dict[str, Any]:
    manifest = _read_json(_manifest_path(workspace_path, cr_id))
    _cr, _event, rows = _request_context(database_path, cr_id)
    work_root = _work_root(workspace_path)
    central_root = _central_root(workspace_path)
    restore_root = _base(workspace_path, cr_id) / "Wiederherstellung"

    operations: list[dict[str, Any]] = []
    move_groups: dict[tuple[str, str], list[str]] = {}
    restore_items: list[str] = []
    remove_files: list[str] = []

    for row in rows:
        if _is_advisory_row(row):
            continue
        old_path = str(row.get("old_path") or "").strip()
        new_path = str(row.get("new_path") or "").strip()
        size = int(row.get("expected_size_bytes") or 0)
        sha = str(row.get("expected_sha256") or "").strip()
        source_kind = str(row.get("source_root_kind") or "camera_archive")
        if source_kind == "shared_workspace":
            if new_path and _matches(_safe_archive_path(archive_root, new_path), size, sha):
                remove_files.append(new_path)
            continue
        if not old_path:
            continue
        old_abs = _safe_archive_path(archive_root, old_path)
        if _matches(old_abs, size, sha):
            continue
        found = _find_archive_location(archive_root, manifest, old_path, new_path, size, sha)
        if found:
            key = (PurePosixPath(found).parent.as_posix(), PurePosixPath(old_path).parent.as_posix())
            move_groups.setdefault(key, []).append(PurePosixPath(found).name)
            continue
        staged = restore_root.joinpath(*_safe_relative(old_path).parts)
        if _matches(staged, size, sha):
            restore_items.append(old_path)
        else:
            restore_items.append(old_path)

    event_json = manifest.get("event_json")
    if event_json:
        target = _safe_archive_path(archive_root, event_json["relative_path"])
        if not _matches(target, int(event_json["size_bytes"]), str(event_json["sha256"])):
            restore_items.append(str(event_json["relative_path"]))
    else:
        generated = PurePosixPath(str(manifest.get("target_root") or ""), "event.json").as_posix()
        generated_path = _safe_archive_path(archive_root, generated)
        if generated_path.exists():
            remove_files.append(generated)

    missing_dirs = [
        rel for rel in manifest.get("original_directories") or []
        if not _safe_archive_path(archive_root, rel).is_dir()
    ]

    if restore_items or missing_dirs:
        operations.append({
            "kind": "restore_from_ssd",
            "title": "Ursprünglichen Bestand aus Später zuordnen zurückkopieren",
            "source": work_display_root + "/" + (
                restore_root.joinpath(*_safe_relative(str(manifest["original_root"])).parts)
                .relative_to(work_root).as_posix()
            ),
            "target": archive_display_root + "/" + PurePosixPath(str(manifest["original_root"])).parent.as_posix(),
            "items": sorted(set([PurePosixPath(value).name for value in restore_items] + [PurePosixPath(value).name for value in missing_dirs])),
            "detail": "Fehlende ursprüngliche Ordner und Dateien aus dem vorbereiteten Rückänderungsbestand zurück in die alte Archivstruktur übernehmen.",
            "state": "pending",
        })

    for (source, target), names in sorted(move_groups.items()):
        operations.append({
            "kind": "move_back",
            "title": "Archivdateien an ihren ursprünglichen Ort zurückverschieben",
            "source": archive_display_root + "/" + source,
            "target": archive_display_root + "/" + target,
            "items": sorted(names),
            "detail": "Diese Dateien sind noch im Archiv vorhanden und müssen nur an ihren ursprünglichen Ort zurück.",
            "state": "pending",
        })

    if remove_files:
        operations.append({
            "kind": "remove_new_files",
            "title": "Nur durch die verworfene Änderung hinzugekommene Archivdateien entfernen",
            "paths": [archive_display_root + "/" + value for value in sorted(set(remove_files))],
            "items": [PurePosixPath(value).name for value in sorted(set(remove_files))],
            "detail": "Diese Dateien gehörten nicht zum ursprünglichen Archivzustand. Die SSD-Originale bleiben erhalten.",
            "state": "pending",
        })

    target_root = str(manifest.get("target_root") or "")
    original_root = str(manifest.get("original_root") or "")
    remove_dirs: list[str] = _extra_archive_directories(archive_root, manifest)
    if target_root and target_root != original_root:
        target_abs = _safe_archive_path(archive_root, target_root)
        if target_abs.exists():
            remove_dirs.append(target_root)
    remove_dirs = sorted(
        set(remove_dirs),
        key=lambda value: (len(PurePosixPath(value).parts), value),
        reverse=True,
    )
    if remove_dirs:
        operations.append({
            "kind": "remove_new_directories",
            "title": "Nicht zum Ursprungszustand gehörende neue Ordner entfernen",
            "paths": [archive_display_root + "/" + value for value in remove_dirs],
            "items": [PurePosixPath(value).name for value in remove_dirs],
            "detail": "Nach der Rücksortierung diese durch die verworfene Änderung entstandenen Ordner entfernen.",
            "state": "pending",
        })

    restore_event_root = restore_root.joinpath(
        *_safe_relative(str(manifest["original_root"])).parts
    )
    return {
        "manifest": manifest,
        "operations": operations,
        "complete": len(operations) == 0,
        "original_stock_path": work_display_root + "/" + (
            restore_event_root.relative_to(work_root).as_posix()
        ),
    }


def build_archive_reversal_assistant(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    scan_live: bool = False,
    archive_display_root: str = "Kamerabibliothek",
    work_display_root: str = "Arbeitsbereich",
) -> dict[str, Any]:
    request_path = _request_path(workspace_path, cr_id)
    if not request_path.is_file():
        return {"active": False, "change_request_id": cr_id}
    request = _read_json(request_path)
    manifest = _read_json(_manifest_path(workspace_path, cr_id))
    if str(request.get("status") or "") == "requested":
        return {
            "active": True,
            "change_request_id": cr_id,
            "phase": "prepare",
            "status": "requested",
            "original_stock_path": work_display_root + "/" + (
                (
                    _base(workspace_path, cr_id)
                    / "Wiederherstellung"
                    / Path(str(manifest["original_root"]))
                )
                .relative_to(_work_root(workspace_path)).as_posix()
            ),
            "original_root": manifest["original_root"],
            "operations": [],
            "path_labels": {
                "archive_root": archive_display_root,
                "work_root": work_display_root,
            },
            "live_refreshed": False,
        }
    state = _reversal_state(
        database_path,
        archive_root,
        workspace_path,
        cr_id,
        archive_display_root=archive_display_root,
        work_display_root=work_display_root,
    )
    return {
        "active": True,
        "change_request_id": cr_id,
        "phase": "finder" if not state["complete"] else "verify",
        "status": str(request.get("status") or "prepared"),
        "original_stock_path": state["original_stock_path"],
        "original_root": manifest["original_root"],
        "operations": state["operations"],
        "path_labels": {
            "archive_root": archive_display_root,
            "work_root": work_display_root,
        },
        "live_refreshed": bool(scan_live),
    }


def verify_archive_reversal(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    manifest = _read_json(_manifest_path(workspace_path, cr_id))
    _cr, _event, rows = _request_context(database_path, cr_id)
    problems: list[dict[str, Any]] = []

    for rel in manifest.get("original_directories") or []:
        if not _safe_archive_path(archive_root, rel).is_dir():
            problems.append({"kind": "directory", "path": rel, "message": "Ursprünglicher Ordner fehlt."})

    for row in rows:
        if _is_advisory_row(row):
            continue
        old_path = str(row.get("old_path") or "").strip()
        new_path = str(row.get("new_path") or "").strip()
        size = int(row.get("expected_size_bytes") or 0)
        sha = str(row.get("expected_sha256") or "").strip()
        source_kind = str(row.get("source_root_kind") or "camera_archive")
        if source_kind == "shared_workspace":
            if new_path and _matches(_safe_archive_path(archive_root, new_path), size, sha):
                problems.append({"kind": "new_file", "path": new_path, "message": "Durch die verworfene Änderung hinzugefügte Archivdatei ist noch vorhanden."})
            continue
        if old_path and not _matches(_safe_archive_path(archive_root, old_path), size, sha):
            problems.append({"kind": "file", "path": old_path, "message": "Ursprüngliche Datei fehlt oder stimmt nicht nach SHA-256."})

    event_json = manifest.get("event_json")
    if event_json:
        if not _matches(
            _safe_archive_path(archive_root, event_json["relative_path"]),
            int(event_json["size_bytes"]),
            str(event_json["sha256"]),
        ):
            problems.append({"kind": "event_json", "path": event_json["relative_path"], "message": "Ursprüngliche event.json ist noch nicht wiederhergestellt."})
    else:
        generated = PurePosixPath(str(manifest.get("target_root") or ""), "event.json").as_posix()
        if _safe_archive_path(archive_root, generated).exists():
            problems.append({"kind": "event_json", "path": generated, "message": "Neu erzeugte event.json ist noch vorhanden."})

    target_root = str(manifest.get("target_root") or "")
    original_root = str(manifest.get("original_root") or "")
    for extra_dir in _extra_archive_directories(archive_root, manifest):
        problems.append({
            "kind": "directory",
            "path": extra_dir,
            "message": "Dieser Ordner gehörte nicht zum ursprünglichen Archivzustand.",
        })
    if target_root and target_root != original_root and _safe_archive_path(archive_root, target_root).exists():
        problems.append({"kind": "directory", "path": target_root, "message": "Neu erzeugter Ereignisordner ist noch vorhanden."})

    return {
        "complete": not problems,
        "problem_count": len(problems),
        "problems": problems,
        "original_root": original_root,
    }


def original_archive_state_intact(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> bool:
    try:
        result = verify_archive_reversal(database_path, archive_root, workspace_path, cr_id)
        return bool(result["complete"])
    except Exception:
        return False


def cleanup_archive_reversal(workspace_path: Path, cr_id: str) -> None:
    base = _base(workspace_path, cr_id)
    if base.exists():
        shutil.rmtree(base)
    parent = base.parent
    try:
        parent.rmdir()
    except OSError:
        pass
    ( _work_root(workspace_path) / "Später zuordnen").mkdir(parents=True, exist_ok=True)


def finish_archive_reversal(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    verification = verify_archive_reversal(database_path, archive_root, workspace_path, cr_id)
    if not verification["complete"]:
        raise ArchiveReversalError(
            f"Rückänderung ist noch nicht vollständig: {verification['problem_count']} Punkt(e) offen."
        )

    from app.archive_staging import cleanup_archive_change_staging
    from app.archive_release_stock import cleanup_archive_release_stock
    from app.archive_release_stock import ArchiveReleaseStockError
    # After the original archive is verified, clear any SSD return copies
    # first. Do not mark reversal successful while copies remain on the SSD.
    try:
        cleanup_archive_release_stock(
            database_path, workspace_path, cr_id, archive_root=archive_root
        )
    except ArchiveReleaseStockError as error:
        raise ArchiveReversalError(
            "Rückänderung noch nicht abgeschlossen: " + str(error)
        ) from error
    cleanup_archive_change_staging(database_path, workspace_path, cr_id, remove_originals=False)
    cleanup_archive_reversal(workspace_path, cr_id)

    now = _now()
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE event_change_requests
               SET status='aenderbar_abgebrochen',cancelled_at=?,updated_at=?
               WHERE id=?""",
            (now, now, cr_id),
        )
    return {
        "status": "abgebrochen",
        "reversal_complete": True,
        "change_request_id": cr_id,
    }
