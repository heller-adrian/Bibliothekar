"""Read-only discovery of workspace sidecars/exports before first apply.

The SQLite import catalogue contains camera/imported files. XMP files and
Lightroom exports may be created later directly in the free SSD stock. This
module observes those physical neighbours without persisting them, so planned
cards and inspectors can show the same complete family that the apply plan
will later move.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from app.database import database_connection
from app.event_inventory import _filename_family_source
from app.filename_collisions import export_collision_base_stem
from app.metadata import classify_media
from app.workspace_layout import backup_root, resolve_workspace_root, shared_work_root


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def discover_workspace_family_assets(
    database_path: Path,
    workspace_path: Path,
    family_ids: Iterable[int],
) -> dict[int, dict[str, Any]]:
    """Return physical non-camera assets grouped by family.

    Returned counts are additional to rows in files. Persisted
    released_archive_assets are included when their SSD file still exists;
    unpersisted XMP/export neighbours are detected conservatively by filename.
    No database or filesystem state is changed.
    """
    ids = sorted({int(value) for value in family_ids})
    if not ids:
        return {}

    try:
        root = resolve_workspace_root(workspace_path).resolve(strict=False)
        central_root = backup_root(workspace_path).resolve(strict=False)
    except Exception:
        return {}
    try:
        work_root = shared_work_root(workspace_path).resolve(strict=False)
    except Exception:
        work_root = None
    if not root.is_dir() or not central_root.is_dir():
        return {}
    if work_root is not None and not work_root.is_dir():
        work_root = None

    def _safe_under(path: Path, base: Path) -> bool:
        try:
            path.relative_to(base)
            return True
        except ValueError:
            return False

    def physical_path(
        relative_value: str,
        *,
        prefer_central: bool = False,
    ) -> tuple[Path, Path, str]:
        relative = Path(str(relative_value or "").strip())
        if relative.is_absolute() or ".." in relative.parts:
            return central_root / "__unsafe__", central_root, "central_stock"
        roots: list[tuple[Path, str]] = [(central_root, "central_stock")]
        if work_root is not None:
            roots.append((work_root, "shared_workspace"))
        if not prefer_central and len(roots) > 1:
            roots = [roots[1], roots[0]]
        for base, kind in roots:
            candidate = (base / relative).resolve(strict=False)
            if _safe_under(candidate, base) and candidate.is_file():
                return candidate, base, kind
        base, kind = roots[0]
        return (base / relative).resolve(strict=False), base, kind

    placeholders = ",".join("?" for _ in ids)
    with database_connection(database_path) as connection:
        known_rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT f.id AS file_id,f.family_id,f.original_relative_path,
                           f.current_relative_path,f.original_filename,f.size_bytes,
                           ff.original_stem
                    FROM files f
                    JOIN file_families ff ON ff.id=f.family_id
                    WHERE f.family_id IN ({placeholders})
                      AND f.current_root_kind='shared_workspace'
                    ORDER BY f.family_id,f.id""",
                tuple(ids),
            ).fetchall()
        ]
        tracked_rows = [
            dict(row)
            for row in connection.execute(
                f"""SELECT id,family_id,source_file_id,asset_kind,
                           current_relative_path,size_bytes
                    FROM released_archive_assets
                    WHERE family_id IN ({placeholders})
                    ORDER BY family_id,current_relative_path,id""",
                tuple(ids),
            ).fetchall()
        ]

    result: dict[int, dict[str, Any]] = {
        family_id: {
            "assets": [],
            "file_count": 0,
            "total_size_bytes": 0,
            "asset_kinds": set(),
            "tracked_file_count": 0,
            "untracked_file_count": 0,
        }
        for family_id in ids
    }
    seen_paths: set[Path] = set()

    def add_asset(
        family_id: int,
        path: Path,
        *,
        source_root: Path,
        source_root_kind: str,
        asset_kind: str,
        tracked: bool,
        source_file_id: int | None = None,
    ) -> None:
        resolved = path.resolve(strict=False)
        source_root = source_root.resolve(strict=False)
        if resolved in seen_paths or not _safe_under(resolved, source_root):
            return
        try:
            if not resolved.is_file() or resolved.is_symlink():
                return
            size = int(resolved.stat(follow_symlinks=False).st_size)
        except OSError:
            return
        seen_paths.add(resolved)
        bucket = result.setdefault(
            family_id,
            {
                "assets": [],
                "file_count": 0,
                "total_size_bytes": 0,
                "asset_kinds": set(),
                "tracked_file_count": 0,
                "untracked_file_count": 0,
            },
        )
        bucket["assets"].append({
            "asset_kind": asset_kind,
            "path": str(resolved.relative_to(source_root).as_posix()),
            "filename": resolved.name,
            "size_bytes": size,
            "tracked": tracked,
            "source_file_id": source_file_id,
            "source_root_kind": source_root_kind,
            "source_root_path": str(source_root),
            "absolute_path": str(resolved),
        })
        bucket["file_count"] += 1
        bucket["total_size_bytes"] += size
        bucket["asset_kinds"].add(asset_kind)
        bucket["tracked_file_count" if tracked else "untracked_file_count"] += 1

    # Persisted archive companions are authoritative family associations.
    for row in tracked_rows:
        family_id = int(row["family_id"])
        relative = str(row.get("current_relative_path") or "").strip()
        if not relative:
            continue
        tracked_path, tracked_root, tracked_kind = physical_path(
            relative,
            prefer_central=True,
        )
        add_asset(
            family_id,
            tracked_path,
            source_root=tracked_root,
            source_root_kind=tracked_kind,
            asset_kind=str(row.get("asset_kind") or "other"),
            tracked=True,
            source_file_id=(
                int(row["source_file_id"])
                if row.get("source_file_id") is not None
                else None
            ),
        )

    known_physical_paths: set[Path] = set()
    scan_directories: set[Path] = set()
    for row in known_rows:
        relative = str(row.get("current_relative_path") or "").strip()
        if not relative:
            continue
        path, source_root, source_kind = physical_path(
            relative,
            prefer_central=str(relative).replace("\\", "/").startswith(
                "Freigewordene Archivdateien/"
            ),
        )
        if not _safe_under(path, source_root):
            continue
        known_physical_paths.add(path)
        scan_directories.add((path.parent, source_root, source_kind))

    # Match only within directories that contain a known camera/import row.
    # Thus an unrelated JPEG elsewhere in Arbeitsbereich is never adopted.
    for directory, source_root, source_kind in sorted(
        scan_directories,
        key=lambda value: str(value[0]),
    ):
        if not directory.is_dir() or not _safe_under(directory, source_root):
            continue
        try:
            candidates = sorted(directory.iterdir(), key=lambda value: value.name.casefold())
        except OSError:
            continue
        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if (
                resolved in known_physical_paths
                or resolved in seen_paths
                or not _safe_under(resolved, source_root)
            ):
                continue
            try:
                if not resolved.is_file() or resolved.is_symlink():
                    continue
            except OSError:
                continue

            media_type = classify_media(resolved)
            if media_type == "xmp":
                asset_kind = "xmp"
            elif (
                media_type in {"jpeg", "image"}
                and export_collision_base_stem(resolved.stem) is not None
            ):
                asset_kind = "export"
            else:
                continue

            family_source = _filename_family_source(resolved.name, known_rows)
            if family_source is None or family_source.get("family_id") is None:
                continue
            family_id = int(family_source["family_id"])
            if family_id not in result:
                continue
            add_asset(
                family_id,
                resolved,
                source_root=source_root,
                source_root_kind=source_kind,
                asset_kind=asset_kind,
                tracked=False,
                source_file_id=(
                    int(family_source["file_id"])
                    if family_source.get("file_id") is not None
                    else None
                ),
            )

    clean: dict[int, dict[str, Any]] = {}
    for family_id, bucket in result.items():
        if not int(bucket["file_count"]):
            continue
        clean[family_id] = {
            **bucket,
            "asset_kinds": sorted(str(value) for value in bucket["asset_kinds"]),
        }
    return clean
