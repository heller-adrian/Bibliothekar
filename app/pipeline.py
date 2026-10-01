from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import hashlib
import json
import math
import os
import shutil
import tempfile

from app.workspace_layout import (
    backup_root as workspace_backup_root,
    resolve_library_work_root,
    shared_work_root,
)


RAW_EXTENSIONS = {
    ".raf", ".dng", ".cr2", ".cr3",
    ".nef", ".arw", ".orf", ".rw2",
}

JPEG_EXTENSIONS = {
    ".jpg", ".jpeg",
}

VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".m4v", ".avi",
    ".mts", ".m2ts",
}


class PipelineError(RuntimeError):
    pass


def classify(extension: str) -> str:
    extension = extension.lower()

    if extension in RAW_EXTENSIONS:
        return "raw"

    if extension in JPEG_EXTENSIONS:
        return "jpeg"

    if extension == ".xmp":
        return "xmp"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    return "other"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")

    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(
            data,
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())

    temporary.replace(path)


def append_log(log_dir: Path, record: dict[str, Any]) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "jobs.jsonl"

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )
        handle.flush()
        os.fsync(handle.fileno())



def _tree_digest(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise PipelineError(f"Verzeichnis fehlt: {root}")

    result: list[dict[str, Any]] = []

    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PipelineError(
                f"Symbolischer Link im Protokoll nicht erlaubt: {path}"
            )
        if path.is_dir():
            continue
        if not path.is_file():
            raise PipelineError(
                f"Nicht unterstützter Eintrag im Protokoll: {path}"
            )
        result.append({
            "relative_path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    return result


def archive_protocol_directory(source: Path, target: Path) -> None:
    """Archive a protocol directory safely across filesystems.

    The live workspace and the application log directory are separate bind
    mounts on TrueNAS. A direct os.replace() therefore raises EXDEV. The
    protocol is copied to a staging directory on the target filesystem, fully
    verified, atomically published there, and only then removed at the source.
    """
    if not source.is_dir():
        raise PipelineError(f"Protokollquelle fehlt: {source}")

    if target.exists() or target.is_symlink():
        raise PipelineError(f"Protokollziel existiert bereits: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    expected = _tree_digest(source)
    staging_parent = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.incoming-",
            dir=target.parent,
        )
    )
    staging = staging_parent / "protocol"

    try:
        shutil.copytree(
            source,
            staging,
            copy_function=shutil.copy2,
        )

        if _tree_digest(staging) != expected:
            raise PipelineError(
                "Kopiertes Protokoll stimmt nicht mit der Quelle überein."
            )

        os.replace(staging, target)

        if _tree_digest(target) != expected:
            raise PipelineError(
                "Veröffentlichtes Protokoll stimmt nicht mit der Quelle überein."
            )

        shutil.rmtree(source)
    except Exception:
        if target.exists() and source.exists():
            shutil.rmtree(target, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging_parent, ignore_errors=True)


def recover_cross_device_protocol_failures(
    workspace: Path,
    log_dir: Path,
) -> list[dict[str, Any]]:
    """Finalize 0.9.0 jobs that failed only while archiving logs."""
    backups_root = workspace_backup_root(workspace)
    work_root = shared_work_root(workspace)
    recovered: list[dict[str, Any]] = []

    if not backups_root.is_dir():
        return recovered

    for temporary_job_root in sorted(backups_root.iterdir()):
        if not temporary_job_root.is_dir():
            continue

        job_id = temporary_job_root.name
        protocol = temporary_job_root / "Protokoll"
        original = temporary_job_root / "Original"
        status_path = protocol / "status.json"
        manifest_path = protocol / "manifest.json"
        snapshot_path = protocol / "snapshot.json"
        permanent_protocol = log_dir / "backups" / job_id

        if not (status_path.is_file() and manifest_path.is_file()):
            continue

        status = json.loads(status_path.read_text(encoding="utf-8"))
        error = str(status.get("error") or "")

        if status.get("state") != "failed":
            continue
        if "Invalid cross-device link" not in error:
            continue
        if permanent_protocol.exists():
            continue
        if original.exists() and any(path.is_file() for path in original.rglob("*")):
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest.get("files")
        if not isinstance(entries, list) or not entries:
            continue

        plan = _shared_destination_plan(build_organization_plan(entries))

        for item in plan:
            destination = work_root / item["destination_relative_path"]
            if not destination.is_file():
                raise PipelineError(
                    f"Wiederherstellung abgebrochen; Zieldatei fehlt: {destination}"
                )
            if destination.stat().st_size != int(item["size_bytes"]):
                raise PipelineError(
                    f"Wiederherstellung abgebrochen; Größe weicht ab: {destination}"
                )
            if sha256_file(destination) != item["sha256"]:
                raise PipelineError(
                    f"Wiederherstellung abgebrochen; SHA-256 weicht ab: {destination}"
                )

        archive_protocol_directory(protocol, permanent_protocol)
        _remove_empty_directories(temporary_job_root)
        if temporary_job_root.exists():
            temporary_job_root.rmdir()

        finished_at = datetime.now(timezone.utc).astimezone().isoformat()
        final_status_path = permanent_protocol / "status.json"
        snapshot = (
            json.loads((permanent_protocol / "snapshot.json").read_text(encoding="utf-8"))
            if (permanent_protocol / "snapshot.json").is_file()
            else {}
        )
        status.update({
            "updated_at": finished_at,
            "stage": "completed",
            "state": "success",
            "recovered_from": "0.9.0_cross_device_protocol_archive",
            "temporary_backup_removed": True,
            "error": None,
            "outputs": {
                "manifest": str(permanent_protocol / "manifest.json"),
                "status": str(final_status_path),
                "snapshot": str(permanent_protocol / "snapshot.json"),
                "protocol": str(permanent_protocol),
            },
        })
        atomic_json(final_status_path, status)

        recovered.append({
            **status,
            "job_id": job_id,
            "source": {
                "file_count": int(manifest.get("file_count") or len(entries)),
                "size_bytes": int(manifest.get("total_size_bytes") or 0),
            },
            "organization": {
                "working_root": str(work_root),
                "file_count": len(plan),
                "verified": True,
            },
            "snapshot": snapshot,
        })

    return recovered

def source_manifest(
    source: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[dict[str, Any]]:
    if not source.is_dir():
        raise PipelineError(
            f"Simulationsquelle fehlt: {source}"
        )

    entries: list[dict[str, Any]] = []
    paths = sorted(source.rglob("*"))
    total_files = sum(
        1
        for candidate in paths
        if candidate.is_file() and not candidate.is_symlink()
    )
    processed_files = 0

    for path in paths:
        if path.is_symlink():
            raise PipelineError(
                f"Symbolischer Link nicht erlaubt: {path}"
            )

        if path.is_dir():
            continue

        if not path.is_file():
            raise PipelineError(
                f"Nicht unterstützter Dateityp: {path}"
            )

        stat = path.stat()
        relative = path.relative_to(source)
        extension = path.suffix.lower()

        entries.append({
            "relative_path": relative.as_posix(),
            "filename": path.name,
            "extension": extension,
            "media_type": classify(extension),
            "family_key": (
                relative.parent / path.stem
            ).as_posix(),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).astimezone().isoformat(),
            "modified_at_ns": int(stat.st_mtime_ns),
            "sha256": sha256_file(path),
        })

        processed_files += 1
        if progress_callback is not None:
            progress_callback(processed_files, total_files)

    if not entries:
        raise PipelineError(
            "Die Simulationsquelle enthält keine Dateien."
        )

    return entries


def copy_and_verify(
    source: Path,
    destination: Path,
    entries: list[dict[str, Any]],
    progress_callback: Callable[[str, int, int], None] | None = None,
) -> None:
    if destination.exists():
        raise PipelineError(
            f"Sicherungsziel existiert bereits: {destination}"
        )

    destination.mkdir(parents=True)

    total_entries = len(entries)

    for index, entry in enumerate(entries, start=1):
        relative = Path(entry["relative_path"])
        source_path = source / relative
        destination_path = destination / relative

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Nur den Dateiinhalt kopieren. ACL, Eigentümer und
        # Unix-Modus der Quelle dürfen nicht übernommen werden.
        source_stat = source_path.stat()

        shutil.copyfile(
            source_path,
            destination_path,
        )

        # Aufnahmeunabhängige Dateisystemzeiten erhalten, ohne
        # chmod, chown oder ACL-Änderungen auszuführen.
        os.utime(
            destination_path,
            ns=(
                source_stat.st_atime_ns,
                source_stat.st_mtime_ns,
            ),
        )

        if progress_callback is not None:
            progress_callback("copy", index, total_entries)

    actual_files = sorted(
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    )

    expected_files = sorted(
        entry["relative_path"]
        for entry in entries
    )

    if actual_files != expected_files:
        raise PipelineError(
            "Dateiliste der Sicherung stimmt "
            "nicht mit der Quelle überein."
        )

    for index, entry in enumerate(entries, start=1):
        copied = destination / entry["relative_path"]

        if copied.stat().st_size != entry["size_bytes"]:
            raise PipelineError(
                f"Größenabweichung: {entry['relative_path']}"
            )

        if sha256_file(copied) != entry["sha256"]:
            raise PipelineError(
                f"SHA-256-Abweichung: "
                f"{entry['relative_path']}"
            )

        if progress_callback is not None:
            progress_callback("verify", index, total_entries)


def build_organization_plan(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    families: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in entries:
        families[entry["family_key"]].append(entry)

    priority = {
        "raw": 0,
        "jpeg": 1,
        "video": 2,
        "xmp": 3,
        "other": 4,
    }

    family_records: list[dict[str, Any]] = []

    for family_key in sorted(families):
        members = sorted(
            families[family_key],
            key=lambda entry: (
                priority.get(entry["media_type"], 99),
                entry["relative_path"],
            ),
        )

        anchor = members[0]

        if anchor["media_type"] in {
            "raw", "jpeg", "video", "xmp"
        }:
            capture_time = datetime.fromisoformat(
                anchor["modified_at"]
            )

            day_folder = capture_time.strftime(
                "%Y-%m-%d"
            )

            base_name = (
                capture_time.strftime("%Y%m%d_%H%M%S")
                + "_SIM-KAMERA"
            )

            needs_review = False
        else:
            capture_time = None
            day_folder = "Ohne_Datum"
            base_name = Path(
                anchor["filename"]
            ).stem
            needs_review = True

        family_records.append({
            "family_key": family_key,
            "members": members,
            "capture_time": capture_time,
            "day_folder": day_folder,
            "base_name": base_name,
            "needs_review": needs_review,
        })

    name_counts: dict[tuple[str, str], int] = defaultdict(int)

    for record in family_records:
        if record["day_folder"] != "Ohne_Datum":
            key = (
                record["day_folder"],
                record["base_name"],
            )
            name_counts[key] += 1

    name_indices: dict[tuple[str, str], int] = defaultdict(int)
    plan: list[dict[str, Any]] = []
    used_destinations: set[str] = set()

    for record in family_records:
        base_name = record["base_name"]
        key = (record["day_folder"], base_name)

        if (
            record["day_folder"] != "Ohne_Datum"
            and name_counts[key] > 1
        ):
            name_indices[key] += 1
            base_name = (
                f"{base_name}_{name_indices[key]:02d}"
            )

        for member in sorted(
            record["members"],
            key=lambda entry: entry["relative_path"],
        ):
            original_name = member["filename"]

            if record["day_folder"] == "Ohne_Datum":
                destination_name = original_name
            else:
                destination_name = (
                    base_name
                    + Path(original_name).suffix
                )

            destination_relative = (
                Path(record["day_folder"])
                / destination_name
            ).as_posix()

            if destination_relative in used_destinations:
                raise PipelineError(
                    f"Zielkollision: {destination_relative}"
                )

            used_destinations.add(destination_relative)

            plan.append({
                "source_relative_path":
                    member["relative_path"],
                "destination_relative_path":
                    destination_relative,
                "size_bytes": member["size_bytes"],
                "sha256": member["sha256"],
                "needs_review":
                    record["needs_review"],
            })

    return plan


def organize_and_verify(
    backup_root: Path,
    working_root: Path,
    plan: list[dict[str, Any]],
) -> None:
    if working_root.exists():
        raise PipelineError(
            f"Arbeitsbestand existiert bereits: {working_root}"
        )

    os.replace(
        backup_root,
        working_root,
    )

    for move in plan:
        old_path = (
            working_root
            / move["source_relative_path"]
        )

        new_path = (
            working_root
            / move["destination_relative_path"]
        )

        if not old_path.is_file():
            raise PipelineError(
                f"Quelldatei fehlt: {old_path}"
            )

        if new_path.exists():
            raise PipelineError(
                f"Zieldatei existiert bereits: {new_path}"
            )

        new_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        os.replace(
            old_path,
            new_path,
        )

    expected_paths = {
        move["destination_relative_path"]
        for move in plan
    }

    actual_paths = {
        path.relative_to(working_root).as_posix()
        for path in working_root.rglob("*")
        if path.is_file()
    }

    if actual_paths != expected_paths:
        raise PipelineError(
            "Dateiliste des Arbeitsbestands stimmt "
            "nicht mit dem Organisationsplan überein."
        )

    for move in plan:
        path = (
            working_root
            / move["destination_relative_path"]
        )

        if path.stat().st_size != move["size_bytes"]:
            raise PipelineError(
                f"Größenabweichung nach Organisation: {path}"
            )

        if sha256_file(path) != move["sha256"]:
            raise PipelineError(
                f"SHA-256-Abweichung nach Organisation: {path}"
            )

    directories = sorted(
        (
            path
            for path in working_root.rglob("*")
            if path.is_dir()
        ),
        key=lambda path: len(path.parts),
        reverse=True,
    )

    for directory in directories:
        try:
            directory.rmdir()
        except OSError:
            pass


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


def _shared_destination_plan(
    plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for item in plan:
        relative = Path(
            str(item["destination_relative_path"])
        )

        if not relative.parts:
            raise PipelineError("Leerer Zielpfad im Organisationsplan.")

        day_folder = relative.parts[0]

        if day_folder == "Ohne_Datum":
            destination = Path("Ohne_Datum") / Path(*relative.parts[1:])
        else:
            try:
                year = day_folder[:4]
                int(year)
            except Exception as error:
                raise PipelineError(
                    "Ungültiger Tagesordner im Organisationsplan: "
                    + day_folder
                ) from error

            destination = Path(year) / relative

        result.append({
            **item,
            "destination_relative_path": destination.as_posix(),
        })

    return result


def move_backup_into_shared_workspace(
    backup_root: Path,
    shared_root: Path,
    plan: list[dict[str, Any]],
) -> None:
    if not backup_root.is_dir():
        raise PipelineError(
            f"Temporäre Sicherung fehlt: {backup_root}"
        )

    shared_root.mkdir(parents=True, exist_ok=True)

    if int(backup_root.stat().st_dev) != int(shared_root.stat().st_dev):
        raise PipelineError(
            "Temporäre Sicherung und Arbeitsbereich liegen nicht "
            "auf demselben Dateisystem."
        )

    moved: list[tuple[Path, Path]] = []

    try:
        for item in plan:
            source = backup_root / item["source_relative_path"]
            destination = shared_root / item["destination_relative_path"]

            if not source.is_file():
                raise PipelineError(
                    f"Quelldatei fehlt vor Überführung: {source}"
                )

            if destination.exists() or destination.is_symlink():
                raise PipelineError(
                    f"Zieldatei existiert bereits: {destination}"
                )

            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(source, destination)
            moved.append((source, destination))

        for item in plan:
            destination = shared_root / item["destination_relative_path"]

            if not destination.is_file():
                raise PipelineError(
                    f"Zieldatei fehlt nach Überführung: {destination}"
                )

            if destination.stat().st_size != int(item["size_bytes"]):
                raise PipelineError(
                    f"Größenabweichung nach Überführung: {destination}"
                )

            if sha256_file(destination) != item["sha256"]:
                raise PipelineError(
                    f"SHA-256-Abweichung nach Überführung: {destination}"
                )

        remaining_files = [
            path
            for path in backup_root.rglob("*")
            if path.is_file()
        ]

        if remaining_files:
            raise PipelineError(
                "Temporäre Sicherung enthält nach der Überführung "
                "noch Dateien."
            )

        _remove_empty_directories(backup_root)
        backup_root.rmdir()

    except Exception:
        rollback_errors: list[str] = []

        for source, destination in reversed(moved):
            try:
                if destination.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(destination, source)
            except Exception as rollback_error:
                rollback_errors.append(
                    f"{destination} → {source}: {rollback_error}"
                )

        if rollback_errors:
            raise PipelineError(
                "Überführung fehlgeschlagen und Rollback war nicht vollständig: "
                + " | ".join(rollback_errors)
            )

        raise


def run_simulated_job(
    workspace: Path,
    pool_probe_path: Path,
    log_dir: Path,
    processing_buffer_percent: int,
    safety_reserve_gib: int,
    job_id: str | None = None,
    progress_callback: Callable[
        [str, str, int, int, str],
        None,
    ] | None = None,
    work_root: Path | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone()

    if job_id is None:
        job_id = now.strftime(
            "WEB_SIM_%Y%m%d_%H%M%S_%f"
        )

    def progress(
        state: str,
        stage: str,
        current: int,
        total: int,
        message: str,
    ) -> None:
        if progress_callback is None:
            return

        progress_callback(
            state,
            stage,
            current,
            total,
            message,
        )

    template = (
        workspace
        / "_test"
        / "SD_SIM_001"
        / "simulierte-sd"
    )

    backups_root = workspace_backup_root(workspace)
    work_root = resolve_library_work_root(
        workspace,
        work_root,
    )
    temporary_job_root = backups_root / job_id
    temporary_original = temporary_job_root / "Original"
    temporary_protocol = temporary_job_root / "Protokoll"
    permanent_protocol = log_dir / "backups" / job_id
    status_path = temporary_protocol / "status.json"
    manifest_path = temporary_protocol / "manifest.json"
    snapshot_path = temporary_protocol / "snapshot.json"

    if temporary_job_root.exists():
        raise PipelineError(
            f"Temporärer Sicherungsbestand existiert bereits: {temporary_job_root}"
        )

    if permanent_protocol.exists():
        raise PipelineError(
            f"Protokollziel existiert bereits: {permanent_protocol}"
        )

    temporary_protocol.mkdir(parents=True)

    status: dict[str, Any] = {
        "schema_version": 2,
        "job_id": job_id,
        "simulation": True,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "stage": "starting",
        "state": "running",
        "lifecycle": {
            "temporary_backup": str(temporary_original),
            "shared_workspace": str(work_root),
            "protocol_archive": str(permanent_protocol),
        },
    }

    atomic_json(status_path, status)

    progress(
        "copying",
        "starting",
        0,
        0,
        "Simulationsauftrag wird vorbereitet.",
    )

    try:
        entries = source_manifest(template)
        total_size = sum(entry["size_bytes"] for entry in entries)
        processing_buffer = math.ceil(
            total_size * processing_buffer_percent / 100
        )
        safety_reserve = safety_reserve_gib * 1024**3
        required_bytes = total_size + processing_buffer + safety_reserve

        dataset_filesystem = os.statvfs(workspace)
        dataset_available_bytes = (
            dataset_filesystem.f_bavail * dataset_filesystem.f_frsize
        )
        pool_filesystem = os.statvfs(pool_probe_path)
        pool_available_bytes = (
            pool_filesystem.f_bavail * pool_filesystem.f_frsize
        )

        if dataset_available_bytes < required_bytes:
            raise PipelineError(
                "Nicht genügend freier Speicher innerhalb der 500-GiB-Quota "
                "des Kamera-Arbeitsbereichs."
            )

        if pool_available_bytes < required_bytes:
            raise PipelineError(
                "Nicht genügend freier Speicher im gesamten apps-Pool."
            )

        manifest = {
            "schema_version": 2,
            "job_id": job_id,
            "simulation": True,
            "source_path": str(template),
            "file_count": len(entries),
            "total_size_bytes": total_size,
            "files": entries,
        }
        atomic_json(manifest_path, manifest)

        status.update({
            "updated_at": datetime.now().astimezone().isoformat(),
            "stage": "copying",
            "source": {
                "file_count": len(entries),
                "size_bytes": total_size,
            },
            "storage_check": {
                "required_bytes": required_bytes,
                "dataset_available_bytes": dataset_available_bytes,
                "pool_available_bytes": pool_available_bytes,
                "dataset_space_sufficient": True,
                "pool_space_sufficient": True,
                "result": "PASS",
            },
        })
        atomic_json(status_path, status)

        progress(
            "copying",
            "copying",
            0,
            len(entries),
            "Dateien werden vollständig in die temporäre Sicherung kopiert.",
        )

        copy_and_verify(template, temporary_original, entries)

        progress(
            "verifying",
            "backup_verification",
            len(entries),
            len(entries),
            "Quelle und temporäre Sicherung stimmen per SHA-256 überein.",
        )

        status.update({
            "updated_at": datetime.now().astimezone().isoformat(),
            "stage": "backup_verified",
            "backup": {
                "path": str(temporary_original),
                "file_count": len(entries),
                "verified": True,
            },
        })
        atomic_json(status_path, status)

        snapshot_reference = (
            "simulated://apps/kamera-arbeitsbereich@"
            + job_id.lower()
            + "-backup-verified"
        )
        snapshot_receipt = {
            "schema_version": 1,
            "job_id": job_id,
            "backend": "simulation_receipt",
            "reference": snapshot_reference,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "automatic": True,
            "production_note": (
                "Der echte ZFS-Snapshot wird erst nach Einrichtung einer "
                "sicheren TrueNAS-Host-Schnittstelle aktiviert."
            ),
        }
        atomic_json(snapshot_path, snapshot_receipt)

        progress(
            "backup_verified",
            "snapshot_created",
            len(entries),
            len(entries),
            "Automatischer Schutz-Snapshot wurde für die Simulation bestätigt.",
        )

        status.update({
            "updated_at": datetime.now().astimezone().isoformat(),
            "stage": "snapshot_created",
            "snapshot": snapshot_receipt,
        })
        atomic_json(status_path, status)

        progress(
            "analyzing_metadata",
            "organization_planning",
            0,
            len(entries),
            "Tagesordner und Dateinamen werden geplant.",
        )

        plan = _shared_destination_plan(
            build_organization_plan(entries)
        )

        progress(
            "organizing",
            "workspace_moving",
            0,
            len(plan),
            "Dateien werden ohne zweite Datenkopie in den Arbeitsbereich verschoben.",
        )

        move_backup_into_shared_workspace(
            temporary_original,
            work_root,
            plan,
        )

        progress(
            "organizing",
            "workspace_verification",
            len(plan),
            len(plan),
            "Arbeitsbereich stimmt vollständig mit dem Manifest überein.",
        )

        status.update({
            "updated_at": datetime.now().astimezone().isoformat(),
            "stage": "workspace_verified",
            "organization": {
                "working_root": str(work_root),
                "file_count": len(plan),
                "review_required_count": sum(
                    1 for move in plan if move["needs_review"]
                ),
                "verified": True,
                "destinations": [
                    move["destination_relative_path"]
                    for move in plan
                ],
            },
        })
        atomic_json(status_path, status)

        permanent_protocol.parent.mkdir(parents=True, exist_ok=True)
        archive_protocol_directory(temporary_protocol, permanent_protocol)

        if temporary_job_root.exists():
            _remove_empty_directories(temporary_job_root)
            temporary_job_root.rmdir()

        finished_at = datetime.now(timezone.utc).astimezone().isoformat()
        final_status_path = permanent_protocol / "status.json"
        final_manifest_path = permanent_protocol / "manifest.json"
        final_snapshot_path = permanent_protocol / "snapshot.json"

        status.update({
            "updated_at": finished_at,
            "stage": "completed",
            "state": "success",
            "temporary_backup_removed": True,
            "outputs": {
                "manifest": str(final_manifest_path),
                "status": str(final_status_path),
                "snapshot": str(final_snapshot_path),
                "protocol": str(permanent_protocol),
            },
        })
        atomic_json(final_status_path, status)

        append_log(
            log_dir,
            {
                "time": finished_at,
                "job_id": job_id,
                "state": "success",
                "stage": "completed",
                "temporary_backup_removed": True,
                "workspace": str(work_root),
            },
        )

        progress(
            "organizing",
            "completed",
            len(plan),
            len(plan),
            "Sicherung, Prüfung, Snapshot, Überführung und Bereinigung sind abgeschlossen.",
        )

        return status

    except Exception as error:
        failed_at = datetime.now(timezone.utc).astimezone().isoformat()
        status.update({
            "updated_at": failed_at,
            "stage": "failed",
            "state": "failed",
            "error": str(error),
        })

        active_status_path = (
            permanent_protocol / "status.json"
            if permanent_protocol.exists()
            else status_path
        )
        active_status_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(active_status_path, status)

        append_log(
            log_dir,
            {
                "time": failed_at,
                "job_id": job_id,
                "state": "failed",
                "error": str(error),
            },
        )

        raise
