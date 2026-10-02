from __future__ import annotations

from pathlib import Path, PurePath
from typing import Iterator


# Betriebssystem-Verwaltungsbereiche sind keine Kameraquelle. Sie dürfen weder
# die Quellsignatur noch Manifest, Sicherung oder Metadatenanalyse beeinflussen.
IGNORED_SOURCE_DIRECTORIES = {
    ".trashes",
    ".spotlight-v100",
    ".fseventsd",
    ".temporaryitems",
    ".documentrevisions-v100",
    "system volume information",
    "$recycle.bin",
}

IGNORED_SOURCE_FILENAMES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
}


def should_ignore_source_relative(relative: str | PurePath) -> bool:
    path = PurePath(str(relative).replace("\\", "/"))
    parts = [str(part) for part in path.parts if str(part) not in {"", "."}]
    if not parts:
        return False

    for part in parts[:-1]:
        if part.casefold() in IGNORED_SOURCE_DIRECTORIES:
            return True

    name = parts[-1]
    folded = name.casefold()
    if folded in IGNORED_SOURCE_FILENAMES:
        return True
    if name.startswith("._"):
        return True
    return False


def should_ignore_source_path(root: Path, path: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return should_ignore_source_relative(relative)


def iter_source_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*")):
        if should_ignore_source_path(root, path):
            continue
        if path.is_file():
            yield path
