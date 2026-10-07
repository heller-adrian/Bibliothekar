from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import uuid

from app.database import database_connection
from app.event_access import event_file_rows
from app.event_inventory import EventInventoryError, scan_event_inventory
from app.archive_locations import (
    ArchiveLocationError,
    archive_path_without_symlinks,
    record_family_anchor,
    record_verified_file_location,
)


class ArchiveVerificationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    raw = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(raw)

    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArchiveVerificationError(
            "Unsicherer relativer Archivpfad: " + raw
        )

    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _event_files(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with database_connection(database_path) as connection:
        event = connection.execute(
            """SELECT * FROM events
               WHERE id=? AND job_id=? AND parent_event_id IS NULL""",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            raise ArchiveVerificationError("Ereignis wurde nicht gefunden.")
        rows = event_file_rows(connection, event_id)
    return dict(event), rows


def latest_archive_verification(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM event_archive_verifications
            WHERE job_id = ?
              AND event_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (job_id, event_id),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    raw_details = result.pop("details_json", None)
    result["details"] = json.loads(raw_details) if raw_details else None
    result["verified"] = result.get("status") == "verified"
    return result


def list_archive_candidates(
    database_path: Path,
    archive_root: Path,
) -> dict[str, Any]:
    archive_root = archive_root.expanduser().resolve(strict=False)
    available = archive_root.exists() and archive_root.is_dir()
    readable = available and os.access(archive_root, os.R_OK | os.X_OK)

    with database_connection(database_path) as connection:
        rows = connection.execute(
            """
            WITH RECURSIVE event_tree AS (
                SELECT
                    parent.id AS root_event_id,
                    parent.id AS event_id
                FROM events AS parent
                WHERE parent.parent_event_id IS NULL

                UNION ALL

                SELECT
                    tree.root_event_id,
                    child.id
                FROM event_tree AS tree
                JOIN events AS child
                    ON child.parent_event_id = tree.event_id
            ),
            event_files AS (
                SELECT DISTINCT
                    tree.root_event_id,
                    files.id AS file_id
                FROM event_tree AS tree
                JOIN event_assignments AS assignments
                    ON assignments.event_id = tree.event_id
                JOIN files
                    ON files.family_id = assignments.family_id
                   AND assignments.family_id IS NOT NULL

                UNION

                SELECT DISTINCT
                    tree.root_event_id,
                    files.id AS file_id
                FROM event_tree AS tree
                JOIN event_assignments AS assignments
                    ON assignments.event_id = tree.event_id
                JOIN files
                    ON files.id = assignments.file_id
                   AND assignments.file_id IS NOT NULL
            ),
            event_file_counts AS (
                SELECT
                    event_files.root_event_id AS event_id,
                    COUNT(DISTINCT files.id) AS file_count,
                    COUNT(DISTINCT files.family_id) AS family_count,
                    COALESCE(SUM(files.size_bytes), 0) AS total_size_bytes
                FROM event_files
                JOIN files
                    ON files.id = event_files.file_id
                GROUP BY event_files.root_event_id
            )
            SELECT
                events.id AS event_id,
                events.job_id,
                events.name,
                events.folder_name,
                events.status,
                events.start_datetime,
                events.end_datetime,
                events.created_at AS event_created_at,
                events.applied_at,
                events.archived_at,
                COALESCE(events.resort_required, 0) AS resort_required,
                COALESCE(counts.file_count, 0) AS file_count,
                COALESCE(counts.family_count, 0) AS family_count,
                COALESCE(counts.total_size_bytes, 0) AS total_size_bytes,
                latest_verification.id AS verification_id,
                latest_verification.status AS verification_status,
                latest_verification.file_count AS verification_file_count,
                latest_verification.total_size_bytes AS verification_total_size_bytes,
                latest_verification.verified_file_count,
                latest_verification.missing_file_count,
                latest_verification.mismatched_file_count,
                latest_verification.completed_at AS verification_completed_at,
                latest_verification.error_message AS verification_error_message,
                latest_release.id AS release_id,
                latest_release.status AS release_status,
                latest_release.deleted_file_count AS release_deleted_file_count,
                latest_release.completed_at AS release_completed_at,
                (SELECT COUNT(*) FROM event_reapply_removed_families pr
                 WHERE pr.event_id=events.id AND pr.target_event_id IS NULL) AS pending_reassignment_count,
                (SELECT COUNT(*) FROM event_mutations em
                 WHERE em.job_id=events.job_id AND em.status IN ('pending_reassignment','pending_apply','manual_archive')) AS active_mutation_count
            FROM events
            LEFT JOIN event_file_counts AS counts
                ON counts.event_id = events.id
            LEFT JOIN event_archive_verifications AS latest_verification
                ON latest_verification.id = (
                    SELECT verification.id
                    FROM event_archive_verifications AS verification
                    WHERE verification.event_id = events.id
                      AND verification.job_id = events.job_id
                    ORDER BY verification.created_at DESC, verification.id DESC
                    LIMIT 1
                )
            LEFT JOIN event_ssd_releases AS latest_release
                ON latest_release.id = (
                    SELECT release.id
                    FROM event_ssd_releases AS release
                    WHERE release.event_id = events.id
                      AND release.job_id = events.job_id
                    ORDER BY release.created_at DESC, release.id DESC
                    LIMIT 1
                )
            WHERE events.parent_event_id IS NULL
              AND events.status IN ('applied', 'archived')
            ORDER BY events.created_at DESC, events.id DESC
            """
        ).fetchall()

    candidates: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)
        item["archive_verification_ready"] = bool(readable)
        item["archive_root"] = str(archive_root)
        item["verification_invalidated"] = (
            item.get("verification_status") == "failed"
            and item.get("verification_error_message") == "verification_invalidated_by_edit"
        )
        item["verified"] = item.get("verification_status") == "verified"
        if item.get("verification_file_count") is not None:
            item["file_count"] = int(item.get("verification_file_count") or 0)
            item["total_size_bytes"] = int(
                item.get("verification_total_size_bytes")
                or item.get("total_size_bytes")
                or 0
            )
        item["released"] = (
            item.get("release_status") == "completed"
            or item.get("status") == "archived"
        )
        item["ssd_release_ready"] = (
            item["verified"]
            and not item["released"]
            and item.get("status") == "applied"
            and int(item.get("pending_reassignment_count") or 0) == 0
            and int(item.get("active_mutation_count") or 0) == 0
            and int(item.get("resort_required") or 0) == 0
        )
        if int(item.get("resort_required") or 0):
            item["ssd_release_block_reason"] = (
                "Nachsortierung noch offen. Bitte die angewendete Änderung zuerst vollständig ausführen."
            )
        elif int(item.get("pending_reassignment_count") or 0) > 0 or int(item.get("active_mutation_count") or 0) > 0:
            item["ssd_release_block_reason"] = (
                "Offene Neu-Zuordnung/Ereignisänderung zuerst abschließen."
            )
        else:
            item["ssd_release_block_reason"] = None
        item["ssd_release_available"] = True
        candidates.append(item)

    return {
        "archive_root": str(archive_root),
        "archive_available": bool(available),
        "archive_readable": bool(readable),
        "candidate_count": sum(1 for item in candidates if not item["released"]),
        "verified_count": sum(1 for item in candidates if item["verified"] and not item["released"]),
        "released_count": sum(1 for item in candidates if item["released"]),
        "blocked_count": sum(
            1 for item in candidates
            if item.get("verification_status") == "failed"
            and not item.get("verification_invalidated")
        ),
        "candidates": candidates,
    }


def verify_event_archive(
    database_path: Path,
    archive_root: Path,
    job_id: str,
    event_id: str,
    *,
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    archive_root = archive_root.expanduser().resolve(strict=False)

    if not archive_root.exists() or not archive_root.is_dir():
        raise ArchiveVerificationError(
            "Die Kamerabibliothek ist nicht als lesbarer Ordner eingebunden."
        )

    if not os.access(archive_root, os.R_OK | os.X_OK):
        raise ArchiveVerificationError(
            "Die Kamerabibliothek ist nicht lesbar eingebunden."
        )

    event, files = _event_files(
        database_path,
        job_id,
        event_id,
    )

    if str(event.get("status")) not in {"applied", "archived"}:
        raise ArchiveVerificationError(
            "Nur angewendete oder archivierte Ereignisse können geprüft werden."
        )

    if str(event.get("status")) == "applied" and int(event.get("resort_required") or 0):
        raise ArchiveVerificationError(
            "Archivprüfung gesperrt: Die Nachsortierung des Ereignisses ist noch nicht abgeschlossen."
        )

    if not files:
        raise ArchiveVerificationError(
            "Dem Ereignis sind keine Dateien zugeordnet."
        )

    try:
        inventory = scan_event_inventory(
            database_path,
            archive_root,
            job_id,
            event_id,
            root_kind="camera_archive",
            persist=True,
            update_known_file_locations=False,
        )
    except EventInventoryError as exc:
        raise ArchiveVerificationError(str(exc)) from exc

    observed_by_file_id = {
        int(item["known_file_id"]): item
        for item in inventory["files"]
        if item.get("known_file_id") is not None
    }

    # 0.27.7: XMP und Exporte sind nach dem Anwenden echter Ereignisbestand.
    # Für die Archivprüfung wird deshalb zusätzlich der aktuelle Arbeitsbereich-Bestand
    # als SOLL gelesen. Unbekannte Fremddateien bleiben weiterhin nur Hinweis.
    managed_asset_kinds = {"xmp", "export", "derived_media"}
    source_assets: list[dict[str, Any]] = []
    source_known_by_file_id: dict[int, dict[str, Any]] = {}
    if workspace_path is not None and str(event.get("status") or "") == "applied":
        try:
            from app.workspace_layout import shared_work_root
            workspace_inventory = scan_event_inventory(
                database_path,
                shared_work_root(workspace_path),
                job_id,
                event_id,
                root_kind="shared_workspace",
                persist=True,
                update_known_file_locations=False,
                fast_refresh=False,
            )
        except (EventInventoryError, Exception) as exc:
            if isinstance(exc, EventInventoryError):
                raise ArchiveVerificationError(str(exc)) from exc
            raise
        source_known_by_file_id = {
            int(item["known_file_id"]): item
            for item in workspace_inventory["files"]
            if item.get("known_file_id") is not None
        }
        source_assets = [
            item
            for item in workspace_inventory["files"]
            if item.get("known_file_id") is None
            and str(item.get("asset_kind") or "") in managed_asset_kinds
        ]

    archive_assets_by_event_path = {
        str(item.get("event_relative_path") or ""): item
        for item in inventory["files"]
        if item.get("known_file_id") is None
        and str(item.get("asset_kind") or "") in managed_asset_kinds
    }

    verification_id = "ARCHIVE_" + uuid.uuid4().hex.upper()
    created_at = _now()
    total_size = (
        sum(int(row["size_bytes"]) for row in files)
        + sum(int(row["size_bytes"]) for row in source_assets)
    )

    with database_connection(database_path) as connection:
        connection.execute(
            """
            INSERT INTO event_archive_verifications (
                id,
                job_id,
                event_id,
                status,
                archive_root,
                file_count,
                total_size_bytes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'running', ?, ?, ?, ?, ?)
            """,
            (
                verification_id,
                job_id,
                event_id,
                str(archive_root),
                len(files) + len(source_assets),
                total_size,
                created_at,
                created_at,
            ),
        )

    results: list[dict[str, Any]] = []
    verified_count = 0
    verified_bytes = 0
    missing_count = 0
    mismatched_count = 0

    archive_event_prefix = str(inventory.get("event_prefix") or "").strip("/")
    for row in files:
        try:
            file_id = int(row["file_id"])
            source_observed = source_known_by_file_id.get(file_id)
            if source_known_by_file_id and source_observed is None:
                relative_text = str(
                    row.get("current_relative_path")
                    or row.get("original_relative_path")
                    or ""
                )
                result = {
                    "file_id": file_id,
                    "expected_relative_path": relative_text,
                    "expected_size_bytes": int(row["size_bytes"]),
                    "expected_sha256": str(
                        row.get("sha256_current") or row.get("sha256_original") or ""
                    ),
                    "status": "missing",
                    "actual_size_bytes": None,
                    "actual_sha256": None,
                    "error_message": (
                        "Die Datei fehlt bereits im aktuellen SSD-Ereignisbestand. "
                        "Eine Löschung muss zuerst durch zwei vollständige Scans bestätigt sein."
                    ),
                }
                missing_count += 1
                results.append(result)
                continue

            if source_observed is not None:
                expected_size = int(source_observed.get("size_bytes") or 0)
                expected_sha256 = str(source_observed.get("sha256") or "").strip()
                source_event_relative = str(
                    source_observed.get("event_relative_path") or ""
                ).replace("\\", "/").strip("/")
                expected_relative = "/".join(
                    part for part in (archive_event_prefix, source_event_relative) if part
                )
            else:
                expected_size = int(row["size_bytes"])
                expected_sha256 = str(
                    row.get("sha256_current")
                    or row.get("sha256_original")
                    or ""
                ).strip()
                expected_relative = str(
                    row.get("current_relative_path")
                    or row.get("original_relative_path")
                    or ""
                ).replace("\\", "/").strip("/")

            if not expected_sha256:
                raise ArchiveVerificationError("Gespeicherte SHA-256-Summe fehlt.")

            observed = observed_by_file_id.get(file_id)
            if observed is None:
                relative_text = expected_relative
                status = "missing"
                actual_size = None
                actual_sha256 = None
                error_message = (
                    "Datei wurde im aktuellen Ereignisordner der Kamerabibliothek nicht gefunden."
                )
                missing_count += 1
            else:
                actual_relative = str(observed["relative_path"]).replace("\\", "/").strip("/")
                relative_text = expected_relative
                candidate = archive_path_without_symlinks(
                    archive_root,
                    actual_relative,
                )
                actual_size = int(observed["size_bytes"])
                actual_sha256 = str(observed["sha256"])
                if actual_size != expected_size:
                    status = "size_mismatch"
                    error_message = "Dateigröße weicht vom aktuellen Arbeitsbereich-Bestand ab."
                    mismatched_count += 1
                elif actual_sha256 != expected_sha256:
                    status = "sha256_mismatch"
                    error_message = "SHA-256-Summe weicht vom aktuellen Arbeitsbereich-Bestand ab."
                    mismatched_count += 1
                elif actual_relative != expected_relative:
                    status = "missing"
                    error_message = (
                        "Die Ordnerlage im Archiv stimmt nicht mit dem aktuellen Arbeitsbereich-Bestand überein. "
                        f"Archiv: {actual_relative} · SSD-SOLL: {expected_relative}"
                    )
                    mismatched_count += 1
                elif not candidate.is_file():
                    status = "missing"
                    error_message = "Datei fehlt in der Kamerabibliothek."
                    missing_count += 1
                else:
                    status = "verified"
                    error_message = None
                    verified_count += 1
                    verified_bytes += expected_size

            result = {
                "file_id": int(row["file_id"]),
                "expected_relative_path": relative_text,
                "expected_size_bytes": expected_size,
                "expected_sha256": expected_sha256,
                "status": status,
                "actual_size_bytes": actual_size,
                "actual_sha256": actual_sha256,
                "error_message": error_message,
            }

        except Exception as error:
            result = {
                "file_id": int(row["file_id"]),
                "expected_relative_path": str(
                    row.get("current_relative_path")
                    or row.get("original_relative_path")
                    or ""
                ),
                "expected_size_bytes": int(row["size_bytes"]),
                "expected_sha256": str(
                    row.get("sha256_current")
                    or row.get("sha256_original")
                    or ""
                ),
                "status": "unsafe_path",
                "actual_size_bytes": None,
                "actual_sha256": None,
                "error_message": str(error),
            }
            mismatched_count += 1

        results.append(result)

    asset_results: list[dict[str, Any]] = []
    event_prefix = archive_event_prefix
    for asset in source_assets:
        event_rel = str(asset.get("event_relative_path") or "").strip("/")
        expected_relative = "/".join(part for part in (event_prefix, event_rel) if part)
        expected_size = int(asset.get("size_bytes") or 0)
        expected_sha256 = str(asset.get("sha256") or "")
        observed = archive_assets_by_event_path.get(event_rel)

        if observed is None:
            status = "missing"
            actual_size = None
            actual_sha256 = None
            error_message = "Zusatzdatei fehlt am erwarteten SOLL-Pfad der Kamerabibliothek."
            missing_count += 1
        else:
            actual_size = int(observed.get("size_bytes") or 0)
            actual_sha256 = str(observed.get("sha256") or "")
            if actual_size != expected_size:
                status = "size_mismatch"
                error_message = "Dateigröße der Zusatzdatei weicht ab."
                mismatched_count += 1
            elif actual_sha256 != expected_sha256:
                status = "sha256_mismatch"
                error_message = "SHA-256-Summe der Zusatzdatei weicht ab."
                mismatched_count += 1
            else:
                status = "verified"
                error_message = None
                verified_count += 1
                verified_bytes += expected_size

        asset_results.append({
            "asset_kind": str(asset.get("asset_kind") or "other"),
            "source_event_relative_path": event_rel,
            "expected_relative_path": expected_relative,
            "expected_size_bytes": expected_size,
            "expected_sha256": expected_sha256,
            "status": status,
            "actual_size_bytes": actual_size,
            "actual_sha256": actual_sha256,
            "error_message": error_message,
        })

    final_status = (
        "verified"
        if verified_count == len(files) + len(source_assets)
        and missing_count == 0
        and mismatched_count == 0
        else "failed"
    )
    completed_at = _now()
    details = {
        "event_name": event.get("name"),
        "folder_name": event.get("folder_name"),
        "files": results,
    }

    with database_connection(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO event_archive_verification_files (
                verification_id,
                file_id,
                expected_relative_path,
                expected_size_bytes,
                expected_sha256,
                status,
                actual_size_bytes,
                actual_sha256,
                error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    verification_id,
                    item["file_id"],
                    item["expected_relative_path"],
                    item["expected_size_bytes"],
                    item["expected_sha256"],
                    item["status"],
                    item["actual_size_bytes"],
                    item["actual_sha256"],
                    item["error_message"],
                )
                for item in results
            ],
        )
        connection.executemany(
            """
            INSERT INTO event_archive_verification_assets (
                verification_id,asset_kind,source_event_relative_path,
                expected_relative_path,expected_size_bytes,expected_sha256,status,
                actual_size_bytes,actual_sha256,error_message
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    verification_id,
                    item["asset_kind"],
                    item["source_event_relative_path"],
                    item["expected_relative_path"],
                    item["expected_size_bytes"],
                    item["expected_sha256"],
                    item["status"],
                    item["actual_size_bytes"],
                    item["actual_sha256"],
                    item["error_message"],
                )
                for item in asset_results
            ],
        )

        connection.execute(
            """
            UPDATE event_archive_verifications
            SET
                status = ?,
                verified_file_count = ?,
                verified_size_bytes = ?,
                missing_file_count = ?,
                mismatched_file_count = ?,
                details_json = ?,
                error_message = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                final_status,
                verified_count,
                verified_bytes,
                missing_count,
                mismatched_count,
                json.dumps(details, ensure_ascii=False, sort_keys=True),
                None if final_status == "verified" else "Archivprüfung ist nicht vollständig erfolgreich.",
                completed_at,
                completed_at,
                verification_id,
            ),
        )

        if final_status == "verified":
            family_by_file = {int(row["file_id"]): int(row["family_id"]) for row in files if row.get("family_id") is not None}
            paths_by_family: dict[int, list[str]] = {}
            for item in results:
                family_id = family_by_file.get(int(item["file_id"]))
                if family_id is not None and item.get("status") == "verified":
                    paths_by_family.setdefault(family_id, []).append(str(item["expected_relative_path"]))
            for family_id, verified_paths in paths_by_family.items():
                record_family_anchor(connection, event_id, family_id, verified_paths, completed_at)
            for item in results:
                family_id = family_by_file.get(int(item["file_id"]))
                if family_id is not None and item.get("status") == "verified":
                    record_verified_file_location(
                        connection, event_id, family_id, int(item["file_id"]),
                        str(item["expected_relative_path"]), completed_at,
                    )

    return {
        "id": verification_id,
        "job_id": job_id,
        "event_id": event_id,
        "status": final_status,
        "verified": final_status == "verified",
        "archive_root": str(archive_root),
        "file_count": len(files) + len(source_assets),
        "camera_file_count": len(files),
        "asset_file_count": len(source_assets),
        "verified_file_count": verified_count,
        "total_size_bytes": total_size,
        "verified_size_bytes": verified_bytes,
        "missing_file_count": missing_count,
        "mismatched_file_count": mismatched_count,
        "files": results,
        "assets": asset_results,
        "ssd_release_ready": final_status == "verified",
        "ssd_release_available": True,
        "inventory_summary": inventory.get("summary"),
        "message": (
            "Kamerabibliothek vollständig identisch geprüft."
            if final_status == "verified"
            else "Kamerabibliothek ist noch nicht vollständig identisch."
        ),
    }
