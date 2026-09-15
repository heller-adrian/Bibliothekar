from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Iterable

from app.database import database_connection


SORT_BRANCHES = {"Alle", "Sortiert", "Export"}


class ArchiveLocationError(ValueError):
    pass


def stable_anchor_from_file_path(relative_path: str) -> str:
    """Return the deepest stable structural directory for an archived file.

    Alle/Sortiert/Export are intentionally excluded because the user may move
    files between these folders after archiving without telling the app.
    """
    raw = str(relative_path or "").replace("\\", "/").strip("/")
    parts = list(PurePosixPath(raw).parts)
    if len(parts) < 2:
        raise ArchiveLocationError("Archivpfad ist zu kurz, um einen Strukturanker abzuleiten.")
    parts = parts[:-1]  # filename
    if parts and parts[-1] in SORT_BRANCHES:
        parts = parts[:-1]
    if not parts:
        raise ArchiveLocationError("Archivpfad enthält keinen stabilen Strukturanker.")
    return PurePosixPath(*parts).as_posix()


def common_stable_anchor(paths: Iterable[str]) -> str:
    anchors = [PurePosixPath(stable_anchor_from_file_path(p)).parts for p in paths]
    if not anchors:
        raise ArchiveLocationError("Keine geprüften Archivpfade vorhanden.")
    prefix = list(anchors[0])
    for parts in anchors[1:]:
        n = min(len(prefix), len(parts))
        i = 0
        while i < n and prefix[i] == parts[i]:
            i += 1
        prefix = prefix[:i]
    if not prefix:
        raise ArchiveLocationError("Die geprüften Dateien besitzen keinen gemeinsamen Strukturanker.")
    return PurePosixPath(*prefix).as_posix()


def record_family_anchor(connection, event_id: str, family_id: int, paths: Iterable[str], now: str) -> str:
    anchor = common_stable_anchor(paths)
    connection.execute(
        """
        INSERT INTO event_archive_family_anchors(event_id,family_id,anchor_relative_path,verified_at,updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(event_id,family_id) DO UPDATE SET
            anchor_relative_path=excluded.anchor_relative_path,
            verified_at=excluded.verified_at,
            updated_at=excluded.updated_at
        """,
        (event_id, int(family_id), anchor, now, now),
    )
    return anchor




def record_verified_file_location(
    connection,
    event_id: str,
    family_id: int,
    file_id: int,
    relative_path: str,
    now: str,
) -> str:
    """Persist the exact path that was successfully checked for one file."""
    rel = str(relative_path or "").replace("\\", "/").strip("/")
    if not rel or len(PurePosixPath(rel).parts) < 2:
        raise ArchiveLocationError("Geprüfter Archivpfad ist ungültig.")
    connection.execute(
        """
        INSERT INTO event_archive_verified_file_locations(
            event_id,family_id,file_id,relative_path,verified_at,updated_at
        ) VALUES (?,?,?,?,?,?)
        ON CONFLICT(event_id,file_id) DO UPDATE SET
            family_id=excluded.family_id,
            relative_path=excluded.relative_path,
            verified_at=excluded.verified_at,
            updated_at=excluded.updated_at
        """,
        (event_id, int(family_id), int(file_id), rel, now, now),
    )
    return rel

def resolve_archived_file_relative_path(
    database_path: Path,
    archive_root: Path,
    *,
    event_id: str,
    family_id: int,
    filename: str,
    fallback_anchor: str,
    file_id: int | None = None,
) -> str:
    """Find one archived file below the last verified structural anchor.

    We never trust an old Alle/Sortiert/Export path. If no durable anchor is
    available (legacy data), search only below the event root as a one-time
    compatibility fallback. Zero or multiple matches are explicit blockers.
    """
    exact_rel = ""
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT anchor_relative_path FROM event_archive_family_anchors WHERE event_id=? AND family_id=?",
            (event_id, int(family_id)),
        ).fetchone()
        if file_id is not None:
            exact = connection.execute(
                "SELECT relative_path FROM event_archive_verified_file_locations WHERE event_id=? AND file_id=?",
                (event_id, int(file_id)),
            ).fetchone()
            if exact is not None:
                exact_rel = str(exact["relative_path"] or "").replace("\\", "/").strip("/")
    anchor_rel = str(row["anchor_relative_path"] if row else fallback_anchor).replace("\\", "/").strip("/")
    if not anchor_rel:
        raise ArchiveLocationError("Für die Familie fehlt ein verifizierter Archiv-Strukturanker.")

    root = archive_root.expanduser().resolve(strict=False)

    # 0.20.0: first trust the last path that was actually verified. This is
    # precise and avoids any search at all in the common case. If the user
    # moved the file afterwards between Alle/Sortiert/Export, use the durable
    # structural anchor below as the bounded fallback.
    if exact_rel:
        exact_path = root.joinpath(*PurePosixPath(exact_rel).parts).resolve(strict=False)
        try:
            exact_path.relative_to(root)
        except ValueError as exc:
            raise ArchiveLocationError("Geprüfter Archivpfad verlässt die Kamerabibliothek.") from exc
        if exact_path.is_file() and exact_path.name == filename:
            return exact_rel

    anchor = root.joinpath(*PurePosixPath(anchor_rel).parts).resolve(strict=False)
    try:
        anchor.relative_to(root)
    except ValueError as exc:
        raise ArchiveLocationError("Archiv-Strukturanker verlässt die Kamerabibliothek.") from exc
    if not anchor.exists() or not anchor.is_dir():
        raise ArchiveLocationError(
            f"Der zuletzt verifizierte Archiv-Strukturanker existiert nicht mehr: {anchor_rel}"
        )

    matches = [p for p in anchor.rglob(filename) if p.is_file() and p.name == filename]
    if len(matches) == 0:
        raise ArchiveLocationError(
            f"Datei wurde innerhalb des zuletzt verifizierten Strukturankers nicht gefunden: {anchor_rel}/{filename}"
        )
    if len(matches) > 1:
        rels = [p.relative_to(root).as_posix() for p in matches[:5]]
        raise ArchiveLocationError(
            "Datei wurde innerhalb des Strukturankers mehrfach gefunden; bitte Duplikat klären: " + ", ".join(rels)
        )
    return matches[0].relative_to(root).as_posix()
