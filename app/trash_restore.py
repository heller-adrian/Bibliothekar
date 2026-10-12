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


