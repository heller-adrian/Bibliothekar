"""Sichere Wiederherstellung von Dateien aus dem gemeinsamen Papierkorb.

Die kanonischen Tagesordner werden mit derselben Zeitlogik berechnet
wie beim regulären zentralen Kamerabestand.
"""
from __future__ import annotations

from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Any, Iterable

from app.database import database_connection
from app.free_stock_layout import FreeStockLayoutError, canonical_free_directory
from app.storage_config import storage_paths
from app.trash import TrashError, _physical_entries, _sha256_file, reconcile_trash_inventory


def _relative(value: Any) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise TrashError("Ungültige Dateiauswahl.")
    path = Path(value)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise TrashError("Unsicherer Dateipfad.")
    return path


def _source(root: Path, relative: Path) -> Path:
    current = root
    for part in relative.parts:
        current = current / part
        info = os.lstat(current)
        if stat.S_ISLNK(info.st_mode):
            raise TrashError("Symbolische Links dürfen nicht wiederhergestellt werden.")
    if not stat.S_ISREG(os.lstat(current).st_mode):
        raise TrashError("Nur reguläre Dateien können wiederhergestellt werden.")
    return current


def _ensure_target_parent(root: Path, relative: Path) -> None:
    if not root.is_dir():
        raise TrashError("Der zentrale Tagesbestand ist nicht erreichbar.")
    current = root
    for part in relative.parent.parts:
        if part == ".":
            continue
        current = current / part
        if current.is_symlink():
            raise TrashError("Symbolischer Link im Zielpfad: " + str(current))
        current.mkdir(exist_ok=True)
        if not current.is_dir():
            raise TrashError("Ziel ist kein Verzeichnis: " + str(current))


def _move_checked(source: Path, target: Path, sha256: str) -> None:
    """No overwrite, SHA check before removing source; EXDEV copy is exclusive."""
    created = False
    try:
        try:
            os.link(source, target, follow_symlinks=False)
            created = True
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(target, flags, 0o640)
            created = True
            with os.fdopen(fd, "wb") as out, source.open("rb") as inp:
                shutil.copyfileobj(inp, out, length=1024 * 1024)
                out.flush()
                os.fsync(out.fileno())
        if _sha256_file(target) != sha256:
            raise TrashError("Prüfsummenfehler: " + source.name)
        source.unlink()
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise


def _databases(values: Iterable[Path]) -> list[Path]:
    result: list[Path] = []
    for value in values:
        path = Path(value).resolve(strict=False)
        if path.is_file() and path not in result:
            result.append(path)
    if not result:
        raise TrashError("Keine Bibliotheksdatenbank erreichbar.")
    return result


# Selection and canonical-target validation follows below.

def restore_trash_files(
    database_paths: Iterable[Path], workspace_root: Path,
    *, relative_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Restore all regular files or just selected paths to daily stock."""
    databases = _databases(database_paths)
    for database in databases:
        reconcile_trash_inventory(database, workspace_root)
    root, entries, _ = _physical_entries(workspace_root)
    files = {str(e["relative_path"]) for e in entries if e["entry_type"] == "file"}
    if relative_paths is None:
        selection = sorted(files)
    else:
        if not isinstance(relative_paths, list) or any(
            not isinstance(v, str) for v in relative_paths
        ) or len(set(relative_paths)) != len(relative_paths):
            raise TrashError("Ungültige oder doppelte Dateiauswahl.")
        selection = sorted(relative_paths)
    if not selection:
        raise TrashError("Keine Dateien zum Wiederherstellen vorhanden.")
    if len(selection) > 100000:
        raise TrashError("Zu viele Dateien in einem Vorgang.")

    central = storage_paths(workspace_root)["backup_root"]
    if not central.is_dir() or central.is_symlink():
        raise TrashError("Der zentrale Tagesbestand ist nicht sicher erreichbar.")
    plans: list[dict[str, Any]] = []
    targets: set[str] = set()
    for name in selection:
        rel = _relative(name)
        if name not in files:
            raise TrashError("Datei nicht mehr im Papierkorb: " + name)
        src = _source(root, rel)
        size, sha = src.stat().st_size, _sha256_file(src)
        goals: set[str] = set()
        identities: set[tuple[str, str]] = set()
        linked: list[tuple[Path, dict[str, Any]]] = []

        # Later stage
        for database in databases:
            with database_connection(database) as c:
                matches = [dict(r) for r in c.execute(
                    "SELECT f.id,f.job_id,f.family_id,f.original_relative_path,f.size_bytes,"
                    " COALESCE(f.sha256_current,f.sha256_original,'') AS sha256,"
                    " COALESCE(ff.selected_capture_time,f.selected_capture_time,'') AS capture_time"
                    " FROM files f LEFT JOIN file_families ff ON ff.id=f.family_id"
                    " WHERE f.current_root_kind='trash' AND f.current_relative_path=?",
                    (name,),
                ).fetchall()]
                if len(matches) > 1:
                    raise TrashError("Mehrdeutiger Katalogeintrag: " + name)
                if not matches:
                    continue
                row = matches[0]
                if size != int(row["size_bytes"]) or sha != str(row["sha256"]):
                    raise TrashError("Größe oder Prüfsumme abweichend: " + name)
                if row["family_id"] is None:
                    raise TrashError("Datei ohne Kamerafamilie: " + name)
                assigned = c.execute(
                    "SELECT 1 FROM event_assignments a JOIN events e ON e.id=a.event_id "
                    "WHERE a.family_id=? AND e.status IN "
                    "('draft','planned','applied','archived') LIMIT 1",
                    (row["family_id"],),
                ).fetchone()
                if assigned:
                    raise TrashError("Noch einem Ereignis zugeordnet: " + name)
                capture = str(row["capture_time"] or "")
                if not capture:
                    raise TrashError("Aufnahmezeit unbekannt: " + name)
