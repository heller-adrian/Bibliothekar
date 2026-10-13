from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import sqlite3


REGISTRY_SCHEMA_VERSION = 3
MAIN_LIBRARY_ID = "main"


REGISTRY_MIGRATIONS: dict[int, str] = {
    1: """
        CREATE TABLE libraries (
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

        CREATE UNIQUE INDEX idx_libraries_single_main
        ON libraries(is_main)
        WHERE is_main = 1;

        CREATE TABLE source_backups (
            backup_id TEXT PRIMARY KEY,
            source_kind TEXT NOT NULL,
            source_identity TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(source_kind, source_identity, backup_path)
        );

        CREATE TABLE canonical_families (
            canonical_family_id TEXT PRIMARY KEY,
            content_fingerprint TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE source_families (
            source_family_key TEXT PRIMARY KEY,
            backup_id TEXT NOT NULL,
            family_key TEXT NOT NULL,
            canonical_family_id TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(backup_id, family_key),
            FOREIGN KEY(backup_id)
                REFERENCES source_backups(backup_id)
                ON DELETE CASCADE,
            FOREIGN KEY(canonical_family_id)
                REFERENCES canonical_families(canonical_family_id)
                ON DELETE RESTRICT
        );

        CREATE INDEX idx_source_families_canonical
        ON source_families(canonical_family_id);

        CREATE TABLE family_claims (
            canonical_family_id TEXT PRIMARY KEY,
            library_id TEXT NOT NULL,
            claim_state TEXT NOT NULL
                CHECK (claim_state IN ('reserved','owned')),
            event_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(canonical_family_id)
                REFERENCES canonical_families(canonical_family_id)
                ON DELETE RESTRICT,
            FOREIGN KEY(library_id)
                REFERENCES libraries(library_id)
                ON DELETE RESTRICT
        );
    """,
    2: """
        ALTER TABLE libraries
        ADD COLUMN is_registered INTEGER NOT NULL DEFAULT 1
        CHECK (is_registered IN (0,1));

        ALTER TABLE libraries
        ADD COLUMN deactivated_at TEXT;

        ALTER TABLE libraries
        ADD COLUMN unregistered_at TEXT;

        CREATE TABLE source_media (
            media_id TEXT PRIMARY KEY,
            backup_id TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL,
            media_type TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(backup_id, relative_path),
            FOREIGN KEY(backup_id)
                REFERENCES source_backups(backup_id)
                ON DELETE CASCADE
        );

        CREATE INDEX idx_source_media_backup_sha
        ON source_media(backup_id, sha256);

        CREATE TABLE source_family_members (
            source_family_key TEXT NOT NULL,
            media_id TEXT NOT NULL,
            member_role TEXT NOT NULL DEFAULT 'member',
            member_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            PRIMARY KEY(source_family_key, media_id),
            FOREIGN KEY(source_family_key)
                REFERENCES source_families(source_family_key)
                ON DELETE CASCADE,
            FOREIGN KEY(media_id)
                REFERENCES source_media(media_id)
                ON DELETE CASCADE
        );

        CREATE INDEX idx_source_family_members_media
        ON source_family_members(media_id);
    """,
    3: """
        ALTER TABLE family_claims RENAME TO family_claims_v2;

        CREATE TABLE family_claims (
            canonical_family_id TEXT NOT NULL,
            library_id TEXT NOT NULL,
            claim_state TEXT NOT NULL
                CHECK (claim_state IN ('reserved','owned')),
            event_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(canonical_family_id, library_id),
            FOREIGN KEY(canonical_family_id)
                REFERENCES canonical_families(canonical_family_id)
                ON DELETE RESTRICT,
            FOREIGN KEY(library_id)
                REFERENCES libraries(library_id)
                ON DELETE RESTRICT
        );

        INSERT INTO family_claims(
            canonical_family_id, library_id, claim_state,
            event_id, created_at, updated_at
        )
        SELECT
            canonical_family_id, library_id, claim_state,
            event_id, created_at, updated_at
        FROM family_claims_v2;

        DROP TABLE family_claims_v2;

        CREATE UNIQUE INDEX idx_family_claims_single_owner
        ON family_claims(canonical_family_id)
        WHERE claim_state = 'owned';

        CREATE INDEX idx_family_claims_library_state
        ON family_claims(library_id, claim_state);
    """,
}


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


def _ensure_registry_schema_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS registry_schema_versions (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def _registry_applied_versions(connection: sqlite3.Connection) -> set[int]:
    _ensure_registry_schema_table(connection)
    rows = connection.execute(
        "SELECT version FROM registry_schema_versions ORDER BY version"
    ).fetchall()
    return {int(row["version"]) for row in rows}


def _apply_registry_migration(
    connection: sqlite3.Connection,
    version: int,
    sql: str,
) -> None:
    if not sql.strip():
        raise LibraryRegistryError(
            f"Registry-Migration {version} ist leer."
        )
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;\n"
            + sql
            + f"""
            INSERT INTO registry_schema_versions(version, applied_at)
            VALUES ({int(version)}, datetime('now'));
            COMMIT;
            """
        )
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.OperationalError:
            pass
        raise


