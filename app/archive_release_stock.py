from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from app.archive_locations import ArchiveLocationError, archive_path_without_symlinks
from app.archive_reassignment_segments import ArchiveSegmentError, build_archive_reassignment_segments
from app.database import database_connection
from app.workspace_layout import WorkspaceLayoutError, backup_root


RELEASE_DIRECTORY_NAME = "Freigewordene Archivdateien"
class ArchiveReleaseStockError(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: Any) -> PurePosixPath:
    raw = str(value or "").replace("\\", "/").strip("/")
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ArchiveReleaseStockError("Unsicherer relativer SSD-Pfad: " + raw)
    return path


def _safe_workspace_path(workspace_path: Path, relative_value: Any) -> Path:
    try:
        root = backup_root(workspace_path).resolve(strict=False)
    except WorkspaceLayoutError as exc:
        raise ArchiveReleaseStockError(str(exc)) from exc
    rel = _safe_relative(relative_value)
    target = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArchiveReleaseStockError("Der Rückkehrpfad verlässt den zentralen Aufnahmebestand.") from exc
    return target


def _safe_archive_path(archive_root: Path, relative_value: Any) -> Path:
    try:
        return archive_path_without_symlinks(archive_root, str(relative_value or ""))
    except ArchiveLocationError as exc:
        raise ArchiveReleaseStockError(str(exc)) from exc


def _segment_folder(segment: dict[str, Any]) -> str:
    day = str(segment.get("day_key") or str(segment.get("start_datetime") or "")[:10])
    start = str(segment.get("start_time") or str(segment.get("start_datetime") or "")[11:16])[:5]
    end = str(segment.get("end_time") or str(segment.get("end_datetime") or "")[11:16])[:5]
    if start == "00:00" and end == "23:59":
        return day
    return f"{day} · {start.replace(':','-')}–{end.replace(':','-')}"


