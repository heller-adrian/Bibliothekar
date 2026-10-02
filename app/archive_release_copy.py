from __future__ import annotations

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

    try:
        for row in rows:
            expected_size = int(row.get("expected_size_bytes") or 0)
            expected_sha = str(row.get("expected_sha256") or "").strip()
            if not expected_sha:
                raise ArchiveReleaseStockError(
                    "Gespeicherte SHA-256-Summe einer freigewordenen Archivdatei fehlt."
                )

            source = _safe_archive_path(archive_root, row.get("old_path"))
            if not source.is_file() or source.is_symlink():
                raise ArchiveReleaseStockError(
                    "Das geplante Archivoriginal ist nicht mehr als reguläre Datei vorhanden: "
                    + str(row.get("old_path") or "")
                )
            source_size = int(source.stat().st_size)
            if expected_size and source_size != expected_size:
                raise ArchiveReleaseStockError(
                    "Das Archivoriginal hat seit der Planung eine andere Dateigröße: "
                    + str(row.get("old_path") or "")
                )
            if _sha256_file(source) != expected_sha:
                raise ArchiveReleaseStockError(
                    "Das Archivoriginal hat sich seit der Planung verändert: "
                    + str(row.get("old_path") or "")
                )

            release_rel = str(row.get("workspace_release_path") or "").strip()
            if not release_rel:
                raise ArchiveReleaseStockError(
                    "Der SSD-Rückkehrpfad wurde noch nicht vorbereitet."
                )
            target = _safe_workspace_path(workspace_path, release_rel)
            if target.exists() or target.is_symlink():
                raise ArchiveReleaseStockError(
                    "Am SSD-Rückkehrpfad existiert bereits ein Eintrag: " + release_rel
                )
            target.parent.mkdir(parents=True, exist_ok=True)

            digest = hashlib.sha256()
            copied_size = 0
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
                "status": "copy_created",
            })
    except Exception:
        for target in reversed(created_paths):
            try:
                if target.is_file() and not target.is_symlink():
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
                    SET verification_status='copy_created',
                        actual_size_bytes=?,actual_sha256=?,
                        verified_at=NULL,updated_at=?
                    WHERE id=? AND change_request_id=?""",
                (copied_size, copied_sha, now, review_id, cr_id),
            )

    return {
        "complete": True,
        "copied_file_count": len(results),
        "file_count": len(results),
        "files": results,
    }
