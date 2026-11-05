from __future__ import annotations

"""Normalize physical released archive stock while preserving provenance.

Only the central stock below SD-Kartensicherungen/Freigewordene Archivdateien
is modified. The camera archive is never written.
"""

from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import Any
import os

from app.database import database_connection
from app.free_stock_layout import released_origin_directory
from app.managed_directory_names import directory_path
from app.workspace_layout import backup_root

ROOT_NAME = "Released Archive Files"


class ReleasedArchiveMaintenanceError(RuntimeError):
    pass


def _safe_work_path(root: Path, relative: str) -> Path:
    rel = PurePosixPath(str(relative or "").replace("\\", "/").strip("/"))
    if not rel.parts or rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        raise ReleasedArchiveMaintenanceError("Unsicherer SSD-Pfad: " + str(relative))
    path = root.joinpath(*rel.parts).resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ReleasedArchiveMaintenanceError("SSD-Pfad verlässt den zentralen Aufnahmebestand.") from exc
    return path


def _days_between(start: str, end: str) -> list[str]:
    first = date.fromisoformat(str(start)[:10])
    last = date.fromisoformat(str(end)[:10])
    result: list[str] = []
    current = first
    while current <= last:
        result.append(current.isoformat())
        current += timedelta(days=1)
    return result


def normalize_released_archive_stock_for_days(
    database_path: Path,
    workspace_path: Path,
    days: list[str] | set[str] | tuple[str, ...],
) -> dict[str, Any]:
    work_root = backup_root(workspace_path).resolve(strict=False)
    release_root = directory_path(work_root, "released_archive").resolve(strict=False)
    release_root.mkdir(parents=True, exist_ok=True)
    wanted_days = sorted({str(value)[:10] for value in days if str(value)})
    if not wanted_days:
        return {"updated_family_count": 0, "moved_file_count": 0, "warnings": []}

    placeholders = ",".join("?" for _ in wanted_days)
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT marker.job_id,marker.family_id,
                           marker.released_start_datetime,marker.released_end_datetime,
                           ff.selected_capture_time
                    FROM released_free_families marker
                    JOIN file_families ff ON ff.id=marker.family_id
                    WHERE substr(ff.selected_capture_time,1,10) IN ({placeholders})
                      AND marker.archive_origin=1
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
                      )
                    ORDER BY marker.job_id,marker.family_id""",
                tuple(wanted_days),
            ).fetchall()
        ]
        targets: dict[int, PurePosixPath] = {}
        for row in rows:
            family_id = int(row["family_id"])
            target = released_origin_directory(
                connection,
                family_id,
                str(row.get("selected_capture_time") or ""),
                physical=True,
                release_name=release_root.name,
            )
            if target is not None:
                targets[family_id] = target

    moved: list[tuple[Path, Path]] = []
    db_changes: list[tuple[str, int, str]] = []
    warnings: list[str] = []
    try:
        with database_connection(database_path) as connection:
            for row in rows:
                family_id = int(row["family_id"])
                target_dir = targets.get(family_id)
                if target_dir is None:
                    warnings.append(
                        f"Familie {family_id} besitzt aktuell kein freies Restzeitsegment."
                    )
                    continue
                file_rows = connection.execute(
                    """SELECT id,current_relative_path FROM files
                       WHERE family_id=? AND current_root_kind='shared_workspace'
                       ORDER BY id""",
                    (family_id,),
                ).fetchall()
                asset_rows = connection.execute(
                    """SELECT id,current_relative_path FROM released_archive_assets
                       WHERE family_id=? ORDER BY id""",
                    (family_id,),
                ).fetchall()
                for kind, source_rows in (("file", file_rows), ("asset", asset_rows)):
                    for source_row in source_rows:
                        old_rel = str(source_row["current_relative_path"] or "")
                        if not old_rel:
                            continue
                        source = _safe_work_path(work_root, old_rel)
                        target_rel = (target_dir / PurePosixPath(old_rel).name).as_posix()
                        target = _safe_work_path(work_root, target_rel)
                        if source == target:
                            continue
                        if not source.is_file() or source.is_symlink():
                            raise ReleasedArchiveMaintenanceError(
                                "Freigewordene SSD-Datei fehlt: " + old_rel
                            )
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if target.exists() or target.is_symlink():
                            raise ReleasedArchiveMaintenanceError(
                                "Ziel für freigewordenen Bestand ist bereits belegt: " + target_rel
                            )
                        os.replace(source, target)
                        moved.append((source, target))
                        db_changes.append((kind, int(source_row["id"]), target_rel))

            connection.execute("BEGIN IMMEDIATE")
            for kind, row_id, new_rel in db_changes:
                if kind == "file":
                    connection.execute(
                        "UPDATE files SET current_relative_path=?,updated_at=datetime('now') WHERE id=?",
                        (new_rel, row_id),
                    )
                else:
                    connection.execute(
                        "UPDATE released_archive_assets SET current_relative_path=?,updated_at=datetime('now') WHERE id=?",
                        (new_rel, row_id),
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
        "updated_family_count": len({int(row["family_id"]) for row in rows if int(row["family_id"]) in targets}),
        "moved_file_count": len(moved),
        "warnings": warnings,
    }


def normalize_released_archive_stock(
    database_path: Path,
    workspace_path: Path,
    occupied_ranges: list[tuple[str, str]],
) -> dict[str, Any]:
    days: set[str] = set()
    for start, end in occupied_ranges:
        if start and end:
            days.update(_days_between(start, end))
    return normalize_released_archive_stock_for_days(
        database_path, workspace_path, days
    )
