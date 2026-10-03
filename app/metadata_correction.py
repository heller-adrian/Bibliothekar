from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid

from app.database import database_connection
from app.metadata import (
    MetadataError,
    analyze_tree,
    classify_media,
    parse_exiftool_datetime,
)
from app.storage_config import storage_paths
from app.folder_import import build_folder_import_plan
from app.free_stock_layout import canonical_free_directory


class MetadataCorrectionError(RuntimeError):
    pass


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
            path.rmdir()
        except OSError:
            pass
    try:
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
    if kind not in {"library", "general"}:
        raise MetadataCorrectionError("Unbekannter Metadatenbereich.")

    paths = storage_paths(workspace_root)
    metadata_root = paths["metadata_root"].resolve(strict=False)
    if create:
        metadata_root.mkdir(parents=True, exist_ok=True)
    _cleanup_empty_legacy_metadata_tree(metadata_root)

    if kind == "library":
        # Undated camera material is global free stock. The technical library
        # id must never become a filesystem directory.
        central_root = paths["backup_root"].resolve(strict=False)
        undated = (central_root / "Ohne_Datum").resolve(strict=False)
        return {
            "root": central_root,
            "input_root": undated,
            "output_root": central_root,
        }

    general = (metadata_root / "Allgemein").resolve(strict=False)
    if not _is_relative_to(general, metadata_root):
        raise MetadataCorrectionError("Metadatenpfad verlässt den konfigurierten Stamm.")
    if create:
        general.mkdir(parents=True, exist_ok=True)
    if general.exists() and not general.is_dir():
        raise MetadataCorrectionError("Metadatenpfad ist kein Ordner: " + str(general))
    return {
        "root": general,
        "input_root": general,
        "output_root": general,
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
                        f.current_relative_path='Ohne_Datum'
                        OR f.current_relative_path LIKE 'Ohne_Datum/%'
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
    by_family: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        current = Path(str(row.get("current_relative_path") or ""))
        if not current.parts or current.parts[0] != "Ohne_Datum":
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
    return parsed.replace(tzinfo=None, microsecond=0).isoformat(timespec="seconds")


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
) -> dict[str, Any]:
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
    if filename_hint and filename_hint.get("datetime") == proposed:
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


