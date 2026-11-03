from __future__ import annotations

from app.managed_directory_names import directory_path as managed_directory_path

from app.root_operations import protect, validate_active_roots



from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import math
import os
import re
import hashlib
import shutil
import time

from app.metadata import analyze_tree, classify_media
from app.source_filter import should_ignore_source_path
from app.import_publication import import_identity, publish_import_file, rollback_import_file
from app.pipeline import (
    PipelineError,
    append_log,
    archive_protocol_directory,
    atomic_json,
    copy_and_verify,
    sha256_file,
    source_manifest,
)
from app.workspace_layout import (
    backup_root as workspace_backup_root,
    resolve_library_work_root,
)


MEDIA_TYPES = {
    "raw",
    "jpeg",
    "image",
    "video",
    "xmp",
}


ProgressCallback = Callable[[str, str, int, int, str], None]
MetadataCallback = Callable[[dict[str, Any], dict[str, str]], None]
PathCallback = Callable[[list[dict[str, Any]]], None]
IdentityCallback = Callable[[str, str], None]
ImportHistoryCallback = Callable[[list[dict[str, Any]]], None]
FamilyAdmissionCallback = Callable[[dict[str, Any], dict[str, str], dict[str, int]], dict[str, Any]]
DestinationDirectoryCallback = Callable[[str], Path | None]
CancellationCallback = Callable[[], bool]


class ImportCancelled(PipelineError):
    pass



def preflight_folder_import(
    source: Path,
    workspace: Path,
    pool_probe_path: Path,
    *,
    processing_buffer_percent: int,
    safety_reserve_gib: int,
    max_scan_seconds: float = 8.0,
    max_entries: int = 200000,
    cancellation_callback: CancellationCallback | None = None,
    allow_workspace_source: bool = False,
) -> dict[str, int]:
    """Vor einer Jobannahme nur Dateigrößen ermitteln, niemals SHA-256 lesen.

    Ein unüberschaubarer NAS-Baum wird kontrolliert abgewiesen, damit der
    HTTP-Worker keine unbegrenzte Verzeichnissuche ausführt. Quoten werden
    über die wirksam verfügbare Kapazität des tatsächlichen Schreibpfads
    abgefragt; ein späterer Check schützt vor zwischenzeitlichen Änderungen.
    """
    source = source.resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    if (source == workspace or source in workspace.parents
            or (workspace in source.parents and not allow_workspace_source)):
        raise PipelineError("Quelle und Kamera-Arbeitsbereich dürfen nicht ineinander liegen.")
    started = time.monotonic()
    count = 0
    bytes_total = 0
    stack = [source]
    while stack:
        if cancellation_callback is not None and cancellation_callback():
            raise ImportCancelled("Import vor Beginn abgebrochen.")
        if time.monotonic() - started > max_scan_seconds:
            raise PipelineError(
                "Die Quelle ist für eine schnelle Speicherprüfung zu umfangreich. "
                "Bitte einen kleineren Unterordner auswählen."
            )
        current = stack.pop()
        with os.scandir(current) as entries:
            for item in entries:
                count += 1
                if count > max_entries:
                    raise PipelineError(
                        "Die Importquelle umfasst zu viele Einträge für eine sichere Vorprüfung. "
                        "Bitte einen kleineren Unterordner auswählen."
                    )
                if item.is_symlink():
                    raise PipelineError("Symbolische Links sind als Importquelle nicht erlaubt.")
                path = Path(item.path)
                if should_ignore_source_path(source, path):
                    continue
                if item.is_dir(follow_symlinks=False):
                    stack.append(path)
                elif item.is_file(follow_symlinks=False):
                    bytes_total += item.stat(follow_symlinks=False).st_size
                else:
                    raise PipelineError("Unzulässiger Dateityp in der Importquelle.")
    reserve = safety_reserve_gib * 1024 ** 3
    required = bytes_total + math.ceil(bytes_total * processing_buffer_percent / 100) + reserve
    workspace_fs = os.statvfs(workspace)
    pool_fs = os.statvfs(pool_probe_path)
    workspace_free = workspace_fs.f_bavail * workspace_fs.f_frsize
    pool_free = pool_fs.f_bavail * pool_fs.f_frsize
    if min(workspace_free, pool_free) < required:
        raise PipelineError(
            "Nicht genügend freier Speicher für diesen Import: benötigt "
            f"{required / 1024**3:.1f} GiB einschließlich Puffer und Sicherheitsreserve; "
            f"im Arbeitsbereich {workspace_free / 1024**3:.1f} GiB verfügbar. "
            "Eventuelle Dataset-Quoten sind maßgeblich."
        )
    return {
        "files_and_directories": count,
        "source_bytes": bytes_total,
        "required_bytes": required,
        "workspace_available_bytes": workspace_free,
        "pool_available_bytes": pool_free,
    }