def _release_context(database_path: Path, cr_id: str) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        cr_row = connection.execute(
            "SELECT * FROM event_change_requests WHERE id=?", (cr_id,)
        ).fetchone()
        if cr_row is None:
            raise ArchiveReleaseStockError("Änderungsauftrag wurde nicht gefunden.")
        cr = dict(cr_row)
        event_row = connection.execute(
            "SELECT folder_name FROM events WHERE id=?", (str(cr["event_id"]),)
        ).fetchone()
        source_event_folder = str(event_row["folder_name"] if event_row else cr.get("event_name") or "Archivereignis")

        pending_rows = [
            dict(row)
            for row in connection.execute(
                """SELECT r.family_id,ff.family_key,ff.original_stem,
                          MAX(NULLIF(r.planned_capture_time,'')) AS planned_capture_time,
                          ff.selected_capture_time,COUNT(DISTINCT f.id) AS file_count
                   FROM event_change_file_reviews r
                   JOIN file_families ff ON ff.id=r.family_id
                   LEFT JOIN files f ON f.family_id=ff.id
                   WHERE r.change_request_id=? AND r.action='delete'
                   GROUP BY r.family_id
                   ORDER BY COALESCE(MAX(NULLIF(r.planned_capture_time,'')),ff.selected_capture_time),ff.id""",
                (cr_id,),
            ).fetchall()
        ]

        # Neue 0.32.5-Aufträge frieren die beim Planen live gelesene
        # Aufnahmezeit direkt in den Review-Zeilen ein. Nur Legacy-Aufträge,
        # die vor Migration 041 entstanden sind, dürfen noch auf den zuletzt
        # inventarisierten Archivbestand bzw. SQLite zurückfallen.
        legacy_family_ids = {
            int(row["family_id"])
            for row in pending_rows
            if not str(row.get("planned_capture_time") or "").strip()
        }
        live_times_by_family: dict[int, set[str]] = {}
        if legacy_family_ids:
            for live_row in connection.execute(
                """SELECT family_id,selected_capture_time
                   FROM event_inventory_files
                   WHERE event_id=? AND root_kind='camera_archive'
                     AND known_file_id IS NOT NULL
                     AND family_id IS NOT NULL
                     AND COALESCE(selected_capture_time,'')<>''""",
                (str(cr["event_id"]),),
            ).fetchall():
                family_id = int(live_row["family_id"])
                if family_id in legacy_family_ids:
                    live_times_by_family.setdefault(family_id, set()).add(
                        str(live_row["selected_capture_time"])
                    )

        for pending in pending_rows:
            frozen = str(pending.get("planned_capture_time") or "").strip()
            if frozen:
                pending["selected_capture_time"] = frozen
                continue
            family_id = int(pending["family_id"])
            live_times = live_times_by_family.get(family_id) or set()
            if len(live_times) > 1:
                raise ArchiveReleaseStockError(
                    "Widersprüchliche Live-Aufnahmezeiten für Archivfamilie "
                    + str(family_id)
                )
            if len(live_times) == 1:
                pending["selected_capture_time"] = next(iter(live_times))

        try:
            segments = build_archive_reassignment_segments(connection, cr, pending_rows)
        except ArchiveSegmentError as exc:
            raise ArchiveReleaseStockError(str(exc)) from exc

        family_segment: dict[int, dict[str, Any]] = {}
        for segment in segments:
            for family_id in segment.get("family_ids") or []:
                family_segment[int(family_id)] = dict(segment)

        released_family_ids = sorted(family_segment)
        camera_rows = [
            {**dict(row), "review_kind": "camera"}
            for row in connection.execute(
                """SELECT * FROM event_change_file_reviews
                   WHERE change_request_id=? AND action='delete'
                   ORDER BY id""",
                (cr_id,),
            ).fetchall()
        ]
        asset_rows: list[dict[str, Any]] = []
        if released_family_ids:
            placeholders = ",".join("?" for _ in released_family_ids)
            asset_rows = [
                {**dict(row), "review_kind": "asset", "file_id": None}
                for row in connection.execute(
                    f"""SELECT * FROM event_change_asset_reviews
                        WHERE change_request_id=?
                          AND action='unresolved'
                          AND family_id IN ({placeholders})
                        ORDER BY id""",
                    (cr_id, *released_family_ids),
                ).fetchall()
            ]

    rows = camera_rows + asset_rows
    family_meta = {
        int(row["family_id"]): dict(row)
        for row in pending_rows
        if row.get("family_id") is not None
    }
    year_by_family = {
        int(row["family_id"]): str(
            family_segment[int(row["family_id"])]["day_key"]
        )[:4]
        for row in rows
        if row.get("family_id") is not None and int(row["family_id"]) in family_segment
    }
    seen_targets: set[str] = set()
    enriched: list[dict[str, Any]] = []
    for row in rows:
        family_id = int(row["family_id"])
        segment = family_segment.get(family_id)
        if segment is None:
            raise ArchiveReleaseStockError(
                f"Familie {family_id} lässt sich keinem freigewordenen Zeitraum zuordnen."
            )

        filename = PurePosixPath(str(row.get("old_path") or "").replace("\\", "/")).name
        if not filename:
            raise ArchiveReleaseStockError("Eine freigewordene Archivdatei besitzt keinen Dateinamen.")

        release_directory = PurePosixPath(
            RELEASE_DIRECTORY_NAME,
            year_by_family[family_id],
            _segment_folder(segment),
        )
        candidate = release_directory / filename
        suffix_index = 1
        while candidate.as_posix() in seen_targets:
            path = PurePosixPath(filename)
            suffix = path.suffix
            stem = path.name[:-len(suffix)] if suffix else path.name
            duplicate_name = f"{stem}_{suffix_index:03d}{suffix}"
            candidate = release_directory / duplicate_name
            suffix_index += 1
        relative = candidate.as_posix()
        seen_targets.add(relative)

        metadata = family_meta.get(family_id, {})
        stored = str(row.get("workspace_release_path") or "").strip()
        enriched.append({
            **row,
            "segment": segment,
            "family_key": metadata.get("family_key"),
            "original_stem": metadata.get("original_stem"),
            "release_filename": candidate.name,
            "workspace_release_directory": release_directory.as_posix(),
            "workspace_release_path": stored or relative,
            "calculated_workspace_release_path": relative,
        })

    display_segments = []
    for segment in segments:
        family_ids = {int(value) for value in (segment.get("family_ids") or [])}
        segment_rows = [
            row
            for row in enriched
            if row.get("family_id") is not None
            and int(row["family_id"]) in family_ids
        ]
        release_file_count = len(segment_rows)
        families = []
        for family_id in sorted(family_ids):
            family_rows = [
                row for row in segment_rows
                if int(row["family_id"]) == family_id
            ]
            metadata = family_meta.get(family_id, {})
            families.append({
                "family_id": family_id,
                "family_key": metadata.get("family_key"),
                "original_stem": metadata.get("original_stem"),
                "file_count": len(family_rows),
                "source_paths": sorted({
                    str(row.get("old_path") or "")
                    for row in family_rows
                    if str(row.get("old_path") or "")
                }),
                "release_filenames": [
                    str(row.get("release_filename") or "")
                    for row in family_rows
                ],
            })
        release_directories = sorted({
            str(row.get("workspace_release_directory") or "")
            for row in segment_rows
            if str(row.get("workspace_release_directory") or "")
        })
        display_segments.append({
            **segment,
            "release_file_count": release_file_count,
            "workspace_release_directory": release_directories[0] if len(release_directories) == 1 else "",
            "families": families,
        })

    return {
        "change_request": cr,
        "source_event_folder": source_event_folder,
        "segments": display_segments,
        "family_ids": released_family_ids,
        "rows": enriched,
    }