def write_metadata_datetime(path: Path, media_type: str, value: str) -> None:
    stamp = _exiftool_value(value)
    command = ["exiftool", "-overwrite_original"]

    if media_type == "video":
        command += [
            f"-QuickTime:CreateDate={stamp}",
            f"-QuickTime:ModifyDate={stamp}",
            f"-Keys:CreationDate={stamp}",
        ]
    elif media_type == "xmp":
        command += [
            f"-XMP-exif:DateTimeOriginal={stamp}",
            f"-XMP-xmp:CreateDate={stamp}",
            f"-XMP-xmp:ModifyDate={stamp}",
        ]
    else:
        command += [
            f"-EXIF:DateTimeOriginal={stamp}",
            f"-EXIF:CreateDate={stamp}",
            f"-EXIF:ModifyDate={stamp}",
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
    matches: list[dict[str, str]] = []
    observed: list[dict[str, str]] = []
    for tag, raw in data[0].items():
        if tag == "SourceFile" or raw is None:
            continue
        raw_text = str(raw)
        parsed = parse_exiftool_datetime(raw_text)
        if parsed is None:
            continue
        normalized = parsed.replace(tzinfo=None).isoformat(timespec="seconds")
        observed.append({"tag": str(tag), "value": normalized})
        if normalized[:19] == expected_second:
            matches.append({"tag": str(tag), "value": normalized})

    if not matches:
        raise MetadataCorrectionError(
            "Die geschriebenen Aufnahmeinformationen konnten nicht bestätigt werden."
        )

    return {
        "expected_datetime": expected_second,
        "matching_tags": matches,
        "observed_tags": observed,
    }


def _mark_task_writing(database_path: Path, correction_id: str) -> None:
    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE metadata_corrections SET status='writing',updated_at=?,error_message=NULL WHERE id=?",
            (_now(), correction_id),
        )


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
    if not _is_relative_to(source, root) or not source.is_file():
        raise MetadataCorrectionError("Die eingefrorene Datei fehlt.")
    if source.is_symlink():
        raise MetadataCorrectionError("Symbolische Links werden nicht verändert.")

    stat = source.stat()
    if int(stat.st_size) != int(task["source_size_bytes"]):
        raise MetadataCorrectionError("Die Datei hat sich seit der Vorbereitung verändert.")
    if _sha256(source) != str(task["source_sha256"]):
        raise MetadataCorrectionError("Die SHA-256-Summe der Datei hat sich verändert.")

    temp = source.parent / (
        "." + source.stem + ".bibliothekar-" + uuid.uuid4().hex + source.suffix
    )
    _mark_task_writing(database_path, str(task["id"]))
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
        os.replace(temp, source)
        _fsync_directory(source.parent)
        if int(source.stat().st_size) != output_size or _sha256(source) != output_sha:
            raise MetadataCorrectionError(
                "Die Datei hat sich nach dem atomaren Abschluss verändert."
            )
        return _complete_task(
            database_path,
            str(task["id"]),
            output_path=source,
            output_size=output_size,
            output_sha=output_sha,
            verification=verification,
        )
    except Exception as error:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
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
    work = (metadata_root / ".work" / str(task["id"])).resolve(strict=False)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=False)

    prepared: list[dict[str, Any]] = []
    replaced: list[tuple[Path, Path]] = []
    incoming_paths: list[Path] = []
    _mark_task_writing(database_path, str(task["id"]))

    try:
        for member in frozen_members:
            current_relative = _safe_relative(str(member.get("current_relative_path") or ""))
            if not current_relative.parts or current_relative.parts[0] != "Ohne_Datum":
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

        # Replace every visible source only after all family members were
        # written and verified successfully.  The old bytes stay adjacent and
        # recoverable until SQLite commits the new metadata state.
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
            if _sha256(incoming) != str(item["output_sha"]):
                raise MetadataCorrectionError(
                    "Korrigierte Arbeitsdatei stimmt vor dem Austausch nicht überein."
                )
            os.replace(source, backup)
            _fsync_directory(source.parent)
            try:
                os.replace(incoming, source)
                _fsync_directory(source.parent)
            except Exception:
                if backup.exists() and not source.exists():
                    os.replace(backup, source)
                    _fsync_directory(source.parent)
                raise
            replaced.append((source, backup))
            item["backup"] = backup

        proposed = str(task["proposed_datetime"])[:19]
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

        for _source, backup in replaced:
            backup.unlink(missing_ok=True)
            _fsync_directory(backup.parent)
        shutil.rmtree(work, ignore_errors=True)

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
        return _complete_task(
            database_path,
            str(task["id"]),
            output_path=Path(first["source"]),
            output_size=sum(int(item["output_size"]) for item in prepared),
            output_sha=str(first["output_sha"]),
            verification=verification,
        )

    except Exception as error:
        for incoming in incoming_paths:
            try:
                incoming.unlink(missing_ok=True)
            except OSError:
                pass
        for source, backup in reversed(replaced):
            try:
                if backup.exists():
                    if source.exists():
                        source.unlink()
                    os.replace(backup, source)
                    _fsync_directory(source.parent)
            except OSError:
                pass
        shutil.rmtree(work, ignore_errors=True)
        _mark_task_blocked(database_path, str(task["id"]), error)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error


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

    if not rows:
        raise MetadataCorrectionError("Die Dateifamilie enthält keine Dateien.")

    work = (
        metadata_root
        / ".reintegrate"
        / ("META_SORT_" + uuid.uuid4().hex.upper())
    ).resolve(strict=False)
    work.mkdir(parents=True, exist_ok=False)
    moved: list[tuple[Path, Path]] = []

    try:
        prepared: list[dict[str, Any]] = []
        for row in rows:
            current_relative = _safe_relative(str(row.get("current_relative_path") or ""))
            if not current_relative.parts or current_relative.parts[0] != "Ohne_Datum":
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
            if not stored_capture or stored_capture[:19] != proposed[:19]:
                raise MetadataCorrectionError(
                    "Die korrigierten Familienmitglieder besitzen keinen einheitlichen Zeitstempel."
                )
            verification = verify_metadata_datetime(source, proposed)

            original_relative = _safe_relative(str(row["original_relative_path"]))
            temp = (work / original_relative).resolve(strict=False)
            if not _is_relative_to(temp, work):
                raise MetadataCorrectionError("Unsicherer Reintegration-Arbeitspfad.")
            temp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, temp)
            if _sha256(temp) != expected_sha:
                raise MetadataCorrectionError(
                    "Reintegration-Arbeitskopie stimmt nicht mit der Quelle überein."
                )
            prepared.append({
                **row,
                "source": source,
                "current_relative": current_relative.as_posix(),
                "temp": temp,
                "verification": verification,
            })

        analysis = analyze_tree(work, include_other=False)
        entries = [
            {
                "relative_path": Path(str(item["original_relative_path"])).as_posix(),
                "size_bytes": int(item["size_bytes"]),
                "sha256": str(item["sha256_current"]),
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
            if destination.exists() or destination.is_symlink():
                raise MetadataCorrectionError(
                    "Reintegrationsziel ist bereits belegt: "
                    + destination_relative.as_posix()
                )
            item["destination"] = destination
            item["destination_relative"] = destination_relative.as_posix()

        for item in prepared:
            source = Path(item["source"])
            destination = Path(item["destination"])
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            _fsync_directory(source.parent)
            _fsync_directory(destination.parent)
            moved.append((source, destination))

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
                or str(live_family["selected_capture_time"] or "")[:19] != proposed[:19]
            ):
                raise MetadataCorrectionError(
                    "Dateifamilie wurde während der Einsortierung verändert."
                )
            for item in prepared:
                cursor = connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,updated_at=?
                       WHERE id=? AND family_id=? AND job_id=?
                         AND current_relative_path=?""",
                    (
                        str(item["destination_relative"]),
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

        shutil.rmtree(work, ignore_errors=True)
        return {
            "family_id": int(family_id),
            "job_id": str(family["job_id"]),
            "family_key": str(family["family_key"]),
            "selected_capture_time": proposed[:19],
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

    except Exception as error:
        for source, destination in reversed(moved):
            try:
                if destination.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(destination, source)
                    _fsync_directory(destination.parent)
                    _fsync_directory(source.parent)
            except OSError:
                pass
        shutil.rmtree(work, ignore_errors=True)
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error

def apply_metadata_correction(
    database_path: Path,
    correction_id: str,
    *,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    task = get_metadata_correction(database_path, correction_id)
    if str(task["status"]) not in {"prepared", "blocked"}:
        raise MetadataCorrectionError(
            "Der Metadatenauftrag ist nicht zum Schreiben bereit."
        )
    if str(task.get("area") or "") == "library":
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
    )
    return apply_metadata_correction(
        database_path,
        str(task["id"]),
        workspace_root=workspace_root,
        library_id=library_id,
    )
