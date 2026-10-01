from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import sqlite3


REGISTRY_SCHEMA_VERSION = 1
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

    if is_active:
        database_file = Path(database_value)
        if not database_file.is_file():
            raise LibraryRegistryError(
                "Eine aktive Bibliothek benötigt eine vorhandene SQLite-Datenbank."
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

    effective_work_root = (
        Path(str(existing["work_root"]))
        if existing
        else work_root
    )

    return register_library(
        registry_path,
        library_id=MAIN_LIBRARY_ID,
        display_name=display_name,
        database_path=database_path,
        workspace_root=workspace_root,
        work_root=effective_work_root,
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
            """,
            (canonical_id,),
        ).fetchone()

        if existing and str(existing["library_id"]) != str(library_id):
            raise LibraryRegistryError(
                "Diese Dateifamilie ist bereits einer anderen Bibliothek vorbehalten."
            )

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
            ON CONFLICT(canonical_family_id) DO UPDATE SET
                library_id = excluded.library_id,
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
            """,
            (canonical_id,),
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


def release_source_family_reservation(
    registry_path: Path,
    *,
    source_family_key: str,
    library_id: str,
) -> bool:
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
            """,
            (canonical_id,),
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
            "DELETE FROM family_claims WHERE canonical_family_id = ?",
            (canonical_id,),
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
        canonical_id = _canonical_for_source_family(
            connection,
            source_family_key,
        )
        if canonical_id is None:
            return None
        row = connection.execute(
            """
            SELECT *
            FROM family_claims
            WHERE canonical_family_id = ?
            """,
            (canonical_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["source_family_key"] = str(source_family_key)
        return result
    finally:
        connection.close()

