"""English defaults for *new* internal directories, legacy name preservation.

All callers resolve the physical parent first. Never rename, merge, relocate,
or delete user data implicitly. An existing legacy directory wins so stored
relative paths remain valid. If both variants contain data, fail closed rather
than silently select a partial inventory.
"""
from __future__ import annotations

from pathlib import Path

NAME_PAIRS = {
    "import_protocol": ("Protokoll", "Protocol"),
    "simulated_sd": ("simulierte-sd", "simulated-sd"),
    "undated": ("Ohne_Datum", "No Date"),
    "metadata_general": ("Allgemein", "General"),
    "metadata_multiple": ("Mehrfachkorrektur", "Batch Correction"),
    "assign_later": ("Später zuordnen", "Assign Later"),
    "released_archive": ("Freigewordene Archivdateien", "Released Archive Files"),
    "reversal": ("Rückänderung", "Reversal"),
    "restoration": ("Wiederherstellung", "Restoration"),
}


class AmbiguousManagedDirectoryError(ValueError):
    pass


def directory_name(root: Path, kind: str) -> str:
    """Return a directory *name* without performing any filesystem mutation."""
    legacy, english = NAME_PAIRS[kind]
    base = Path(root)
    old = base / legacy
    new = base / english
    if old.is_symlink() or new.is_symlink():
        raise AmbiguousManagedDirectoryError(
            "A managed storage directory must not be a symbolic link."
        )
    if old.exists() and not old.is_dir():
        raise AmbiguousManagedDirectoryError(
            f"Legacy managed storage location is not a directory: {old}"
        )
    if new.exists() and not new.is_dir():
        raise AmbiguousManagedDirectoryError(
            f"English managed storage location is not a directory: {new}"
        )
    if old.is_dir() and new.is_dir():
        # Never silently hide data inside either variant.
        if any(old.iterdir()) and any(new.iterdir()):
            raise AmbiguousManagedDirectoryError(
                f"Both language variants contain data: {old} and {new}"
            )
        if any(new.iterdir()):
            return english
        return legacy
    return legacy if old.is_dir() else english


def directory_path(root: Path, kind: str) -> Path:
    return Path(root) / directory_name(root, kind)


def is_undated_name(name: str) -> bool:
    return name in NAME_PAIRS["undated"]


def is_released_archive_name(name: str) -> bool:
    return name in NAME_PAIRS["released_archive"]
