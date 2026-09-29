from __future__ import annotations

"""Keep remaining released archive stock aligned with its exact free interval.

This module writes only below Arbeitsbereich/Freigewordene Archivdateien.
The camera archive is never touched.
"""

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import os

from app.database import database_connection
from app.workspace_layout import shared_work_root

ROOT_NAME = "Freigewordene Archivdateien"


class ReleasedArchiveMaintenanceError(RuntimeError):
    pass


def _segment_folder(start: str, end: str) -> str:
    day = start[:10]
    start_time = start[11:16] or "00:00"
    end_time = end[11:16] or "23:59"
    if start_time == "00:00" and end_time == "23:59":
        return day
    return f"{day} · {start_time.replace(':','-')}–{end_time.replace(':','-')}"


def _subtract(
    start: str,
    end: str,
    occupied: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    parts = [(start, end)]
    for occ_start, occ_end in sorted(occupied):
        next_parts: list[tuple[str, str]] = []
        for left, right in parts:
            if occ_end < left or occ_start > right:
                next_parts.append((left, right))
                continue
            if occ_start > left:
                next_parts.append((left, occ_start))
            if occ_end < right:
                next_parts.append((occ_end, right))
        parts = next_parts
    return parts


def _safe_work_path(root: Path, relative: str) -> Path:
    rel = PurePosixPath(str(relative or "").replace("\\", "/").strip("/"))
    if not rel.parts or rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ReleasedArchiveMaintenanceError("Unsicherer SSD-Pfad: " + str(relative))
    path = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReleasedArchiveMaintenanceError("SSD-Pfad verlässt den Arbeitsbereich.") from exc
    return path


def normalize_released_archive_stock(
    database_path: Path,
    workspace_path: Path,
    occupied_ranges: list[tuple[str, str]],
) -> dict[str, Any]:
    work_root = shared_work_root(workspace_path).resolve(strict=False)
    release_root = (work_root / ROOT_NAME).resolve(strict=False)
    release_root.mkdir(parents=True, exist_ok=True)
    normalized_occupied = [
        (str(a)[:19], str(b)[:19])
        for a, b in occupied_ranges
        if str(a) and str(b)
    ]
    if not normalized_occupied:
        return {"updated_family_count": 0, "moved_file_count": 0, "warnings": []}

    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT marker.job_id,marker.family_id,
                          marker.released_start_datetime,marker.released_end_datetime,
                          ff.selected_capture_time
                   FROM released_free_families marker
                   JOIN file_families ff ON ff.id=marker.family_id
                   WHERE ff.selected_capture_time IS NOT NULL
                     AND NOT EXISTS (
                       SELECT 1 FROM event_assignments ea
                       JOIN events e ON e.id=ea.event_id
                       WHERE ea.family_id=marker.family_id
                         AND e.status IN ('draft','planned','applied','archived')
                     )
                     AND EXISTS (
                       SELECT 1 FROM files f
                       WHERE f.family_id=marker.family_id
                         AND f.current_root_kind='shared_workspace'
                         AND f.current_relative_path LIKE 'Freigewordene Archivdateien/%'
                     )
                   ORDER BY marker.job_id,marker.family_id"""
            ).fetchall()
        ]

    updates: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        start = str(row.get("released_start_datetime") or "")[:19]
        end = str(row.get("released_end_datetime") or "")[:19]
        capture = str(row.get("selected_capture_time") or "")[:19]
        if not start or not end or not capture:
            continue
        overlaps = [
            (a, b) for a, b in normalized_occupied
            if not (b < start or a > end)
        ]
        if not overlaps:
            continue
        residual = _subtract(start, end, overlaps)
        containing = [
            (a, b) for a, b in residual
            if a <= capture <= b
        ]
        if len(containing) != 1:
            warnings.append(
                f"Familie {row['family_id']} besitzt nach der Teilzuordnung kein eindeutiges Restzeitsegment."
            )
            continue
        new_start, new_end = containing[0]
        if (new_start, new_end) == (start, end):
            continue
        updates.append({
            **row,
            "new_start": new_start,
            "new_end": new_end,
            "target_directory": PurePosixPath(
                ROOT_NAME,
                new_start[:4],
                _segment_folder(new_start, new_end),
            ).as_posix(),
        })

    moved: list[tuple[Path, Path]] = []
    db_changes: list[tuple[str, int, int | None, str, str]] = []
    try:
        with database_connection(database_path) as connection:
            for update in updates:
                family_id = int(update["family_id"])
                job_id = str(update["job_id"])
                camera_rows = connection.execute(
                    """SELECT id,current_relative_path
                       FROM files
                       WHERE family_id=? AND job_id=?
                         AND current_root_kind='shared_workspace'
                         AND current_relative_path LIKE 'Freigewordene Archivdateien/%'
                       ORDER BY id""",
                    (family_id, job_id),
                ).fetchall()
                asset_rows = connection.execute(
                    """SELECT id,current_relative_path
                       FROM released_archive_assets
                       WHERE family_id=? AND job_id=?
                       ORDER BY id""",
                    (family_id, job_id),
                ).fetchall()
                for kind, source_rows in (("file", camera_rows), ("asset", asset_rows)):
                    for source_row in source_rows:
                        old_rel = str(source_row["current_relative_path"])
                        source = _safe_work_path(work_root, old_rel)
                        filename = PurePosixPath(old_rel).name
                        target_rel = PurePosixPath(
                            str(update["target_directory"]), filename
                        ).as_posix()
                        target = _safe_work_path(work_root, target_rel)
                        if source == target:
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if target.exists() or target.is_symlink():
                            stem = target.stem
                            suffix = target.suffix
                            index = 1
                            while target.exists() or target.is_symlink():
                                target_rel = PurePosixPath(
                                    str(update["target_directory"]),
                                    f"{stem}_{index:03d}{suffix}",
                                ).as_posix()
                                target = _safe_work_path(work_root, target_rel)
                                index += 1
                        if not source.is_file() or source.is_symlink():
                            raise ReleasedArchiveMaintenanceError(
                                "Freigewordene SSD-Datei fehlt: " + old_rel
                            )
                        os.replace(source, target)
                        moved.append((source, target))
                        db_changes.append(
                            (kind, int(source_row["id"]), family_id, old_rel, target_rel)
                        )

            connection.execute("BEGIN IMMEDIATE")
            for update in updates:
                connection.execute(
                    """UPDATE released_free_families
                       SET released_start_datetime=?,released_end_datetime=?
                       WHERE job_id=? AND family_id=?""",
                    (
                        update["new_start"], update["new_end"],
                        str(update["job_id"]), int(update["family_id"]),
                    ),
                )
            now = datetime.now(timezone.utc).isoformat()
            for kind, row_id, _family_id, _old_rel, new_rel in db_changes:
                if kind == "file":
                    connection.execute(
                        "UPDATE files SET current_relative_path=?,updated_at=? WHERE id=?",
                        (new_rel, now, row_id),
                    )
                else:
                    connection.execute(
                        "UPDATE released_archive_assets SET current_relative_path=?,updated_at=? WHERE id=?",
                        (new_rel, now, row_id),
                    )
            connection.commit()
    except Exception:
        for source, target in reversed(moved):
            try:
                source.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not source.exists():
                    os.replace(target, source)
            except OSError:
                pass
        raise

    # Remove only empty descendants; persistent root itself remains.
    for directory in sorted(
        [p for p in release_root.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass

    return {
        "updated_family_count": len(updates),
        "moved_file_count": len(moved),
        "warnings": warnings,
    }
