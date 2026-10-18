from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.library_registry import LibraryRegistryError, get_library, list_libraries


@dataclass(frozen=True)
class LibraryContext:
    library_id: str
    display_name: str
    database_path: Path
    workspace_root: Path
    work_root: Path
    archive_root: Path
    is_main: bool
    settings: dict[str, Any]
    root_generation: tuple[int, int] | None = None

    def public_dict(self) -> dict[str, Any]:
        return {
            "library_id": self.library_id,
            "display_name": self.display_name,
            "is_main": self.is_main,
        }


def _context_from_row(row: dict[str, Any]) -> LibraryContext:
    from app.root_operations import generation
    return LibraryContext(
        library_id=str(row["library_id"]),
        display_name=str(row["display_name"]),
        database_path=Path(str(row["database_path"])),
        workspace_root=Path(str(row["workspace_root"])),
        work_root=Path(str(row["work_root"])),
        archive_root=Path(str(row["archive_root"])),
        is_main=bool(row["is_main"]),
        settings=dict(row.get("settings") or {}),
        root_generation=generation(Path(str(row["workspace_root"])),str(row["library_id"])),
    )


def resolve_library_context(
    registry_path: Path,
    library_id: str,
) -> LibraryContext:
    row = get_library(registry_path, library_id, active_only=True)
    if row is None:
        raise LibraryRegistryError(
            f"Aktive Bibliothek wurde nicht gefunden: {library_id}"
        )
    return _context_from_row(row)


def list_active_library_contexts(registry_path: Path) -> list[LibraryContext]:
    return [
        _context_from_row(row)
        for row in list_libraries(registry_path, active_only=True)
    ]
