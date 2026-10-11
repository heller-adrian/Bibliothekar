from __future__ import annotations

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

from app.metadata import analyze_tree
from app.source_filter import should_ignore_source_path
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
) -> dict[str, int]:
    """Vor einer Jobannahme nur Dateigrößen ermitteln, niemals SHA-256 lesen.

    Ein unüberschaubarer NAS-Baum wird kontrolliert abgewiesen, damit der
    HTTP-Worker keine unbegrenzte Verzeichnissuche ausführt. Quoten werden
    über die wirksam verfügbare Kapazität des tatsächlichen Schreibpfads
    abgefragt; ein späterer Check schützt vor zwischenzeitlichen Änderungen.
    """
    source = source.resolve(strict=True)
    workspace = workspace.resolve(strict=True)
    if source == workspace or source in workspace.parents or workspace in source.parents:
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
    reserved: set[str] = set()
    plan: list[dict[str, Any]] = []
    review_family_count = 0
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
        day = capture.strftime("%Y-%m-%d")
        year = capture.strftime("%Y")
        base = capture.strftime("%Y%m%d_%H%M%S") + "_" + device_token
        destination_directory = Path(year) / day
        if destination_directory_callback is not None:
            resolved_directory = destination_directory_callback(
                str(capture_value)[:19]
            )
            if resolved_directory is not None:
                candidate_directory = Path(resolved_directory)
                if (
                    candidate_directory.is_absolute()
                    or ".." in candidate_directory.parts
                ):
                    raise PipelineError(
                        "Unsicherer kanonischer Zielordner für Import: "
                        + str(candidate_directory)
                    )
                destination_directory = candidate_directory

        suffix_index = 0
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
        path.unlink()

    _remove_empty_directories(temporary_original)


def move_import_into_workspace(
    temporary_original: Path,
    shared_root: Path,
    plan: list[dict[str, Any]],
    *,
    post_move_callback: PathCallback | None = None,
    cancellation_callback: CancellationCallback | None = None,
) -> None:
    if not temporary_original.is_dir():
        raise PipelineError(
            f"Temporäre Sicherung fehlt: {temporary_original}"
        )

    shared_root.mkdir(parents=True, exist_ok=True)
    if int(temporary_original.stat().st_dev) != int(shared_root.stat().st_dev):
        raise PipelineError(
            "Temporäre Sicherung und Arbeitsbereich liegen nicht auf demselben Dateisystem."
        )

    moved: list[tuple[Path, Path]] = []
    try:
        for item in plan:
            if cancellation_callback is not None and cancellation_callback():
                raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
            source = temporary_original / str(item["source_relative_path"])
            destination = shared_root / str(item["destination_relative_path"])
            if not source.is_file():
                raise PipelineError(f"Quelldatei fehlt: {source}")
            if destination.exists() or destination.is_symlink():
                raise PipelineError(f"Zieldatei existiert bereits: {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved.append((source, destination))

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

        _remove_empty_directories(temporary_original)
        temporary_original.rmdir()

        # SQLite wird erst nach vollständig geprüfter Dateibewegung
        # aktualisiert. Scheitert die Transaktion, stellt der folgende
        # Except-Block alle Dateien an ihren Sicherungspfad zurück.
        if cancellation_callback is not None and cancellation_callback():
            raise ImportCancelled("Import wurde vom Nutzer abgebrochen.")
        if post_move_callback is not None:
            post_move_callback(plan)
    except Exception:
        rollback_errors: list[str] = []
        for source, destination in reversed(moved):
            try:
                if destination.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(destination, source)
            except Exception as error:
                rollback_errors.append(f"{destination} → {source}: {error}")
        if rollback_errors:
            raise PipelineError(
                "Ordnerimport fehlgeschlagen; Rollback unvollständig: "
                + " | ".join(rollback_errors)
            )
        raise


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
    temporary_protocol = temporary_job_root / "Protokoll"
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
        if temporary_job_root.exists():
            _remove_empty_directories(temporary_job_root)
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
        cleanup_errors: list[str] = []
        for item in committed_plan:
            destination = work_root / str(item["destination_relative_path"])
            try:
                if not destination.exists():
                    continue
                if not destination.is_file() or destination.is_symlink():
                    raise PipelineError(
                        "Unerwarteter Eintrag beim Abbruch: " + str(destination)
                    )
                if (
                    destination.stat().st_size != int(item["size_bytes"])
                    or sha256_file(destination) != str(item["sha256"])
                ):
                    raise PipelineError(
                        "Datei hat sich während des Abbruchs verändert: "
                        + str(destination)
                    )
                destination.unlink()
                _remove_empty_directories(destination.parent)
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))

        if temporary_job_root.exists():
            try:
                shutil.rmtree(temporary_job_root)
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))
        if permanent_protocol.exists():
            try:
                shutil.rmtree(permanent_protocol)
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))

        if cleanup_errors:
            raise PipelineError(
                "Import wurde abgebrochen, aber die Bereinigung war unvollständig: "
                + " | ".join(cleanup_errors)
            )

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
        path.unlink()
        parent = path.parent
        while parent != root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
