from __future__ import annotations

from app.root_operations import protect, validate_active_roots



import hashlib
import os
from pathlib import Path
from typing import Any

from app.archive_release_stock import (
    ArchiveReleaseStockError,
    _release_context,
    _safe_archive_path,
    _safe_workspace_path,
    _sha256_file,
)
from app.database import database_connection


@protect(workspace_arg='workspace_path', database_arg='database_path', kind='archive', error_type=ArchiveReleaseStockError)
def create_archive_release_copies(
    database_path: Path,
    archive_root: Path,
    workspace_path: Path,
    cr_id: str,
) -> dict[str, Any]:
    """Copy the frozen archive source set to the prepared SSD return paths.

    The archive is read only. Sources are verified before copying, targets are
    created exclusively, and every completed target is verified again before
    the database records the copy as created.
    """

    context = _release_context(database_path, cr_id)
    rows = list(context.get("rows") or [])
    if not rows:
        return {
            "complete": True,
            "copied_file_count": 0,
            "file_count": 0,
            "files": [],
        }

    created_paths: list[Path] = []
    copied_rows: list[tuple[str, int, int, str]] = []
    results: list[dict[str, Any]] = []

    def refused(code: str, detail: str) -> dict[str, Any]:
        """A proven read-only precondition failure is NOT an interrupted write.

        Return normally from the durable root operation so no orphan lease is
        created for an expected collision or an archive source discrepancy.
        """
        return {
            "complete": False, "copied_file_count": 0,
            "file_count": len(rows), "status": "needs_review",
            "error_code": code, "message": detail,
            "files": [],
        }

    # Phase 1: preflight the WHOLE frozen set before writing a single byte.
    # Idempotent retries are allowed ONLY for paths already recorded as
    # verified by this exact change request. A merely byte-identical foreign
    # file does not prove ownership and must not become a cleanup candidate.
    inspected: list[tuple[dict[str, Any], Path, Path, int, str, bool]] = []
    for row in rows:
        expected_size = int(row.get("expected_size_bytes") or 0)
        expected_sha = str(row.get("expected_sha256") or "").strip()
        if not expected_sha:
            return refused("archive_release_missing_sha256", "A saved source SHA-256 is missing.")
        release_rel = str(row.get("workspace_release_path") or "").strip()
        if not release_rel:
            return refused("archive_release_path_missing", "The SSD return path has not been prepared.")
        source = _safe_archive_path(archive_root, row.get("old_path"))
        target = _safe_workspace_path(workspace_path, release_rel)
        recorded = str(row.get("verification_status") or "") in {"release_copy_verified", "verified"}
        if target.exists() or target.is_symlink():
            if (not recorded or not target.is_file() or target.is_symlink()
                    or (expected_size and int(target.stat().st_size) != expected_size)
                    or _sha256_file(target) != expected_sha):
                return refused(
                    "archive_release_target_exists",
                    "The SSD return path is occupied or has no verified ownership: " + release_rel,
                )
        elif recorded:
            return refused(
                "archive_release_verified_copy_missing",
                "A previously verified SSD copy is missing: " + release_rel,
            )
        if not recorded or source.exists():
            if not source.is_file() or source.is_symlink():
                return refused(
                    "archive_release_source_missing",
                    "The planned archive original is missing: " + str(row.get("old_path") or ""),
                )
            if ((expected_size and int(source.stat().st_size) != expected_size)
                    or _sha256_file(source) != expected_sha):
                return refused(
                    "archive_release_source_mismatch",
                    "The planned archive original has changed: " + str(row.get("old_path") or ""),
                )
        inspected.append((row, source, target, expected_size, expected_sha, recorded))

    try:
        for row, source, target, expected_size, expected_sha, recorded in inspected:
            if recorded:
                results.append({
                    "review_kind": row["review_kind"], "id": int(row["id"]),
                    "family_id": row.get("family_id"),
                    "old_path": row.get("old_path"),
                    "workspace_release_path": row.get("workspace_release_path"),
                    "status": "release_copy_verified",
                })
                continue
            # A target could appear after preflight. This is a race / unknown
            # owner, not authority to overwrite it; the durable lease stays
            # unresolved unless the original operation can prove rollback.

            release_rel = str(row["workspace_release_path"])
            validate_active_roots()
            target.parent.mkdir(parents=True, exist_ok=True)

            digest = hashlib.sha256()
            copied_size = 0
            validate_active_roots()
            with source.open("rb") as src, target.open("xb") as dst:
                created_paths.append(target)
                while True:
                    block = src.read(1024 * 1024)
                    if not block:
                        break
                    dst.write(block)
                    digest.update(block)
                    copied_size += len(block)
                dst.flush()
                os.fsync(dst.fileno())

            copied_sha = digest.hexdigest()
            if (expected_size and copied_size != expected_size) or copied_sha != expected_sha:
                raise ArchiveReleaseStockError(
                    "Die neu angelegte SSD-Kopie stimmt nicht mit dem Archivoriginal überein: "
                    + release_rel
                )

            copied_rows.append((
                str(row["review_kind"]),
                int(row["id"]),
                copied_size,
                copied_sha,
            ))
            results.append({
                "review_kind": row["review_kind"],
                "id": int(row["id"]),
                "family_id": row.get("family_id"),
                "old_path": row.get("old_path"),
                "workspace_release_path": release_rel,
                "status": "release_copy_verified",
            })
    except Exception:
        for target in reversed(created_paths):
            try:
                if target.is_file() and not target.is_symlink():
                    validate_active_roots()
                    target.unlink()
            except OSError:
                pass
        raise

    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
    with database_connection(database_path) as connection:
        for kind, review_id, copied_size, copied_sha in copied_rows:
            table = "event_change_asset_reviews" if kind == "asset" else "event_change_file_reviews"
            connection.execute(
                f"""UPDATE {table}
                    SET verification_status='release_copy_verified',
                        actual_size_bytes=?,actual_sha256=?,
                        verified_at=?,updated_at=?
                    WHERE id=? AND change_request_id=?""",
                (copied_size, copied_sha, now, now, review_id, cr_id),
            )

    return {
        "complete": True,
        "copied_file_count": len(copied_rows),
        "verified_file_count": len(results),
        "file_count": len(rows),
        "files": results,
    }