def initialize_library_registry(path: Path) -> dict[str, Any]:
    connection = _connect(path)
    try:
        applied = _registry_applied_versions(connection)
        unsupported = sorted(
            version
            for version in applied
            if version > REGISTRY_SCHEMA_VERSION
        )
        if unsupported:
            raise LibraryRegistryError(
                "Die Bibliotheks-Registry stammt aus einer neueren "
                "Anwendungsversion: "
                + ", ".join(str(version) for version in unsupported)
            )

        newly_applied: list[int] = []
        for version in sorted(REGISTRY_MIGRATIONS):
            if version in applied:
                continue
            _apply_registry_migration(
                connection,
                version,
                REGISTRY_MIGRATIONS[version],
            )
            newly_applied.append(version)

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

        versions = sorted(_registry_applied_versions(connection))
        expected = set(range(1, REGISTRY_SCHEMA_VERSION + 1))
        if set(versions) != expected:
            raise LibraryRegistryError(
                "Registry-Schemastand ist unvollständig: "
                + ", ".join(str(version) for version in versions)
            )

        return {
            "database_path": str(path),
            "schema_versions": versions,
            "newly_applied_versions": newly_applied,
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

    if (
        Path(archive_value) == Path(workspace_value)
        or Path(archive_value) in Path(workspace_value).parents
        or Path(workspace_value) in Path(archive_value).parents
    ):
        raise LibraryRegistryError(
            "Archiv und Workspace dürfen nicht ineinander verschachtelt sein."
        )

    if is_active:
        database_file = Path(database_value)
        if not database_file.is_file():
            raise LibraryRegistryError(
                "Eine aktive Bibliothek benötigt eine vorhandene SQLite-Datenbank: "
                + str(database_file)
            )
        try:
            database_identity = read_library_identity(database_file)
        except sqlite3.DatabaseError as error:
            raise LibraryRegistryError(
                "Die Bibliotheks-Datenbank ist nicht initialisiert oder nicht lesbar."
            ) from error
        if database_identity != clean_id:
            raise LibraryRegistryError(
                "Die interne Bibliotheks-ID der Datenbank stimmt nicht mit "
                f"{clean_id!r} überein."
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

        if is_active:
            active_rows = connection.execute(
                """
                SELECT library_id, work_root, archive_root
                FROM libraries
                WHERE is_active = 1
                  AND library_id <> ?
                """,
                (clean_id,),
            ).fetchall()
            requested_root = Path(work_value)
            requested_archive = Path(archive_value)
            for active_row in active_rows:
                active_root = Path(str(active_row["work_root"]))
                if (
                    requested_root == active_root
                    or requested_root in active_root.parents
                    or active_root in requested_root.parents
                ):
                    raise LibraryRegistryError(
                        "Aktive Bibliotheks-Arbeitsbereiche dürfen sich nicht "
                        "überschneiden oder ineinander liegen."
                    )

                active_archive = Path(str(active_row["archive_root"]))
                if (
                    requested_archive == active_archive
                    or requested_archive in active_archive.parents
                    or active_archive in requested_archive.parents
                ):
                    raise LibraryRegistryError(
                        "Aktive Bibliotheks-Archive dürfen sich nicht "
                        "überschneiden oder ineinander liegen."
                    )

        connection.execute(
            """
            INSERT INTO libraries(
                library_id, display_name, database_path,
                workspace_root, work_root, archive_root,
                settings_json, is_main, is_active, is_registered,
                created_at, updated_at, deactivated_at, unregistered_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, NULL)
            ON CONFLICT(library_id) DO UPDATE SET
                display_name = excluded.display_name,
                database_path = excluded.database_path,
                workspace_root = excluded.workspace_root,
                work_root = excluded.work_root,
                archive_root = excluded.archive_root,
                settings_json = excluded.settings_json,
                is_main = excluded.is_main,
                is_active = excluded.is_active,
                is_registered = 1,
                deactivated_at = excluded.deactivated_at,
                unregistered_at = NULL,
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
                None if is_active else now,
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

    effective_work_root = (
        Path(str(existing["work_root"]))
        if existing
        else work_root
    )
    effective_archive_root = (
        Path(str(existing["archive_root"]))
        if existing
        else archive_root
    )

    return register_library(
        registry_path,
        library_id=MAIN_LIBRARY_ID,
        display_name=display_name,
        database_path=database_path,
        workspace_root=workspace_root,
        work_root=effective_work_root,
        archive_root=effective_archive_root,
        is_main=True,
        is_active=True,
        settings=settings,
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["is_main"] = bool(result["is_main"])
    result["is_active"] = bool(result["is_active"])
    if "is_registered" in result:
        result["is_registered"] = bool(result["is_registered"])
    else:
        result["is_registered"] = True
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
    registered_only: bool = True,
) -> list[dict[str, Any]]:
    connection = _connect(registry_path)
    try:
        conditions: list[str] = []
        if active_only:
            conditions.append("is_active = 1")
        if registered_only:
            conditions.append("COALESCE(is_registered, 1) = 1")
        sql = "SELECT * FROM libraries"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY is_main DESC, display_name COLLATE NOCASE, library_id"
        rows = connection.execute(sql).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        connection.close()


def update_library_display_name(
    registry_path: Path,
    library_id: str,
    display_name: str,
) -> dict[str, Any]:
    clean_name = " ".join(str(display_name or "").split()).strip()
    if not clean_name:
        raise LibraryRegistryError("Anzeigename darf nicht leer sein.")

    connection = _connect(registry_path)
    try:
        cursor = connection.execute(
            """
            UPDATE libraries
            SET display_name = ?, updated_at = ?
            WHERE library_id = ?
              AND COALESCE(is_registered, 1) = 1
            """,
            (clean_name, _now(), str(library_id)),
        )
        if cursor.rowcount != 1:
            raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
        connection.commit()
    finally:
        connection.close()

    result = get_library(registry_path, library_id, active_only=False)
    if result is None:
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
    return result


def update_library_settings(
    registry_path: Path,
    library_id: str,
    updates: dict[str, Any],
) -> dict[str, Any]:
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None or not existing.get("is_registered", True):
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")

    current = dict(existing.get("settings") or {})
    for key, value in dict(updates or {}).items():
        if value is None:
            current.pop(str(key), None)
        else:
            current[str(key)] = value

    return register_library(
        registry_path,
        library_id=str(existing["library_id"]),
        display_name=str(existing["display_name"]),
        database_path=Path(str(existing["database_path"])),
        workspace_root=Path(str(existing["workspace_root"])),
        work_root=Path(str(existing["work_root"])),
        archive_root=Path(str(existing["archive_root"])),
        is_main=bool(existing["is_main"]),
        is_active=bool(existing["is_active"]),
        settings=current,
    )


def update_library_database_path(
    registry_path: Path,
    library_id: str,
    database_path: Path,
) -> dict[str, Any]:
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None or not existing.get("is_registered", True):
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")

    database_value = _absolute(database_path, "database_path")
    database_file = Path(database_value)
    if not database_file.is_file():
        raise LibraryRegistryError(
            "Bibliotheks-Datenbank wurde nicht gefunden: " + database_value
        )

    try:
        identity = read_library_identity(database_file)
    except sqlite3.DatabaseError as error:
        raise LibraryRegistryError(
            "Bibliotheks-Datenbank ist nicht lesbar: " + database_value
        ) from error
    if identity != str(existing["library_id"]):
        raise LibraryRegistryError(
            "Die gefundene SQLite-Datenbank gehört zu einer anderen Bibliothek: "
            + str(identity or "ohne Bibliotheks-ID")
        )

    registry_value = _absolute(registry_path, "registry_path")
    if database_value == registry_value:
        raise LibraryRegistryError(
            "Bibliotheks-Datenbank und globale Registry müssen getrennte Dateien sein."
        )

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        conflict = connection.execute(
            """
            SELECT library_id
            FROM libraries
            WHERE database_path = ?
              AND library_id <> ?
              AND COALESCE(is_registered, 1) = 1
            """,
            (database_value, str(library_id)),
        ).fetchone()
        if conflict is not None:
            raise LibraryRegistryError(
                "Diese SQLite-Datenbank ist bereits einer anderen Bibliothek zugeordnet."
            )
        cursor = connection.execute(
            """
            UPDATE libraries
            SET database_path = ?, updated_at = ?
            WHERE library_id = ?
              AND COALESCE(is_registered, 1) = 1
            """,
            (database_value, _now(), str(library_id)),
        )
        if cursor.rowcount != 1:
            raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = get_library(registry_path, library_id, active_only=False)
    if result is None:
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
    return result


def update_library_paths(
    registry_path: Path,
    library_id: str,
    *,
    work_root: Path | None = None,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None or not existing.get("is_registered", True):
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")

    next_work = (
        _absolute(work_root, "work_root")
        if work_root is not None
        else str(existing["work_root"])
    )
    next_archive = (
        _absolute(archive_root, "archive_root")
        if archive_root is not None
        else str(existing["archive_root"])
    )

    # Die bestehende Registerlogik enthält bereits die Überlappungs- und
    # Identitätsprüfungen. Ein Pfadwechsel ändert keine Dateien und keine DB.
    return register_library(
        registry_path,
        library_id=str(existing["library_id"]),
        display_name=str(existing["display_name"]),
        database_path=Path(str(existing["database_path"])),
        workspace_root=Path(str(existing["workspace_root"])),
        work_root=Path(next_work),
        archive_root=Path(next_archive),
        is_main=bool(existing["is_main"]),
        is_active=bool(existing["is_active"]),
        settings={
            **dict(existing.get("settings") or {}),
            "paths_updated_at": _now(),
        },
    )


def set_library_active(
    registry_path: Path,
    library_id: str,
    active: bool,
) -> dict[str, Any]:
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None or not existing.get("is_registered", True):
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
    if existing.get("is_main") and not active:
        raise LibraryRegistryError("Die Hauptbibliothek kann nicht deaktiviert werden.")

    return register_library(
        registry_path,
        library_id=str(existing["library_id"]),
        display_name=str(existing["display_name"]),
        database_path=Path(str(existing["database_path"])),
        workspace_root=Path(str(existing["workspace_root"])),
        work_root=Path(str(existing["work_root"])),
        archive_root=Path(str(existing["archive_root"])),
        is_main=bool(existing["is_main"]),
        is_active=bool(active),
        settings=dict(existing.get("settings") or {}),
    )


def remove_library_registration(
    registry_path: Path,
    library_id: str,
    *,
    allow_main: bool = False,
) -> None:
    """Remove a just-created registry row after a failed creation transaction.

    This is intentionally stricter than unregister_library(): it is only valid
    when the library has no claims. It never deletes a library database or any
    filesystem content.
    """
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None:
        return
    if existing.get("is_main") and not allow_main:
        raise LibraryRegistryError(
            "Die Hauptbibliothek darf nicht aus der Registry entfernt werden."
        )

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        claim = connection.execute(
            "SELECT 1 FROM family_claims WHERE library_id=? LIMIT 1",
            (str(library_id),),
        ).fetchone()
        if claim is not None:
            raise LibraryRegistryError(
                "Bibliotheksregistrierung besitzt bereits globale Claims und "
                "darf nicht automatisch entfernt werden."
            )
        connection.execute(
            "DELETE FROM libraries WHERE library_id=?",
            (str(library_id),),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def unregister_library(
    registry_path: Path,
    library_id: str,
) -> dict[str, Any]:
    existing = get_library(registry_path, library_id, active_only=False)
    if existing is None:
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
    if existing.get("is_main"):
        raise LibraryRegistryError("Die Hauptbibliothek kann nicht abgemeldet werden.")

    now = _now()
    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            """
            UPDATE libraries
            SET is_active = 0,
                is_registered = 0,
                deactivated_at = COALESCE(deactivated_at, ?),
                unregistered_at = ?,
                updated_at = ?
            WHERE library_id = ?
            """,
            (now, now, now, str(library_id)),
        )
        if cursor.rowcount != 1:
            raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    result = get_library(registry_path, library_id, active_only=False)
    if result is None:
        raise LibraryRegistryError("Bibliothek wurde nicht gefunden.")
    return result


def get_source_backup(
    registry_path: Path,
    backup_id: str,
) -> dict[str, Any] | None:
    clean_backup_id = str(backup_id or "").strip()
    if not clean_backup_id:
        return None

    connection = _connect(registry_path)
    try:
        row = connection.execute(
            """
            SELECT *
            FROM source_backups
            WHERE backup_id = ?
            """,
            (clean_backup_id,),
        ).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    result = dict(row)
    try:
        result["metadata"] = json.loads(str(result.get("metadata_json") or "{}"))
    except (TypeError, ValueError):
        result["metadata"] = {}
    return result



def source_backup_claim_count(
    registry_path: Path,
    backup_id: str,
) -> int:
    clean_backup_id = str(backup_id or "").strip()
    if not clean_backup_id:
        return 0

    connection = _connect(registry_path)
    try:
        row = connection.execute(
            """
            SELECT COUNT(DISTINCT claims.canonical_family_id) AS n
            FROM source_families AS families
            JOIN family_claims AS claims
              ON claims.canonical_family_id = families.canonical_family_id
            WHERE families.backup_id = ?
            """,
            (clean_backup_id,),
        ).fetchone()
        return int(row["n"] or 0) if row is not None else 0
    finally:
        connection.close()


def remove_source_backup(
    registry_path: Path,
    backup_id: str,
) -> bool:
    """Remove one source-backup occurrence when no library still claims it.

    Source-family/media rows are removed by foreign-key cascades. Canonical
    families are retained when another source occurrence still references them
    and are otherwise cleaned up once they are truly orphaned.
    """
    clean_backup_id = str(backup_id or "").strip()
    if not clean_backup_id:
        return False

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        canonical_rows = connection.execute(
            """
            SELECT DISTINCT canonical_family_id
            FROM source_families
            WHERE backup_id = ?
            """,
            (clean_backup_id,),
        ).fetchall()
        canonical_ids = [
            str(row["canonical_family_id"])
            for row in canonical_rows
        ]

        cursor = connection.execute(
            "DELETE FROM source_backups WHERE backup_id = ?",
            (clean_backup_id,),
        )

        for canonical_id in canonical_ids:
            connection.execute(
                """
                DELETE FROM canonical_families
                WHERE canonical_family_id = ?
                  AND NOT EXISTS (
                      SELECT 1
                      FROM source_families
                      WHERE canonical_family_id = ?
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM family_claims
                      WHERE canonical_family_id = ?
                  )
                """,
                (canonical_id, canonical_id, canonical_id),
            )

        connection.commit()
        return cursor.rowcount == 1
    except Exception:
        connection.rollback()
        raise
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
    clean_backup_id = str(backup_id or "").strip()
    clean_kind = str(source_kind or "").strip()
    clean_identity = str(source_identity or "").strip()
    clean_path = str(backup_path or "").strip()
    if not all((clean_backup_id, clean_kind, clean_identity, clean_path)):
        raise LibraryRegistryError(
            "Backup-ID, Quellentyp, Quellenidentität und Sicherungspfad sind erforderlich."
        )

    now = _now()
    serialized = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )
    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT source_kind, source_identity, backup_path, metadata_json, created_at
            FROM source_backups
            WHERE backup_id = ?
            """,
            (clean_backup_id,),
        ).fetchone()
        effective_identity = clean_identity
        if existing is not None:
            existing_kind = str(existing["source_kind"])
            existing_identity = str(existing["source_identity"])
            existing_path = str(existing["backup_path"])
            if existing_kind != clean_kind:
                metadata_library = str((metadata or {}).get("library_id") or "")
                physical_identity = str(
                    (metadata or {}).get("physical_source_identity") or ""
                )
                safe_main_import_upgrade = (
                    existing_kind == "existing_library"
                    and clean_kind == "import"
                    and metadata_library == MAIN_LIBRARY_ID
                    and physical_identity
                    and clean_identity == physical_identity
                    and existing_path == clean_path
                    and existing_identity in {
                        physical_identity,
                        metadata_library + ":" + physical_identity,
                    }
                )
                if not safe_main_import_upgrade:
                    raise LibraryRegistryError(
                        "Eine bestehende Backup-ID darf nicht auf einen anderen "
                        "Quellentyp umgebunden werden."
                    )
                # 0.33.4: Vor der globalen Import-Registry konnte auch die
                # Main Library beim Backfill als existing_library landen.
                # Genau dieser eng eingegrenzte Altfall wird wieder als
                # physischer Import markiert; andere Quellentypwechsel bleiben
                # weiterhin strikt verboten.
                connection.execute(
                    """
                    UPDATE source_backups
                    SET source_kind=?, source_identity=?, metadata_json=?, updated_at=?
                    WHERE backup_id=?
                    """,
                    (
                        clean_kind,
                        clean_identity,
                        serialized,
                        now,
                        clean_backup_id,
                    ),
                )
                existing_kind = clean_kind
                existing_identity = clean_identity
            if existing_identity != clean_identity:
                metadata_library = str((metadata or {}).get("library_id") or "")
                physical_identity = str(
                    (metadata or {}).get("physical_source_identity") or ""
                )
                safe_legacy_upgrade = (
                    clean_kind == "existing_library"
                    and metadata_library
                    and physical_identity
                    and existing_identity == physical_identity
                    and clean_identity == metadata_library + ":" + physical_identity
                    and existing_path == clean_path
                )
                # 0.54.1: Earlier import registration could have used
                # the job's stale source_path/source_device_id while the
                # persisted job already contained the measured SHA signature.
                # Reconcile only this exact, provenance-matched legacy case.
                # Arbitrary changed source identities remain forbidden.
                try:
                    old_metadata = json.loads(str(existing["metadata_json"] or "{}"))
                except (TypeError, ValueError, json.JSONDecodeError):
                    old_metadata = {}
                old_metadata = old_metadata if isinstance(old_metadata, dict) else {}
                fallback_identity = str((metadata or {}).get("legacy_import_identity") or "")
                matching_main_job = (
                    metadata_library == MAIN_LIBRARY_ID
                    and str((metadata or {}).get("job_id") or "")
                    and str(old_metadata.get("library_id") or "") == metadata_library
                    and str(old_metadata.get("job_id") or "") == str((metadata or {}).get("job_id") or "")
                    and clean_backup_id == metadata_library + ":" + str((metadata or {}).get("job_id"))
                )
                safe_stale_import_upgrade = (
                    existing_kind == clean_kind == "import"
                    and matching_main_job
                    and existing_path == clean_path
                    and fallback_identity
                    and existing_identity == fallback_identity
                    and clean_identity == physical_identity
                    and clean_identity != fallback_identity
                )
                if not (safe_legacy_upgrade or safe_stale_import_upgrade):
                    raise LibraryRegistryError(
                        "Eine bestehende Backup-ID darf nicht auf eine andere "
                        "Quelle umgebunden werden."
                    )
                # Both legacy upgrades preserve the same backup ID,
                # original source path and proven job ownership; no files
                # or ownership claims are changed.
                connection.execute(
                    """
                    UPDATE source_backups
                    SET source_identity=?, metadata_json=?, updated_at=?
                    WHERE backup_id=?
                    """,
                    (
                        clean_identity,
                        serialized,
                        now,
                        clean_backup_id,
                    ),
                )
                effective_identity = clean_identity
            else:
                effective_identity = existing_identity

        connection.execute(
            """
            INSERT INTO source_backups(
                backup_id, source_kind, source_identity, backup_path,
                metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backup_id) DO UPDATE SET
                backup_path = excluded.backup_path,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                clean_backup_id,
                clean_kind,
                effective_identity,
                clean_path,
                serialized,
                str(existing["created_at"]) if existing else now,
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

def _canonical_family_id(content_fingerprint: str) -> str:
    clean = str(content_fingerprint or "").strip()
    if not clean:
        raise LibraryRegistryError(
            "Eine globale Dateifamilie benötigt einen Inhaltsfingerprint."
        )
    digest = hashlib.sha256(
        clean.encode("utf-8", "surrogateescape")
    ).hexdigest()
    return "family-" + digest


def _canonical_for_source_family(
    connection: sqlite3.Connection,
    source_family_key: str,
) -> str | None:
    row = connection.execute(
        """
        SELECT canonical_family_id
        FROM source_families
        WHERE source_family_key = ?
        """,
        (str(source_family_key),),
    ).fetchone()
    return str(row["canonical_family_id"]) if row else None


def list_library_import_job_ids(
    registry_path: Path,
    library_id: str,
) -> list[str]:
    """Return camera-import jobs that physically originated in one library.

    Projected copies in other library databases use source_kind
    existing_library and are deliberately excluded. This gives global
    workflows one stable owner for otherwise shared central-stock rows.
    """
    clean_id = str(library_id or "").strip()
    if not clean_id:
        return []

    connection = _connect(registry_path)
    try:
        rows = connection.execute(
            """
            SELECT backup_id, metadata_json
            FROM source_backups
            WHERE source_kind='import'
            ORDER BY created_at, backup_id
            """
        ).fetchall()
    finally:
        connection.close()

    result: list[str] = []
    for row in rows:
        try:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
        except (TypeError, ValueError):
            metadata = {}
        if str(metadata.get("library_id") or "") != clean_id:
            continue
        job_id = str(metadata.get("job_id") or "").strip()
        if not job_id:
            backup_id = str(row["backup_id"] or "")
            prefix = clean_id + ":"
            if backup_id.startswith(prefix):
                job_id = backup_id[len(prefix):]
        if job_id and job_id not in result:
            result.append(job_id)
    return result

def register_source_family(
    registry_path: Path,
    *,
    source_family_key: str,
    backup_id: str,
    family_key: str,
    content_fingerprint: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_source_key = str(source_family_key or "").strip()
    clean_backup_id = str(backup_id or "").strip()
    clean_family_key = str(family_key or "").strip()
    clean_fingerprint = str(content_fingerprint or "").strip()
    if not clean_source_key or not clean_backup_id or not clean_family_key:
        raise LibraryRegistryError(
            "Quellfamilien-ID, Backup-ID und Familien-ID sind erforderlich."
        )
    canonical_id = _canonical_family_id(clean_fingerprint)
    now = _now()
    serialized = json.dumps(
        metadata or {},
        ensure_ascii=False,
        sort_keys=True,
    )

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")

        backup = connection.execute(
            "SELECT backup_id FROM source_backups WHERE backup_id = ?",
            (clean_backup_id,),
        ).fetchone()
        if backup is None:
            raise LibraryRegistryError(
                "Die Quellfamilie verweist auf eine unbekannte Sicherung."
            )

        existing = connection.execute(
            """
            SELECT backup_id, family_key, canonical_family_id, created_at
            FROM source_families
            WHERE source_family_key = ?
            """,
            (clean_source_key,),
        ).fetchone()
        if existing is not None and (
            str(existing["backup_id"]) != clean_backup_id
            or str(existing["family_key"]) != clean_family_key
            or str(existing["canonical_family_id"]) != canonical_id
        ):
            raise LibraryRegistryError(
                "Eine bestehende Quellfamilien-ID darf nicht auf eine andere "
                "Herkunft oder einen anderen Inhalt umgebunden werden."
            )

        canonical = connection.execute(
            """
            SELECT canonical_family_id
            FROM canonical_families
            WHERE content_fingerprint = ?
            """,
            (clean_fingerprint,),
        ).fetchone()
        if canonical is not None:
            canonical_id = str(canonical["canonical_family_id"])

        connection.execute(
            """
            INSERT INTO canonical_families(
                canonical_family_id, content_fingerprint,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(content_fingerprint) DO UPDATE SET
                updated_at = excluded.updated_at
            """,
            (
                canonical_id,
                clean_fingerprint,
                now,
                now,
            ),
        )

        connection.execute(
            """
            INSERT INTO source_families(
                source_family_key, backup_id, family_key,
                canonical_family_id, metadata_json,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_family_key) DO UPDATE SET
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                clean_source_key,
                clean_backup_id,
                clean_family_key,
                canonical_id,
                serialized,
                str(existing["created_at"]) if existing else now,
                now,
            ),
        )

        row = connection.execute(
            """
            SELECT
                source_family_key,
                backup_id,
                family_key,
                canonical_family_id,
                metadata_json,
                created_at,
                updated_at
            FROM source_families
            WHERE source_family_key = ?
            """,
            (clean_source_key,),
        ).fetchone()
        connection.commit()
        result = dict(row)
        result["content_fingerprint"] = clean_fingerprint
        return result
    except sqlite3.IntegrityError as error:
        connection.rollback()
        raise LibraryRegistryError(str(error)) from error
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()



def register_source_media(
    registry_path: Path,
    *,
    backup_id: str,
    relative_path: str,
    size_bytes: int,
    sha256: str,
    media_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_backup = str(backup_id or "").strip()
    clean_relative = str(relative_path or "").strip().replace("\\", "/")
    clean_sha = str(sha256 or "").strip().lower()
    if not clean_backup or not clean_relative or not clean_sha:
        raise LibraryRegistryError(
            "Backup-ID, relativer Pfad und SHA256 sind für Quelldateien erforderlich."
        )
    media_id = "media-" + hashlib.sha256(
        (clean_backup + "\0" + clean_relative).encode("utf-8", "surrogateescape")
    ).hexdigest()
    now = _now()
    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        backup = connection.execute(
            "SELECT backup_id FROM source_backups WHERE backup_id = ?",
            (clean_backup,),
        ).fetchone()
        if backup is None:
            raise LibraryRegistryError("Quelldatei verweist auf unbekannte Sicherung.")

        existing = connection.execute(
            "SELECT media_id, sha256, created_at FROM source_media WHERE backup_id=? AND relative_path=?",
            (clean_backup, clean_relative),
        ).fetchone()
        if existing is not None and str(existing["sha256"]).lower() != clean_sha:
            raise LibraryRegistryError(
                "Eine bekannte Quelldatei darf nicht still durch anderen Inhalt ersetzt werden."
            )

        connection.execute(
            """
            INSERT INTO source_media(
                media_id, backup_id, relative_path, size_bytes,
                sha256, media_type, metadata_json, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(backup_id, relative_path) DO UPDATE SET
                size_bytes = excluded.size_bytes,
                media_type = excluded.media_type,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at
            """,
            (
                media_id,
                clean_backup,
                clean_relative,
                max(0, int(size_bytes or 0)),
                clean_sha,
                str(media_type or "").strip() or None,
                json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                str(existing["created_at"]) if existing else now,
                now,
            ),
        )
        row = connection.execute(
            "SELECT * FROM source_media WHERE backup_id=? AND relative_path=?",
            (clean_backup, clean_relative),
        ).fetchone()
        connection.commit()
        return dict(row)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def register_source_family_members(
    registry_path: Path,
    *,
    source_family_key: str,
    media_ids: list[str],
) -> int:
    clean_family = str(source_family_key or "").strip()
    unique_media = [str(value).strip() for value in dict.fromkeys(media_ids) if str(value).strip()]
    if not clean_family:
        raise LibraryRegistryError("Quellfamilien-ID fehlt.")

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        family = connection.execute(
            "SELECT source_family_key FROM source_families WHERE source_family_key=?",
            (clean_family,),
        ).fetchone()
        if family is None:
            raise LibraryRegistryError("Quellfamilie wurde nicht gefunden.")

        connection.execute(
            "DELETE FROM source_family_members WHERE source_family_key=?",
            (clean_family,),
        )
        now = _now()
        for order, media_id in enumerate(unique_media):
            media = connection.execute(
                "SELECT media_id FROM source_media WHERE media_id=?",
                (media_id,),
            ).fetchone()
            if media is None:
                raise LibraryRegistryError(
                    "Familienmitglied verweist auf unbekannte Quelldatei: " + media_id
                )
            connection.execute(
                """
                INSERT INTO source_family_members(
                    source_family_key, media_id, member_role, member_order, created_at
                )
                VALUES (?, ?, 'member', ?, ?)
                """,
                (clean_family, media_id, order, now),
            )
        connection.commit()
        return len(unique_media)
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def list_source_family_members(
    registry_path: Path,
    source_family_key: str,
) -> list[dict[str, Any]]:
    connection = _connect(registry_path)
    try:
        rows = connection.execute(
            """
            SELECT m.*, fm.member_role, fm.member_order
            FROM source_family_members fm
            JOIN source_media m ON m.media_id = fm.media_id
            WHERE fm.source_family_key = ?
            ORDER BY fm.member_order, m.relative_path
            """,
            (str(source_family_key),),
        ).fetchall()
        return [dict(row) for row in rows]
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
    """Create the single global reservation or ownership claim.

    Planning already reserves the canonical family globally. Applying the event
    promotes that same library's reservation to owned.
    """
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

        canonical_id = _canonical_for_source_family(
            connection,
            source_family_key,
        )
        if canonical_id is None:
            raise LibraryRegistryError(
                "Die Dateifamilie ist nicht in der globalen Quellen-Registry registriert."
            )

        existing = connection.execute(
            """
            SELECT *
            FROM family_claims
            WHERE canonical_family_id = ?
              AND library_id = ?
            """,
            (canonical_id, str(library_id)),
        ).fetchone()
        other_claim = connection.execute(
            """
            SELECT *
            FROM family_claims
            WHERE canonical_family_id = ?
              AND library_id <> ?
            ORDER BY CASE claim_state WHEN 'owned' THEN 0 ELSE 1 END, library_id
            LIMIT 1
            """,
            (canonical_id, str(library_id)),
        ).fetchone()

        # Planung ist bereits eine globale Belegung. Eine kanonische Familie
        # darf deshalb zu jedem Zeitpunkt nur zu genau einer Bibliothek gehören.
        if other_claim is not None:
            if str(other_claim["claim_state"]) == "owned":
                message = (
                    "Diese Dateifamilie wurde bereits von einer anderen "
                    "Bibliothek übernommen."
                )
            else:
                message = (
                    "Diese Dateifamilie ist bereits für ein geplantes Ereignis "
                    "einer anderen Bibliothek reserviert."
                )
            raise LibraryRegistryError(message)

        if (
            existing
            and str(existing["claim_state"]) == "owned"
            and claim_state == "reserved"
        ):
            raise LibraryRegistryError(
                "Eine bereits übernommene Dateifamilie kann nicht auf reserviert zurückgesetzt werden."
            )

        connection.execute(
            """
            INSERT INTO family_claims(
                canonical_family_id, library_id, claim_state,
                event_id, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(canonical_family_id, library_id) DO UPDATE SET
                claim_state = excluded.claim_state,
                event_id = excluded.event_id,
                updated_at = excluded.updated_at
            """,
            (
                canonical_id,
                str(library_id),
                claim_state,
                str(event_id) if event_id else None,
                str(existing["created_at"]) if existing else now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT *
            FROM family_claims
            WHERE canonical_family_id = ?
              AND library_id = ?
            """,
            (canonical_id, str(library_id)),
        ).fetchone()
        connection.commit()
        result = dict(row)
        result["source_family_key"] = str(source_family_key)
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def release_source_family_claim(
    registry_path: Path,
    *,
    source_family_key: str,
    library_id: str,
    allowed_states: set[str] | None = None,
) -> bool:
    allowed = set(allowed_states or {"reserved"})
    if not allowed or not allowed.issubset({"reserved", "owned"}):
        raise LibraryRegistryError("Ungültiger Freigabezustand.")

    connection = _connect(registry_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        canonical_id = _canonical_for_source_family(
            connection,
            source_family_key,
        )
        if canonical_id is None:
            connection.commit()
            return False

        row = connection.execute(
            """
            SELECT claim_state, library_id
            FROM family_claims
            WHERE canonical_family_id = ?
              AND library_id = ?
            """,
            (canonical_id, str(library_id)),
        ).fetchone()

        if row is None:
            connection.commit()
            return False
        if str(row["claim_state"]) not in allowed:
            raise LibraryRegistryError(
                "Dieser Familienzustand darf in diesem Workflow nicht freigegeben werden."
            )

        connection.execute(
            """
            DELETE FROM family_claims
            WHERE canonical_family_id = ?
              AND library_id = ?
            """,
            (canonical_id, str(library_id)),
        )
        connection.commit()
        return True
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
    return release_source_family_claim(
        registry_path,
        source_family_key=source_family_key,
        library_id=library_id,
        allowed_states={"reserved"},
    )


def _source_family_library_id(row: dict[str, Any]) -> str:
    try:
        metadata = json.loads(str(row.get("source_metadata_json") or "{}"))
        value = str(metadata.get("library_id") or "").strip()
        if value:
            return value
    except (TypeError, ValueError):
        pass
    source_key = str(row.get("source_family_key") or "")
    return source_key.split(":", 1)[0] if ":" in source_key else ""


def _effective_claim(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Return the single globally effective claim for one canonical family.

    Since 0.32.3 both reservation and ownership are globally exclusive. The
    composite primary key introduced in 0.32.2 is retained for migration
    compatibility, but contradictory multi-library reservations are surfaced
    explicitly instead of being hidden.
    """
    if not rows:
        return None

    owners = [
        row
        for row in rows
        if str(row.get("claim_state") or "") == "owned"
    ]
    if len(owners) > 1:
        raise LibraryRegistryError(
            "Widersprüchliche globale Besitz-Claims für eine Dateifamilie."
        )
    if owners:
        return owners[0]

    reservations = [
        row
        for row in rows
        if str(row.get("claim_state") or "") == "reserved"
    ]
    if len(reservations) > 1:
        libraries = sorted({
            str(row.get("library_id") or "")
            for row in reservations
        })
        raise LibraryRegistryError(
            "Widersprüchliche globale Reservierungen für eine Dateifamilie: "
            + ", ".join(value for value in libraries if value)
        )
    return reservations[0] if reservations else None


def get_source_family_claims(
    registry_path: Path,
    source_family_keys: list[str],
) -> dict[str, dict[str, Any]]:
    """Return the globally effective claim for each library occurrence.

    Both reserved and owned claims block the same canonical family in every
    other library. Planning itself is therefore globally exclusive.
    """
    keys = [
        str(value).strip()
        for value in dict.fromkeys(source_family_keys)
        if str(value).strip()
    ]
    if not keys:
        return {}

    connection = _connect(registry_path)
    try:
        candidates: dict[str, list[dict[str, Any]]] = {}
        for offset in range(0, len(keys), 400):
            chunk = keys[offset:offset + 400]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"""
                SELECT
                    sf.source_family_key,
                    sf.metadata_json AS source_metadata_json,
                    fc.canonical_family_id,
                    fc.library_id,
                    fc.claim_state,
                    fc.event_id,
                    fc.created_at,
                    fc.updated_at
                FROM source_families sf
                JOIN family_claims fc
                  ON fc.canonical_family_id = sf.canonical_family_id
                WHERE sf.source_family_key IN ({placeholders})
                ORDER BY sf.source_family_key, fc.claim_state, fc.library_id
                """,
                chunk,
            ).fetchall()
            for raw in rows:
                item = dict(raw)
                candidates.setdefault(
                    str(item["source_family_key"]),
                    [],
                ).append(item)

        result: dict[str, dict[str, Any]] = {}
        for source_key, rows in candidates.items():
            claim = _effective_claim(rows)
            if claim is None:
                continue
            item = dict(claim)
            item.pop("source_metadata_json", None)
            result[source_key] = item
        return result
    finally:
        connection.close()


def get_source_family_local_claims(
    registry_path: Path,
    source_family_keys: list[str],
    library_id: str,
) -> dict[str, dict[str, Any]]:
    """Return only claims owned/reserved by the explicitly named library."""
    keys = [
        str(value).strip()
        for value in dict.fromkeys(source_family_keys)
        if str(value).strip()
    ]
    if not keys:
        return {}

    connection = _connect(registry_path)
    try:
        result: dict[str, dict[str, Any]] = {}
        for offset in range(0, len(keys), 400):
            chunk = keys[offset:offset + 400]
            placeholders = ",".join("?" for _ in chunk)
            rows = connection.execute(
                f"""
                SELECT
                    sf.source_family_key,
                    fc.canonical_family_id,
                    fc.library_id,
                    fc.claim_state,
                    fc.event_id,
                    fc.created_at,
                    fc.updated_at
                FROM source_families sf
                JOIN family_claims fc
                  ON fc.canonical_family_id = sf.canonical_family_id
                 AND fc.library_id = ?
                WHERE sf.source_family_key IN ({placeholders})
                """,
                [str(library_id), *chunk],
            ).fetchall()
            for raw in rows:
                item = dict(raw)
                result[str(item["source_family_key"])] = item
        return result
    finally:
        connection.close()


def get_source_family_claim(
    registry_path: Path,
    source_family_key: str,
) -> dict[str, Any] | None:
    return get_source_family_claims(
        registry_path,
        [source_family_key],
    ).get(str(source_family_key))


def get_source_family_local_claim(
    registry_path: Path,
    source_family_key: str,
    library_id: str,
) -> dict[str, Any] | None:
    return get_source_family_local_claims(
        registry_path,
        [source_family_key],
        library_id,
    ).get(str(source_family_key))
