from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import database_connection
from app.safe_transfer import reconcile_migrated_file
from app.workspace_layout import backup_root, shared_work_root


class GlobalStockError(RuntimeError):
    pass


def _table_columns(connection: Any, table: str) -> list[str]:
    return [
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    ]


def _insert_row(
    connection: Any,
    table: str,
    row: dict[str, Any],
    *,
    exclude: set[str] | None = None,
) -> None:
    excluded = exclude or set()
    available = set(_table_columns(connection, table))
    columns = [
        column
        for column in row
        if column in available and column not in excluded
    ]
    if not columns:
        raise GlobalStockError("Keine kompatiblen Spalten für Tabelle " + table)
    placeholders = ",".join("?" for _ in columns)
    names = ",".join(columns)
    connection.execute(
        f"INSERT INTO {table} ({names}) VALUES ({placeholders})",
        tuple(row[column] for column in columns),
    )


def project_import_job(
    source_database: Path,
    target_database: Path,
    job_id: str,
) -> dict[str, int]:
    """Project one completed global import into another library database.

    IDs of families/files are deliberately local to the target database.
    Natural keys (job_id/family_key and job_id/original_relative_path) provide
    the stable mapping. Existing target rows are never overwritten, because an
    applied library is allowed to have a different physical current path.
    """

    if source_database.resolve(strict=False) == target_database.resolve(strict=False):
        return {"jobs": 0, "families": 0, "files": 0}

    with database_connection(source_database) as source:
        raw_job = source.execute(
            "SELECT * FROM jobs WHERE id=? AND kind='sd_import'",
            (str(job_id),),
        ).fetchone()
        if raw_job is None:
            return {"jobs": 0, "families": 0, "files": 0}
        job = dict(raw_job)
        families = [
            dict(row)
            for row in source.execute(
                "SELECT * FROM file_families WHERE job_id=? ORDER BY id",
                (str(job_id),),
            ).fetchall()
        ]
        files = [
            dict(row)
            for row in source.execute(
                "SELECT * FROM files WHERE job_id=? ORDER BY id",
                (str(job_id),),
            ).fetchall()
        ]

    source_family_key = {
        int(row["id"]): str(row["family_key"])
        for row in families
    }

    inserted_jobs = 0
    inserted_families = 0
    inserted_files = 0

    with database_connection(target_database) as target:
        target.execute("BEGIN IMMEDIATE")

        existing_job = target.execute(
            "SELECT id FROM jobs WHERE id=?",
            (str(job_id),),
        ).fetchone()
        if existing_job is None:
            _insert_row(target, "jobs", job)
            inserted_jobs += 1

        family_id_by_key: dict[str, int] = {}
        for family in families:
            key = str(family["family_key"])
            existing = target.execute(
                "SELECT id FROM file_families WHERE job_id=? AND family_key=?",
                (str(job_id), key),
            ).fetchone()
            if existing is None:
                _insert_row(
                    target,
                    "file_families",
                    family,
                    exclude={"id"},
                )
                existing = target.execute(
                    "SELECT id FROM file_families WHERE job_id=? AND family_key=?",
                    (str(job_id), key),
                ).fetchone()
                inserted_families += 1
            if existing is None:
                raise GlobalStockError(
                    "Familienprojektion konnte nicht bestätigt werden: " + key
                )
            family_id_by_key[key] = int(existing["id"])

        for file_row in files:
            relative = str(file_row["original_relative_path"])
            existing = target.execute(
                "SELECT id FROM files WHERE job_id=? AND original_relative_path=?",
                (str(job_id), relative),
            ).fetchone()
            if existing is not None:
                continue

            projected = dict(file_row)
            source_family_id = projected.get("family_id")
            if source_family_id is not None:
                key = source_family_key.get(int(source_family_id))
                if not key or key not in family_id_by_key:
                    raise GlobalStockError(
                        "Dateifamilie der Projektion fehlt: " + relative
                    )
                projected["family_id"] = family_id_by_key[key]

            _insert_row(
                target,
                "files",
                projected,
                exclude={"id"},
            )
            inserted_files += 1

        target.commit()

    return {
        "jobs": inserted_jobs,
        "families": inserted_families,
        "files": inserted_files,
    }


def project_all_imports(
    source_database: Path,
    target_database: Path,
) -> dict[str, int]:
    if source_database.resolve(strict=False) == target_database.resolve(strict=False):
        return {"jobs": 0, "families": 0, "files": 0}

    with database_connection(source_database) as source:
        job_ids = [
            str(row["id"])
            for row in source.execute(
                """SELECT id FROM jobs
                   WHERE kind='sd_import' AND state='completed'
                   ORDER BY created_at,id"""
            ).fetchall()
        ]

    totals = {"jobs": 0, "families": 0, "files": 0}
    for job_id in job_ids:
        result = project_import_job(
            source_database,
            target_database,
            job_id,
        )
        for key in totals:
            totals[key] += int(result[key])
    return totals


