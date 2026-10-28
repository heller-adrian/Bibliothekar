from __future__ import annotations

from app.root_operations import protect, validate_active_roots


from contextlib import contextmanager
from functools import wraps
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import uuid

from app.database import database_connection
from app.metadata import (
    MetadataError,
    analyze_tree,
    classify_media,
    LOCAL_TIMEZONE,
    parse_exiftool_datetime,
)
from app.storage_config import storage_paths
from app.folder_import import build_folder_import_plan
from app.free_stock_layout import canonical_free_directory


class MetadataCorrectionError(RuntimeError):
    pass


@contextmanager
def _metadata_writer(workspace_root: Path):
    from app.metadata_swap_recovery import metadata_write_guard, MetadataSwapRecoveryError
    try:
        with metadata_write_guard(storage_paths(workspace_root)["metadata_root"]):
            yield
    except MetadataSwapRecoveryError as error:
        raise MetadataCorrectionError(str(error)) from error


def _exclusive_metadata_write(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        with _metadata_writer(kwargs["workspace_root"]):
            return function(*args, **kwargs)
    return guarded


def _metadata_projection_databases(database_path: Path) -> list[Path]:
    """Use the already registered workspace authority, including inactive copies."""
    from app.root_operations import _registered
    row = _registered(database_path)
    if row is None:
        return [Path(database_path)]
    candidates = [Path(database_path).parent / 'registry.sqlite3',
                  Path(database_path).parent / 'bibliothekar-global.sqlite3']
    if os.environ.get('KAMERA_REGISTRY_DATABASE'):
        candidates.insert(0, Path(os.environ['KAMERA_REGISTRY_DATABASE']))
    for registry in dict.fromkeys(candidates):
        if not registry.is_file():
            continue
        try:
            with database_connection(registry) as connection:
                copies = [Path(value[0]) for value in connection.execute(
                    'SELECT database_path FROM libraries WHERE workspace_root=?',
                    (row['workspace_root'],))]
        except sqlite3.OperationalError as error:
            if 'no such table' in str(error):
                continue
            raise
        if any(path.resolve() == Path(database_path).resolve() for path in copies):
            return list(dict.fromkeys(copies))
    raise MetadataCorrectionError('Die gemeinsame Metadaten-Registry ist nicht eindeutig verfügbar.')


def _assert_family_projection_finished(database_path: Path, task: dict[str, Any], *, allow_current_task: bool = False) -> None:
    if task.get('area') != 'library':
        return
    family = task.get('detected') or {}
    for database in _metadata_projection_databases(database_path):
        if not database.is_file():
            raise MetadataCorrectionError('Eine Metadaten-Projektionsdatenbank fehlt.')
        with database_connection(database) as connection:
            rows = connection.execute(
                "SELECT id,detected_json,verification_json,status FROM metadata_corrections "
                "WHERE area='library' AND status IN ('writing','completed')").fetchall()
        for row in rows:
            if allow_current_task and database.resolve() == Path(database_path).resolve() and row['id'] == task.get('id'):
                continue
            detected = json.loads(row['detected_json'] or '{}')
            if (detected.get('job_id'), detected.get('family_key')) != (family.get('job_id'), family.get('family_key')):
                continue
            if row['status'] == 'writing' or json.loads(row['verification_json'] or '{}').get('projection_pending'):
                raise MetadataCorrectionError(
                    'Die vorherige Metadatenkorrektur dieser Aufnahme ist noch nicht '
                    'vollständig in allen Bibliotheken bestätigt. Bitte ihren Abschluss abwarten.')


SUPPORTED_MEDIA = {
    "raw",
    "jpeg",
    "image",
    "video",
    "xmp",
}


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    validate_active_roots()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    validate_active_roots()
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _safe_library_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or not re.fullmatch(r"[A-Za-z0-9._-]+", text):
        raise MetadataCorrectionError("Ungültige Bibliotheks-ID.")
    return text


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_relative(value: str) -> Path:
    validate_active_roots()
    raw = str(value or "").replace("\\", "/").strip()
    relative = Path(raw)
    if (
        not raw
        or relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise MetadataCorrectionError("Unsicherer relativer Dateipfad.")
    return relative


def _cleanup_empty_legacy_metadata_tree(metadata_root: Path) -> None:
    """Remove only empty 0.33.0 compatibility folders.

    Never delete a file supplied by the user. The obsolete Bibliothek/<id>/
    Eingang/Ausgang tree disappears automatically only when every directory is
    empty.
    """
    legacy = metadata_root / "Bibliothek"
    if not legacy.exists() or not legacy.is_dir() or legacy.is_symlink():
        return
    for path in sorted(
        (item for item in legacy.rglob("*") if item.is_dir() and not item.is_symlink()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        try:
            validate_active_roots()
            path.rmdir()
        except OSError:
            pass
    try:
        validate_active_roots()
        legacy.rmdir()
    except OSError:
        pass


def metadata_area_paths(
    *,
    area: str,
    workspace_root: Path,
    library_id: str,
    create: bool = True,
) -> dict[str, Path]:
    kind = str(area or "").strip().lower()
    if kind not in {"library", "general", "multiple"}:
        raise MetadataCorrectionError("Unbekannter Metadatenbereich.")

    paths = storage_paths(workspace_root)
    metadata_root = paths["metadata_root"].resolve(strict=False)
    if create:
        validate_active_roots()
        metadata_root.mkdir(parents=True, exist_ok=True)
    _cleanup_empty_legacy_metadata_tree(metadata_root)

    if kind == "library":
        # Undated camera material is global free stock. The technical library
        # id must never become a filesystem directory.
        central_root = paths["backup_root"].resolve(strict=False)
        from app.managed_directory_names import directory_path
        undated = directory_path(central_root, "undated").resolve(strict=False)
        return {
            "root": central_root,
            "input_root": undated,
            "output_root": central_root,
        }

    from app.managed_directory_names import directory_name
    folder_name = directory_name(
        metadata_root, "metadata_general" if kind == "general" else "metadata_multiple"
    )
    target = (metadata_root / folder_name).resolve(strict=False)
    if not _is_relative_to(target, metadata_root):
        raise MetadataCorrectionError("Metadatenpfad verlässt den konfigurierten Stamm.")
    if create:
        validate_active_roots()
        target.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_dir():
        raise MetadataCorrectionError("Metadatenpfad ist kein Ordner: " + str(target))
    return {
        "root": target,
        "input_root": target,
        "output_root": target,
    }


_FILENAME_PATTERNS: list[tuple[str, re.Pattern[str], bool]] = [
    (
        "camera_yyyymmdd_hhmmss",
        re.compile(
            r"(?<!\d)(?P<y>20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>[0-3]\d)"
            r"[_ -]?(?P<h>[0-2]\d)(?P<mi>[0-5]\d)(?P<s>[0-5]\d)(?!\d)",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "iso_date_time",
        re.compile(
            r"(?<!\d)(?P<y>20\d{2})[-_.](?P<m>0[1-9]|1[0-2])[-_.](?P<d>[0-3]\d)"
            r"[ T_-]+(?P<h>[0-2]\d)[-_.:]?(?P<mi>[0-5]\d)[-_.:]?(?P<s>[0-5]\d)(?!\d)",
            re.IGNORECASE,
        ),
        True,
    ),
    (
        "whatsapp",
        re.compile(
            r"(?i)(?:IMG|VID)[-_](?P<y>20\d{2})(?P<m>0[1-9]|1[0-2])(?P<d>[0-3]\d)[-_]WA\d+"
        ),
        False,
    ),
    (
        "signal_or_generic_date",
        re.compile(
            r"(?<!\d)(?P<y>20\d{2})[-_.]?(?P<m>0[1-9]|1[0-2])[-_.]?(?P<d>[0-3]\d)(?!\d)",
            re.IGNORECASE,
        ),
        False,
    ),
]


def detect_filename_datetime(filename: str) -> dict[str, Any] | None:
    name = Path(str(filename or "")).stem

    for rule, pattern, has_time in _FILENAME_PATTERNS:
        match = pattern.search(name)
        if match is None:
            continue
        values = match.groupdict()
        try:
            year = int(values["y"])
            month = int(values["m"])
            day = int(values["d"])
            hour = int(values.get("h") or 0)
            minute = int(values.get("mi") or 0)
            second = int(values.get("s") or 0)
            parsed = datetime(year, month, day, hour, minute, second)
        except (TypeError, ValueError):
            continue

        return {
            "rule": rule,
            "date": parsed.strftime("%Y-%m-%d"),
            "time": parsed.strftime("%H:%M:%S") if has_time else None,
            "datetime": parsed.isoformat(timespec="seconds") if has_time else None,
            "requires_time": not has_time,
            "confidence": "high" if has_time else "medium",
            "source": "filename",
        }

    return None


def _metadata_suggestion(record: dict[str, Any]) -> dict[str, Any] | None:
    value = str(record.get("selected_capture_time") or "").strip()
    confidence = str(record.get("capture_time_confidence") or "")
    if value and confidence in {"high", "medium"}:
        return {
            "datetime": value[:19],
            "date": value[:10],
            "time": value[11:19],
            "requires_time": False,
            "confidence": confidence,
            "source": "metadata",
            "tag": record.get("selected_capture_source"),
        }
    return None


def _analysis_by_relative(root: Path) -> dict[str, dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        return {}
    try:
        analysis = analyze_tree(root, include_other=False)
    except MetadataError:
        return {}
    return {
        str(row.get("relative_path") or ""): dict(row)
        for row in (analysis.get("files") or [])
        if str(row.get("relative_path") or "")
    }


def _completed_correction_history(
    database_path: Path | None,
    *,
    area: str,
) -> dict[str, dict[Any, dict[str, Any]]]:
    """Return the latest durable pre-correction snapshot for visible records."""
    result: dict[str, dict[Any, dict[str, Any]]] = {
        "by_relative": {},
        "by_family": {},
    }
    if database_path is None or not Path(database_path).is_file():
        return result
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT source_relative_path,proposal_source,proposed_datetime,
                          detected_json,completed_at,created_at
                   FROM metadata_corrections
                   WHERE area=? AND status='completed'
                   ORDER BY COALESCE(completed_at,created_at) DESC, created_at DESC""",
                (str(area),),
            ).fetchall()
        ]
    for row in rows:
        try:
            detected = json.loads(str(row.get("detected_json") or "{}"))
        except (TypeError, ValueError, json.JSONDecodeError):
            detected = {}
        before = dict(
            detected.get("before_metadata")
            or {
                key: detected.get(key)
                for key in (
                    "selected_capture_time",
                    "selected_capture_source",
                    "capture_time_confidence",
                    "metadata_candidates",
                    "filename_suggestion",
                )
            }
        )
        snapshot = {
            "corrected_at": row.get("completed_at") or row.get("created_at"),
            "proposed_datetime": row.get("proposed_datetime"),
            "proposal_source": row.get("proposal_source"),
            "before_metadata": before,
        }
        relative = str(row.get("source_relative_path") or "")
        if relative and relative not in result["by_relative"]:
            result["by_relative"][relative] = snapshot
        family_id = detected.get("family_id")
        if family_id is not None:
            try:
                family_key = int(family_id)
            except (TypeError, ValueError):
                family_key = None
            if family_key is not None and family_key not in result["by_family"]:
                result["by_family"][family_key] = snapshot
    return result


def _scan_library_undated(
    *,
    database_path: Path,
    workspace_root: Path,
    library_id: str,
    library_name: str | None,
    allowed_job_ids: set[str] | None,
) -> dict[str, Any]:
    paths = metadata_area_paths(
        area="library",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    input_root = paths["input_root"]
    central_root = paths["output_root"]
    jobs = sorted({str(value) for value in (allowed_job_ids or set()) if str(value)})
    if allowed_job_ids is not None and not jobs:
        rows = []
    else:
        job_sql = ""
        params: list[Any] = []
        if jobs:
            placeholders = ",".join("?" for _ in jobs)
            job_sql = f" AND ff.job_id IN ({placeholders})"
            params.extend(jobs)
        with database_connection(database_path) as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    f"""
                    SELECT
                        ff.id AS family_id,
                        ff.job_id,
                        ff.family_key,
                        ff.original_stem,
                        ff.selected_capture_time AS family_capture_time,
                        ff.capture_time_confidence AS family_confidence,
                        f.id AS file_id,
                        f.original_relative_path,
                        f.current_relative_path,
                        f.original_filename,
                        f.extension,
                        f.media_type,
                        f.size_bytes,
                        COALESCE(f.source_size_bytes, f.size_bytes) AS source_size_bytes,
                        f.sha256_original,
                        COALESCE(f.sha256_current, f.sha256_original) AS sha256_current,
                        f.selected_capture_time,
                        f.selected_capture_source,
                        f.capture_time_confidence,
                        f.review_status
                    FROM file_families ff
                    JOIN files f
                      ON f.family_id=ff.id AND f.job_id=ff.job_id
                    WHERE f.current_root_kind='shared_workspace'
                      AND (
                        f.current_relative_path IN ('Ohne_Datum','No Date')
                        OR f.current_relative_path LIKE 'Ohne_Datum/%'
                        OR f.current_relative_path LIKE 'No Date/%'
                      )
                      {job_sql}
                      AND NOT EXISTS (
                        SELECT 1
                        FROM event_assignments ea
                        JOIN events e ON e.id=ea.event_id
                        WHERE ea.family_id=ff.id
                          AND e.status IN ('draft','planned','applied','archived')
                      )
                    ORDER BY ff.job_id, ff.id, f.id
                    """,
                    tuple(params),
                ).fetchall()
            ]

    analyzed = _analysis_by_relative(input_root)
    correction_history = _completed_correction_history(
        database_path,
        area="library",
    )
    by_family: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        current = Path(str(row.get("current_relative_path") or ""))
        if not current.parts or current.parts[0] != input_root.name:
            continue
        relative_inside = Path(*current.parts[1:]).as_posix()
        source = (central_root / current).resolve(strict=False)
        if not _is_relative_to(source, central_root) or not source.is_file() or source.is_symlink():
            continue
        item = dict(row)
        item["physical_path"] = str(source)
        item["relative_inside_undated"] = relative_inside
        item["analysis"] = analyzed.get(relative_inside) or {}
        by_family.setdefault(int(row["family_id"]), []).append(item)

    records: list[dict[str, Any]] = []
    for family_id, members in by_family.items():
        members = sorted(members, key=lambda row: (str(row["media_type"]), int(row["file_id"])))
        anchor = next(
            (
                row for row in members
                if str(row.get("media_type") or "") in {"raw", "jpeg", "image", "video"}
            ),
            members[0],
        )
        observed = dict(anchor.get("analysis") or {})
        filename = str(anchor.get("original_filename") or Path(str(anchor["physical_path"])).name)
        filename_hint = detect_filename_datetime(filename)
        metadata_hint = _metadata_suggestion(observed)
        preferred = metadata_hint or filename_hint
        stored_capture = str(anchor.get("family_capture_time") or "").strip()
        reintegration_ready = bool(stored_capture) and all(
            str(member.get("selected_capture_time") or "").strip()
            for member in members
        )
        records.append({
            **observed,
            "family_id": family_id,
            "job_id": str(anchor["job_id"]),
            "family_key": str(anchor["family_key"]),
            "filename": filename,
            "relative_path": str(anchor["current_relative_path"]),
            "media_type": str(anchor["media_type"]),
            "selected_capture_time": (
                stored_capture
                or observed.get("selected_capture_time")
            ),
            "selected_capture_source": (
                "metadata_correction"
                if reintegration_ready
                else observed.get("selected_capture_source")
            ),
            "capture_time_confidence": (
                str(anchor.get("family_confidence") or "high")
                if reintegration_ready
                else str(observed.get("capture_time_confidence") or "missing")
            ),
            "review_required": not reintegration_ready,
            "reintegration_ready": reintegration_ready,
            "filename_suggestion": filename_hint,
            "preferred_suggestion": preferred,
            "needs_attention": not reintegration_ready,
            "original_metadata": correction_history["by_family"].get(family_id),
            "member_count": len(members),
            "members": [
                {
                    key: row.get(key)
                    for key in (
                        "file_id",
                        "original_relative_path",
                        "current_relative_path",
                        "original_filename",
                        "media_type",
                        "size_bytes",
                        "source_size_bytes",
                        "sha256_original",
                        "sha256_current",
                    )
                }
                for row in members
            ],
            "library_id": library_id,
            "library_name": library_name or library_id,
        })

    return {
        "area": "library",
        "library_id": library_id,
        "library_name": library_name or library_id,
        "paths": {key: str(value) for key, value in paths.items()},
        "summary": {
            "file_count": sum(int(row.get("member_count") or 1) for row in records),
            "family_count": len(records),
            "needs_attention": sum(not bool(row.get("reintegration_ready")) for row in records),
            "ready_to_reintegrate": sum(bool(row.get("reintegration_ready")) for row in records),
            "filename_suggestions": sum(row.get("filename_suggestion") is not None for row in records),
        },
        "files": records,
    }


def scan_metadata_area(
    *,
    area: str,
    workspace_root: Path,
    library_id: str,
    database_path: Path | None = None,
    library_name: str | None = None,
    allowed_job_ids: set[str] | None = None,
) -> dict[str, Any]:
    kind = str(area or "").strip().lower()
    if kind == "library":
        if database_path is None:
            raise MetadataCorrectionError(
                "Für den Bibliotheksbestand fehlt die zugehörige Datenbank."
            )
        return _scan_library_undated(
            database_path=database_path,
            workspace_root=workspace_root,
            library_id=library_id,
            library_name=library_name,
            allowed_job_ids=allowed_job_ids,
        )

    if kind == "multiple":
        return _multiple_scan(
            workspace_root=workspace_root,
            library_id=library_id,
        )

    paths = metadata_area_paths(
        area="general",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    input_root = paths["input_root"]

    if not any(path.is_file() and not path.name.startswith(".") for path in input_root.rglob("*")):
        return {
            "area": "general",
            "paths": {key: str(value) for key, value in paths.items()},
            "summary": {
                "file_count": 0,
                "needs_attention": 0,
                "filename_suggestions": 0,
            },
            "files": [],
        }

    analysis = analyze_tree(input_root, include_other=False)
    correction_history = _completed_correction_history(
        database_path,
        area="general",
    )
    records: list[dict[str, Any]] = []
    for record in analysis.get("files") or []:
        media_type = str(record.get("media_type") or "")
        if media_type not in SUPPORTED_MEDIA:
            continue
        filename = str(record.get("filename") or "")
        filename_hint = detect_filename_datetime(filename)
        metadata_hint = _metadata_suggestion(record)
        preferred = metadata_hint
        if (
            filename_hint is not None
            and str(record.get("capture_time_confidence") or "")
            in {"missing", "low", "conflict", ""}
        ):
            preferred = filename_hint

        records.append({
            **record,
            "filename_suggestion": filename_hint,
            "preferred_suggestion": preferred,
            "needs_attention": bool(record.get("review_required"))
            or filename_hint is not None,
            "original_metadata": correction_history["by_relative"].get(
                str(record.get("relative_path") or "")
            ),
        })

    return {
        "area": "general",
        "paths": {key: str(value) for key, value in paths.items()},
        "summary": {
            "file_count": len(records),
            "needs_attention": sum(bool(item["needs_attention"]) for item in records),
            "filename_suggestions": sum(
                item.get("filename_suggestion") is not None for item in records
            ),
        },
        "files": records,
    }


def _multiple_scan(
    *,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    paths = metadata_area_paths(
        area="multiple",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    root = paths["input_root"]
    visible_files = [
        path for path in root.rglob("*")
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(root).parts)
    ]
    if not visible_files:
        return {
            "area": "multiple",
            "paths": {key: str(value) for key, value in paths.items()},
            "summary": {
                "file_count": 0,
                "usable_time_count": 0,
                "missing_time_count": 0,
            },
            "files": [],
        }

    analysis = analyze_tree(root, include_other=False)
    records: list[dict[str, Any]] = []
    for record in analysis.get("files") or []:
        media_type = str(record.get("media_type") or "")
        if media_type not in SUPPORTED_MEDIA:
            continue
        relative = _safe_relative(str(record.get("relative_path") or ""))
        source = (root / relative).resolve(strict=False)
        if not _is_relative_to(source, root) or not source.is_file() or source.is_symlink():
            continue
        item = dict(record)
        item["relative_path"] = relative.as_posix()
        item["filename"] = str(record.get("filename") or relative.name)
        item["size_bytes"] = int(source.stat().st_size)
        item["sha256"] = _sha256(source)
        item["usable_time"] = bool(str(record.get("selected_capture_time") or "").strip())
        records.append(item)

    records.sort(key=lambda row: str(row.get("relative_path") or ""))
    return {
        "area": "multiple",
        "paths": {key: str(value) for key, value in paths.items()},
        "summary": {
            "file_count": len(records),
            "usable_time_count": sum(bool(row["usable_time"]) for row in records),
            "missing_time_count": sum(not bool(row["usable_time"]) for row in records),
        },
        "files": records,
    }


def _naive_capture_datetime(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise MetadataCorrectionError("Aufnahmezeit fehlt.")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise MetadataCorrectionError(
            "Eine Aufnahmezeit ist ungültig: " + raw
        ) from error
    validate_active_roots()
    return parsed.replace(tzinfo=None, microsecond=0)


def preview_multiple_metadata_correction(
    *,
    workspace_root: Path,
    library_id: str,
    reference_relative_path: str,
    proposed_datetime: Any,
    selected_relative_paths: list[str] | None = None,
) -> dict[str, Any]:
    proposed = _normalize_manual_datetime(proposed_datetime)
    scan = _multiple_scan(
        workspace_root=workspace_root,
        library_id=library_id,
    )
    all_records = list(scan.get("files") or [])
    if not all_records:
        raise MetadataCorrectionError(
            "Der Ordner Mehrfachkorrektur enthält keine unterstützten Medien."
        )

    selected_relatives = {
        _safe_relative(value).as_posix()
        for value in (selected_relative_paths or [])
        if str(value or "").strip()
    }
    if selected_relatives:
        available_relatives = {
            str(row.get("relative_path") or "")
            for row in all_records
        }
        missing_selection = sorted(selected_relatives - available_relatives)
        if missing_selection:
            raise MetadataCorrectionError(
                "Mindestens eine ausgewählte Datei wurde nicht gefunden: "
                + ", ".join(missing_selection[:10])
            )
        records = [
            row for row in all_records
            if str(row.get("relative_path") or "") in selected_relatives
        ]
    else:
        records = all_records

    reference_relative = _safe_relative(reference_relative_path).as_posix()
    if selected_relatives and reference_relative not in selected_relatives:
        raise MetadataCorrectionError(
            "Die Referenzaufnahme muss Teil der ausgewählten Dateien sein."
        )
    reference = next(
        (
            row for row in records
            if str(row.get("relative_path") or "") == reference_relative
        ),
        None,
    )
    if reference is None:
        raise MetadataCorrectionError("Die Referenzdatei wurde nicht gefunden.")
    reference_old = str(reference.get("selected_capture_time") or "").strip()
    if not reference_old:
        raise MetadataCorrectionError(
            "Die Referenzdatei besitzt keine belastbare Aufnahmezeit."
        )

    missing = [
        str(row.get("relative_path") or "")
        for row in records
        if not str(row.get("selected_capture_time") or "").strip()
    ]
    if missing:
        raise MetadataCorrectionError(
            "Für die Mehrfachkorrektur benötigen alle Dateien eine vorhandene "
            "Aufnahmezeit. Ohne Aufnahmezeit: " + ", ".join(missing[:10])
        )

    delta = (
        _naive_capture_datetime(proposed)
        - _naive_capture_datetime(reference_old)
    )
    rows: list[dict[str, Any]] = []
    for record in records:
        old = _naive_capture_datetime(record["selected_capture_time"])
        new = old + delta
        rows.append({
            "relative_path": str(record["relative_path"]),
            "filename": str(record.get("filename") or Path(str(record["relative_path"])).name),
            "media_type": str(record.get("media_type") or ""),
            "capture_time_confidence": str(record.get("capture_time_confidence") or "missing"),
            "old_datetime": old.isoformat(timespec="seconds"),
            "new_datetime": new.isoformat(timespec="seconds"),
            "size_bytes": int(record["size_bytes"]),
            "sha256": str(record["sha256"]),
        })

    fingerprint_payload = json.dumps(
        {
            "reference_relative_path": reference_relative,
            "reference_old_datetime": _naive_capture_datetime(reference_old).isoformat(timespec="seconds"),
            "reference_new_datetime": proposed,
            "offset_seconds": int(delta.total_seconds()),
            "files": [
                {
                    key: row[key]
                    for key in (
                        "relative_path",
                        "old_datetime",
                        "new_datetime",
                        "size_bytes",
                        "sha256",
                    )
                }
                for row in rows
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    preview_fingerprint = hashlib.sha256(
        fingerprint_payload.encode("utf-8")
    ).hexdigest()
    return {
        "area": "multiple",
        "reference_relative_path": reference_relative,
        "reference_old_datetime": _naive_capture_datetime(reference_old).isoformat(timespec="seconds"),
        "reference_new_datetime": proposed,
        "offset_seconds": int(delta.total_seconds()),
        "preview_fingerprint": preview_fingerprint,
        "file_count": len(rows),
        "total_file_count": len(all_records),
        "selection_is_subset": (
            bool(selected_relatives)
            and len(rows) < len(all_records)
        ),
        "selected_relative_paths": [
            str(row["relative_path"])
            for row in rows
        ],
        "files": rows,
    }


@protect(workspace_arg='workspace_root', database_arg='database_path', kind='metadata', error_type=MetadataCorrectionError)
@_exclusive_metadata_write
def apply_multiple_metadata_correction(
    *,
    workspace_root: Path,
    library_id: str,
    reference_relative_path: str,
    proposed_datetime: Any,
    expected_preview_fingerprint: str,
    selected_relative_paths: list[str] | None = None,
) -> dict[str, Any]:
    preview = preview_multiple_metadata_correction(
        workspace_root=workspace_root,
        library_id=library_id,
        reference_relative_path=reference_relative_path,
        proposed_datetime=proposed_datetime,
        selected_relative_paths=selected_relative_paths,
    )
    expected = str(expected_preview_fingerprint or "").strip()
    if not expected or expected != str(preview["preview_fingerprint"]):
        raise MetadataCorrectionError(
            "Der Bestand hat sich seit der Vorschau verändert. Bitte die Vorschau neu berechnen."
        )

    paths = metadata_area_paths(
        area="multiple",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    root = paths["root"]
    metadata_root = storage_paths(workspace_root)["metadata_root"].resolve(strict=False)
    from app.metadata_swap_recovery import (
        assert_no_pending_swaps, create_swap_journal, fsync_staged_file,
        mark_swap_committed, recover_swap_journal,
    )
    assert_no_pending_swaps(metadata_root)
    work = (
        metadata_root / ".multiple-work" / ("MULTI_" + uuid.uuid4().hex.upper())
    ).resolve(strict=False)
    validate_active_roots()
    work.mkdir(parents=True, exist_ok=False)

    prepared: list[dict[str, Any]] = []
    incoming_paths: list[Path] = []
    swap_journal: Path | None = None
    try:
        for row in preview["files"]:
            relative = _safe_relative(str(row["relative_path"]))
            source = (root / relative).resolve(strict=False)
            if (
                not _is_relative_to(source, root)
                or not source.is_file()
                or source.is_symlink()
            ):
                raise MetadataCorrectionError(
                    "Eine Datei der Vorschau fehlt: " + relative.as_posix()
                )
            if (
                int(source.stat().st_size) != int(row["size_bytes"])
                or _sha256(source) != str(row["sha256"])
            ):
                raise MetadataCorrectionError(
                    "Eine Datei wurde seit der Vorschau verändert: "
                    + relative.as_posix()
                )

            temp = (work / relative).resolve(strict=False)
            if not _is_relative_to(temp, work):
                raise MetadataCorrectionError("Unsicherer Mehrfachkorrektur-Arbeitspfad.")
            validate_active_roots()
            temp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, temp)
            if _sha256(temp) != str(row["sha256"]):
                raise MetadataCorrectionError(
                    "Arbeitskopie stimmt nicht mit der Vorschau überein: "
                    + relative.as_posix()
                )
            media_type = str(row.get("media_type") or classify_media(temp))
            write_metadata_datetime(
                temp,
                media_type,
                str(row["new_datetime"]),
            )
            verification = verify_metadata_datetime(
                temp,
                str(row["new_datetime"]),
            )
            prepared.append({
                **row,
                "source": source,
                "temp": temp,
                "verification": verification,
                "output_sha256": _sha256(temp),
                "output_size_bytes": int(temp.stat().st_size),
            })

        swap_files: list[dict[str, Any]] = []
        for item in prepared:
            source = Path(item["source"])
            incoming = source.parent / (
                "." + source.name + ".multiple-" + uuid.uuid4().hex
            )
            backup = source.parent / (
                "." + source.name + ".multiple-before-" + uuid.uuid4().hex
            )
            incoming_paths.append(incoming)
            shutil.copyfile(Path(item["temp"]), incoming)
            fsync_staged_file(incoming)
            if _sha256(incoming) != str(item["output_sha256"]):
                raise MetadataCorrectionError(
                    "Korrigierte Arbeitsdatei stimmt vor dem Austausch nicht überein."
                )
            item["incoming"] = incoming
            item["backup"] = backup
            swap_files.append({
                "source": str(source), "incoming": str(incoming),
                "backup": str(backup),
                "before_sha": str(item["sha256"]),
                "after_sha": str(item["output_sha256"]),
            })
        swap_journal = create_swap_journal(
            metadata_root, kind="multiple", file_entries=swap_files,
            data_root=root,
        )
        for item in prepared:
            source = Path(item["source"])
            validate_active_roots()
            os.replace(source, Path(item["backup"]))
            _fsync_directory(source.parent)
            validate_active_roots()
            os.replace(Path(item["incoming"]), source)
            _fsync_directory(source.parent)

        # A multiple-folder edit has no SQLite commit; the fsync'ed journal
        # transition is its durable finish boundary.
        mark_swap_committed(swap_journal, metadata_root)
        recover_swap_journal(metadata_root, swap_journal)
        shutil.rmtree(work, ignore_errors=True)
        return {
            "status": "completed",
            "file_count": len(prepared),
            "total_file_count": int(preview["total_file_count"]),
            "selection_is_subset": bool(preview["selection_is_subset"]),
            "offset_seconds": int(preview["offset_seconds"]),
            "reference_relative_path": str(preview["reference_relative_path"]),
            "preview_fingerprint": str(preview["preview_fingerprint"]),
            "files": [
                {
                    "relative_path": str(item["relative_path"]),
                    "old_datetime": str(item["old_datetime"]),
                    "new_datetime": str(item["new_datetime"]),
                    "output_size_bytes": int(item["output_size_bytes"]),
                    "output_sha256": str(item["output_sha256"]),
                    "verification": item["verification"],
                }
                for item in prepared
            ],
        }
    except Exception as error:
        if swap_journal is not None:
            try:
                disposition = recover_swap_journal(metadata_root, swap_journal)
                if disposition == "completed":
                    # The transaction is already durable: report success
                    # without re-running edits on an outdated preview.
                    shutil.rmtree(work, ignore_errors=True)
                    return {
                        "status": "completed",
                        "file_count": len(prepared),
                        "total_file_count": int(preview["total_file_count"]),
                        "selection_is_subset": bool(preview["selection_is_subset"]),
                        "offset_seconds": int(preview["offset_seconds"]),
                        "reference_relative_path": str(preview["reference_relative_path"]),
                        "preview_fingerprint": str(preview["preview_fingerprint"]),
                        "files": [
                            {
                                "relative_path": str(item["relative_path"]),
                                "old_datetime": str(item["old_datetime"]),
                                "new_datetime": str(item["new_datetime"]),
                                "output_size_bytes": int(item["output_size_bytes"]),
                                "output_sha256": str(item["output_sha256"]),
                                "verification": item["verification"],
                            }
                            for item in prepared
                        ],
                    }
            except Exception as recovery_error:
                raise MetadataCorrectionError(
                    "Mehrfachkorrektur unterbrochen: automatischer Rückbau "
                    "gesperrt; Sicherheitskopien und Journal bleiben bestehen ("
                    + str(recovery_error) + ")."
                ) from error
        else:
            for incoming in incoming_paths:
                try:
                    validate_active_roots()
                    incoming.unlink(missing_ok=True)
                except OSError:
                    pass
        shutil.rmtree(work, ignore_errors=True)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error


def _normalize_manual_datetime(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise MetadataCorrectionError("Datum und Uhrzeit fehlen.")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as error:
        raise MetadataCorrectionError(
            "Datum und Uhrzeit sind ungültig."
        ) from error
    if parsed.year < 1905 or parsed.year > 2200:
        raise MetadataCorrectionError("Datum liegt außerhalb des zulässigen Bereichs.")
    validate_active_roots()
    return parsed.replace(microsecond=0).isoformat(timespec="seconds")


def _find_scan_record(
    *,
    area: str,
    relative_path: str,
    workspace_root: Path,
    library_id: str,
    database_path: Path,
    family_id: int | None = None,
    library_name: str | None = None,
    allowed_job_ids: set[str] | None = None,
) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    paths = metadata_area_paths(
        area=area,
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    scan = scan_metadata_area(
        area=area,
        workspace_root=workspace_root,
        library_id=library_id,
        database_path=database_path,
        library_name=library_name,
        allowed_job_ids=allowed_job_ids,
    )

    if str(area) == "library":
        wanted = int(family_id or 0)
        row = next(
            (
                item for item in (scan.get("files") or [])
                if int(item.get("family_id") or 0) == wanted
            ),
            None,
        )
        if row is None:
            raise MetadataCorrectionError(
                "Die ausgewählte Ohne-Datum-Familie wurde nicht gefunden."
            )
        source = (
            paths["output_root"] / _safe_relative(str(row["relative_path"]))
        ).resolve(strict=False)
        if not _is_relative_to(source, paths["output_root"]) or not source.is_file():
            raise MetadataCorrectionError("Die ausgewählte Kameradatei wurde nicht gefunden.")
        return row, source, paths

    relative = _safe_relative(relative_path)
    source = (paths["input_root"] / relative).resolve(strict=False)
    if not _is_relative_to(source, paths["input_root"]) or not source.is_file():
        raise MetadataCorrectionError("Die ausgewählte Datei wurde nicht gefunden.")
    row = next(
        (
            item
            for item in scan.get("files") or []
            if str(item.get("relative_path") or "") == relative.as_posix()
        ),
        None,
    )
    if row is None:
        raise MetadataCorrectionError(
            "Die Datei wird von der Metadatenkorrektur nicht unterstützt."
        )
    return row, source, paths


def create_metadata_correction(
    database_path: Path,
    *,
    area: str,
    relative_path: str,
    proposed_datetime: Any,
    workspace_root: Path,
    library_id: str,
    family_id: int | None = None,
    library_name: str | None = None,
    allowed_job_ids: set[str] | None = None,
    proposal_source_tag: str | None = None,
    _prevalidated_row: dict[str, Any] | None = None,
    _prevalidated_source: Path | None = None,
) -> dict[str, Any]:
    if _prevalidated_row is not None and _prevalidated_source is not None:
        row = dict(_prevalidated_row)
        source = Path(_prevalidated_source).resolve(strict=False)
        if not source.is_file() or source.is_symlink():
            raise MetadataCorrectionError("Die vorgeprüfte Metadatendatei fehlt.")
    else:
        row, source, _ = _find_scan_record(
            area=area,
            relative_path=relative_path,
            workspace_root=workspace_root,
            library_id=library_id,
            database_path=database_path,
            family_id=family_id,
            library_name=library_name,
            allowed_job_ids=allowed_job_ids,
        )
    proposed = _normalize_manual_datetime(proposed_datetime)
    stat = source.stat()
    digest = _sha256(source)
    filename_hint = row.get("filename_suggestion")
    metadata_hint = _metadata_suggestion(row)
    source_kind = "manual"
    verified_source_tag = str(proposal_source_tag or "").strip()
    if verified_source_tag:
        candidate = next(
            (
                item
                for item in (row.get("metadata_candidates") or [])
                if str(item.get("tag_name") or "") == verified_source_tag
                and bool(item.get("usable"))
                and str(item.get("normalized_datetime") or "")[:19] == proposed[:19]
            ),
            None,
        )
        if candidate is None:
            raise MetadataCorrectionError(
                "Der gewählte Metadaten-Quelltyp passt nicht mehr zum aktuellen Dateibestand."
            )
        # The UI submits the chosen wall clock plus its source tag. Preserve
        # that candidate's explicit offset, including deliberately selected low
        # confidence filesystem dates. A freely edited time uses local time.
        proposed = _normalize_manual_datetime(candidate["normalized_datetime"])
        source_kind = "metadata"
    elif filename_hint and filename_hint.get("datetime") == proposed:
        source_kind = "filename"
    elif metadata_hint and str(metadata_hint.get("datetime") or "")[:19] == proposed:
        source_kind = "metadata"

    correction_id = "META_" + uuid.uuid4().hex.upper()
    now = _now()
    before_metadata = {
        "selected_capture_time": row.get("selected_capture_time"),
        "selected_capture_source": row.get("selected_capture_source"),
        "capture_time_confidence": row.get("capture_time_confidence"),
        "metadata_candidates": row.get("metadata_candidates") or [],
        "filename_suggestion": filename_hint,
    }
    detected = {
        **before_metadata,
        "before_metadata": before_metadata,
        "proposal_source_tag": verified_source_tag or None,
        "library_id": library_id,
        "library_name": library_name or library_id,
    }
    if str(area) == "library":
        detected.update({
            "family_id": int(row["family_id"]),
            "job_id": str(row["job_id"]),
            "family_key": str(row["family_key"]),
            "members": list(row.get("members") or []),
        })

    with database_connection(database_path) as connection:
        active_write = connection.execute(
            """SELECT id
               FROM metadata_corrections
               WHERE area=? AND source_path=? AND status='writing'
               LIMIT 1""",
            (str(area), str(source)),
        ).fetchone()
        if active_write is not None:
            raise MetadataCorrectionError(
                "Für diese Datei läuft bereits eine Metadatenkorrektur."
            )

        # 0.33.2 führt Einzelkorrekturen direkt aus. Ein älterer, noch nicht
        # geschriebener Auftrag derselben Datei wird daher durch die neue
        # bewusste Korrektur ersetzt, statt als Dublette in Aufgaben zu bleiben.
        connection.execute(
            """UPDATE metadata_corrections
               SET status='cancelled', updated_at=?, error_message=NULL
               WHERE area=? AND source_path=?
                 AND status IN ('pending_review','prepared','blocked')""",
            (now, str(area), str(source)),
        )
        connection.execute(
            """
            INSERT INTO metadata_corrections(
                id,area,status,source_path,source_relative_path,source_filename,
                source_size_bytes,source_sha256,media_type,detected_json,
                proposed_datetime,proposal_source,verification_json,
                created_at,updated_at
            )
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                correction_id,
                str(area),
                "prepared",
                str(source),
                str(row["relative_path"]),
                str(row["filename"]),
                int(stat.st_size),
                digest,
                str(row["media_type"]),
                json.dumps(detected, ensure_ascii=False, sort_keys=True),
                proposed,
                source_kind,
                "{}",
                now,
                now,
            ),
        )
    return get_metadata_correction(database_path, correction_id)


def _row_to_task(row: Any) -> dict[str, Any]:
    result = dict(row)
    for key in ("detected_json", "verification_json"):
        try:
            result[key[:-5]] = json.loads(str(result.pop(key) or "{}"))
        except (TypeError, ValueError):
            result[key[:-5]] = {}
            result.pop(key, None)
    return result


def get_metadata_correction(
    database_path: Path,
    correction_id: str,
) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM metadata_corrections WHERE id=?",
            (str(correction_id),),
        ).fetchone()
    if row is None:
        raise MetadataCorrectionError("Metadatenauftrag wurde nicht gefunden.")
    return _row_to_task(row)


def list_metadata_corrections(
    database_path: Path,
    *,
    include_completed: bool = False,
) -> list[dict[str, Any]]:
    with database_connection(database_path) as connection:
        sql = "SELECT * FROM metadata_corrections"
        if not include_completed:
            sql += " WHERE status NOT IN ('completed','cancelled')"
        sql += " ORDER BY created_at DESC"
        rows = connection.execute(sql).fetchall()
    return [_row_to_task(row) for row in rows]


def cancel_metadata_correction(
    database_path: Path,
    correction_id: str,
) -> dict[str, Any]:
    current = get_metadata_correction(database_path, correction_id)
    if str(current["status"]) in {"writing", "completed"}:
        raise MetadataCorrectionError(
            "Dieser Metadatenauftrag kann nicht mehr verworfen werden."
        )
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE metadata_corrections
               SET status='cancelled', updated_at=?, error_message=NULL
               WHERE id=?""",
            (_now(), correction_id),
        )
    return get_metadata_correction(database_path, correction_id)


def _exiftool_value(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y:%m:%d %H:%M:%S")


def _capture_with_zone(parsed: datetime) -> datetime:
    if parsed.tzinfo is not None:
        return parsed
    # A naive local timestamp must have exactly one valid UTC interpretation.
    choices = {}
    for fold in (0, 1):
        aware = parsed.replace(tzinfo=LOCAL_TIMEZONE, fold=fold)
        if aware.astimezone(timezone.utc).astimezone(LOCAL_TIMEZONE).replace(tzinfo=None) == parsed:
            choices[aware.utcoffset()] = aware
    if len(choices) != 1:
        raise MetadataCorrectionError("Diese lokale Uhrzeit ist wegen der Zeitumstellung ungültig oder mehrdeutig. Bitte einen expliziten UTC-Offset angeben.")
    return next(iter(choices.values()))


def write_metadata_datetime(path: Path, media_type: str, value: str) -> None:
    stamp = _exiftool_value(value)
    parsed = datetime.fromisoformat(value)
    parsed = _capture_with_zone(parsed)
    offset = parsed.strftime("%z")
    offset = offset[:3] + ":" + offset[3:]
    zoned_stamp = stamp + offset
    command = ["exiftool", "-overwrite_original_in_place"]

    if media_type == "video":
        command += [
            f"-QuickTime:CreateDate={stamp}",
            f"-QuickTime:ModifyDate={stamp}",
            f"-Keys:CreationDate={stamp}",
        ]
    elif media_type == "xmp":
        command += [
            f"-XMP-exif:DateTimeOriginal={zoned_stamp}",
            f"-XMP-xmp:CreateDate={zoned_stamp}",
            f"-XMP-xmp:ModifyDate={zoned_stamp}",
        ]
    else:
        command += [
            f"-EXIF:DateTimeOriginal={stamp}",
            f"-EXIF:CreateDate={stamp}",
            f"-EXIF:ModifyDate={stamp}",
            f"-EXIF:OffsetTimeOriginal={offset}",
            f"-EXIF:OffsetTimeDigitized={offset}",
            f"-EXIF:OffsetTime={offset}",
            # Stills can carry a second high-confidence timestamp in XMP.
            # Normalize it together with EXIF so a previously conflicting
            # Prüffall cannot remain conflicting after a manual correction.
            f"-XMP-exif:DateTimeOriginal={zoned_stamp}",
            f"-XMP-xmp:CreateDate={zoned_stamp}",
            f"-XMP-xmp:ModifyDate={zoned_stamp}",
        ]

    command.append(str(path))
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise MetadataCorrectionError(
            "ExifTool konnte die Metadaten nicht schreiben: "
            + (result.stderr.strip() or result.stdout.strip())
        )


def verify_metadata_datetime(path: Path, expected: str) -> dict[str, Any]:
    command = [
        "exiftool",
        "-json",
        "-G0:1",
        "-a",
        "-s",
        "-DateTimeOriginal",
        "-CreateDate",
        "-ModifyDate",
        "-CreationDate",
        "-OffsetTimeOriginal",
        "-OffsetTimeDigitized",
        "-OffsetTime",
        str(path),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode not in {0, 1}:
        raise MetadataCorrectionError(
            "ExifTool konnte die geschriebenen Metadaten nicht prüfen."
        )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise MetadataCorrectionError(
            "ExifTool lieferte bei der Prüfung ungültiges JSON."
        ) from error
    if not data or not isinstance(data[0], dict):
        raise MetadataCorrectionError("Keine Metadaten nach dem Schreiben gefunden.")

    expected_second = expected[:19]
    expected_time = datetime.fromisoformat(expected)
    expected_time = _capture_with_zone(expected_time)
    offsets = {str(key).rsplit(":", 1)[-1]: str(value)
               for key, value in data[0].items() if str(key).startswith("EXIF:")}
    timestamp_offsets = {"DateTimeOriginal": "OffsetTimeOriginal",
                         "CreateDate": "OffsetTimeDigitized", "ModifyDate": "OffsetTime"}
    mismatches: list[str] = []
    matches: list[dict[str, str]] = []
    observed: list[dict[str, str]] = []
    for tag, raw in data[0].items():
        if tag == "SourceFile" or raw is None:
            continue
        name = str(tag).rsplit(":", 1)[-1]
        if name not in {"DateTimeOriginal", "CreateDate", "ModifyDate", "CreationDate"}:
            continue
        raw_text = str(raw)
        if str(tag).startswith("EXIF:") and not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", raw_text):
            raw_text += offsets.get(timestamp_offsets.get(name, ""), "")
        parsed = parse_exiftool_datetime(raw_text)
        if parsed is None:
            mismatches.append(str(tag) + ' (invalid timestamp)')
            continue
        validate_active_roots()
        normalized = parsed.isoformat(timespec="seconds")
        observed.append({"tag": str(tag), "value": normalized})
        # Keep the pre-existing video/container wall-clock contract; this
        # correction concerns the coupled EXIF/XMP still-image timestamps.
        if (parsed.replace(tzinfo=None).isoformat(timespec="seconds")[:19] == expected_second
                if classify_media(path) == "video" else parsed == expected_time and parsed.replace(tzinfo=None) == expected_time.replace(tzinfo=None)):
            matches.append({"tag": str(tag), "value": normalized})
        else:
            mismatches.append(str(tag))

    if not matches or (mismatches and classify_media(path) != "video"):
        raise MetadataCorrectionError(
            "Die geschriebenen Aufnahmeinformationen konnten nicht bestätigt werden. "
            + 'Expected: '+expected_time.isoformat(timespec='seconds')+'; '
            + 'Observed: '+json.dumps(observed,ensure_ascii=False)+'; '
            + 'Conflicting tags: '+', '.join(mismatches)
        )

    return {
        "expected_datetime": expected_second,
        "expected_with_offset": expected_time.isoformat(timespec='seconds'),
        "matching_tags": matches,
        "observed_tags": observed,
    }


def _mark_task_writing(database_path: Path, correction_id: str) -> None:
    with database_connection(database_path) as connection:
        claimed = connection.execute(
            "UPDATE metadata_corrections SET status='writing',updated_at=?,error_message=NULL "
            "WHERE id=? AND status IN ('prepared','blocked')",
            (_now(), correction_id),
        )
        if claimed.rowcount != 1:
            raise MetadataCorrectionError("Der Metadatenauftrag wurde bereits übernommen.")


def _mark_task_blocked(
    database_path: Path,
    correction_id: str,
    error: Exception,
) -> None:
    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE metadata_corrections
               SET status='blocked',error_message=?,updated_at=?
               WHERE id=?""",
            (str(error), _now(), correction_id),
        )


def _complete_task(
    database_path: Path,
    correction_id: str,
    *,
    output_path: Path,
    output_size: int,
    output_sha: str,
    verification: dict[str, Any],
) -> dict[str, Any]:
    now = _now()
    with database_connection(database_path) as connection:
        row = connection.execute("SELECT area FROM metadata_corrections WHERE id=?", (correction_id,)).fetchone()
        verification = dict(verification)
        if row and row["area"] == "library":
            verification["projection_pending"] = True
        connection.execute(
            """UPDATE metadata_corrections
               SET status='completed',output_path=?,output_size_bytes=?,
                   output_sha256=?,verification_json=?,error_message=NULL,
                   updated_at=?,completed_at=?
               WHERE id=?""",
            (
                str(output_path),
                int(output_size),
                str(output_sha),
                json.dumps(verification, ensure_ascii=False, sort_keys=True),
                now,
                now,
                correction_id,
            ),
        )
    return get_metadata_correction(database_path, correction_id)


def finish_metadata_propagation(database_path: Path, task_id: str) -> None:
    with database_connection(database_path) as connection:
        row = connection.execute("SELECT verification_json FROM metadata_corrections WHERE id=? AND status='completed'", (task_id,)).fetchone()
        if row:
            details = json.loads(row["verification_json"] or "{}")
            details.pop("projection_pending", None)
            connection.execute("UPDATE metadata_corrections SET verification_json=? WHERE id=?", (json.dumps(details, ensure_ascii=False, sort_keys=True), task_id))


def replay_pending_metadata_propagations(databases: list[Path]) -> int:
    from app.global_stock import propagate_corrected_family
    from app.global_stock import GlobalStockError
    for database in databases:
        if not Path(database).is_file():
            raise GlobalStockError("Metadaten-Zieldatenbank fehlt: " + str(database))
    count = 0
    for database in databases:
        for task in list_metadata_corrections(database, include_completed=True):
            if task["area"] != "library" or task["status"] != "completed" or not task.get("verification", {}).get("projection_pending"):
                continue
            detected = task.get("detected") or {}
            job_id, family_key = str(detected.get("job_id") or ""), str(detected.get("family_key") or "")
            if not job_id or not family_key:
                raise MetadataCorrectionError("Ausstehende Metadatenpropagation ohne Familienidentität.")
            from app.root_operations import _registered
            registered = _registered(database)
            if registered is None:
                raise MetadataCorrectionError("Ausstehende Metadatenprojektion ohne registrierten Workspace.")
            with _metadata_writer(Path(registered['workspace_root'])):
                _assert_family_projection_finished(database, task, allow_current_task=True)
                propagate_corrected_family(database, databases, job_id=job_id, family_key=family_key)
                finish_metadata_propagation(database, str(task["id"]))
            count += 1
    return count


def _apply_general_metadata_correction(
    database_path: Path,
    task: dict[str, Any],
    *,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    paths = metadata_area_paths(
        area="general",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    source = Path(str(task["source_path"])).resolve(strict=False)
    root = paths["root"]
    metadata_root = storage_paths(workspace_root)["metadata_root"].resolve(strict=False)
    from app.metadata_swap_recovery import (
        assert_no_pending_swaps, create_swap_journal, fsync_staged_file,
        mark_swap_committed, recover_swap_journal, create_preparation_journal,
    )
    assert_no_pending_swaps(metadata_root)
    if not _is_relative_to(source, root) or not source.is_file():
        raise MetadataCorrectionError("Die eingefrorene Datei fehlt.")
    if source.is_symlink():
        raise MetadataCorrectionError("Symbolische Links werden nicht verändert.")

    stat = source.stat()
    if int(stat.st_size) != int(task["source_size_bytes"]):
        raise MetadataCorrectionError("Die Datei hat sich seit der Vorbereitung verändert.")
    if _sha256(source) != str(task["source_sha256"]):
        raise MetadataCorrectionError("Die SHA-256-Summe der Datei hat sich verändert.")

    temp = source.parent / ("." + source.name + ".metadata-" + uuid.uuid4().hex + source.suffix)
    backup = source.parent / ("." + source.name + ".metadata-before-" + uuid.uuid4().hex)
    swap_journal: Path | None = None
    preparation = create_preparation_journal(
        metadata_root, data_root=root, database_path=database_path,
        task_id=str(task["id"]), source=source, incoming=temp, backup=backup,
        before_sha=str(task["source_sha256"]),
    )
    try:
        # TrueNAS/ZFS: nur Dateiinhalte kopieren. copy2()/copystat kann beim
        # Übertragen von Modus/ACL-Metadaten mit EPERM scheitern.
        shutil.copyfile(source, temp)
        if _sha256(temp) != str(task["source_sha256"]):
            raise MetadataCorrectionError(
                "Die Arbeitskopie stimmt vor dem Schreiben nicht mit der Quelle überein."
            )
        write_metadata_datetime(
            temp,
            str(task["media_type"]),
            str(task["proposed_datetime"]),
        )
        verification = verify_metadata_datetime(
            temp,
            str(task["proposed_datetime"]),
        )
        output_size = int(temp.stat().st_size)
        output_sha = _sha256(temp)
        fsync_staged_file(temp)
        swap_journal = create_swap_journal(
            metadata_root, kind="general", data_root=root, database_path=database_path,
            task_id=str(task["id"]), preparation=preparation, file_entries=[{
                "source": str(source), "incoming": str(temp), "backup": str(backup),
                "before_sha": str(task["source_sha256"]), "after_sha": output_sha,
            }],
        )
        # Persist a newly created .swap-journals directory before moving originals.
        _fsync_directory(metadata_root)
        _mark_task_writing(database_path, str(task["id"]))
        validate_active_roots()
        os.replace(source, backup)
        _fsync_directory(source.parent)
        validate_active_roots()
        os.replace(temp, source)
        _fsync_directory(source.parent)
        if int(source.stat().st_size) != output_size or _sha256(source) != output_sha:
            raise MetadataCorrectionError(
                "Die Datei hat sich nach dem atomaren Abschluss verändert."
            )
        result = _complete_task(
            database_path,
            str(task["id"]),
            output_path=source,
            output_size=output_size,
            output_sha=output_sha,
            verification=verification,
        )
        mark_swap_committed(swap_journal, metadata_root)
        recover_swap_journal(metadata_root, swap_journal, allowed_databases={database_path})
        return result
    except Exception as error:
        if swap_journal is not None:
            try:
                disposition = recover_swap_journal(metadata_root, swap_journal, allowed_databases={database_path})
                if disposition == "completed":
                    return get_metadata_correction(database_path, str(task["id"]))
            except Exception as recovery_error:
                raise MetadataCorrectionError(
                    "Metadatenkorrektur unterbrochen; Sicherheitskopie und Journal bleiben erhalten: "
                    + str(recovery_error)
                ) from error
        if swap_journal is None:
            recover_swap_journal(metadata_root, preparation, allowed_databases={database_path})
        _mark_task_blocked(database_path, str(task["id"]), error)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error


def _apply_library_metadata_correction(
    database_path: Path,
    task: dict[str, Any],
    *,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    """Write and verify one undated family, but keep it in Ohne_Datum.

    0.33.5 deliberately separates metadata editing from physical
    reintegration.  The user can inspect the corrected family and move it into
    the canonical day stock with a second explicit action.
    """
    detected = dict(task.get("detected") or {})
    family_id = int(detected.get("family_id") or 0)
    job_id = str(detected.get("job_id") or "")
    family_key = str(detected.get("family_key") or "")
    frozen_members = list(detected.get("members") or [])
    if not family_id or not job_id or not family_key or not frozen_members:
        raise MetadataCorrectionError(
            "Der Metadatenauftrag enthält keine vollständige Dateifamilie."
        )

    paths = metadata_area_paths(
        area="library",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    central_root = paths["output_root"]
    metadata_root = storage_paths(workspace_root)["metadata_root"].resolve(strict=False)
    from app.metadata_swap_recovery import (
        assert_no_pending_swaps, create_swap_journal, fsync_staged_file,
        mark_swap_committed, recover_swap_journal,
    )
    assert_no_pending_swaps(metadata_root)
    work = (metadata_root / ".work" / str(task["id"])).resolve(strict=False)
    if work.exists():
        shutil.rmtree(work)
    validate_active_roots()
    work.mkdir(parents=True, exist_ok=False)

    prepared: list[dict[str, Any]] = []
    incoming_paths: list[Path] = []
    swap_journal: Path | None = None
    _mark_task_writing(database_path, str(task["id"]))

    try:
        for member in frozen_members:
            current_relative = _safe_relative(str(member.get("current_relative_path") or ""))
            from app.managed_directory_names import is_undated_name
            if not current_relative.parts or not is_undated_name(current_relative.parts[0]):
                raise MetadataCorrectionError(
                    "Die Dateifamilie liegt nicht mehr im Ohne-Datum-Bestand."
                )
            source = (central_root / current_relative).resolve(strict=False)
            if (
                not _is_relative_to(source, central_root)
                or not source.is_file()
                or source.is_symlink()
            ):
                raise MetadataCorrectionError(
                    "Eine eingefrorene Ohne-Datum-Datei fehlt: "
                    + str(current_relative)
                )
            expected_sha = str(
                member.get("sha256_current")
                or member.get("sha256_original")
                or ""
            )
            if not expected_sha or _sha256(source) != expected_sha:
                raise MetadataCorrectionError(
                    "Eine Ohne-Datum-Datei hat sich seit der Vorbereitung verändert: "
                    + str(current_relative)
                )

            original_relative = _safe_relative(
                str(member.get("original_relative_path") or "")
            )
            temp = (work / original_relative).resolve(strict=False)
            if not _is_relative_to(temp, work):
                raise MetadataCorrectionError("Unsicherer Arbeitskopiepfad.")
            validate_active_roots()
            temp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, temp)
            if _sha256(temp) != expected_sha:
                raise MetadataCorrectionError(
                    "Arbeitskopie stimmt nicht mit der eingefrorenen Datei überein."
                )
            media_type = str(member.get("media_type") or classify_media(temp))
            write_metadata_datetime(
                temp,
                media_type,
                str(task["proposed_datetime"]),
            )
            verification = verify_metadata_datetime(
                temp,
                str(task["proposed_datetime"]),
            )
            prepared.append({
                **member,
                "source": source,
                "temp": temp,
                "media_type": media_type,
                "verification": verification,
                "output_sha": _sha256(temp),
                "output_size": int(temp.stat().st_size),
                "current_relative": current_relative.as_posix(),
            })

        # Prepare and fsync ALL incoming copies BEFORE the first removal.
        # The journal is fsync'ed before any original is moved aside.
        swap_files: list[dict[str, Any]] = []
        for item in prepared:
            source = Path(item["source"])
            incoming = source.parent / (
                "." + source.name + ".metadata-" + uuid.uuid4().hex
            )
            backup = source.parent / (
                "." + source.name + ".metadata-before-" + uuid.uuid4().hex
            )
            incoming_paths.append(incoming)
            shutil.copyfile(Path(item["temp"]), incoming)
            fsync_staged_file(incoming)
            if _sha256(incoming) != str(item["output_sha"]):
                raise MetadataCorrectionError(
                    "Korrigierte Arbeitsdatei stimmt vor dem Austausch nicht überein."
                )
            item["incoming"] = incoming
            item["backup"] = backup
            swap_files.append({
                "source": str(source), "incoming": str(incoming),
                "backup": str(backup),
                "before_sha": str(item.get("sha256_current") or item.get("sha256_original")),
                "after_sha": str(item["output_sha"]), "file_id": int(item["file_id"]),
            })

        proposed = str(task["proposed_datetime"])
        first = prepared[0]
        verification = {
            "family_id": family_id,
            "job_id": job_id,
            "family_key": family_key,
            "proposed_datetime": proposed,
            "reintegration_pending": True,
            "members": [
                {
                    "file_id": int(item["file_id"]),
                    "output_path": str(item["source"]),
                    "output_relative_path": str(item["current_relative"]),
                    "output_sha256": str(item["output_sha"]),
                    "output_size_bytes": int(item["output_size"]),
                    "metadata": item["verification"],
                }
                for item in prepared
            ],
        }
        swap_journal = create_swap_journal(
            metadata_root, kind="library", file_entries=swap_files,
            data_root=central_root, database_path=database_path,
            task_id=str(task["id"]), family_id=family_id,
            proposed=proposed,
            task_verification={
                "output_path": str(first["source"]),
                "output_size": sum(int(item["output_size"]) for item in prepared),
                "output_sha": str(first["output_sha"]),
                "verification": verification,
            },
        )
        for item in prepared:
            source = Path(item["source"])
            validate_active_roots()
            os.replace(source, Path(item["backup"]))
            _fsync_directory(source.parent)
            validate_active_roots()
            os.replace(Path(item["incoming"]), source)
            _fsync_directory(source.parent)

        now = _now()
        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            family = connection.execute(
                "SELECT id,job_id,family_key FROM file_families WHERE id=?",
                (family_id,),
            ).fetchone()
            if (
                family is None
                or str(family["job_id"]) != job_id
                or str(family["family_key"]) != family_key
            ):
                raise MetadataCorrectionError(
                    "Dateifamilie wurde während der Korrektur verändert."
                )

            connection.execute(
                """UPDATE file_families
                   SET selected_capture_time=?,
                       capture_time_confidence='high',
                       status='complete'
                   WHERE id=?""",
                (proposed, family_id),
            )
            for item in prepared:
                file_id = int(item["file_id"])
                cursor = connection.execute(
                    """UPDATE files
                       SET source_size_bytes=COALESCE(source_size_bytes,size_bytes),
                           size_bytes=?,
                           sha256_current=?,
                           selected_capture_time=?,
                           selected_capture_source='metadata_correction',
                           capture_time_confidence='high',
                           review_status='corrected',
                           metadata_write_status='written',
                           updated_at=?
                       WHERE id=? AND family_id=? AND job_id=?
                         AND current_relative_path=?""",
                    (
                        int(item["output_size"]),
                        str(item["output_sha"]),
                        proposed,
                        now,
                        file_id,
                        family_id,
                        job_id,
                        str(item["current_relative"]),
                    ),
                )
                if int(cursor.rowcount or 0) != 1:
                    raise MetadataCorrectionError(
                        "Dateipfad wurde während der Metadatenkorrektur verändert."
                    )
            connection.commit()

        # The SQLite file/family updates have committed. Recovery detects
        # that boundary even if the process dies before the journal marker.
        mark_swap_committed(swap_journal, metadata_root)
        recover_swap_journal(
            metadata_root, swap_journal, allowed_databases={database_path},
        )
        shutil.rmtree(work, ignore_errors=True)
        return get_metadata_correction(database_path, str(task["id"]))

    except Exception as error:
        if swap_journal is not None:
            try:
                disposition = recover_swap_journal(
                    metadata_root, swap_journal, allowed_databases={database_path},
                )
                if disposition == "completed":
                    shutil.rmtree(work, ignore_errors=True)
                    return get_metadata_correction(database_path, str(task["id"]))
            except Exception as recovery_error:
                # Keep the journal AND original safety copies for restart/manual
                # resolution. Never do an unjournaled destructive rollback.
                raise MetadataCorrectionError(
                    "Unterbrochene Dateikorrektur: Wiederherstellung gesperrt ("
                    + str(recovery_error) + "). Bitte das Journal prüfen."
                ) from error
        else:
            for incoming in incoming_paths:
                try:
                    validate_active_roots()
                    incoming.unlink(missing_ok=True)
                except OSError:
                    pass
            _mark_task_blocked(database_path, str(task["id"]), error)
        shutil.rmtree(work, ignore_errors=True)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error


def _reintegration_capture(database_path, family_id, rows, stored, *, job_id, family_key):
    """Qualify RC14's truncated offset from its exact completed swap receipt.

    Never infer a correction from current EXIF alone or alter a source origin.
    Fresh verification against this value still precedes every physical move.
    """
    if datetime.fromisoformat(stored).tzinfo is not None:return stored
    matches=set()
    with database_connection(database_path) as connection:
        tasks=connection.execute("SELECT proposed_datetime,detected_json,verification_json FROM metadata_corrections WHERE area='library' AND status='completed'").fetchall()
    by_id={int(r['file_id']):r for r in rows}
    for task in tasks:
        detected=json.loads(task['detected_json'] or '{}')
        if int(detected.get('family_id') or 0)!=int(family_id):continue
        if detected.get('job_id')!=job_id or detected.get('family_key')!=family_key:continue
        proposal=str(task['proposed_datetime'] or '')
        stamp=datetime.fromisoformat(proposal)
        if stamp.tzinfo is None or proposal[:19]!=stored[:19]:continue
        verification=json.loads(task['verification_json'] or '{}')
        if (int(verification.get('family_id') or 0)!=int(family_id)
            or any(str(verification.get(key) or '')!=str(detected.get(key) or '') for key in ('job_id','family_key'))
            # RC14 truncated this receipt too; only its exact catalogue value
            # is a permitted legacy representation of the full task proposal.
            or verification.get('proposed_datetime') not in {proposal,stored}):continue
        members=verification.get('members',[])
        if (not verification.get('reintegration_pending') or len(members)!=len(rows)
            or {int(m.get('file_id') or 0) for m in members}!=set(by_id)):continue
        if any(m.get('output_sha256')!=by_id[int(m['file_id'])]['sha256_current']
               or int(m.get('output_size_bytes') or -1)!=int(by_id[int(m['file_id'])]['size_bytes'])
               or m.get('output_relative_path')!=by_id[int(m['file_id'])]['current_relative_path'] for m in members):continue
        matches.add(proposal)
    if len(matches)>1:raise MetadataCorrectionError('Widersprüchliche Zeitzonen-Nachweise der abgeschlossenen Korrektur.')
    return next(iter(matches),stored)


@protect(workspace_arg='workspace_root', database_arg='database_path', kind='metadata', error_type=MetadataCorrectionError)
@_exclusive_metadata_write
def reintegrate_library_metadata_family(
    database_path: Path,
    *,
    workspace_root: Path,
    library_id: str,
    family_id: int,
) -> dict[str, Any]:
    """Move one already corrected family from Ohne_Datum into day stock."""
    paths = metadata_area_paths(
        area="library",
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    central_root = paths["output_root"]
    metadata_root = storage_paths(workspace_root)["metadata_root"].resolve(strict=False)
    from app.metadata_swap_recovery import (
        assert_no_pending_swaps, create_swap_journal, fsync_staged_file,
        mark_swap_committed, recover_swap_journal,
    )
    assert_no_pending_swaps(metadata_root)

    with database_connection(database_path) as connection:
        family = connection.execute(
            """SELECT id,job_id,family_key,selected_capture_time,
                      capture_time_confidence
               FROM file_families
               WHERE id=?""",
            (int(family_id),),
        ).fetchone()
        if family is None:
            raise MetadataCorrectionError("Dateifamilie wurde nicht gefunden.")
        proposed = str(family["selected_capture_time"] or "").strip()
        if not proposed:
            raise MetadataCorrectionError(
                "Die Dateifamilie besitzt noch kein bestätigtes Aufnahmedatum."
            )
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT id AS file_id,job_id,original_relative_path,
                          current_relative_path,original_filename,media_type,
                          size_bytes,COALESCE(source_size_bytes,size_bytes) AS source_size_bytes,
                          sha256_original,COALESCE(sha256_current,sha256_original) AS sha256_current,
                          selected_capture_time,selected_capture_source,
                          capture_time_confidence,review_status,
                          metadata_write_status
                   FROM files
                   WHERE family_id=? AND job_id=?
                   ORDER BY id""",
                (int(family_id), str(family["job_id"])),
            ).fetchall()
        ]

    original_proposed = proposed
    proposed = _reintegration_capture(database_path, family_id, rows, proposed, job_id=str(family["job_id"]), family_key=str(family["family_key"]))

    if not rows:
        raise MetadataCorrectionError("Die Dateifamilie enthält keine Dateien.")

    work = (
        metadata_root
        / ".reintegrate"
        / ("META_SORT_" + uuid.uuid4().hex.upper())
    ).resolve(strict=False)
    validate_active_roots()
    work.mkdir(parents=True, exist_ok=False)
    incoming_paths: list[Path] = []
    swap_journal: Path | None = None

    try:
        prepared: list[dict[str, Any]] = []
        for row in rows:
            current_relative = _safe_relative(str(row.get("current_relative_path") or ""))
            from app.managed_directory_names import is_undated_name
            if not current_relative.parts or not is_undated_name(current_relative.parts[0]):
                raise MetadataCorrectionError(
                    "Die Dateifamilie liegt nicht vollständig im Ohne-Datum-Bestand."
                )
            source = (central_root / current_relative).resolve(strict=False)
            if (
                not _is_relative_to(source, central_root)
                or not source.is_file()
                or source.is_symlink()
            ):
                raise MetadataCorrectionError(
                    "Eine korrigierte Ohne-Datum-Datei fehlt: "
                    + current_relative.as_posix()
                )
            expected_sha = str(row.get("sha256_current") or "")
            if not expected_sha or _sha256(source) != expected_sha:
                raise MetadataCorrectionError(
                    "Eine korrigierte Datei hat sich seit der Prüfung verändert: "
                    + current_relative.as_posix()
                )
            stored_capture = str(row.get("selected_capture_time") or "").strip()
            if not stored_capture or stored_capture != original_proposed:
                raise MetadataCorrectionError(
                    "Die korrigierten Familienmitglieder besitzen keinen einheitlichen Zeitstempel."
                )
            verification = verify_metadata_datetime(source, proposed)

            original_relative = _safe_relative(str(row["original_relative_path"]))
            temp = (work / original_relative).resolve(strict=False)
            if not _is_relative_to(temp, work):
                raise MetadataCorrectionError("Unsicherer Reintegration-Arbeitspfad.")
            validate_active_roots()
            temp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, temp)
            if _sha256(temp) != expected_sha:
                raise MetadataCorrectionError(
                    "Reintegration-Arbeitskopie stimmt nicht mit der Quelle überein."
                )

            # A family corrected by an older 0.33.x build can still contain
            # conflicting secondary EXIF/XMP fields. Re-normalize the verified
            # working copy before planning the canonical day destination.
            media_type = str(row.get("media_type") or classify_media(temp))
            write_metadata_datetime(temp, media_type, proposed)
            verification = verify_metadata_datetime(temp, proposed)
            normalized_sha = _sha256(temp)
            normalized_size = int(temp.stat().st_size)

            prepared.append({
                **row,
                "source": source,
                "current_relative": current_relative.as_posix(),
                "temp": temp,
                "media_type": media_type,
                "verification": verification,
                "normalized_sha": normalized_sha,
                "normalized_size": normalized_size,
            })

        analysis = analyze_tree(work, include_other=False)

        # The explicit, verified correction is authoritative for reintegration.
        # Camera/model metadata from analyze_tree is still used for canonical
        # filenames, but stale secondary timestamps must never route a corrected
        # family back into Ohne_Datum.
        for record in analysis.get("files") or []:
            record["selected_capture_time"] = proposed
            record["selected_capture_source"] = "metadata_correction"
            record["capture_time_confidence"] = "high"
            record["review_required"] = False
        for family_record in analysis.get("families") or []:
            family_record["selected_capture_time"] = proposed
            family_record["capture_time_confidence"] = "high"

        entries = [
            {
                "relative_path": Path(str(item["original_relative_path"])).as_posix(),
                "size_bytes": int(item["normalized_size"]),
                "sha256": str(item["normalized_sha"]),
            }
            for item in prepared
        ]

        def destination_directory(capture_value: str) -> Path:
            with database_connection(database_path) as connection:
                return Path(str(canonical_free_directory(
                    connection,
                    capture_value,
                    physical=True,
                )))

        plan, excluded, _summary = build_folder_import_plan(
            entries,
            analysis,
            central_root,
            destination_directory_callback=destination_directory,
        )
        if excluded or len(plan) != len(prepared):
            raise MetadataCorrectionError(
                "Die korrigierte Dateifamilie konnte nicht vollständig neu eingeordnet werden."
            )

        plan_by_source = {
            str(row["source_relative_path"]): dict(row)
            for row in plan
        }
        prepared_by_source = {
            Path(str(row["original_relative_path"])).as_posix(): row
            for row in prepared
        }
        if set(plan_by_source) != set(prepared_by_source):
            raise MetadataCorrectionError(
                "Reintegrationsplan und korrigierte Familie stimmen nicht überein."
            )

        # Preflight every destination before moving the first file.
        for source_relative, plan_row in plan_by_source.items():
            item = prepared_by_source[source_relative]
            destination_relative = _safe_relative(
                str(plan_row["destination_relative_path"])
            )
            destination = (central_root / destination_relative).resolve(strict=False)
            if not _is_relative_to(destination, central_root):
                raise MetadataCorrectionError(
                    "Reintegrationsziel verlässt den Zentralbestand."
                )
            if (
                destination_relative.parts and destination_relative.parts[0] in {"Ohne_Datum", "No Date"}
            ):
                raise MetadataCorrectionError(
                    "Korrigierte Metadaten würden erneut in Ohne_Datum einsortiert."
                )
            if destination.exists() or destination.is_symlink():
                raise MetadataCorrectionError(
                    "Reintegrationsziel ist bereits belegt: "
                    + destination_relative.as_posix()
                )
            item["destination"] = destination
            item["destination_relative"] = destination_relative.as_posix()

        swap_files: list[dict[str, Any]] = []
        for item in prepared:
            source = Path(item["source"])
            destination = Path(item["destination"])
            validate_active_roots()
            destination.parent.mkdir(parents=True, exist_ok=True)
            incoming = source.parent / (
                "." + source.name + ".reintegrate-" + uuid.uuid4().hex
            )
            backup = source.parent / (
                "." + source.name + ".reintegrate-before-" + uuid.uuid4().hex
            )
            incoming_paths.append(incoming)
            shutil.copyfile(Path(item["temp"]), incoming)
            fsync_staged_file(incoming)
            if _sha256(incoming) != str(item["normalized_sha"]):
                raise MetadataCorrectionError(
                    "Normalisierte Reintegration stimmt vor dem Austausch nicht überein."
                )
            item["incoming"] = incoming
            item["backup"] = backup
            swap_files.append({
                "source": str(source), "incoming": str(incoming),
                "backup": str(backup), "destination": str(destination),
                "before_sha": str(item["sha256_current"]),
                "after_sha": str(item["normalized_sha"]),
                "file_id": int(item["file_id"]),
                "source_relative": str(item["current_relative"]),
                "destination_relative": str(item["destination_relative"]),
            })

        swap_journal = create_swap_journal(
            metadata_root, kind="reintegrate", file_entries=swap_files,
            data_root=central_root, database_path=database_path,
            family_id=int(family_id), proposed=proposed,
        )
        for item in prepared:
            source = Path(item["source"])
            destination = Path(item["destination"])
            validate_active_roots()
            os.replace(source, Path(item["backup"]))
            _fsync_directory(source.parent)
            validate_active_roots()
            os.replace(Path(item["incoming"]), source)
            _fsync_directory(source.parent)
            validate_active_roots()
            os.replace(source, destination)
            _fsync_directory(source.parent)
            _fsync_directory(destination.parent)

        now = _now()
        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            live_family = connection.execute(
                "SELECT job_id,family_key,selected_capture_time FROM file_families WHERE id=?",
                (int(family_id),),
            ).fetchone()
            if (
                live_family is None
                or str(live_family["job_id"]) != str(family["job_id"])
                or str(live_family["family_key"]) != str(family["family_key"])
                or str(live_family["selected_capture_time"] or "") != original_proposed
            ):
                raise MetadataCorrectionError(
                    "Dateifamilie wurde während der Einsortierung verändert."
                )
            connection.execute("UPDATE file_families SET selected_capture_time=? WHERE id=?",(proposed,int(family_id)))
            for item in prepared:
                cursor = connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,
                           size_bytes=?,
                           sha256_current=?,
                           selected_capture_time=?,
                           selected_capture_source='metadata_correction',
                           capture_time_confidence='high',
                           review_status='corrected',
                           metadata_write_status='written',
                           updated_at=?
                       WHERE id=? AND family_id=? AND job_id=?
                         AND current_relative_path=?""",
                    (
                        str(item["destination_relative"]),
                        int(item["normalized_size"]),
                        str(item["normalized_sha"]),
                        proposed,
                        now,
                        int(item["file_id"]),
                        int(family_id),
                        str(family["job_id"]),
                        str(item["current_relative"]),
                    ),
                )
                if int(cursor.rowcount or 0) != 1:
                    raise MetadataCorrectionError(
                        "Dateipfad wurde während der Einsortierung verändert."
                    )
            connection.commit()

        # SQLite changed the canonical source paths in one transaction.
        # A crash before the journal marker can still be resolved by checking
        # those canonical DB paths and hashes against the journal.
        mark_swap_committed(swap_journal, metadata_root)
        recover_swap_journal(
            metadata_root, swap_journal, allowed_databases={database_path},
        )
        shutil.rmtree(work, ignore_errors=True)
        def result_payload() -> dict[str, Any]:
            return {
                "family_id": int(family_id),
                "job_id": str(family["job_id"]),
                "family_key": str(family["family_key"]),
                "selected_capture_time": proposed,
                "file_count": len(prepared),
                "files": [
                    {
                        "file_id": int(item["file_id"]),
                        "source_relative_path": str(item["current_relative"]),
                        "destination_relative_path": str(item["destination_relative"]),
                    }
                    for item in prepared
                ],
            }
        return result_payload()

    except Exception as error:
        if swap_journal is not None:
            try:
                disposition = recover_swap_journal(
                    metadata_root, swap_journal, allowed_databases={database_path},
                )
                if disposition == "completed":
                    shutil.rmtree(work, ignore_errors=True)
                    return {
                        "family_id": int(family_id),
                        "job_id": str(family["job_id"]),
                        "family_key": str(family["family_key"]),
                        "selected_capture_time": proposed,
                        "file_count": len(prepared),
                        "files": [
                            {
                                "file_id": int(item["file_id"]),
                                "source_relative_path": str(item["current_relative"]),
                                "destination_relative_path": str(item["destination_relative"]),
                            }
                            for item in prepared
                        ],
                    }
            except Exception as recovery_error:
                raise MetadataCorrectionError(
                    "Metadaten-Reintegration unterbrochen: "
                    "Wiederherstellung gesperrt; geprüfte Sicherheitskopien "
                    "und Journal bleiben erhalten (" + str(recovery_error) + ")."
                ) from error
        else:
            for incoming in incoming_paths:
                try:
                    validate_active_roots()
                    incoming.unlink(missing_ok=True)
                except OSError:
                    pass
        shutil.rmtree(work, ignore_errors=True)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error


@protect(workspace_arg='workspace_root', database_arg='database_path', kind='metadata', error_type=MetadataCorrectionError)
def apply_metadata_correction(
    database_path: Path,
    correction_id: str,
    *,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    task = get_metadata_correction(database_path, correction_id)
    with _metadata_writer(workspace_root):
        # The first read is advisory. Re-read after winning the physical writer
        # decision: another caller may already have completed this same task.
        task = get_metadata_correction(database_path, correction_id)
        if str(task["status"]) not in {"prepared", "blocked"}:
            raise MetadataCorrectionError(
                "Der Metadatenauftrag ist nicht zum Schreiben bereit."
            )
        if str(task.get("area") or "") == "library":
            _assert_family_projection_finished(database_path, task)
            return _apply_library_metadata_correction(
                database_path,
                task,
                workspace_root=workspace_root,
                library_id=library_id,
            )
        return _apply_general_metadata_correction(
            database_path,
            task,
            workspace_root=workspace_root,
            library_id=library_id,
        )



@protect(workspace_arg='workspace_root', database_arg='database_path', kind='metadata', error_type=MetadataCorrectionError)
def execute_metadata_correction(
    database_path: Path,
    *,
    area: str,
    relative_path: str,
    proposed_datetime: Any,
    workspace_root: Path,
    library_id: str,
    family_id: int | None = None,
    library_name: str | None = None,
    allowed_job_ids: set[str] | None = None,
    proposal_source_tag: str | None = None,
    _prevalidated_row: dict[str, Any] | None = None,
    _prevalidated_source: Path | None = None,
) -> dict[str, Any]:
    """Create and execute one user-confirmed metadata correction.

    The durable correction row remains the audit/rollback evidence, but the
    normal 0.33.2 UI no longer exposes a separate prepare/apply workflow.
    """
    task = create_metadata_correction(
        database_path,
        area=area,
        relative_path=relative_path,
        proposed_datetime=proposed_datetime,
        workspace_root=workspace_root,
        library_id=library_id,
        family_id=family_id,
        library_name=library_name,
        allowed_job_ids=allowed_job_ids,
        proposal_source_tag=proposal_source_tag,
        _prevalidated_row=_prevalidated_row,
        _prevalidated_source=_prevalidated_source,
    )
    return apply_metadata_correction(
        database_path,
        str(task["id"]),
        workspace_root=workspace_root,
        library_id=library_id,
    )
