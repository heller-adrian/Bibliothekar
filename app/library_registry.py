from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import os
import sqlite3


REGISTRY_SCHEMA_VERSION = 1
MAIN_LIBRARY_ID = "main"


class LibraryRegistryError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def initialize_library_registry(path: Path) -> dict[str, Any]:
    connection = _connect(path)
    try:
        connection.executescript(
            """
            BEGIN IMMEDIATE;

            CREATE TABLE IF NOT EXISTS registry_schema_versions (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS libraries (
                library_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                database_path TEXT NOT NULL UNIQUE,
                workspace_root TEXT NOT NULL,
                work_root TEXT NOT NULL,
                archive_root TEXT NOT NULL,
                settings_json TEXT NOT NULL DEFAULT '{}',
                is_main INTEGER NOT NULL DEFAULT 0 CHECK (is_main IN (0,1)),
                is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_libraries_single_main
            ON libraries(is_main)
            WHERE is_main = 1;

            CREATE TABLE IF NOT EXISTS source_backups (
                backup_id TEXT PRIMARY KEY,
                source_kind TEXT NOT NULL,
                source_identity TEXT NOT NULL,
                backup_path TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(source_kind, source_identity, backup_path)
            );

            CREATE TABLE IF NOT EXISTS source_families (
                source_family_key TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                family_key TEXT NOT NULL,
                content_fingerprint TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(backup_id, family_key),
                FOREIGN KEY(backup_id)
                    REFERENCES source_backups(backup_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS family_claims (
                source_family_key TEXT PRIMARY KEY,
                library_id TEXT NOT NULL,
                claim_state TEXT NOT NULL
                    CHECK (claim_state IN ('reserved','owned')),
                event_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_family_key)
                    REFERENCES source_families(source_family_key)
                    ON DELETE CASCADE,
                FOREIGN KEY(library_id)
                    REFERENCES libraries(library_id)
                    ON DELETE RESTRICT
            );

            INSERT OR IGNORE INTO registry_schema_versions(version, applied_at)
            VALUES (1, datetime('now'));

            COMMIT;
            """
        )

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise LibraryRegistryError(
                f"Integritätsprüfung der Bibliotheks-Registry fehlgeschlagen: {integrity}"
            )

        foreign_key_errors = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()
        if foreign_key_errors:
            raise LibraryRegistryError(
                "Fremdschlüsselprüfung der Bibliotheks-Registry ist fehlgeschlagen."
            )

        versions = [
            int(row["version"])
            for row in connection.execute(
                "SELECT version FROM registry_schema_versions ORDER BY version"
            ).fetchall()
        ]
        return {
            "database_path": str(path),
            "schema_versions": versions,
            "integrity": integrity,
            "foreign_key_errors": 0,
        }
    except Exception:
        try:
            connection.rollback()
        except sqlite3.OperationalError:
            pass
        raise
    finally:
        connection.close()


def ensure_library_identity(database_path: Path, library_id: str) -> dict[str, str]:
    clean_id = str(library_id or "").strip()
    if not clean_id:
        raise LibraryRegistryError("Bibliotheks-ID darf nicht leer sein.")

    from app.database import database_connection

    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT library_id, created_at FROM library_identity WHERE singleton = 1"
        ).fetchone()

        if row is None:
            created_at = _now()
            connection.execute(
                """
                INSERT INTO library_identity(singleton, library_id, created_at)
                VALUES (1, ?, ?)
                """,
                (clean_id, created_at),
            )
            return {"library_id": clean_id, "created_at": created_at}

        existing = str(row["library_id"])
        if existing != clean_id:
            raise LibraryRegistryError(
                "Datenbank gehört bereits zu einer anderen Bibliothek: "
                f"{existing!r} statt {clean_id!r}."
            )

        return {
            "library_id": existing,
            "created_at": str(row["created_at"]),
        }


def read_library_identity(database_path: Path) -> str | None:
    from app.database import database_connection

    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT library_id FROM library_identity WHERE singleton = 1"
        ).fetchone()
    return str(row["library_id"]) if row else None


def _absolute(path: Path, field: str) -> str:
    resolved = path.expanduser().resolve(strict=False)
    if not resolved.is_absolute():
        raise LibraryRegistryError(f"{field} muss absolut sein.")
    return str(resolved)