def migrate_main_free_stock_to_central(
    database_path: Path,
    workspace_path: Path,
) -> dict[str, int]:
    """Move legacy free/planned Main files from Arbeitsbereich to central stock.

    Applied event files and library-specific "Später zuordnen" material remain
    in the Main library work root. The operation is idempotent and validates
    every destination before deleting a source.
    """

    central = backup_root(workspace_path).resolve(strict=False)
    work = shared_work_root(workspace_path).resolve(strict=False)

    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """
                SELECT
                    f.id,
                    f.family_id,
                    f.current_relative_path,
                    f.size_bytes,
                    f.sha256_current,
                    f.sha256_original,
                    EXISTS (
                        SELECT 1
                        FROM event_assignments ea
                        JOIN events assigned ON assigned.id=ea.event_id
                        JOIN events root
                          ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                        WHERE root.status='applied'
                          AND (
                              (ea.family_id IS NOT NULL AND ea.family_id=f.family_id)
                              OR (ea.file_id IS NOT NULL AND ea.file_id=f.id)
                          )
                    ) AS belongs_to_applied
                FROM files f
                WHERE f.current_root_kind='shared_workspace'
                  AND COALESCE(TRIM(f.current_relative_path),'') <> ''
                ORDER BY f.id
                """
            ).fetchall()
        ]

    migrated = 0
    already = 0
    kept_applied = 0
    kept_staging = 0

    for row in rows:
        relative = Path(str(row["current_relative_path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise GlobalStockError(
                "Unsicherer relativer Pfad in Main-Bestand: " + str(relative)
            )

        normalized = relative.as_posix()
        if normalized == "Später zuordnen" or normalized.startswith("Später zuordnen/"):
            kept_staging += 1
            continue
        if bool(row["belongs_to_applied"]):
            kept_applied += 1
            continue

        source = work / relative
        destination = central / relative
        expected_hash = str(
            row.get("sha256_current")
            or row.get("sha256_original")
            or ""
        ).strip()
        if not expected_hash:
            raise GlobalStockError(
                "Für die Migration fehlt SHA-256: " + str(relative)
            )

        result = reconcile_migrated_file(
            source,
            destination,
            expected_size=int(row["size_bytes"]),
            expected_sha256=expected_hash,
        )
        if str(result.get("status")) == "migrated":
            migrated += 1
        else:
            already += 1

    with database_connection(database_path) as connection:
        connection.execute(
            """UPDATE jobs
               SET working_path=?
               WHERE kind='sd_import'
                 AND operation='folder_import'""",
            (str(central),),
        )
        connection.commit()

    return {
        "migrated": migrated,
        "already_migrated": already,
        "kept_applied": kept_applied,
        "kept_staging": kept_staging,
    }



def synchronize_central_stock_projections(
    database_paths: list[Path],
    workspace_path: Path,
) -> dict[str, Any]:
    """Refresh free-file paths in every library from the physical central stock.

    Every library keeps local IDs and local applied-event paths. A path is
    propagated only when the corresponding file is physically present in the
    central stock. Locally applied/archived files and "Später zuordnen" staging
    are never overwritten.
    """

    central = backup_root(workspace_path).resolve(strict=False)
    unique_databases: list[Path] = []
    seen_databases: set[str] = set()
    for raw in database_paths:
        path = Path(raw).resolve(strict=False)
        key = str(path)
        if key in seen_databases or not path.is_file():
            continue
        seen_databases.add(key)
        unique_databases.append(path)

    central_paths: dict[tuple[str, str], dict[str, Any]] = {}
    conflicts: list[str] = []

    for database_path in unique_databases:
        with database_connection(database_path) as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """SELECT job_id,original_relative_path,current_relative_path,
                              size_bytes,sha256_current,sha256_original
                       FROM files
                       WHERE current_root_kind='shared_workspace'
                         AND COALESCE(TRIM(current_relative_path),'') <> ''
                       ORDER BY job_id,id"""
                ).fetchall()
            ]

        for row in rows:
            relative = Path(str(row["current_relative_path"]))
            if relative.is_absolute() or ".." in relative.parts:
                continue
            normalized = relative.as_posix()
            if (
                normalized == "Später zuordnen"
                or normalized.startswith("Später zuordnen/")
            ):
                continue
            candidate = (central / relative).resolve(strict=False)
            try:
                candidate.relative_to(central)
            except ValueError:
                continue
            if not candidate.is_file():
                continue
            try:
                if int(candidate.stat().st_size) != int(row["size_bytes"]):
                    continue
            except OSError:
                continue

            identity = (
                str(row["job_id"]),
                str(row["original_relative_path"]),
            )
            existing = central_paths.get(identity)
            if (
                existing is not None
                and str(existing["current_relative_path"]) != normalized
            ):
                conflicts.append(
                    identity[0]
                    + ":"
                    + identity[1]
                    + " → "
                    + str(existing["current_relative_path"])
                    + " / "
                    + normalized
                )
                continue
            central_paths[identity] = {
                **row,
                "current_relative_path": normalized,
            }

    if conflicts:
        raise GlobalStockError(
            "Mehrdeutige zentrale Dateipfade erkannt: "
            + " | ".join(conflicts[:10])
        )

    # Archivfreigaben liegen physisch ebenfalls im globalen zentralen Bestand.
    # Ihre lokalen Familien-/Datei-IDs dürfen jedoch nicht zwischen
    # Bibliotheksdatenbanken kopiert werden. Deshalb wird ausschließlich über
    # stabile natürliche Identitäten projiziert.
    central_release_markers: dict[tuple[str, str], dict[str, Any]] = {}
    central_release_assets: dict[tuple[str, str, str], dict[str, Any]] = {}

    for database_path in unique_databases:
        with database_connection(database_path) as connection:
            marker_rows = [
                dict(row)
                for row in connection.execute(
                    """SELECT marker.job_id,marker.family_id,
                              marker.released_start_datetime,
                              marker.released_end_datetime,
                              marker.created_at,marker.archive_origin,
                              ff.family_key
                       FROM released_free_families marker
                       JOIN file_families ff ON ff.id=marker.family_id
                       WHERE marker.archive_origin=1"""
                ).fetchall()
            ]
            asset_rows = [
                dict(row)
                for row in connection.execute(
                    """SELECT asset.*,ff.family_key,
                              source.original_relative_path AS source_original_relative_path
                       FROM released_archive_assets asset
                       LEFT JOIN file_families ff ON ff.id=asset.family_id
                       LEFT JOIN files source ON source.id=asset.source_file_id
                       ORDER BY asset.job_id,asset.current_relative_path,asset.id"""
                ).fetchall()
            ]

        for row in marker_rows:
            family_key = str(row.get("family_key") or "")
            job_id = str(row.get("job_id") or "")
            if not family_key or not job_id:
                continue
            identity = (job_id, family_key)
            existing = central_release_markers.get(identity)
            if existing is not None:
                if (
                    str(existing.get("released_start_datetime") or "")
                    != str(row.get("released_start_datetime") or "")
                    or str(existing.get("released_end_datetime") or "")
                    != str(row.get("released_end_datetime") or "")
                ):
                    raise GlobalStockError(
                        "Widersprüchliche globale Archivfreigabe für "
                        + job_id + ":" + family_key
                    )
                continue
            central_release_markers[identity] = row

        for row in asset_rows:
            family_key = str(row.get("family_key") or "")
            job_id = str(row.get("job_id") or "")
            relative = str(row.get("current_relative_path") or "")
            if not family_key or not job_id or not relative:
                continue
            rel = Path(relative)
            if rel.is_absolute() or ".." in rel.parts:
                continue
            candidate = (central / rel).resolve(strict=False)
            try:
                candidate.relative_to(central)
            except ValueError:
                continue
            if not candidate.is_file():
                continue
            try:
                if int(candidate.stat().st_size) != int(row.get("size_bytes") or 0):
                    continue
            except OSError:
                continue
            identity = (job_id, family_key, rel.as_posix())
            existing = central_release_assets.get(identity)
            if existing is not None and (
                str(existing.get("sha256") or "") != str(row.get("sha256") or "")
                or str(existing.get("asset_kind") or "") != str(row.get("asset_kind") or "")
            ):
                raise GlobalStockError(
                    "Widersprüchliche globale freigewordene Zusatzdatei: "
                    + "/".join(identity)
                )
            central_release_assets[identity] = {
                **row,
                "current_relative_path": rel.as_posix(),
            }

    updated_by_database: dict[str, int] = {}
    total_updated = 0

    for database_path in unique_databases:
        updated = 0
        with database_connection(database_path) as connection:
            rows = [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT
                        f.id,
                        f.job_id,
                        f.original_relative_path,
                        f.current_relative_path,
                        EXISTS (
                            SELECT 1
                            FROM event_assignments ea
                            JOIN events assigned ON assigned.id=ea.event_id
                            JOIN events root
                              ON root.id=COALESCE(
                                  assigned.parent_event_id,
                                  assigned.id
                              )
                            WHERE root.status IN ('applied','archived')
                              AND (
                                  (ea.family_id IS NOT NULL
                                   AND ea.family_id=f.family_id)
                                  OR
                                  (ea.file_id IS NOT NULL
                                   AND ea.file_id=f.id)
                              )
                        ) AS locally_owned
                    FROM files f
                    ORDER BY f.id
                    """
                ).fetchall()
            ]

            for row in rows:
                identity = (
                    str(row["job_id"]),
                    str(row["original_relative_path"]),
                )
                central_row = central_paths.get(identity)
                if central_row is None or bool(row["locally_owned"]):
                    continue

                current = str(row.get("current_relative_path") or "")
                if (
                    current == "Später zuordnen"
                    or current.startswith("Später zuordnen/")
                ):
                    continue

                central_relative = str(
                    central_row["current_relative_path"]
                )
                if current == central_relative:
                    continue

                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,
                           current_root_kind='shared_workspace',
                           updated_at=datetime('now')
                       WHERE id=?""",
                    (central_relative, int(row["id"])),
                )
                updated += 1

            family_rows = connection.execute(
                "SELECT id,job_id,family_key FROM file_families"
            ).fetchall()
            family_map = {
                (str(row["job_id"]), str(row["family_key"])): int(row["id"])
                for row in family_rows
            }
            file_rows = connection.execute(
                "SELECT id,job_id,original_relative_path FROM files"
            ).fetchall()
            file_map = {
                (str(row["job_id"]), str(row["original_relative_path"])): int(row["id"])
                for row in file_rows
            }

            # Veraltete Archivfreigabe-Projektionen entfernen.
            for row in connection.execute(
                """SELECT marker.family_id,ff.job_id,ff.family_key
                   FROM released_free_families marker
                   JOIN file_families ff ON ff.id=marker.family_id
                   WHERE marker.archive_origin=1"""
            ).fetchall():
                identity = (str(row["job_id"]), str(row["family_key"]))
                if identity not in central_release_markers:
                    connection.execute(
                        "DELETE FROM released_free_families WHERE family_id=? AND archive_origin=1",
                        (int(row["family_id"]),),
                    )

            for row in connection.execute(
                """SELECT asset.id,asset.job_id,asset.current_relative_path,ff.family_key
                   FROM released_archive_assets asset
                   LEFT JOIN file_families ff ON ff.id=asset.family_id"""
            ).fetchall():
                identity = (
                    str(row["job_id"]),
                    str(row["family_key"] or ""),
                    str(row["current_relative_path"]),
                )
                if identity not in central_release_assets:
                    connection.execute(
                        "DELETE FROM released_archive_assets WHERE id=?",
                        (int(row["id"]),),
                    )

            # Globale Archivfreigabe-Marker auf lokale Familien-IDs abbilden.
            for identity, marker in central_release_markers.items():
                family_id = family_map.get(identity)
                if family_id is None:
                    continue
                connection.execute(
                    """INSERT OR REPLACE INTO released_free_families(
                           job_id,family_id,released_start_datetime,
                           released_end_datetime,created_at,archive_origin)
                       VALUES (?,?,?,?,?,1)""",
                    (
                        identity[0],
                        family_id,
                        marker.get("released_start_datetime"),
                        marker.get("released_end_datetime"),
                        str(marker.get("created_at") or ""),
                    ),
                )

            # Zusatzdateien ebenfalls über natürliche Identitäten projizieren.
            for identity, asset in central_release_assets.items():
                family_id = family_map.get((identity[0], identity[1]))
                if family_id is None:
                    continue
                source_original = str(asset.get("source_original_relative_path") or "")
                source_file_id = (
                    file_map.get((identity[0], source_original))
                    if source_original
                    else None
                )
                connection.execute(
                    """INSERT INTO released_archive_assets(
                           job_id,family_id,source_file_id,asset_kind,
                           current_relative_path,size_bytes,sha256,
                           origin_change_request_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(job_id,current_relative_path) DO UPDATE SET
                           family_id=excluded.family_id,
                           source_file_id=excluded.source_file_id,
                           asset_kind=excluded.asset_kind,
                           size_bytes=excluded.size_bytes,
                           sha256=excluded.sha256,
                           origin_change_request_id=excluded.origin_change_request_id,
                           updated_at=excluded.updated_at""",
                    (
                        identity[0],
                        family_id,
                        source_file_id,
                        str(asset.get("asset_kind") or "other"),
                        identity[2],
                        int(asset.get("size_bytes") or 0),
                        str(asset.get("sha256") or ""),
                        str(asset.get("origin_change_request_id") or ""),
                        str(asset.get("created_at") or ""),
                        str(asset.get("updated_at") or ""),
                    ),
                )

            connection.commit()

        updated_by_database[str(database_path)] = updated
        total_updated += updated

    return {
        "database_count": len(unique_databases),
        "central_file_count": len(central_paths),
        "central_release_family_count": len(central_release_markers),
        "central_release_asset_count": len(central_release_assets),
        "updated_file_count": total_updated,
        "updated_by_database": updated_by_database,
    }
