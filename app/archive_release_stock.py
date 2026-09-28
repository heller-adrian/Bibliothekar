from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from app.archive_locations import ArchiveLocationError, archive_path_without_symlinks
from app.archive_reassignment_segments import ArchiveSegmentError, build_archive_reassignment_segments
from app.database import database_connection
from app.workspace_layout import WorkspaceLayoutError, shared_work_root


RELEASE_DIRECTORY_NAME = "Freigewordene Archivdateien"
BRANCHES = ("Alle", "Sortiert", "Export")


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
        root = shared_work_root(workspace_path).resolve(strict=False)
    except WorkspaceLayoutError as exc:
        raise ArchiveReleaseStockError(str(exc)) from exc
    rel = _safe_relative(relative_value)
    target = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ArchiveReleaseStockError("Der SSD-Pfad verlässt den Arbeitsbereich.") from exc
    return target


def _safe_archive_path(archive_root: Path, relative_value: Any) -> Path:
    try:
        return archive_path_without_symlinks(archive_root, str(relative_value or ""))
    except ArchiveLocationError as exc:
        raise ArchiveReleaseStockError(str(exc)) from exc


def _branch_for(old_path: str, asset_kind: str = "") -> str:
    parts = PurePosixPath(str(old_path or "").replace("\\", "/")).parts
    for part in parts:
        if part in BRANCHES:
            return part
    return "Export" if asset_kind == "export" else "Alle"


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
                          ff.selected_capture_time,COUNT(DISTINCT f.id) AS file_count
                   FROM event_change_file_reviews r
                   JOIN file_families ff ON ff.id=r.family_id
                   LEFT JOIN files f ON f.family_id=ff.id
                   WHERE r.change_request_id=? AND r.action='delete'
                   GROUP BY r.family_id
                   ORDER BY ff.selected_capture_time,ff.id""",
                (cr_id,),
            ).fetchall()
        ]
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
        branch = _branch_for(
            str(row.get("old_path") or ""),
            str(row.get("asset_kind") or ""),
        )
        filename = PurePosixPath(str(row.get("old_path") or "").replace("\\", "/")).name
        if not filename:
            raise ArchiveReleaseStockError("Eine freigewordene Archivdatei besitzt keinen Dateinamen.")
        relative = PurePosixPath(
            RELEASE_DIRECTORY_NAME,
            year_by_family[family_id],
            _segment_folder(segment),
            source_event_folder,
            branch,
            filename,
        ).as_posix()
        if relative in seen_targets:
            raise ArchiveReleaseStockError(
                "Zwei freigewordene Archivdateien würden denselben SSD-Zielpfad erhalten: " + relative
            )
        seen_targets.add(relative)
        stored = str(row.get("workspace_release_path") or "").strip()
        enriched.append({
            **row,
            "segment": segment,
            "branch": branch,
            "workspace_release_path": stored or relative,
            "calculated_workspace_release_path": relative,
        })

    display_segments = []
    for segment in segments:
        family_ids = {int(value) for value in (segment.get("family_ids") or [])}
        release_file_count = sum(
            1
            for row in enriched
            if row.get("family_id") is not None
            and int(row["family_id"]) in family_ids
        )
        display_segments.append({
            **segment,
            "release_file_count": release_file_count,
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
    stage = "complete" if archive_removed else ("remove_archive" if copy_verified else "copy_to_ssd")
    return {
        "required": True,
        "file_count": len(rows),
        "family_count": len(context["family_ids"]),
        "segments": context["segments"],
        "rows": rows,
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

    root = shared_work_root(workspace_path).resolve(strict=False)
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
) -> dict[str, Any]:
    context = _release_context(database_path, cr_id)
    root = shared_work_root(workspace_path).resolve(strict=False)
    removed = 0
    warnings: list[str] = []
    parents: set[Path] = set()
    for row in context["rows"]:
        relative = str(row.get("workspace_release_path") or "").strip()
        if not relative:
            continue
        target = _safe_workspace_path(workspace_path, relative)
        parents.add(target.parent)
        if not target.exists():
            continue
        expected_size = int(row.get("expected_size_bytes") or 0)
        expected_sha = str(row.get("expected_sha256") or "").strip()
        try:
            if (
                not target.is_file()
                or target.is_symlink()
                or (expected_size and int(target.stat().st_size) != expected_size)
                or not expected_sha
                or _sha256_file(target) != expected_sha
            ):
                warnings.append("SSD-Rückkehrkopie wurde wegen abweichendem Inhalt nicht entfernt: " + relative)
                continue
            target.unlink()
            removed += 1
        except OSError as exc:
            warnings.append(f"SSD-Rückkehrkopie konnte nicht entfernt werden: {relative}: {exc}")

    release_root = (root / RELEASE_DIRECTORY_NAME).resolve(strict=False)
    for parent in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        cursor = parent
        while cursor != root and cursor != release_root.parent:
            try:
                if cursor.exists() and cursor.is_dir() and not any(cursor.iterdir()):
                    cursor.rmdir()
                else:
                    break
            except OSError:
                break
            if cursor == release_root:
                break
            cursor = cursor.parent
    return {
        "removed_file_count": removed,
        "warnings": warnings,
    }
