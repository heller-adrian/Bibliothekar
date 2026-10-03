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
from app.storage_config import (
    load_metadata_correction_settings,
    storage_paths,
)


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

    if kind == "library":
        root = (
            storage_paths(workspace_root)["metadata_root"]
            / "Bibliothek"
            / _safe_library_id(library_id)
        ).resolve(strict=False)
    else:
        configured = load_metadata_correction_settings()
        raw = str(configured.get("general_root") or "").strip()
        if not raw:
            raise MetadataCorrectionError(
                "Für „Allgemein“ ist noch kein eigener TrueNAS-Host-Path konfiguriert."
            )
        root = Path(raw).expanduser().resolve(strict=False)
        if not root.exists() or not root.is_dir():
            raise MetadataCorrectionError(
                "Der konfigurierte Host-Path für „Allgemein“ ist nicht verfügbar: "
                + str(root)
            )
        if not os.access(root, os.R_OK | os.W_OK | os.X_OK):
            raise MetadataCorrectionError(
                "Der Host-Path für „Allgemein“ ist nicht vollständig beschreibbar: "
                + str(root)
            )

    incoming = (root / "Eingang").resolve(strict=False)
    outgoing = (root / "Ausgang").resolve(strict=False)

    for candidate in (incoming, outgoing):
        if not _is_relative_to(candidate, root):
            raise MetadataCorrectionError("Metadatenpfad verlässt den konfigurierten Stamm.")
        if create:
            candidate.mkdir(parents=True, exist_ok=True)
        if candidate.exists() and not candidate.is_dir():
            raise MetadataCorrectionError(
                "Metadatenpfad ist kein Ordner: " + str(candidate)
            )

    return {
        "root": root,
        "input_root": incoming,
        "output_root": outgoing,
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


def scan_metadata_area(
    *,
    area: str,
    workspace_root: Path,
    library_id: str,
) -> dict[str, Any]:
    paths = metadata_area_paths(
        area=area,
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    input_root = paths["input_root"]

    if not any(path.is_file() for path in input_root.rglob("*")):
        return {
            "area": area,
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

        # Filename evidence is especially useful when metadata is missing,
        # low-confidence or conflicting. Strong embedded metadata remains
        # visible but is not silently replaced.
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
        "area": area,
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
) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    relative = _safe_relative(relative_path)
    paths = metadata_area_paths(
        area=area,
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    source = (paths["input_root"] / relative).resolve(strict=False)
    if not _is_relative_to(source, paths["input_root"]) or not source.is_file():
        raise MetadataCorrectionError("Die ausgewählte Eingangsdatei wurde nicht gefunden.")

    scan = scan_metadata_area(
        area=area,
        workspace_root=workspace_root,
        library_id=library_id,
    )
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
) -> dict[str, Any]:
    row, source, _ = _find_scan_record(
        area=area,
        relative_path=relative_path,
        workspace_root=workspace_root,
        library_id=library_id,
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
    detected = {
        "selected_capture_time": row.get("selected_capture_time"),
        "selected_capture_source": row.get("selected_capture_source"),
        "capture_time_confidence": row.get("capture_time_confidence"),
        "metadata_candidates": row.get("metadata_candidates") or [],
        "filename_suggestion": filename_hint,
    }
    with database_connection(database_path) as connection:
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

    paths = metadata_area_paths(
        area=str(task["area"]),
        workspace_root=workspace_root,
        library_id=library_id,
        create=True,
    )
    source = Path(str(task["source_path"])).resolve(strict=False)
    input_root = paths["input_root"]
    output_root = paths["output_root"]
    if not _is_relative_to(source, input_root) or not source.is_file():
        raise MetadataCorrectionError("Die eingefrorene Eingangsdatei fehlt.")
    if source.is_symlink():
        raise MetadataCorrectionError(
            "Symbolische Links werden in der Metadatenkorrektur nicht verändert."
        )

    relative = _safe_relative(str(task["source_relative_path"]))
    destination = (output_root / relative).resolve(strict=False)
    if not _is_relative_to(destination, output_root):
        raise MetadataCorrectionError("Ausgabepfad verlässt den sicheren Bereich.")
    if destination.exists():
        raise MetadataCorrectionError(
            "Im Ausgang existiert bereits eine Datei mit demselben Pfad. Es wird nichts überschrieben."
        )

    stat = source.stat()
    if int(stat.st_size) != int(task["source_size_bytes"]):
        raise MetadataCorrectionError("Die Eingangsdatei hat sich seit der Vorbereitung verändert.")
    if _sha256(source) != str(task["source_sha256"]):
        raise MetadataCorrectionError("Die SHA-256-Summe der Eingangsdatei hat sich verändert.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # ExifTool determines the media format from the extension. Keep the real
    # extension on the temporary file; a generic .tmp suffix would make RAW,
    # JPEG and XMP writes fail as an unknown file type.
    temp = destination.parent / (
        "."
        + destination.stem
        + ".bibliothekar-"
        + uuid.uuid4().hex
        + destination.suffix
    )

    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE metadata_corrections SET status='writing',updated_at=?,error_message=NULL WHERE id=?",
            (_now(), correction_id),
        )

    try:
        shutil.copy2(source, temp)
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

        os.replace(temp, destination)
        _fsync_directory(destination.parent)

        # Source is removed only after the fully written output has been
        # verified and atomically placed. A write/verify failure therefore
        # never destroys the input file.
        if _sha256(destination) != output_sha:
            raise MetadataCorrectionError(
                "Die Ausgabe hat sich nach dem atomaren Abschluss verändert."
            )
        source.unlink()
        _fsync_directory(source.parent)

        now = _now()
        with database_connection(database_path) as connection:
            connection.execute(
                """UPDATE metadata_corrections
                   SET status='completed',output_path=?,output_size_bytes=?,
                       output_sha256=?,verification_json=?,error_message=NULL,
                       updated_at=?,completed_at=?
                   WHERE id=?""",
                (
                    str(destination),
                    output_size,
                    output_sha,
                    json.dumps(verification, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    correction_id,
                ),
            )
        return get_metadata_correction(database_path, correction_id)

    except Exception as error:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        with database_connection(database_path) as connection:
            connection.execute(
                """UPDATE metadata_corrections
                   SET status='blocked',error_message=?,updated_at=?
                   WHERE id=?""",
                (str(error), _now(), correction_id),
            )
        if isinstance(error, MetadataCorrectionError):
            raise
        raise MetadataCorrectionError(str(error)) from error