def describe_archive_release_stock(
    database_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    context = _release_context(database_path, cr_id)
    rows = context["rows"]
    if not rows:
        return {
            "required": False,
            "file_count": 0,
            "family_count": 0,
            "segments": [],
            "rows": [],
            "copy_verified": True,
            "archive_removed": True,
            "stage": "complete",
            "root": RELEASE_DIRECTORY_NAME,
        }

    statuses = [str(row.get("verification_status") or "pending") for row in rows]
    archive_removed = all(status == "verified" for status in statuses)
    copy_verified = all(status in {"release_copy_verified", "verified"} for status in statuses)
    copies_created = all(
        status in {"copy_created", "release_copy_verified", "verified"}
        for status in statuses
    )
    stage = (
        "complete" if archive_removed
        else "remove_archive" if copy_verified
        else "verify_copy" if copies_created
        else "copy_to_ssd"
    )
    return {
        "required": True,
        "file_count": len(rows),
        "family_count": len(context["family_ids"]),
        "segments": context["segments"],
        "rows": rows,
        "copies_created": copies_created,
        "copy_verified": copy_verified,
        "archive_removed": archive_removed,
        "stage": stage,
        "root": RELEASE_DIRECTORY_NAME,
    }


def prepare_archive_release_stock(
    database_path: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    context = _release_context(database_path, cr_id)
    rows = context["rows"]
    created_directories: list[str] = []
    if not rows:
        return {
            "required": False,
            "prepared_file_count": 0,
            "created_directories": [],
            "root": RELEASE_DIRECTORY_NAME,
        }

    root = backup_root(workspace_path).resolve(strict=False)
    prepared: list[tuple[str, int, str]] = []
    created_paths: list[Path] = []
    try:
        for row in rows:
            relative = str(row["calculated_workspace_release_path"])
            target = _safe_workspace_path(workspace_path, relative)
            parent = target.parent
            if parent.exists() and not parent.is_dir():
                raise ArchiveReleaseStockError("SSD-Zielstruktur ist blockiert: " + str(parent))
            if not parent.exists():
                missing: list[Path] = []
                cursor = parent
                while cursor != root and not cursor.exists():
                    missing.append(cursor)
                    cursor = cursor.parent
                parent.mkdir(parents=True, exist_ok=True)
                for directory in reversed(missing):
                    created_paths.append(directory)
                    created_directories.append(str(directory.relative_to(root)))
            if target.exists() or target.is_symlink():
                raise ArchiveReleaseStockError(
                    "Am vorbereiteten SSD-Rückkehrpfad existiert bereits ein Eintrag. "
                    "Die App verwendet dort niemals stillschweigend eine ältere Datei: "
                    + str(target)
                )
            prepared.append((str(row["review_kind"]), int(row["id"]), relative))
    except Exception:
        for directory in sorted(created_paths, key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    with database_connection(database_path) as connection:
        for kind, review_id, relative in prepared:
            table = "event_change_asset_reviews" if kind == "asset" else "event_change_file_reviews"
            connection.execute(
                f"""UPDATE {table}
                    SET workspace_release_path=?,verification_status='pending',updated_at=?
                    WHERE id=? AND change_request_id=?""",
                (relative, now, review_id, cr_id),
            )
    return {
        "required": True,
        "prepared_file_count": len(prepared),
        "created_directories": sorted(set(created_directories)),
        "root": RELEASE_DIRECTORY_NAME,
    }


def _verify_copy_row(
    row: dict[str, Any],
    archive_root: Path,
    workspace_path: Path,
    *,
    require_archive_source: bool = True,
) -> tuple[str, int | None, str | None, str | None]:
    expected_size = int(row.get("expected_size_bytes") or 0)
    expected_sha = str(row.get("expected_sha256") or "").strip()
    if not expected_sha:
        return "missing_sha256", None, None, "Gespeicherte SHA-256-Summe fehlt."

    release_rel = str(row.get("workspace_release_path") or "").strip()
    if not release_rel:
        return "release_path_missing", None, None, "Der SSD-Rückkehrpfad wurde noch nicht vorbereitet."
    target = _safe_workspace_path(workspace_path, release_rel)
    if not target.is_file() or target.is_symlink():
        return "release_copy_missing", None, None, "Die freigewordene Datei fehlt im SSD-Rückkehrbereich."
    actual_size = int(target.stat().st_size)
    if expected_size and actual_size != expected_size:
        return "release_size_mismatch", actual_size, None, "Die SSD-Kopie hat eine abweichende Dateigröße."
    actual_sha = _sha256_file(target)
    if actual_sha != expected_sha:
        return "release_sha256_mismatch", actual_size, actual_sha, "Die SSD-Kopie hat eine abweichende SHA-256-Summe."

    old_path = _safe_archive_path(archive_root, row.get("old_path"))
    if old_path.is_symlink():
        return "archive_source_invalid", actual_size, actual_sha, "Der ursprüngliche Archivpfad ist keine reguläre Datei."
    if not old_path.exists():
        if require_archive_source:
            return (
                "archive_source_missing",
                actual_size,
                actual_sha,
                "Das Archivoriginal fehlt bereits. Die SSD-Kopie darf erst geprüft werden, solange das Original noch unverändert im Archiv vorhanden ist.",
            )
        return "release_copy_verified", actual_size, actual_sha, None
    if not old_path.is_file():
        return "archive_source_invalid", actual_size, actual_sha, "Der ursprüngliche Archivpfad ist keine reguläre Datei."
    if expected_size and int(old_path.stat().st_size) != expected_size:
        return "archive_source_size_mismatch", actual_size, actual_sha, "Das Archivoriginal hat sich seit der Planung verändert."
    if _sha256_file(old_path) != expected_sha:
        return "archive_source_sha256_mismatch", actual_size, actual_sha, "Das Archivoriginal hat sich seit der Planung verändert."
    return "release_copy_verified", actual_size, actual_sha, None


def verify_archive_release_copies(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    context = _release_context(database_path, cr_id)
    rows = context["rows"]
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    results = []
    ok = 0
    with database_connection(database_path) as connection:
        for row in rows:
            status, actual_size, actual_sha, message = _verify_copy_row(
                row, archive_root, workspace_path
            )
            if status == "release_copy_verified":
                ok += 1
            table = "event_change_asset_reviews" if row["review_kind"] == "asset" else "event_change_file_reviews"
            connection.execute(
                f"""UPDATE {table}
                    SET verification_status=?,actual_size_bytes=?,actual_sha256=?,
                        verified_at=?,updated_at=?
                    WHERE id=? AND change_request_id=?""",
                (status, actual_size, actual_sha, now if status == "release_copy_verified" else None, now, int(row["id"]), cr_id),
            )
            results.append({
                "review_kind": row["review_kind"],
                "id": int(row["id"]),
                "family_id": row.get("family_id"),
                "old_path": row.get("old_path"),
                "workspace_release_path": row.get("workspace_release_path"),
                "status": status,
                "message": message,
            })
    return {
        "complete": ok == len(rows),
        "verified_file_count": ok,
        "file_count": len(rows),
        "files": results,
    }


def verify_archive_release_removal(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    context = _release_context(database_path, cr_id)
    rows = context["rows"]
    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    results = []
    ok = 0
    with database_connection(database_path) as connection:
        for row in rows:
            prior_status = str(row.get("verification_status") or "pending")
            if prior_status not in {"release_copy_verified", "verified"}:
                status = "release_copy_not_verified"
                actual_size = row.get("actual_size_bytes")
                actual_sha = row.get("actual_sha256")
                message = (
                    "Die SSD-Kopie wurde noch nicht erfolgreich geprüft, während "
                    "das Archivoriginal unverändert vorhanden war."
                )
            else:
                copy_status, actual_size, actual_sha, copy_message = _verify_copy_row(
                    row, archive_root, workspace_path, require_archive_source=False
                )
                old_path = _safe_archive_path(archive_root, row.get("old_path"))
                if copy_status != "release_copy_verified":
                    status = copy_status
                    message = copy_message
                elif old_path.exists() or old_path.is_symlink():
                    status = "archive_source_still_exists"
                    message = "Das bestätigte Archivoriginal ist noch vorhanden."
                else:
                    status = "verified"
                    message = None
                    ok += 1
            table = "event_change_asset_reviews" if row["review_kind"] == "asset" else "event_change_file_reviews"
            connection.execute(
                f"""UPDATE {table}
                    SET verification_status=?,actual_size_bytes=?,actual_sha256=?,
                        verified_at=?,updated_at=?
                    WHERE id=? AND change_request_id=?""",
                (status, actual_size, actual_sha, now if status == "verified" else None, now, int(row["id"]), cr_id),
            )
            results.append({
                "review_kind": row["review_kind"],
                "id": int(row["id"]),
                "family_id": row.get("family_id"),
                "old_path": row.get("old_path"),
                "workspace_release_path": row.get("workspace_release_path"),
                "status": status,
                "message": message,
            })
    return {
        "complete": ok == len(rows),
        "verified_file_count": ok,
        "file_count": len(rows),
        "files": results,
    }


def cleanup_archive_release_stock(
    database_path: Path,
    workspace_path: Path,
    cr_id: str,
    *,
    archive_root: Path,
) -> dict[str, Any]:
    """Discard only this request's SSD return copies, after archive verification.

    The return area is shared by several requests and may contain unrelated
    user files. Never remove its root or arbitrary contents. All existing
    request-owned SSD copies are checked BEFORE deleting the first one.
    A failed check leaves the request open, not silently marked cancelled.
    """
    context = _release_context(database_path, cr_id)
    root = backup_root(workspace_path).resolve(strict=False)
    release_root = root / RELEASE_DIRECTORY_NAME
    prepared: list[tuple[Path, Path, str]] = []
    parents: set[Path] = set()

    # Pass 1: reject missing/modified archive originals and unsafe or modified
    # SSD copies before doing any filesystem mutation.
    for row in context["rows"]:
        relative = str(row.get("workspace_release_path") or "").strip()
        if not relative:
            continue
        rel = _safe_relative(relative)
        if not rel.parts or rel.parts[0] != RELEASE_DIRECTORY_NAME:
            raise ArchiveReleaseStockError(
                "SSD-Rückkehrpfad gehört nicht zum freigewordenen Archivbestand: " + relative
            )
        candidate = root.joinpath(*rel.parts)
        # resolve() alone would hide a symlink to a second path inside root.
        current = root
        for part in rel.parts:
            current = current / part
            if current.is_symlink():
                raise ArchiveReleaseStockError(
                    "Symlink im SSD-Rückkehrpfad: " + relative
                )
        target = _safe_workspace_path(workspace_path, relative)
        parents.add(target.parent)

        expected_size = int(row.get("expected_size_bytes") or 0)
        expected_sha = str(row.get("expected_sha256") or "").strip()
        old_rel = str(row.get("old_path") or "").strip()
        if not old_rel or not expected_sha:
            raise ArchiveReleaseStockError(
                "Archivoriginal oder SHA-256 fehlt für SSD-Rückkehrdatei: " + relative
            )
        original = _safe_archive_path(archive_root, old_rel)
        if (
            not original.is_file()
            or original.is_symlink()
            or (expected_size and original.stat().st_size != expected_size)
            or _sha256_file(original) != expected_sha
        ):
            raise ArchiveReleaseStockError(
                "Archivoriginal fehlt oder ist verändert. Zuerst sicheren "
                "Rückänderungsauftrag abschließen: " + old_rel
            )

        if not candidate.exists():
            continue
        if (
            not candidate.is_file()
            or (expected_size and candidate.stat().st_size != expected_size)
            or _sha256_file(candidate) != expected_sha
        ):
            raise ArchiveReleaseStockError(
                "SSD-Rückkehrkopie wurde verändert und wird nicht gelöscht: " + relative
            )
        prepared.append((candidate, original, relative))

    removed = 0
    # Pass 2: verify again immediately before each unlink. A partial failure
    # is retryable; already removed copies will be skipped on the next call.
    for target, original, relative in prepared:
        row = next(
            row for row in context["rows"]
            if str(row.get("workspace_release_path") or "").strip() == relative
        )
        expected_sha = str(row.get("expected_sha256") or "").strip()
        expected_size = int(row.get("expected_size_bytes") or 0)
        try:
            if (
                not original.is_file()
                or original.is_symlink()
                or (expected_size and original.stat().st_size != expected_size)
                or _sha256_file(original) != expected_sha
                or not target.is_file()
                or target.is_symlink()
                or (expected_size and target.stat().st_size != expected_size)
                or _sha256_file(target) != expected_sha
            ):
                raise ArchiveReleaseStockError(
                    "Archiv oder SSD-Kopie hat sich während der Bereinigung "
                    "verändert: " + relative
                )
            target.unlink()
            removed += 1
        except OSError as exc:
            raise ArchiveReleaseStockError(
                "SSD-Rückkehrdatei konnte nicht entfernt werden: "
                + relative + ": " + str(exc)
            ) from exc

    # Pass 3: remove now-empty segment/year directories, but stop at the
    # shared 'Freigewordene Archivdateien' root. Foreign contents remain.
    removed_directories = 0
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        cursor = parent
        while cursor != release_root and cursor != root:
            if not cursor.is_dir() or cursor.is_symlink():
                break
            try:
                cursor.rmdir()
                removed_directories += 1
            except OSError:
                break
            cursor = cursor.parent

    # Re-check request-owned paths; a successful request MUST NOT leave a
    # known SSD copy behind while marking the change as cancelled.
    for row in context["rows"]:
        relative = str(row.get("workspace_release_path") or "").strip()
        if relative and _safe_workspace_path(workspace_path, relative).exists():
            raise ArchiveReleaseStockError(
                "SSD-Rückkehrkopie ist weiterhin vorhanden: " + relative
            )
    release_root.mkdir(parents=True, exist_ok=True)
    return {
        "removed_file_count": removed,
        "removed_directory_count": removed_directories,
        "warnings": [],
    }
