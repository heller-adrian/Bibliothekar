"""Narrow, evidence-bound recovery for pre.7's duplicate release-copy lease.

This handler is ONLY called under the immutable original F14 archive lease by
app.domain_recovery.replay. It neither writes nor removes media. In particular,
it cannot authorize a mere byte-identical foreign file as an owned SSD copy.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from app.archive_release_stock import (
    _release_context, _safe_archive_path, _safe_workspace_path, _sha256_file,
)
from app.database import database_connection
from app.root_operations import validate_active_roots


def recover_archive_release_copy(
    database_path: Path, archive_root: Path, workspace_path: Path, cr_id: str,
) -> dict:
    """Revalidate pre.7's recorded, already verified copies without re-copying.

    Pre.7 incorrectly replaced release_copy_verified with
    archive_source_still_exists after an early removal verification. Its next
    copy attempt then failed on an existing path, leaving an orphan F14 lease.
    Only a preserved SHA record and *both* byte-identical physical copies can
    justify restoring the earlier state. Any ambiguity remains fenced.
    """
    validate_active_roots()
    context = _release_context(database_path, cr_id, workspace_path)
    request = context["change_request"]
    rows = list(context["rows"])
    if request.get("status") != "aenderbar_bestaetigt" or not rows:
        raise ValueError("archive_release_recovery_wrong_change_request_state")
    states = {str(row.get("verification_status") or "") for row in rows}
    if not states <= {"archive_source_still_exists", "release_copy_verified"}:
        raise ValueError("archive_release_recovery_unproven_copy_status")
    if "archive_source_still_exists" not in states:
        raise ValueError("archive_release_recovery_no_pre7_regression_evidence")

    verified = []
    seen: set[str] = set()
    for row in rows:
        rel = str(row.get("workspace_release_path") or "").strip()
        old = str(row.get("old_path") or "").strip()
        sha = str(row.get("expected_sha256") or "").lower()
        actual = str(row.get("actual_sha256") or "").lower()
        size = int(row.get("expected_size_bytes") or 0)
        actual_size = row.get("actual_size_bytes")
        if (not rel or not old or rel in seen or not re.fullmatch(r"[0-9a-f]{64}", sha)
                or actual != sha or actual_size is None or int(actual_size) != size):
            raise ValueError("archive_release_recovery_unproven_row_identity")
        seen.add(rel)
        source = _safe_archive_path(archive_root, old)
        target = _safe_workspace_path(workspace_path, rel)
        # Both old archive originals and the pre-existing return copies must
        # be ordinary, non-symlink files matching the frozen bytes.
        for path in (source, target):
            if (not path.is_file() or path.is_symlink()
                    or int(path.stat().st_size) != size or _sha256_file(path) != sha):
                raise ValueError("archive_release_recovery_file_mismatch: " + rel)
        verified.append(row)

    validate_active_roots()
    now = datetime.now(timezone.utc).isoformat()
    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        for row in verified:
            if str(row["verification_status"]) == "release_copy_verified":
                continue
            table = (
                "event_change_asset_reviews" if row["review_kind"] == "asset"
                else "event_change_file_reviews"
            )
            cursor = connection.execute(
                f"""UPDATE {table}
                       SET verification_status='release_copy_verified',
                           verified_at=COALESCE(verified_at,?), updated_at=?
                     WHERE id=? AND change_request_id=?
                       AND verification_status='archive_source_still_exists'
                       AND expected_sha256=? AND actual_sha256=?
                       AND expected_size_bytes=? AND actual_size_bytes=?""",
                (now, now, row["id"], cr_id, row["expected_sha256"],
                 row["actual_sha256"], row["expected_size_bytes"], row["actual_size_bytes"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("archive_release_recovery_concurrent_change")
        validate_active_roots()
    return {
        "recovered": True,
        "change_request_id": cr_id,
        "verified_file_count": len(verified),
        "restored_stage": "remove_archive",
        "archive_modified": False,
        "workspace_files_modified": False,
    }