def register_library(
    registry_path: Path,
    *,
    library_id: str,
    display_name: str,
    database_path: Path,
    workspace_root: Path,
    work_root: Path,
    archive_root: Path,
    is_main: bool = False,
    is_active: bool = True,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_id = str(library_id or "").strip()
    clean_name = " ".join(str(display_name or "").split()).strip()
    if not clean_id or not clean_name:
        raise LibraryRegistryError("Bibliotheks-ID und Anzeigename sind erforderlich.")

    database_value = _absolute(database_path, "database_path")
    workspace_value = _absolute(workspace_root, "workspace_root")
    work_value = _absolute(work_root, "work_root")
    archive_value = _absolute(archive_root, "archive_root")

    registry_value = _absolute(registry_path, "registry_path")
    if Path(database_value) == Path(registry_value):
        raise LibraryRegistryError(
            "Bibliotheks-Datenbank und globale Registry müssen getrennte Dateien sein."
        )

    try:
        Path(work_value).relative_to(Path(workspace_value))
    except ValueError as error:
        raise LibraryRegistryError(
            "Der Arbeitsbereich einer Bibliothek muss innerhalb des Workspace liegen."
        ) from error

    if (
        Path(archive_value) == Path(workspace_value)
        or Path(archive_value) in Path(workspace_value).parents
        or Path(workspace_value) in Path(archive_value).parents
    ):
        raise LibraryRegistryError(
            "Archiv und Workspace dürfen nicht ineinander verschachtelt sein."
        )

    now = _now()
    serialized = json.dumps(settings or {}, ensure_ascii=False, sort_keys=True)

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT created_at FROM libraries WHERE library_id = ?",
            (clean_id,),
        ).fetchone()
        created_at = str(existing["created_at"]) if existing else now

        connection.execute(
            """
            INSERT INTO libraries(
                library_id, display_name, database_path,
                workspace_root, work_root, archive_root,
                settings_json, is_main, is_active,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(library_id) DO UPDATE SET
                display_name = excluded.display_name,
                database_path = excluded.database_path,
                workspace_root = excluded.workspace_root,
                work_root = excluded.work_root,
                archive_root = excluded.archive_root,
                settings_json = excluded.settings_json,
                is_main = excluded.is_main,
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (
                clean_id,
                clean_name,
                database_value,
                workspace_value,
                work_value,
                archive_value,
                serialized,
                1 if is_main else 0,
                1 if is_active else 0,
                created_at,
                now,
            ),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        raise LibraryRegistryError(str(error)) from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = get_library(registry_path, clean_id, active_only=False)
    if result is None:
        raise LibraryRegistryError("Bibliothek konnte nicht registriert werden.")
    return result


def adopt_main_library(
    registry_path: Path,
    *,
    database_path: Path,
    workspace_root: Path,
    work_root: Path,
    archive_root: Path,
) -> dict[str, Any]:
    ensure_library_identity(database_path, MAIN_LIBRARY_ID)

    existing = get_library(
        registry_path,
        MAIN_LIBRARY_ID,
        active_only=False,
    )
    display_name = (
        str(existing["display_name"])
        if existing
        else "Main Library"
    )
    settings = dict(existing.get("settings") or {}) if existing else {}
    settings["adopted_existing_database"] = True

    return register_library(
        registry_path,
        library_id=MAIN_LIBRARY_ID,
        display_name=display_name,
        database_path=database_path,
        workspace_root=workspace_root,
        work_root=work_root,
        archive_root=archive_root,
        is_main=True,
        is_active=True,
        settings=settings,
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_main"] = bool(result["is_main"])
    result["is_active"] = bool(result["is_active"])
    try:
        result["settings"] = json.loads(str(result.pop("settings_json") or "{}"))
    except (TypeError, ValueError):
        result["settings"] = {}
        result.pop("settings_json", None)
    return result


def get_library(
    registry_path: Path,
    library_id: str,
    *,
    active_only: bool = True,
) -> dict[str, Any] | None:
    connection = _connect(registry_path)
    try:
        sql = "SELECT * FROM libraries WHERE library_id = ?"
        params: list[Any] = [str(library_id)]
        if active_only:
            sql += " AND is_active = 1"
        row = connection.execute(sql, params).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        connection.close()


def list_libraries(
    registry_path: Path,
    *,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    connection = _connect(registry_path)
    try:
        sql = "SELECT * FROM libraries"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY is_main DESC, display_name COLLATE NOCASE, library_id"
        rows = connection.execute(sql).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def register_source_backup(
    registry_path: Path,
    *,
    backup_id: str,
    source_kind: str,
    source_identity: str,
    backup_path: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _now()
    connection = _connect(registry_path)
    try:
        connection.execute(
            """
            INSERT INTO source_backups(
                backup_id, source_kind, source_identity, backup_path,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backup_id) DO UPDATE SET
                source_kind = excluded.source_kind,
                source_identity = excluded.source_identity,
                backup_path = excluded.backup_path,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                str(backup_id),
                str(source_kind),
                str(source_identity),
                str(backup_path),
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def register_source_family(
    registry_path: Path,
    *,
    source_family_key: str,
    backup_id: str,
    family_key: str,
    content_fingerprint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    now = _now()
    connection = _connect(registry_path)
    try:
        connection.execute(
            """
            INSERT INTO source_families(
                source_family_key, backup_id, family_key,
                content_fingerprint, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_family_key) DO UPDATE SET
                backup_id = excluded.backup_id,
                family_key = excluded.family_key,
                content_fingerprint = excluded.content_fingerprint,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                str(source_family_key),
                str(backup_id),
                str(family_key),
                str(content_fingerprint) if content_fingerprint else None,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                now,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()


def claim_source_family(
    registry_path: Path,
    *,
    source_family_key: str,
    library_id: str,
    event_id: str | None,
    claim_state: str = "reserved",
) -> dict[str, Any]:
    if claim_state not in {"reserved", "owned"}:
        raise LibraryRegistryError("Ungültiger Reservierungszustand.")

    now = _now()
    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        library = connection.execute(
            """
            SELECT library_id
            FROM libraries
            WHERE library_id = ?
              AND is_active = 1
            """,
            (str(library_id),),
        ).fetchone()
        if library is None:
            raise LibraryRegistryError(
                "Dateifamilien können nur einer aktiven Bibliothek zugeordnet werden."
            )

        existing = connection.execute(
            "SELECT * FROM family_claims WHERE source_family_key = ?",
            (str(source_family_key),),
        ).fetchone()

        if existing and str(existing["library_id"]) != str(library_id):
            raise LibraryRegistryError(
                "Diese Dateifamilie ist bereits einer anderen Bibliothek vorbehalten."
            )

        if existing and str(existing["claim_state"]) == "owned" and claim_state == "reserved":
            raise LibraryRegistryError(
                "Eine bereits übernommene Dateifamilie kann nicht auf reserviert zurückgesetzt werden."
            )

        connection.execute(
            """
            INSERT INTO family_claims(
                source_family_key, library_id, claim_state,
                event_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_family_key) DO UPDATE SET
                library_id = excluded.library_id,
                claim_state = excluded.claim_state,
                event_id = excluded.event_id,
                updated_at = excluded.updated_at
            """,
            (
                str(source_family_key),
                str(library_id),
                claim_state,
                str(event_id) if event_id else None,
                str(existing["created_at"]) if existing else now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM family_claims WHERE source_family_key = ?",
            (str(source_family_key),),
        ).fetchone()
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def release_source_family_reservation(
    registry_path: Path,
    *,
    source_family_key: str,
    library_id: str,
) -> bool:
    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT claim_state, library_id FROM family_claims WHERE source_family_key = ?",
            (str(source_family_key),),
        ).fetchone()

        if row is None:
            connection.commit()
            return False

        if str(row["library_id"]) != str(library_id):
            raise LibraryRegistryError(
                "Reservierung gehört zu einer anderen Bibliothek."
            )
        if str(row["claim_state"]) != "reserved":
            raise LibraryRegistryError(
                "Übernommene Dateifamilien werden nicht durch Abbruch wieder freigegeben."
            )

        connection.execute(
            "DELETE FROM family_claims WHERE source_family_key = ?",
            (str(source_family_key),),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_source_family_claim(
    registry_path: Path,
    source_family_key: str,
) -> dict[str, Any] | None:
    connection = _connect(registry_path)
    try:
        row = connection.execute(
            "SELECT * FROM family_claims WHERE source_family_key = ?",
            (str(source_family_key),),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()
