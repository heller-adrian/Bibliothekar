from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from app.source_filter import should_ignore_source_path
from zoneinfo import ZoneInfo
import json
import re
import subprocess


LOCAL_TIMEZONE = ZoneInfo("Europe/Berlin")

RAW_EXTENSIONS = {
    ".raf",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
    ".orf",
    ".rw2",
}

JPEG_EXTENSIONS = {
    ".jpg",
    ".jpeg",
}

IMAGE_EXTENSIONS = {
    ".png",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

VIDEO_EXTENSIONS = {
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".mts",
    ".m2ts",
}

XMP_EXTENSIONS = {
    ".xmp",
}


class MetadataError(RuntimeError):
    pass


def classify_media(path: Path) -> str:
    extension = path.suffix.lower()

    if extension in RAW_EXTENSIONS:
        return "raw"

    if extension in JPEG_EXTENSIONS:
        return "jpeg"

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    if extension in XMP_EXTENSIONS:
        return "xmp"

    return "other"


def family_key(
    source_root: Path,
    path: Path,
) -> str:
    relative = path.relative_to(source_root)

    return (
        relative.parent
        / path.stem
    ).as_posix()


def parse_exiftool_datetime(
    raw_value: str,
) -> datetime | None:
    value = raw_value.strip()

    if not value:
        return None

    match = re.fullmatch(
        r"""
        (?P<year>\d{4})
        :
        (?P<month>\d{2})
        :
        (?P<day>\d{2})
        [ T]
        (?P<hour>\d{2})
        :
        (?P<minute>\d{2})
        :
        (?P<second>\d{2})
        (?:\.(?P<fraction>\d+))?
        (?P<offset>Z|[+-]\d{2}:\d{2})?
        """,
        value,
        flags=re.VERBOSE,
    )

    if match is None:
        return None

    year = int(match.group("year"))

    # QuickTime verwendet 1904 als Nullpunkt.
    # Solche Werte gelten nicht als Aufnahmedatum.
    if year <= 1904:
        return None

    fraction = match.group("fraction") or ""
    microsecond = int(
        (fraction + "000000")[:6]
    )

    offset = match.group("offset")

    if offset == "Z":
        tzinfo = timezone.utc

    elif offset:
        sign = 1 if offset[0] == "+" else -1
        hours = int(offset[1:3])
        minutes = int(offset[4:6])

        from datetime import timedelta

        tzinfo = timezone(
            sign * timedelta(
                hours=hours,
                minutes=minutes,
            )
        )

    else:
        tzinfo = LOCAL_TIMEZONE

    try:
        return datetime(
            year=year,
            month=int(match.group("month")),
            day=int(match.group("day")),
            hour=int(match.group("hour")),
            minute=int(match.group("minute")),
            second=int(match.group("second")),
            microsecond=microsecond,
            tzinfo=tzinfo,
        )

    except ValueError:
        return None


def normalize_datetime(
    value: datetime,
) -> str:
    # Den am Medium gespeicherten Offset erhalten. Für die spätere
    # Tagesgruppierung zählt der lokale Aufnahmetag der Kamera, nicht
    # die Zeitzone des NAS. Vergleiche erfolgen separat in UTC.
    return value.isoformat()


def candidate_definition(
    media_type: str,
) -> list[tuple[str, int, str]]:
    if media_type == "video":
        return [
            # Fuji und viele aktuelle Kameras schreiben ein belastbares
            # EXIF-Aufnahmedatum einschließlich Offset in die Videodatei.
            # Dieses hat Vorrang; QuickTime bleibt Kontrollquelle.
            ("EXIF:ExifIFD:DateTimeOriginal", 10, "high"),
            ("EXIF:ExifIFD:CreateDate", 20, "high"),
            ("QuickTime:Keys:CreationDate", 30, "high"),
            ("QuickTime:CreationDate", 40, "high"),
            ("QuickTime:CreateDate", 50, "high"),
            ("QuickTime:Track1:MediaCreateDate", 60, "medium"),
            ("QuickTime:Track1:TrackCreateDate", 70, "medium"),
            ("XMP:XMP-xmp:CreateDate", 80, "medium"),
            ("File:System:FileCreateDate", 850, "low"),
            ("File:System:FileModifyDate", 900, "low"),
        ]

    if media_type in {
        "raw",
        "jpeg",
        "image",
        "xmp",
    }:
        return [
            ("EXIF:ExifIFD:DateTimeOriginal", 10, "high"),
            ("XMP:XMP-exif:DateTimeOriginal", 20, "high"),
            ("EXIF:ExifIFD:CreateDate", 30, "high"),
            ("XMP:XMP-xmp:CreateDate", 40, "medium"),
            ("EXIF:IFD0:ModifyDate", 100, "low"),
            ("File:System:FileCreateDate", 850, "low"),
            ("File:System:FileModifyDate", 900, "low"),
        ]

    return []


def run_exiftool(
    source_root: Path,
    *,
    progress_callback: Callable[[int, int], None] | None = None,
    cancellation_callback: Callable[[], None] | None = None,
) -> list[dict[str, Any]]:
    common = [
        "exiftool",
        "-json",
        "-G0:1",
        "-a",
        "-s",
        "-api",
        "QuickTimeUTC=1",
        "-DateTimeOriginal",
        "-OffsetTimeOriginal",
        "-SubSecTimeOriginal",
        "-SubSecTimeDigitized",
        "-CreateDate",
        "-Make",
        "-Model",
        "-ModifyDate",
        "-CreationDate",
        "-MediaCreateDate",
        "-MediaModifyDate",
        "-TrackCreateDate",
        "-TrackModifyDate",
        "-DateCreated",
        "-TimeCreated",
        "-FileCreateDate",
        "-FileModifyDate",
        "-FileName",
        "-Directory",
    ]

    def execute(
        command: list[str],
    ) -> list[dict[str, Any]]:
        if cancellation_callback is None:
            result = subprocess.run(
                command, check=False, capture_output=True, text=True,
            )
        else:
            # Nur den zu diesem Import gehörenden ExifTool-Kindprozess beenden.
            cancellation_callback()
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            try:
                while True:
                    cancellation_callback()
                    try:
                        out, err = process.communicate(timeout=0.5)
                        break
                    except subprocess.TimeoutExpired:
                        continue
                result = subprocess.CompletedProcess(command, process.returncode, out, err)
                cancellation_callback()
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.communicate(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.communicate()
                raise
        if result.returncode not in {0, 1}:
            raise MetadataError(
                "ExifTool konnte nicht ausgeführt werden: "
                + result.stderr.strip()
            )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise MetadataError(
                "ExifTool lieferte ungültiges JSON."
            ) from error
        if not isinstance(data, list):
            raise MetadataError(
                "ExifTool-Ausgabe besitzt ein unerwartetes Format."
            )
        return data

    if progress_callback is None:
        command = [
            *common,
            "-r",
            "-ext", "RAF",
            "-ext", "DNG",
            "-ext", "CR2",
            "-ext", "CR3",
            "-ext", "NEF",
            "-ext", "ARW",
            "-ext", "ORF",
            "-ext", "RW2",
            "-ext", "JPG",
            "-ext", "JPEG",
            "-ext", "PNG",
            "-ext", "TIF",
            "-ext", "TIFF",
            "-ext", "HEIC",
            "-ext", "HEIF",
            "-ext", "MOV",
            "-ext", "MP4",
            "-ext", "M4V",
            "-ext", "AVI",
            "-ext", "MTS",
            "-ext", "M2TS",
            "-ext", "XMP",
            str(source_root),
        ]
        return execute(command)

    paths = [
        path
        for path in sorted(source_root.rglob("*"))
        if path.is_file()
        and classify_media(path) != "other"
        and not should_ignore_source_path(
            source_root,
            path,
        )
    ]
    total = len(paths)
    if not paths:
        progress_callback(0, 0)
        return []

    entries: list[dict[str, Any]] = []
    # Ein Chunk begrenzt die Prozesszahl, liefert aber bei großen Karten
    # trotzdem sichtbaren, echten Fortschritt während der ExifTool-Phase.
    chunk_size = 160
    for offset in range(0, total, chunk_size):
        if cancellation_callback is not None:
            cancellation_callback()
        chunk = paths[
            offset : offset + chunk_size
        ]
        entries.extend(
            execute(
                [
                    *common,
                    *(str(path) for path in chunk),
                ]
            )
        )
        progress_callback(
            min(offset + len(chunk), total),
            total,
        )

    return entries

def _candidate_rule(
    tag_name: str,
    media_type: str,
) -> tuple[int, str] | None:
    """Classify date tags without depending on one ExifTool Group1 path."""
    parts = str(tag_name).split(":")
    if len(parts) < 2:
        return None
    group = parts[0]
    leaf = parts[-1]
    middle = parts[1:-1]

    if media_type == "video":
        if group == "EXIF" and leaf == "DateTimeOriginal":
            return (10, "high")
        if group == "EXIF" and leaf == "CreateDate":
            return (20, "high")
        if group == "QuickTime" and leaf == "CreationDate":
            return (30 if "Keys" in middle else 40, "high")
        if group == "QuickTime" and leaf == "CreateDate":
            return (50, "high")
        if group == "QuickTime" and leaf == "MediaCreateDate":
            return (60, "medium")
        if group == "QuickTime" and leaf == "TrackCreateDate":
            return (70, "medium")
        if group == "XMP" and leaf == "CreateDate":
            return (80, "medium")
        if group == "File" and leaf == "FileCreateDate":
            return (850, "low")
        if group == "File" and leaf == "FileModifyDate":
            return (900, "low")
        return None

    if media_type in {"raw", "jpeg", "image", "xmp"}:
        if group == "EXIF" and leaf == "DateTimeOriginal":
            return (10, "high")
        if group == "XMP" and leaf == "DateTimeOriginal":
            return (20, "high")
        if group == "EXIF" and leaf == "CreateDate":
            return (30, "high")
        if group == "XMP" and leaf == "CreateDate":
            return (40, "medium")
        if group == "EXIF" and leaf == "ModifyDate":
            return (100, "low")
        if group == "File" and leaf == "FileCreateDate":
            return (850, "low")
        if group == "File" and leaf == "FileModifyDate":
            return (900, "low")
    return None


_CANDIDATE_LABELS_DE = {
    "DateTimeOriginal": "Aufnahmezeit",
    "CreateDate": "Erstellungszeit",
    "CreationDate": "Aufnahme-/Erstellungszeit",
    "MediaCreateDate": "Medien-Erstellungszeit",
    "TrackCreateDate": "Spur-Erstellungszeit",
    "ModifyDate": "Änderungszeit",
    "FileCreateDate": "Datei-Erstellungszeit",
    "FileModifyDate": "Datei-Änderungszeit",
}


def _candidate_display(tag_name: str, confidence: str, priority: int) -> dict[str, Any]:
    leaf = str(tag_name).rsplit(":", 1)[-1]
    label = _CANDIDATE_LABELS_DE.get(leaf, leaf)
    trust = {"high": "hoch", "medium": "mittel", "low": "niedrig"}.get(
        str(confidence), "nicht nutzbar"
    )
    base = {"high": 90, "medium": 70, "low": 35}.get(str(confidence), 0)
    # Deterministisch: bei gleicher Vertrauensklasse gewinnt die etablierte
    # Kandidatenpriorität. Kein Modell/Heuristikdienst ist beteiligt.
    score = max(0, base - min(max(int(priority), 0), 999) // 100)
    return {
        "source_type": leaf,
        "label_de": label,
        "technical_tag": str(tag_name),
        "trust_label": trust,
        "trust_score": score,
    }


def build_candidates(
    metadata: dict[str, Any],
    media_type: str,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for tag_name, raw_value in sorted(metadata.items()):
        rule = _candidate_rule(str(tag_name), media_type)
        if rule is None or raw_value is None:
            continue
        priority, confidence = rule
        raw_text = str(raw_value).strip()

        # Real Exif subsecond metadata belongs to its photographic timestamp.
        # Never synthesize a fractional part from FPS, filenames or file mtime.
        leaf = str(tag_name).rsplit(":", 1)[-1]
        if str(tag_name).startswith("EXIF:") and leaf in {
            "DateTimeOriginal", "CreateDate"
        } and not re.search(r"\d{2}:\d{2}:\d{2}\.\d+", raw_text):
            fraction_leaf = (
                "SubSecTimeOriginal" if leaf == "DateTimeOriginal"
                else "SubSecTimeDigitized"
            )
            fraction = next(
                (
                    str(value).strip()
                    for key, value in metadata.items()
                    if str(key).startswith("EXIF:")
                    and str(key).endswith(":" + fraction_leaf)
                    and re.fullmatch(r"\d{1,9}", str(value).strip())
                ),
                None,
            )
            if fraction is not None:
                # Insert before a camera-supplied timezone, if present.
                raw_text = re.sub(
                    r"(Z|[+-]\d{2}:\d{2})$",
                    lambda m: "." + fraction + m.group(1),
                    raw_text,
                    count=1,
                ) if re.search(r"(Z|[+-]\d{2}:\d{2})$", raw_text) else raw_text + "." + fraction

        if (
            str(tag_name).startswith("EXIF:")
            and str(tag_name).rsplit(":", 1)[-1] in {"DateTimeOriginal", "CreateDate"}
            and not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", raw_text)
        ):
            offset = next(
                (
                    value
                    for key, value in metadata.items()
                    if str(key).startswith("EXIF:")
                    and str(key).endswith(":OffsetTimeOriginal")
                    and value
                ),
                None,
            )
            if offset:
                raw_text = raw_text + str(offset).strip()

        parsed = parse_exiftool_datetime(raw_text)

        effective_confidence = confidence if parsed is not None else "unusable"
        candidates.append({
            "metadata_group": str(tag_name).split(":", 1)[0],
            "tag_name": str(tag_name),
            "raw_value": raw_text,
            "normalized_datetime": (
                # Preserve a *real* explicitly recorded .000 subsecond. Python's
                # default isoformat() would silently remove it otherwise.
                parsed.isoformat(timespec="microseconds")
                if parsed is not None and re.search(
                    r"\d{2}:\d{2}:\d{2}\.\d+", raw_text
                )
                else normalize_datetime(parsed) if parsed is not None else None
            ),
            "priority": priority,
            "confidence": effective_confidence,
            "usable": parsed is not None,
            "is_selected": False,
            "conflicts_with_selected": False,
            **_candidate_display(str(tag_name), effective_confidence, priority),
        })

    candidates.sort(
        key=lambda candidate: (
            int(candidate["priority"]),
            str(candidate["tag_name"]),
        )
    )
    return candidates


def select_candidate(
    candidates: list[dict[str, Any]],
    media_type: str,
) -> tuple[
    str | None,
    str | None,
    str,
    bool,
]:
    usable = sorted(
        (
            candidate
            for candidate in candidates
            if candidate["usable"]
        ),
        key=lambda candidate: (
            candidate["priority"],
            candidate["tag_name"],
        ),
    )

    if not usable:
        return (
            None,
            None,
            "missing",
            False,
        )

    selected = usable[0]
    selected["is_selected"] = True

    selected_time = datetime.fromisoformat(
        selected["normalized_datetime"]
    )

    conflict = False

    for candidate in usable[1:]:
        # Reine Dateisystem-Fallbacks erzeugen keinen Konflikt
        # gegen echte Medienmetadaten.
        if candidate["confidence"] == "low":
            continue

        candidate_time = datetime.fromisoformat(
            candidate["normalized_datetime"]
        )

        difference = abs(
            (
                candidate_time.astimezone(timezone.utc)
                - selected_time.astimezone(timezone.utc)
            ).total_seconds()
        )

        # Video-Containerzeiten und Kamera-EXIF können sich durch den
        # Schreibabschluss des Clips um einige Sekunden unterscheiden.
        # Bis zwei Minuten gilt das als konsistent; bei Fotos bleiben
        # zwei Sekunden die Grenze.
        conflict_tolerance_seconds = (
            120
            if media_type == "video"
            else 2
        )

        if difference > conflict_tolerance_seconds:
            candidate["conflicts_with_selected"] = True
            conflict = True

    if conflict:
        confidence = "conflict"
    else:
        confidence = selected["confidence"]

    return (
        selected["normalized_datetime"],
        selected["tag_name"],
        confidence,
        conflict,
    )


def analyze_tree(
    source_root: Path,
    *,
    include_other: bool = True,
    progress_callback: Callable[[int, int], None] | None = None,
    cancellation_callback: Callable[[], None] | None = None,
) -> dict[str, Any]:
    if not source_root.is_dir():
        raise MetadataError(
            f"Quellordner fehlt: {source_root}"
        )

    exif_entries = run_exiftool(
        source_root,
        progress_callback=progress_callback,
        cancellation_callback=cancellation_callback,
    )

    metadata_by_path: dict[str, dict[str, Any]] = {}

    for entry in exif_entries:
        source_file = entry.get(
            "SourceFile"
        )

        if not source_file:
            continue

        source_path = Path(source_file)
        if should_ignore_source_path(source_root, source_path):
            continue
        metadata_by_path[str(source_path.resolve())] = entry

    files: list[dict[str, Any]] = []

    for path in sorted(source_root.rglob("*")):
        if cancellation_callback is not None:
            cancellation_callback()
        if should_ignore_source_path(source_root, path):
            continue
        if not path.is_file():
            continue

        media_type = classify_media(path)

        if not include_other and media_type == "other":
            continue

        relative = path.relative_to(
            source_root
        ).as_posix()

        metadata = metadata_by_path.get(
            str(path.resolve()),
            {},
        )

        candidates = build_candidates(
            metadata,
            media_type,
        )

        (
            selected_time,
            selected_source,
            confidence,
            conflict,
        ) = select_candidate(
            candidates,
            media_type,
        )

        files.append({
            "relative_path": relative,
            "filename": path.name,
            "extension": path.suffix.lower(),
            "media_type": media_type,
            "family_key": family_key(
                source_root,
                path,
            ),
            "size_bytes": path.stat().st_size,
            "selected_capture_time": selected_time,
            "selected_capture_source": selected_source,
            "capture_time_confidence": confidence,
            "metadata_conflict": conflict,
            "camera_make": metadata.get("EXIF:IFD0:Make")
                or metadata.get("EXIF:ExifIFD:Make")
                or metadata.get("QuickTime:Make"),
            "camera_model": metadata.get("EXIF:IFD0:Model")
                or metadata.get("EXIF:ExifIFD:Model")
                or metadata.get("QuickTime:Model"),
            "inherited_from_family": False,
            "review_required": confidence in {
                "low",
                "conflict",
                "missing",
            },
            "metadata_candidates": candidates,
        })

    families: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for record in files:
        families[
            record["family_key"]
        ].append(record)

    family_results: list[dict[str, Any]] = []

    for key in sorted(families):
        members = families[key]

        strong_members = [
            member
            for member in members
            if member["capture_time_confidence"]
            in {
                "high",
                "medium",
            }
            and member["selected_capture_time"]
        ]

        strong_times = {
            member["selected_capture_time"]
            for member in strong_members
        }

        # RAF and JPEG from the same original family may expose different
        # precision: a precise 17:11:37.025 and a seconds-only 17:11:37.
        # Keep the trustworthy precision instead of misclassifying the entire
        # family as contradictory. Two *different* precise instants still
        # require manual review.
        if len(strong_times) > 1:
            try:
                parsed_times = {
                    raw: datetime.fromisoformat(str(raw))
                    for raw in strong_times
                }
                precise = [
                    raw for raw in strong_times
                    if re.search(r"T\\d{2}:\\d{2}:\\d{2}\\.\\d+", raw)
                ]
                precise_instants = {parsed_times[raw] for raw in precise}
                if len(precise_instants) == 1 and all(
                    parsed_times[raw].replace(microsecond=0)
                    == parsed_times[precise[0]].replace(microsecond=0)
                    for raw in strong_times
                ):
                    strong_times = {sorted(precise)[0]}
                elif len(set(parsed_times.values())) == 1:
                    strong_times = {sorted(
                        strong_times,
                        key=lambda raw: (
                            0 if re.search(r"T\\d{2}:\\d{2}:\\d{2}\\.\\d+", raw) else 1,
                            raw,
                        )
                    )[0]}
            except (ValueError, TypeError):
                pass

        if len(strong_times) == 1:
            family_time = next(
                iter(strong_times)
            )

            for member in members:
                if (
                    member["capture_time_confidence"]
                    in {
                        "low",
                        "missing",
                    }
                    and member["media_type"]
                    in {
                        "raw",
                        "jpeg",
                        "image",
                        "xmp",
                    }
                ):
                    member[
                        "selected_capture_time"
                    ] = family_time

                    member[
                        "selected_capture_source"
                    ] = "family_inheritance"

                    member[
                        "capture_time_confidence"
                    ] = "high"

                    member[
                        "inherited_from_family"
                    ] = True

                    member[
                        "review_required"
                    ] = False

            family_confidence = "high"
            family_status = "complete"

        elif len(strong_times) > 1:
            family_time = None
            family_confidence = "conflict"
            family_status = "review_required"

            for member in members:
                member["review_required"] = True

        else:
            family_time = None

            confidences = {
                member["capture_time_confidence"]
                for member in members
            }

            if "conflict" in confidences:
                family_confidence = "conflict"
                family_status = "review_required"

            elif "low" in confidences:
                family_confidence = "low"
                family_status = "review_required"

            else:
                family_confidence = "missing"
                family_status = "review_required"

        family_results.append({
            "family_key": key,
            "member_count": len(members),
            "selected_capture_time": family_time,
            "capture_time_confidence":
                family_confidence,
            "status": family_status,
            "members": [
                member["relative_path"]
                for member in members
            ],
        })

    summary = {
        "file_count": len(files),
        "family_count": len(family_results),
        "high": sum(
            record["capture_time_confidence"]
            == "high"
            for record in files
        ),
        "medium": sum(
            record["capture_time_confidence"]
            == "medium"
            for record in files
        ),
        "low": sum(
            record["capture_time_confidence"]
            == "low"
            for record in files
        ),
        "conflict": sum(
            record["capture_time_confidence"]
            == "conflict"
            for record in files
        ),
        "missing": sum(
            record["capture_time_confidence"]
            == "missing"
            for record in files
        ),
        "review_required": sum(
            bool(record["review_required"])
            for record in files
        ),
    }

    return {
        "source_root": str(source_root),
        "summary": summary,
        "families": family_results,
        "files": files,
    }