def quick_source_signature(
    source: Path,
    cancellation_callback: CancellationCallback | None = None,
) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.rglob("*")):
        if cancellation_callback is not None and cancellation_callback():
            raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
        if should_ignore_source_path(source, path):
            continue
        if path.is_symlink() or not path.is_file():
            continue
        stat = path.stat()
        relative = path.relative_to(source).as_posix()
        digest.update(relative.encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def manifest_fingerprint(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: str(item["relative_path"])):
        digest.update(str(entry["relative_path"]).encode("utf-8", "surrogateescape"))
        digest.update(b"\0")
        digest.update(str(int(entry["size_bytes"])).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(entry["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def partition_import_entries(
    entries: list[dict[str, Any]],
    known_hashes: set[tuple[int, str]] | None = None,
    duplicate_origins: dict[tuple[int, str], dict[str, Any]] | None = None,
    known_sha256: set[str] | None = None,
    duplicate_origins_by_sha: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Split one source manifest into new files and exact known duplicates.

    SHA-256 is the stable identity of the original imported bytes. 0.42.0
    deliberately keeps the historical size+SHA fast path, but also accepts an
    exact original SHA match when legacy metadata corrections left an
    unreliable source_size_bytes backfill behind.
    """
    known = known_hashes or set()
    known_sha = {str(value) for value in (known_sha256 or set()) if str(value)}
    origins = duplicate_origins or {}
    origins_by_sha = duplicate_origins_by_sha or {}
    new_entries: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for raw in entries:
        entry = dict(raw)
        sha = str(entry["sha256"])
        key = (int(entry["size_bytes"]), sha)
        if key not in known and sha not in known_sha:
            new_entries.append(entry)
            continue
        duplicates.append(entry)
        origin = dict(origins.get(key) or origins_by_sha.get(sha) or {})
        details.append({
            "relative_path": str(entry["relative_path"]),
            "size_bytes": int(entry["size_bytes"]),
            "sha256": str(entry["sha256"]),
            "existing_job_id": str(origin.get("job_id") or ""),
            "existing_source_label": str(origin.get("source_volume_label") or ""),
            "existing_relative_path": str(
                origin.get("current_relative_path")
                or origin.get("original_relative_path")
                or ""
            ),
            "existing_filename": str(origin.get("original_filename") or ""),
        })
    return new_entries, duplicates, details


def normalize_device_name(
    make: str | None,
    model: str | None,
) -> tuple[str, str]:
    raw_make = " ".join(str(make or "").strip().split())
    raw_model = " ".join(str(model or "").strip().split())
    make_upper = raw_make.upper()

    if make_upper in {"FUJIFILM", "FUJI PHOTO FILM CO., LTD."}:
        display = f"Fuji {raw_model}".strip()
    elif make_upper == "APPLE":
        display = raw_model or "Apple"
    elif raw_make and raw_model:
        if raw_model.lower().startswith(raw_make.lower()):
            display = raw_model
        else:
            display = f"{raw_make} {raw_model}"
    else:
        display = raw_model or raw_make or "Unbekanntes-Gerät"

    display = " ".join(display.split())
    token = re.sub(r"[^0-9A-Za-zÄÖÜäöüß+-]+", "-", display)
    token = re.sub(r"-+", "-", token).strip("-")

    return display, token or "Unbekanntes-Gerät"


def _family_capture_time(
    family: dict[str, Any],
    members: list[dict[str, Any]],
) -> str | None:
    value = family.get("selected_capture_time")
    if value:
        return str(value)

    values = {
        str(member["selected_capture_time"])
        for member in members
        if member.get("selected_capture_time")
        and member.get("capture_time_confidence") in {"high", "medium"}
    }

    if len(values) == 1:
        return next(iter(values))

    return None


def _destination_is_free(
    shared_root: Path,
    relative_paths: list[Path],
    reserved: set[str],
) -> bool:
    for relative in relative_paths:
        key = relative.as_posix()
        if key in reserved:
            return False
        target = shared_root / relative
        if target.exists() or target.is_symlink():
            return False
    return True


def build_folder_import_plan(
    entries: list[dict[str, Any]],
    analysis: dict[str, Any],
    shared_root: Path,
    destination_directory_callback: DestinationDirectoryCallback | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entry_by_path = {
        str(entry["relative_path"]): entry
        for entry in entries
    }

    files = [
        record
        for record in analysis.get("files", [])
        if str(record.get("media_type")) in MEDIA_TYPES
    ]

    family_by_key = {
        str(family["family_key"]): family
        for family in analysis.get("families", [])
    }

    members_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in files:
        members_by_family[str(record["family_key"])].append(record)

    from app.managed_directory_names import directory_name
    undated_name = directory_name(shared_root, "undated")

    # Read each target directory once: an incremental import must consider
    # existing media, but may not silently rename existing or archived files.
    existing_stems_by_directory: dict[str, set[str]] = {}
    def existing_stems(directory: Path) -> set[str]:
        key = directory.as_posix()
        if key not in existing_stems_by_directory:
            stems: set[str] = set()
            target = shared_root / directory
            if target.is_dir() and not target.is_symlink():
                with os.scandir(target) as children:
                    for child in children:
                        if child.is_file(follow_symlinks=False):
                            stems.add(Path(child.name).stem.casefold())
            existing_stems_by_directory[key] = stems
        return existing_stems_by_directory[key]

    def location_for(capture: str) -> Path:
        value = datetime.fromisoformat(capture)
        directory = Path(value.strftime("%Y")) / value.strftime("%Y-%m-%d")
        if destination_directory_callback is not None:
            resolved = destination_directory_callback(capture[:19])
            if resolved is not None:
                directory = Path(resolved)
                if directory.is_absolute() or ".." in directory.parts:
                    raise PipelineError(
                        "Unsicherer kanonischer Zielordner für Import: " + str(directory)
                    )
        return directory

    # Counts are per target directory + camera + whole camera-local second.
    # Different models in the same second are not a naming collision.
    burst_groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for key, source_members in members_by_family.items():
        family = family_by_key.get(key, {})
        capture = _family_capture_time(family, source_members)
        confidence = str(family.get("capture_time_confidence")
                         or source_members[0].get("capture_time_confidence") or "missing")
        if not capture or confidence in {"low", "conflict", "missing"}:
            continue
        camera = next(
            (member for member in source_members
             if member.get("camera_make") or member.get("camera_model")),
            source_members[0],
        )
        _, token = normalize_device_name(camera.get("camera_make"), camera.get("camera_model"))
        group = (location_for(capture).as_posix().casefold(), capture[:19], token.casefold())
        burst_groups[group].add(key)
    reserved: set[str] = set()
    plan: list[dict[str, Any]] = []
    review_family_count = 0
    burst_family_count = 0
    burst_without_subseconds_count = 0
    device_counts: dict[str, int] = defaultdict(int)

    for family_key in sorted(members_by_family):
        members = sorted(
            members_by_family[family_key],
            key=lambda item: str(item["relative_path"]),
        )
        family = family_by_key.get(family_key, {})
        capture_value = _family_capture_time(family, members)
        confidence = str(
            family.get("capture_time_confidence")
            or members[0].get("capture_time_confidence")
            or "missing"
        )

        device_member = next(
            (
                member
                for member in members
                if member.get("camera_make") or member.get("camera_model")
            ),
            members[0],
        )
        device_display, device_token = normalize_device_name(
            device_member.get("camera_make"),
            device_member.get("camera_model"),
        )
        device_counts[device_display] += 1

        needs_review = (
            not capture_value
            or confidence in {"low", "conflict", "missing"}
        )

        if needs_review:
            review_family_count += 1
            family_targets: list[Path] = []
            for member in members:
                source_relative = str(member["relative_path"])
                original = Path(source_relative)
                candidate = Path(undated_name) / original.name
                index = 0
                while not _destination_is_free(
                    shared_root,
                    [candidate],
                    reserved,
                ):
                    index += 1
                    candidate = (
                        Path(undated_name)
                        / f"{original.stem}_{index:03d}{original.suffix}"
                    )
                reserved.add(candidate.as_posix())
                family_targets.append(candidate)

            for member, destination in zip(members, family_targets, strict=True):
                source_relative = str(member["relative_path"])
                entry = entry_by_path[source_relative]
                plan.append({
                    "source_relative_path": source_relative,
                    "destination_relative_path": destination.as_posix(),
                    "family_key": family_key,
                    "size_bytes": int(entry["size_bytes"]),
                    "sha256": str(entry["sha256"]),
                    "selected_capture_time": capture_value,
                    "capture_time_confidence": confidence,
                    "device_display_name": device_display,
                    "device_token": device_token,
                    "needs_review": True,
                })
            continue

        capture = datetime.fromisoformat(str(capture_value))
        stamp = capture.strftime("%Y%m%d_%H%M%S")
        base = stamp + "_" + device_token
        destination_directory = location_for(str(capture_value))
        group = (destination_directory.as_posix().casefold(),
                 str(capture_value)[:19], device_token.casefold())
        stems = existing_stems(destination_directory)
        burst_prefix = re.compile(
            r"^" + re.escape(stamp) + r"\d{3}_" + re.escape(device_token)
            + r"(?:_\d{3})?$", flags=re.IGNORECASE,
        )
        existing_burst = base.casefold() in stems or any(
            burst_prefix.fullmatch(stem) for stem in stems
        )
        burst = len(burst_groups.get(group, ())) > 1 or existing_burst
        fractional = re.search(
            r"\.(\d+)(?=Z|[+-]\d{2}:\d{2}|$)", str(capture_value)
        )
        if burst:
            burst_family_count += 1
            if fractional:
                # Exactly three real millisecond digits, not hundredths.
                base = f"{stamp}{capture.microsecond // 1000:03d}_{device_token}"
            else:
                # EXIF lacks a fractional capture time: a clearly marked
                # sequence fallback, never a fabricated millisecond value.
                burst_without_subseconds_count += 1
                base += "_Burst"

        suffix_index = 0 if fractional or not burst else 1
        while True:
            family_base = base if suffix_index == 0 else f"{base}_{suffix_index:03d}"
            relative_paths = [
                destination_directory
                / (family_base + Path(str(member["filename"])).suffix)
                for member in members
            ]
            if _destination_is_free(shared_root, relative_paths, reserved):
                break
            suffix_index += 1

        for relative in relative_paths:
            reserved.add(relative.as_posix())

        for member, destination in zip(members, relative_paths, strict=True):
            source_relative = str(member["relative_path"])
            entry = entry_by_path[source_relative]
            plan.append({
                "source_relative_path": source_relative,
                "destination_relative_path": destination.as_posix(),
                "family_key": family_key,
                "size_bytes": int(entry["size_bytes"]),
                "sha256": str(entry["sha256"]),
                "selected_capture_time": capture_value,
                "capture_time_confidence": confidence,
                "device_display_name": device_display,
                "device_token": device_token,
                "needs_review": False,
            })

    included_paths = {
        str(item["source_relative_path"])
        for item in plan
    }
    excluded = [
        entry
        for entry in entries
        if str(entry["relative_path"]) not in included_paths
    ]

    dated_capture_times = sorted({
        str(item.get("selected_capture_time") or "")[:19]
        for item in plan
        if str(item.get("selected_capture_time") or "").strip()
    })
    summary = {
        "media_file_count": len(plan),
        "excluded_file_count": len(excluded),
        "family_count": len(members_by_family),
        "review_family_count": review_family_count,
        "burst_family_count": burst_family_count,
        "burst_without_subseconds_count": burst_without_subseconds_count,
        "devices": [
            {"name": name, "family_count": count}
            for name, count in sorted(device_counts.items())
        ],
        "capture_start_date": (
            dated_capture_times[0][:10] if dated_capture_times else None
        ),
        "capture_end_date": (
            dated_capture_times[-1][:10] if dated_capture_times else None
        ),
    }

    return plan, excluded, summary


def _remove_empty_directories(root: Path) -> None:
    if not root.exists():
        return
    directories = sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for directory in directories:
        try:
            validate_active_roots()
            directory.rmdir()
        except OSError:
            pass


def remove_excluded_files(
    temporary_original: Path,
    excluded: list[dict[str, Any]],
) -> None:
    for entry in excluded:
        relative = Path(str(entry["relative_path"]))
        path = temporary_original / relative
        if not path.is_file():
            raise PipelineError(
                f"Ausgeschlossene Sicherungsdatei fehlt: {relative.as_posix()}"
            )
        if path.stat().st_size != int(entry["size_bytes"]):
            raise PipelineError(
                f"Größenabweichung bei ausgeschlossener Datei: {relative.as_posix()}"
            )
        if sha256_file(path) != str(entry["sha256"]):
            raise PipelineError(
                f"SHA-256-Abweichung bei ausgeschlossener Datei: {relative.as_posix()}"
            )
        validate_active_roots()
        path.unlink()

    _remove_empty_directories(temporary_original)


def move_import_into_workspace(
    temporary_original: Path,
    shared_root: Path,
    plan: list[dict[str, Any]],
    *,
    post_move_callback: PathCallback | None = None,
    cancellation_callback: CancellationCallback | None = None,
    ownership_record: dict | None = None,
) -> None:
    if not temporary_original.is_dir() and ownership_record is None:
        raise PipelineError(
            f"Temporäre Sicherung fehlt: {temporary_original}"
        )

    validate_active_roots()
    shared_root.mkdir(parents=True, exist_ok=True)
    if temporary_original.exists() and int(temporary_original.stat().st_dev) != int(shared_root.stat().st_dev):
        raise PipelineError(
            "Temporäre Sicherung und Arbeitsbereich liegen nicht auf demselben Dateisystem."
        )

    from app.trash_selective import _atomic_json, _sync_dir
    # The original inode survives an exclusive same-filesystem rename. Persist ownership
    # before the first move, including the gap before the path callback.
    journal = temporary_original.parent / "move-journal.json"
    from app.import_recovery import read_record, relative
    if ownership_record is None and (journal.exists() or journal.is_symlink()):
        ownership_record = read_record(journal)
    ownership = []
    supplied = (ownership_record or {}).get('files', [])
    if ownership_record is not None and (ownership_record.get('format') != 1
            or ownership_record.get('root') != str(shared_root.resolve()) or len(supplied) != len(plan)):
        raise PipelineError('import_recovery_journal_mismatch: '+str(journal))
    for index,item in enumerate(plan):
        source = temporary_original / relative(item['source_relative_path'])
        destination = shared_root / relative(item['destination_relative_path'])
        if ownership_record is None:
            owned = {**item,'inode':import_identity(source,item)}
        else:
            owned = supplied[index]
            if any(owned.get(k) != item.get(k) for k in ('source_relative_path','destination_relative_path','sha256','size_bytes')):
                raise PipelineError('import_recovery_plan_changed: '+str(source))
            present = [p for p in (source,destination) if p.exists() or p.is_symlink()]
            if len(present) != 1 or import_identity(present[0],owned) != owned.get('inode'):
                raise PipelineError('import_recovery_ownership_ambiguous: '+str(source))
        ownership.append(owned)
    if ownership_record is None:
        _atomic_json(journal, dict(format=1, root=str(shared_root.resolve()), files=ownership))
        _sync_dir(journal.parent.parent)
    moved: list[tuple[Path, Path, dict]] = []
    try:
        for item, owned in zip(plan, ownership, strict=True):
            if cancellation_callback is not None and cancellation_callback():
                raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
            source = temporary_original / str(item["source_relative_path"])
            destination = shared_root / str(item["destination_relative_path"])
            if ownership_record is not None and not source.exists() and destination.exists():
                moved.append((source,destination,owned))
                continue
            if not source.is_file():
                raise PipelineError(f"Quelldatei fehlt: {source}")
            if destination.exists() or destination.is_symlink():
                raise PipelineError(f"Zieldatei existiert bereits: {destination}")
            # Preserve the F14 root binding and F12 exclusive publication.
            validate_active_roots()
            moved.append((source, destination, owned))
            publish_import_file(source, destination, owned)

        for item in plan:
            if cancellation_callback is not None and cancellation_callback():
                raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
            destination = shared_root / str(item["destination_relative_path"])
            if not destination.is_file():
                raise PipelineError(f"Zieldatei fehlt: {destination}")
            if destination.stat().st_size != int(item["size_bytes"]):
                raise PipelineError(f"Größenabweichung am Ziel: {destination}")
            if sha256_file(destination) != str(item["sha256"]):
                raise PipelineError(f"SHA-256-Abweichung am Ziel: {destination}")

        remaining = [
            path
            for path in temporary_original.rglob("*")
            if path.is_file()
        ]
        if remaining:
            raise PipelineError(
                "Temporäre Sicherung enthält nach der Überführung noch Dateien."
            )

        # SQLite wird erst nach vollständig geprüfter Dateibewegung
        # aktualisiert. Scheitert die Transaktion, stellt der folgende
        # Except-Block alle Dateien an ihren Sicherungspfad zurück.
        if cancellation_callback is not None and cancellation_callback():
            raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
        if post_move_callback is not None:
            post_move_callback(plan)
        if temporary_original.exists():
            _remove_empty_directories(temporary_original)
            validate_active_roots()
            temporary_original.rmdir()
    except Exception:
        rollback_errors: list[str] = []
        for source, destination, owned in reversed(moved):
            try:
                validate_active_roots()
                rollback_import_file(source, destination, owned)
            except Exception as error:
                rollback_errors.append(f"{destination} → {source}: {error}")
        if rollback_errors:
            raise PipelineError(
                "Ordnerimport fehlgeschlagen; Rollback unvollständig: "
                + " | ".join(rollback_errors)
            )
        raise


def discard_import_moves(central: Path, job_id: str, rows: list, *, verify_callback=None) -> int:
    """Preflight every owned copy before deleting any; retain unknown bytes."""
    import json
    from app.trash_restore import _relative, _source
    from app.trash_selective import _sync_dir
    journal = central / ".incoming" / job_id / "move-journal.json"
    candidates = {}
    known = {str(row["original_relative_path"]): row for row in rows}
    if journal.exists() or journal.is_symlink():
        if journal.is_symlink() or not journal.is_file():
            raise PipelineError("Unsicheres Import-Movejournal.")
        data = json.loads(journal.read_text())
        if data.get("format") != 1 or data.get("root") != str(central.resolve()) or not isinstance(data.get("files"), list):
            raise PipelineError("Import-Movejournal passt nicht zum Bestand.")
        for item in data["files"]:
            row = known.get(str(item["source_relative_path"]))
            if row is None or int(row["size_bytes"]) != item["size_bytes"] or str(row["sha256"]) != item["sha256"]:
                raise PipelineError("Import-Movejournal passt nicht zum Katalog.")
            rel = _relative(item["destination_relative_path"])
            candidate = central / rel
            if candidate.exists() or candidate.is_symlink():
                candidate = _source(central, rel)
                info = candidate.stat()
                if [info.st_dev, info.st_ino] != item["inode"]:
                    raise PipelineError("Importziel besitzt keinen nachgewiesenen Besitz.")
                candidates[str(rel)] = (candidate, item["size_bytes"], item["sha256"])
    for row in rows:
        if row["current_root_kind"] != "shared_workspace": continue
        rel = _relative(str(row["current_relative_path"]))
        candidate = central / rel
        if candidate.exists() or candidate.is_symlink():
            candidate = _source(central, rel)
            candidates[str(rel)] = (candidate, int(row["size_bytes"]), str(row["sha256"] or ""))
    for path, size, sha in candidates.values():
        if verify_callback is not None:
            verify_callback(path, size, sha)
        elif not sha or path.stat().st_size != size or sha256_file(path) != sha:
            raise PipelineError("Importdatei wurde verändert; Bereinigung gesperrt: " + str(path))
    for path, size, sha in candidates.values():
        validate_active_roots()
        path.unlink()
        _sync_dir(path.parent)
    return len(candidates)


@protect(workspace_arg='workspace', database_arg='None', kind='import', error_type=PipelineError)
def run_folder_import_job(
    *,
    source: Path,
    workspace: Path,
    pool_probe_path: Path,
    log_dir: Path,
    processing_buffer_percent: int,
    safety_reserve_gib: int,
    job_id: str,
    progress_callback: ProgressCallback | None = None,
    metadata_callback: MetadataCallback | None = None,
    path_callback: PathCallback | None = None,
    identity_callback: IdentityCallback | None = None,
    imported_hashes: set[tuple[int, str]] | None = None,
    duplicate_origins: dict[tuple[int, str], dict[str, Any]] | None = None,
    imported_sha256: set[str] | None = None,
    duplicate_origins_by_sha: dict[str, dict[str, Any]] | None = None,
    import_history_callback: ImportHistoryCallback | None = None,
    family_admission_callback: FamilyAdmissionCallback | None = None,
    destination_directory_callback: DestinationDirectoryCallback | None = None,
    work_root: Path | None = None,
    central_stock: bool = False,
    allow_workspace_source: bool = False,
    cancellation_callback: CancellationCallback | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone()

    def check_cancelled() -> None:
        if cancellation_callback is not None and cancellation_callback():
            raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")

    def progress(
        state: str,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        check_cancelled()
        if progress_callback is not None:
            progress_callback(state, stage, current, total, message)

    if not source.is_dir():
        raise PipelineError(f"Importquelle fehlt: {source}")
    source_resolved = source.resolve()
    workspace_resolved = workspace.resolve()
    source_inside_workspace = workspace_resolved in source_resolved.parents
    workspace_inside_source = source_resolved in workspace_resolved.parents
    if (
        source_resolved == workspace_resolved
        or workspace_inside_source
        or (source_inside_workspace and not allow_workspace_source)
    ):
        raise PipelineError(
            "Importquelle und Arbeitsbereich dürfen nicht ineinander liegen."
        )

    backups_root = workspace_backup_root(workspace)
    if central_stock:
        destination_root = backups_root
        temporary_job_root = backups_root / ".incoming" / job_id
    else:
        destination_root = resolve_library_work_root(
            workspace,
            work_root,
        )
        temporary_job_root = backups_root / job_id
    # Keep the historic local variable for the mature import pipeline below.
    # In 0.31.1 it points at the central stock for real camera imports.
    work_root = destination_root
    temporary_original = temporary_job_root / "Original"
    temporary_protocol = managed_directory_path(temporary_job_root, "import_protocol")
    permanent_protocol = log_dir / "backups" / job_id
    status_path = temporary_protocol / "status.json"
    manifest_path = temporary_protocol / "manifest.json"
    snapshot_path = temporary_protocol / "snapshot.json"
    plan: list[dict[str, Any]] = []
    committed_plan: list[dict[str, Any]] = []

    if temporary_job_root.exists():
        raise PipelineError(f"Temporärer Sicherungsbestand existiert bereits: {temporary_job_root}")
    if permanent_protocol.exists():
        raise PipelineError(f"Protokollziel existiert bereits: {permanent_protocol}")

    validate_active_roots()
    temporary_protocol.mkdir(parents=True)
    status: dict[str, Any] = {
        "schema_version": 3,
        "job_id": job_id,
        "simulation": False,
        "import_mode": "folder",
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "stage": "starting",
        "state": "running",
        "source_path": str(source),
        "lifecycle": {
            "temporary_backup": str(temporary_original),
            "central_stock": str(work_root) if central_stock else None,
            "shared_workspace": str(work_root) if not central_stock else None,
            "protocol_archive": str(permanent_protocol),
        },
    }
    atomic_json(status_path, status)

    try:
        progress("copying", "starting", 0, 0, "Ordnerimport wird vorbereitet.")
        progress(
            "copying",
            "source_manifest",
            0,
            1,
            "Quelle wird inventarisiert und per SHA-256 erfasst.",
        )
        # Zuerst ein begrenzter Größen-Scan, bevor irgendeine Datei gehasht wird.
        preflight_folder_import(
            source, workspace, pool_probe_path,
            processing_buffer_percent=processing_buffer_percent,
            safety_reserve_gib=safety_reserve_gib,
            cancellation_callback=cancellation_callback,
            allow_workspace_source=allow_workspace_source,
        )
        all_entries = source_manifest(
            source,
            progress_callback=lambda current, total: progress(
                "copying",
                "source_manifest",
                current,
                max(total, 1),
                "Quelldateien werden inventarisiert und per SHA-256 erfasst.",
            ),
            cancellation_callback=check_cancelled,
        )
        check_cancelled()
        source_signature = quick_source_signature(source, cancellation_callback)
        source_fingerprint = manifest_fingerprint(all_entries)
        if identity_callback is not None:
            identity_callback(source_signature, source_fingerprint)

        entries, already_imported, duplicate_details = partition_import_entries(
            all_entries,
            imported_hashes,
            duplicate_origins,
            imported_sha256,
            duplicate_origins_by_sha,
        )
        if already_imported and not any(classify_media(Path(item["relative_path"])) in MEDIA_TYPES for item in entries):
            # A verified duplicate-only recheck is a successful no-op. Preserve
            # per-card history even when no bytes need to be published.
            if import_history_callback is not None:
                import_history_callback(already_imported)
            status.update({"state": "success", "stage": "completed", "temporary_backup_removed": True,
                           "source": {"file_count": 0, "total_source_file_count": len(all_entries),
                                      "duplicate_file_count": len(already_imported), "already_imported_file_count": len(already_imported),
                                      "new_file_count": 0, "signature": source_signature, "fingerprint": source_fingerprint,
                                      "file_history_complete": True},
                           "organization": {"working_root": str(work_root), "file_count": 0, "verified": True,
                                            "imported_source_files": [], "destinations": []}})
            atomic_json(status_path, status)
            archive_protocol_directory(temporary_protocol, permanent_protocol)
            _remove_empty_directories(temporary_job_root)
            validate_active_roots()
            temporary_job_root.rmdir()
            return status
        if not entries:
            raise PipelineError(
                "Auf dieser SD-Karte wurden keine neuen Dateien gefunden. "
                "Alle Dateien wurden bereits erfolgreich gesichert."
            )

        total_size = sum(int(entry["size_bytes"]) for entry in entries)
        required_bytes = (
            total_size
            + math.ceil(total_size * processing_buffer_percent / 100)
            + safety_reserve_gib * 1024**3
        )
        dataset_fs = os.statvfs(workspace)
        dataset_available = dataset_fs.f_bavail * dataset_fs.f_frsize
        pool_fs = os.statvfs(pool_probe_path)
        pool_available = pool_fs.f_bavail * pool_fs.f_frsize
        if dataset_available < required_bytes:
            raise PipelineError("Nicht genügend freier Speicher im Kamera-Arbeitsbereich.")
        if pool_available < required_bytes:
            raise PipelineError("Nicht genügend freier Speicher im apps-Pool.")

        manifest = {
            "schema_version": 3,
            "job_id": job_id,
            "simulation": False,
            "import_mode": "folder",
            "source_path": str(source),
            "file_count": len(entries),
            "total_source_file_count": len(all_entries),
            "already_imported_file_count": len(already_imported),
            "new_file_count": len(entries),
            "total_size_bytes": total_size,
            "source_signature": source_signature,
            "source_fingerprint": source_fingerprint,
            "files": entries,
            "already_imported_files": duplicate_details,
        }
        atomic_json(manifest_path, manifest)

        progress(
            "copying",
            "copying",
            0,
            len(entries),
            "Quelle wird vollständig in die temporäre Sicherung kopiert.",
        )
        def report_copy_progress(phase: str, current: int, total: int) -> None:
            if phase == "copy":
                progress(
                    "copying",
                    "copying",
                    current,
                    max(total, 1),
                    "Dateien werden in die temporäre Sicherung kopiert.",
                )
            else:
                progress(
                    "verifying",
                    "backup_verification",
                    current,
                    max(total, 1),
                    "Temporäre Sicherung wird Datei für Datei per SHA-256 geprüft.",
                )

        copy_and_verify(
            source,
            temporary_original,
            entries,
            progress_callback=report_copy_progress,
            cancellation_callback=check_cancelled,
        )

        progress(
            "verifying",
            "backup_verification",
            len(entries),
            len(entries),
            "Quelle und temporäre Sicherung stimmen per SHA-256 überein.",
        )

        snapshot_reference = (
            "receipt://apps/kamera-arbeitsbereich@"
            + job_id.lower()
            + "-backup-verified"
        )
        snapshot_receipt = {
            "schema_version": 2,
            "job_id": job_id,
            "backend": "verification_receipt",
            "reference": snapshot_reference,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "automatic": True,
            "real_zfs_snapshot": False,
            "formatting_allowed": False,
            "note": (
                "Der Ordnerimport ist vollständig geprüft. Ein echter ZFS-Snapshot "
                "und die Freigabe zum Formatieren werden erst mit der Host-Schnittstelle aktiviert."
            ),
        }
        atomic_json(snapshot_path, snapshot_receipt)

        progress(
            "backup_verified",
            "snapshot_created",
            len(entries),
            len(entries),
            "Prüfbeleg wurde automatisch erstellt; Formatieren bleibt gesperrt.",
        )

        progress(
            "analyzing_metadata",
            "metadata_analysis",
            0,
            len(entries),
            "ExifTool analysiert Aufnahmezeit, Zeitzone und Aufnahmegerät.",
        )
        analysis = analyze_tree(
            temporary_original,
            include_other=False,
            cancellation_callback=check_cancelled,
            progress_callback=lambda current, total: progress(
                "analyzing_metadata",
                "metadata_analysis",
                current,
                max(total, 1),
                (
                    "ExifTool analysiert Aufnahmezeit, Zeitzone und "
                    f"Aufnahmegerät ({current}/{max(total, 1)})."
                ),
            ),
        )
        checksum_by_path = {
            str(entry["relative_path"]): str(entry["sha256"])
            for entry in entries
        }
        size_by_path = {
            str(entry["relative_path"]): int(entry["size_bytes"])
            for entry in entries
        }

        admission: dict[str, Any] = {
            "allowed_family_keys": None,
            "blocked_families": [],
        }
        if family_admission_callback is not None:
            admission = family_admission_callback(
                analysis,
                checksum_by_path,
                size_by_path,
            ) or admission
            allowed_raw = admission.get("allowed_family_keys")
            if allowed_raw is not None:
                allowed = {str(value) for value in allowed_raw}
                analysis = {
                    **analysis,
                    "files": [
                        row for row in (analysis.get("files") or [])
                        if str(row.get("family_key") or "") in allowed
                    ],
                    "families": [
                        row for row in (analysis.get("families") or [])
                        if str(row.get("family_key") or "") in allowed
                    ],
                }

        media_checksums = {
            str(record["relative_path"]):
                checksum_by_path[str(record["relative_path"])]
            for record in analysis.get("files", [])
            if str(record.get("relative_path") or "") in checksum_by_path
        }
        if metadata_callback is not None:
            metadata_callback(analysis, media_checksums)

        plan, excluded, organization_summary = build_folder_import_plan(
            entries,
            analysis,
            work_root,
            destination_directory_callback=destination_directory_callback,
        )
        if not plan and not admission.get("blocked_families"):
            raise PipelineError("Die Quelle enthält keine unterstützten Medien.")
        organization_summary["blocked_family_count"] = len(
            admission.get("blocked_families") or []
        )
        organization_summary["blocked_families"] = list(
            admission.get("blocked_families") or []
        )

        manifest["organization"] = organization_summary
        manifest["excluded_files"] = [
            {
                "relative_path": str(entry["relative_path"]),
                "size_bytes": int(entry["size_bytes"]),
                "sha256": str(entry["sha256"]),
                "reason": "non_media_or_card_management_file",
            }
            for entry in excluded
        ]
        atomic_json(manifest_path, manifest)

        remove_excluded_files(temporary_original, excluded)

        progress(
            "organizing",
            "workspace_moving",
            0,
            len(plan),
            (
                "Medienfamilien werden in den zentralen Tagesbestand übernommen."
                if central_stock
                else "Medienfamilien werden ohne zweite Datenkopie in Tagesordner verschoben."
            ),
        )
        move_import_into_workspace(
            temporary_original,
            work_root,
            plan,
            post_move_callback=path_callback,
            cancellation_callback=cancellation_callback,
        )
        # Erst ab vollständiger, bestätigter Überführung gehören diese Pfade
        # diesem Job. Vorher ist der Rollback ausschließlich Sache der Move-Routine.
        committed_plan = list(plan)

        if import_history_callback is not None:
            imported_paths = {str(item["source_relative_path"]) for item in plan}
            # Auch sicher erkannte Duplikate werden für diese konkrete
            # Quellen-ID als gesehen protokolliert. So ist der nächste
            # Schnellscan derselben SD-Karte konsistent mit der SHA-Prüfung.
            history_entries = [
                entry for entry in entries
                if str(entry["relative_path"]) in imported_paths
            ]
            history_entries.extend(already_imported)
            import_history_callback(history_entries)

        progress(
            "organizing",
            "workspace_verification",
            len(plan),
            len(plan),
            (
                "Zentraler Aufnahmebestand wurde vollständig gegen das Manifest geprüft."
                if central_stock
                else "Arbeitsbereich wurde vollständig gegen das Manifest geprüft."
            ),
        )

        status.update({
            "updated_at": datetime.now().astimezone().isoformat(),
            "stage": "workspace_verified",
            "source": {
                "file_count": len(entries),
                "total_source_file_count": len(all_entries),
                "file_history_complete": len(plan) + len(already_imported) == sum(classify_media(Path(e["relative_path"])) in MEDIA_TYPES for e in all_entries),
                "already_imported_file_count": len(already_imported),
                "duplicate_file_count": len(already_imported),
                "duplicate_files": duplicate_details,
                "new_file_count": len(plan),
                "blocked_family_count": len(admission.get("blocked_families") or []),
                "signature": source_signature,
                "fingerprint": source_fingerprint,
                "size_bytes": total_size,
            },
            "snapshot": snapshot_receipt,
            "organization": {
                "working_root": str(work_root),
                "storage_scope": "central_stock" if central_stock else "library_workspace",
                "file_count": len(plan),
                "excluded_file_count": len(excluded),
                "verified": True,
                **organization_summary,
                "destinations": [
                    str(item["destination_relative_path"])
                    for item in plan
                ],
                "imported_source_files": [
                    {
                        "relative_path": str(item["source_relative_path"]),
                        "size_bytes": int(item["size_bytes"]),
                        "sha256": str(item["sha256"]),
                    }
                    for item in plan
                ],
            },
        })
        atomic_json(status_path, status)

        archive_protocol_directory(temporary_protocol, permanent_protocol)
        from app.import_recovery import read_record
        atomic_json(permanent_protocol / 'move-journal.json', read_record(temporary_job_root / 'move-journal.json'))
        if temporary_job_root.exists():
            _remove_empty_directories(temporary_job_root)
            validate_active_roots()
            (temporary_job_root / "move-journal.json").unlink(missing_ok=True)
            validate_active_roots()
            temporary_job_root.rmdir()

        finished_at = datetime.now(timezone.utc).astimezone().isoformat()
        final_status = permanent_protocol / "status.json"
        status.update({
            "updated_at": finished_at,
            "stage": "completed",
            "state": "success",
            "temporary_backup_removed": True,
            "formatting_allowed": False,
            "outputs": {
                "manifest": str(permanent_protocol / "manifest.json"),
                "status": str(final_status),
                "snapshot": str(permanent_protocol / "snapshot.json"),
                "protocol": str(permanent_protocol),
            },
        })
        atomic_json(final_status, status)
        append_log(log_dir, {
            "time": finished_at,
            "job_id": job_id,
            "state": "success",
            "stage": "completed",
            "import_mode": "folder",
            "temporary_backup_removed": True,
            "workspace": str(work_root),
            "storage_scope": "central_stock" if central_stock else "library_workspace",
        })

        progress(
            "organizing",
            "completed",
            len(plan),
            len(plan),
            (
                "Ordnerimport, Metadatenanalyse und Übernahme in den zentralen "
                "Tagesbestand sind abgeschlossen."
                if central_stock
                else "Ordnerimport, Metadatenanalyse, Tagesgruppierung und Prüfung sind abgeschlossen."
            ),
        )
        return status
    except ImportCancelled:
        # A stopped copy is evidence, not disposable scratch. Publication itself
        # rolls owned moves back; preserve staged bytes and all protocol files.
        append_log(log_dir, {
            "time": datetime.now(timezone.utc).astimezone().isoformat(),
            "job_id": job_id,
            "state": "cancelled",
            "stage": "cancelled",
            "import_mode": "folder",
        })
        raise
    except Exception as error:
        failed_at = datetime.now(timezone.utc).astimezone().isoformat()
        status.update({
            "updated_at": failed_at,
            "stage": "failed",
            "state": "failed",
            "error": str(error),
        })
        active_status = (
            permanent_protocol / "status.json"
            if permanent_protocol.exists()
            else status_path
        )
        validate_active_roots()
        active_status.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(active_status, status)
        append_log(log_dir, {
            "time": failed_at,
            "job_id": job_id,
            "state": "failed",
            "stage": "failed",
            "import_mode": "folder",
            "error": str(error),
        })
        raise



def cleanup_completed_folder_import(
    result: dict[str, Any],
    destination_root: Path,
) -> None:
    """Remove a just-finished import when a cancellation wins the final race."""
    organization = dict(result.get("organization") or {})
    destinations = list(organization.get("destinations") or [])
    imported = list(organization.get("imported_source_files") or [])
    if len(destinations) != len(imported):
        raise PipelineError(
            "Abbruchbereinigung kann die importierten Zieldateien nicht eindeutig zuordnen."
        )

    root = destination_root.resolve(strict=False)
    checked: list[Path] = []
    for destination_value, entry in zip(destinations, imported, strict=True):
        relative = Path(str(destination_value or ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise PipelineError("Unsicherer Zielpfad in Abbruchbereinigung.")
        path = (root / relative).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError as error:
            raise PipelineError("Zielpfad liegt außerhalb des Arbeitsbestands.") from error
        if not path.is_file() or path.is_symlink():
            raise PipelineError("Importziel fehlt bei Abbruchbereinigung: " + str(relative))
        if (
            path.stat().st_size != int(entry.get("size_bytes") or 0)
            or sha256_file(path) != str(entry.get("sha256") or "")
        ):
            raise PipelineError(
                "Importziel stimmt bei Abbruchbereinigung nicht mehr: " + str(relative)
            )
        checked.append(path)

    for path in checked:
        validate_active_roots()
        path.unlink()
        parent = path.parent
        while parent != root:
            try:
                validate_active_roots()
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
