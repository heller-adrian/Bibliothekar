from __future__ import annotations

from app.root_operations import protect, validate_active_roots



from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat

from app.database import database_connection
from app.external_changes import record_notice, resolve_notice_key
from app.free_stock_layout import (
    FreeStockLayoutError,
    canonical_free_directory,
    released_origin_directory,
)
from app.storage_config import storage_paths
from app.trash import reconcile_trash_inventory


SENTINEL_NAME = ".bibliothekar-central-stock-v1"
IGNORED_TOP_LEVEL = {".incoming"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    validate_active_roots()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: Any) -> Path | None:
    validate_active_roots()
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _expected_free_relative(
    connection: Any,
    row: dict[str, Any],
) -> str:
    validate_active_roots()
    current = str(row.get("current_relative_path") or "").replace("\\", "/").strip("/")
    filename = Path(
        current
        or str(row.get("original_filename") or "")
    ).name
    capture = str(row.get("selected_capture_time") or "").strip()
    family_id = row.get("family_id")

    # Ohne_Datum ist ein bewusst manueller Korrekturbereich. Eine bekannte
    # Aufnahme darf dorthin zurückgelegt werden, ohne dass Bibliothekar dies als
    # falschen Tagesordner interpretiert; die Metadatenkorrektur übernimmt von
    # dort wieder die kontrollierte Reintegration.
    if (
        current in ("Ohne_Datum", "No Date")
        or current.startswith(("Ohne_Datum/", "No Date/"))
    ):
        return current

    if not filename or not capture:
        return current

    try:
        directory = None
        if (
            current in ("Freigewordene Archivdateien", "Released Archive Files")
            or current.startswith(("Freigewordene Archivdateien/", "Released Archive Files/"))
        ) and family_id is not None:
            directory = released_origin_directory(
                connection,
                int(family_id),
                capture,
                physical=True,
                release_name=PurePosixPath(current).parts[0],
            )
        if directory is None:
            directory = canonical_free_directory(
                connection,
                capture,
                physical=True,
            )
        return (directory / filename).as_posix()
    except FreeStockLayoutError:
        return current


def _free_rows(
    connection: Any,
    excluded_family_ids: set[int],
) -> list[dict[str, Any]]:
    params: list[Any] = []
    excluded_sql = ""
    if excluded_family_ids:
        placeholders = ",".join("?" for _ in excluded_family_ids)
        excluded_sql = f" AND ff.id NOT IN ({placeholders})"
        params.extend(sorted(excluded_family_ids))

    rows = connection.execute(
        f"""SELECT f.id AS file_id,f.job_id,f.family_id,
                   f.current_relative_path,f.original_relative_path,
                   f.original_filename,f.size_bytes,
                   COALESCE(f.sha256_current,f.sha256_original,'') AS sha256,
                   ff.family_key,ff.selected_capture_time
            FROM files f
            JOIN file_families ff ON ff.id=f.family_id
            WHERE f.current_root_kind='shared_workspace'
              AND COALESCE(TRIM(f.current_relative_path),'')<>''
              AND f.current_relative_path<>'Später zuordnen'
              AND f.current_relative_path NOT LIKE 'Später zuordnen/%'
              AND f.current_relative_path<>'Assign Later'
              AND f.current_relative_path NOT LIKE 'Assign Later/%'
              AND NOT EXISTS (
                  SELECT 1 FROM event_assignments ea
                  JOIN events assigned ON assigned.id=ea.event_id
                  JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                  WHERE ea.family_id=ff.id
                    AND root.status IN ('applied','archived')
              )
              AND NOT EXISTS (
                  SELECT 1 FROM event_reapply_removed_families r
                  WHERE r.family_id=ff.id
                    AND r.target_event_id IS NULL
              )
              {excluded_sql}
            ORDER BY f.job_id,f.id""",
        tuple(params),
    ).fetchall()
    result: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        row["expected_relative_path"] = _expected_free_relative(
            connection,
            row,
        )
        result.append(row)
    return result


def _ensure_root_identity(
    central_root: Path,
    rows: list[dict[str, Any]],
) -> tuple[bool, str]:
    if not central_root.is_dir():
        return False, "Der zentrale Sicherungsbestand ist nicht erreichbar."
    sentinel = central_root / SENTINEL_NAME
    if sentinel.is_file():
        return True, ""
    if not rows:
        return True, ""

    found_known = False
    for row in rows[:256]:
        for value in (
            row.get("expected_relative_path"),
            row.get("current_relative_path"),
        ):
            relative = _safe_relative(value)
            if relative is not None and (central_root / relative).is_file():
                found_known = True
                break
        if found_known:
            break
    if not found_known:
        return (
            False,
            "Zentralbestand enthält bekannte SQLite-Dateien, aber keine davon ist "
            "physisch erreichbar. Reconciliation wurde sicherheitshalber ausgesetzt.",
        )

    sentinel.write_text("Bibliothekar central stock v1\n", encoding="utf-8")
    return True, ""


def _actual_files(central_root: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for dirpath, dirnames, filenames in os.walk(central_root):
        dirnames[:] = [
            name
            for name in dirnames
            if name not in IGNORED_TOP_LEVEL and not name.startswith(".")
        ]
        directory = Path(dirpath)
        for filename in filenames:
            if filename == SENTINEL_NAME or filename.startswith("."):
                continue
            path = directory / filename
            try:
                info = os.lstat(path)
            except FileNotFoundError:
                continue
            if not stat.S_ISREG(info.st_mode):
                continue
            result.append({
                "path": path,
                "relative_path": path.relative_to(central_root).as_posix(),
                "size_bytes": int(info.st_size),
            })
    return result


def _directory_group(relative_path: str) -> str:
    parts = PurePosixPath(str(relative_path)).parts
    if not parts:
        return ""
    if parts[0] in ("Freigewordene Archivdateien", "Released Archive Files"):
        take = min(3, max(1, len(parts) - 1))
        return PurePosixPath(*parts[:take]).as_posix()
    if parts[0] in ("Ohne_Datum", "No Date"):
        return parts[0]
    if len(parts) >= 3 and len(parts[0]) == 4 and parts[0].isdigit():
        return PurePosixPath(parts[0], parts[1]).as_posix()
    return (
        PurePosixPath(*parts[:-1]).as_posix()
        if len(parts) > 1
        else parts[0]
    )


def _inventory_matches(
    connection: Any,
    *,
    size_bytes: int,
    sha256: str,
    filename: str,
) -> list[dict[str, Any]]:
    if not sha256:
        return []
    rows = connection.execute(
        """SELECT inv.event_id,inv.job_id,inv.root_kind,inv.relative_path,
                  inv.filename,e.name AS event_name
           FROM event_inventory_files inv
           JOIN events e ON e.id=inv.event_id
           WHERE inv.size_bytes=?
             AND inv.sha256=?
             AND inv.filename=?
           ORDER BY inv.root_kind,inv.event_id,inv.relative_path""",
        (int(size_bytes), str(sha256), str(filename)),
    ).fetchall()
    return [dict(row) for row in rows]


def _record_placement_conflict(
    connection: Any,
    *,
    row: dict[str, Any],
    observed_root_kind: str,
    observed_relative_path: str,
    expected_root_kind: str,
    expected_relative_path: str,
    timestamp: str,
    title: str = "Datei falsch zugeordnet",
    detail: str | None = None,
    repairable: bool = True,
    force_repair: bool = False,
    adopt_observed: bool = True,
) -> None:
    file_id = int(row["file_id"])
    observed_kind = str(observed_root_kind)
    expected_kind = str(expected_root_kind)
    observed = str(observed_relative_path)
    expected = str(expected_relative_path)
    message = detail or (
        f"{row.get('original_filename') or Path(observed).name} liegt unter "
        f"„{observed}“, fachlich erwartet wird „{expected}“."
    )
    record_notice(
        connection,
        notice_key=f"placement:{file_id}",
        kind="placement_conflict",
        root_kind=observed_kind,
        title=title,
        detail=message,
        job_id=str(row.get("job_id") or ""),
        file_id=file_id,
        relative_path=observed,
        repairable=bool(repairable and observed_kind != "camera_archive"),
        action_required=True,
        group_key="placement_conflict",
        details={
            "expected_root_kind": expected_kind,
            "observed_root_kind": observed_kind,
            "expected_relative_path": expected,
            "observed_relative_path": observed,
            "size_bytes": int(row.get("size_bytes") or 0),
            "sha256": str(row.get("sha256") or ""),
            "family_id": row.get("family_id"),
            "force_repair": bool(force_repair),
        },
        now=timestamp,
    )
    # Im Normalfall folgt SQLite dem physischen IST. Für den bewusst
    # einseitigen Korrekturweg Ohne_Datum -> Tagesbestand bleibt dagegen das
    # logische SOLL unter Ohne_Datum stehen, bis die manuelle Bewegung
    # rückgängig gemacht wurde.
    if adopt_observed:
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,
                   current_root_kind=?,
                   updated_at=?
               WHERE id=?""",
            (
                observed,
                (
                    "shared_workspace"
                    if observed_kind == "central_stock"
                    else observed_kind
                ),
                timestamp,
                file_id,
            ),
        )


@protect(workspace_arg='workspace_root', database_arg='database_path', kind='inventory', error_type=RuntimeError)
def reconcile_central_free_stock(
    database_path: Path,
    workspace_root: Path,
    *,
    library_id: str,
    excluded_family_ids: set[int] | None = None,
) -> dict[str, Any]:
    timestamp = _now()
    trash_state = reconcile_trash_inventory(database_path, workspace_root)
    central_root = storage_paths(workspace_root)["backup_root"].resolve(strict=False)
    excluded = {int(value) for value in (excluded_family_ids or set())}

    with database_connection(database_path) as connection:
        rows = _free_rows(connection, excluded)

    ready, root_error = _ensure_root_identity(central_root, rows)
    if not ready:
        return {
            "ready": False,
            "error": root_error,
            "expected_file_count": len(rows),
            "pending_missing_count": 0,
            "deleted_file_count": 0,
            "misplaced_file_count": 0,
        }

    actual = _actual_files(central_root)
    actual_by_relative = {
        str(item["relative_path"]): item
        for item in actual
    }

    hash_cache: dict[str, str] = {}
    deleted_rows: list[dict[str, Any]] = []
    pending: list[int] = []
    misplaced = 0
    modified = 0
    matched_central_paths: set[str] = set()

    with database_connection(database_path) as connection:
        prior_rows = connection.execute(
            "SELECT file_id,consecutive_misses FROM central_missing_file_observations"
        ).fetchall()
        prior = {
            int(row["file_id"]): int(row["consecutive_misses"] or 0)
            for row in prior_rows
        }

        def digest_for(item: dict[str, Any]) -> str:
            key = str(item["path"])
            digest = hash_cache.get(key)
            if digest is None:
                digest = _sha256_file(Path(item["path"]))
                hash_cache[key] = digest
            return digest

        for row in rows:
            file_id = int(row["file_id"])
            job_id = str(row["job_id"])
            validate_active_roots()
            expected = str(
                row.get("expected_relative_path")
                or row.get("current_relative_path")
                or ""
            ).replace("\\", "/").strip("/")
            validate_active_roots()
            current = str(
                row.get("current_relative_path")
                or ""
            ).replace("\\", "/").strip("/")
            filename = Path(
                expected
                or current
                or str(row.get("original_filename") or "")
            ).name
            expected_size = int(row.get("size_bytes") or 0)
            expected_sha = str(row.get("sha256") or "")

            expected_item = actual_by_relative.get(expected)
            if expected_item is not None:
                matched_central_paths.add(expected)
                if int(expected_item["size_bytes"]) != expected_size:
                    # Eine externe Metadaten-/Dateiänderung im fachlich richtigen
                    # Ordner wird als neuer IST-Inhalt übernommen, nicht als
                    # Benutzeraufgabe.
                    new_sha = digest_for(expected_item)
                    connection.execute(
                        """UPDATE files
                           SET current_relative_path=?,
                               current_root_kind='shared_workspace',
                               size_bytes=?,sha256_current=?,updated_at=?
                           WHERE id=?""",
                        (
                            expected,
                            int(expected_item["size_bytes"]),
                            new_sha,
                            timestamp,
                            file_id,
                        ),
                    )
                    row["size_bytes"] = int(expected_item["size_bytes"])
                    row["sha256"] = new_sha
                    modified += 1
                elif current != expected:
                    connection.execute(
                        """UPDATE files
                           SET current_relative_path=?,
                               current_root_kind='shared_workspace',
                               updated_at=?
                           WHERE id=?""",
                        (expected, timestamp, file_id),
                    )

                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )
                resolve_notice_key(
                    connection,
                    f"placement:{file_id}",
                    now=timestamp,
                )
                continue

            central_matches: list[dict[str, Any]] = []
            if expected_sha:
                for candidate in actual:
                    if (
                        str(candidate["relative_path"]) in matched_central_paths
                        or int(candidate["size_bytes"]) != expected_size
                    ):
                        continue
                    if digest_for(candidate) == expected_sha:
                        central_matches.append(candidate)

            inventory_matches = _inventory_matches(
                connection,
                size_bytes=expected_size,
                sha256=expected_sha,
                filename=filename,
            )

            locations: list[dict[str, Any]] = [
                {
                    "root_kind": "central_stock",
                    "relative_path": str(item["relative_path"]),
                }
                for item in central_matches
            ] + [
                {
                    "root_kind": str(item["root_kind"]),
                    "relative_path": str(item["relative_path"]),
                    "event_id": str(item["event_id"]),
                    "event_name": str(item.get("event_name") or ""),
                }
                for item in inventory_matches
            ]

            unique_locations = {
                (
                    str(item["root_kind"]),
                    str(item["relative_path"]),
                ): item
                for item in locations
            }
            locations = list(unique_locations.values())

            if len(locations) == 1:
                location = locations[0]
                observed_kind = str(location["root_kind"])
                observed = str(location["relative_path"])
                if observed_kind == "central_stock":
                    matched_central_paths.add(observed)
                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )

                observed_is_undated = (
                    observed in ("Ohne_Datum", "No Date")
                    or observed.startswith(("Ohne_Datum/", "No Date/"))
                )
                current_is_undated = (
                    current in ("Ohne_Datum", "No Date")
                    or current.startswith(("Ohne_Datum/", "No Date/"))
                )
                canonical_dated = ""
                if current_is_undated and str(row.get("selected_capture_time") or ""):
                    try:
                        canonical_dated = (
                            canonical_free_directory(
                                connection,
                                str(row["selected_capture_time"]),
                                physical=True,
                            )
                            / filename
                        ).as_posix()
                    except FreeStockLayoutError:
                        canonical_dated = ""

                # Bewusster Metadaten-Korrekturweg:
                # Tagesbestand -> Ohne_Datum ist zulässig und wird sofort als
                # realer Korrekturbestand übernommen. Der umgekehrte manuelle
                # Weg ist absichtlich gesperrt: Aus Ohne_Datum wird nur über
                # Bibliothekars kontrollierte Metadaten-/Einsortierfunktion
                # wieder ein Tagesbestand.
                if (
                    observed_kind == "central_stock"
                    and observed_is_undated
                ):
                    connection.execute(
                        """UPDATE files
                           SET current_relative_path=?,
                               current_root_kind='shared_workspace',
                               updated_at=?
                           WHERE id=?""",
                        (observed, timestamp, file_id),
                    )
                    resolve_notice_key(
                        connection,
                        f"placement:{file_id}",
                        now=timestamp,
                    )
                    continue

                if (
                    observed_kind == "central_stock"
                    and current_is_undated
                    and not observed_is_undated
                ):
                    _record_placement_conflict(
                        connection,
                        row=row,
                        observed_root_kind=observed_kind,
                        observed_relative_path=observed,
                        expected_root_kind="central_stock",
                        expected_relative_path=expected,
                        timestamp=timestamp,
                        title="Ohne Datum muss über Bibliothekar einsortiert werden",
                        detail=(
                            f"{filename} wurde manuell aus „Ohne_Datum“ nach "
                            f"„{observed}“ verschoben. Bitte die Änderung "
                            "rückgängig machen und die Datei anschließend über "
                            "die Metadatenkorrektur einsortieren."
                        ),
                        repairable=True,
                        force_repair=True,
                        adopt_observed=False,
                    )
                    misplaced += 1
                    continue

                _record_placement_conflict(
                    connection,
                    row=row,
                    observed_root_kind=observed_kind,
                    observed_relative_path=observed,
                    expected_root_kind="central_stock",
                    expected_relative_path=expected,
                    timestamp=timestamp,
                    repairable=observed_kind != "camera_archive",
                    detail=(
                        f"{filename} befindet sich unter „{observed}“. "
                        f"Nach Aufnahmezeit und Zuordnung gehört die Datei nach "
                        f"„{expected}“."
                    ),
                )
                misplaced += 1
                continue

            if len(locations) > 1:
                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )
                first = locations[0]
                _record_placement_conflict(
                    connection,
                    row=row,
                    observed_root_kind=str(first["root_kind"]),
                    observed_relative_path=str(first["relative_path"]),
                    expected_root_kind="central_stock",
                    expected_relative_path=expected,
                    timestamp=timestamp,
                    repairable=False,
                    title="Dateiposition ist mehrdeutig",
                    detail=(
                        f"{filename} fehlt am fachlich erwarteten Ort; "
                        "mehrere byte-identische physische Kandidaten wurden gefunden."
                    ),
                )
                misplaced += 1
                continue

            count = prior.get(file_id, 0) + 1
            if file_id in prior:
                connection.execute(
                    """UPDATE central_missing_file_observations
                       SET consecutive_misses=?,last_missing_at=?
                       WHERE file_id=?""",
                    (count, timestamp, file_id),
                )
            else:
                connection.execute(
                    """INSERT INTO central_missing_file_observations(
                           file_id,job_id,consecutive_misses,first_missing_at,last_missing_at)
                       VALUES (?,?,1,?,?)""",
                    (file_id, job_id, timestamp, timestamp),
                )
            if count < 2:
                pending.append(file_id)
                continue
            deleted_rows.append({**row, "confirmed_after_scans": count})

        # Dateien, die aus einem Ereignis manuell in den zentralen Tagesbestand
        # verschoben wurden, gehören nicht zu den freien Sollzeilen oben. Nur
        # die wenigen physisch unbeanspruchten Zentraldateien werden deshalb
        # gegen bekannte Ereignisdateien geprüft.
        unmatched_actual = [
            item
            for item in actual
            if str(item["relative_path"]) not in matched_central_paths
        ]
        for item in unmatched_actual:
            digest = digest_for(item)
            known = connection.execute(
                """SELECT f.id AS file_id,f.job_id,f.family_id,
                          f.current_relative_path,f.current_root_kind,
                          f.original_filename,f.size_bytes,
                          COALESCE(f.sha256_current,f.sha256_original,'') AS sha256
                   FROM files f
                   WHERE f.size_bytes=?
                     AND COALESCE(f.sha256_current,f.sha256_original,'')=?
                     AND EXISTS (
                         SELECT 1 FROM event_assignments ea
                         JOIN events assigned ON assigned.id=ea.event_id
                         JOIN events root ON root.id=COALESCE(
                             assigned.parent_event_id,assigned.id
                         )
                         WHERE (
                             ea.file_id=f.id
                             OR (
                                 ea.file_id IS NULL
                                 AND ea.family_id=f.family_id
                             )
                         )
                           AND root.status IN ('applied','archived')
                     )
                   ORDER BY f.id""",
                (int(item["size_bytes"]), digest),
            ).fetchall()
            if len(known) != 1:
                continue
            known_row = dict(known[0])
            file_id = int(known_row["file_id"])
            observed = str(item["relative_path"])
            expected_kind = str(
                known_row.get("current_root_kind")
                or "shared_workspace"
            )
            archived_source = expected_kind == "camera_archive"
            _record_placement_conflict(
                connection,
                row=known_row,
                observed_root_kind="central_stock",
                observed_relative_path=observed,
                expected_root_kind=expected_kind,
                expected_relative_path=str(
                    known_row.get("current_relative_path") or ""
                ),
                timestamp=timestamp,
                repairable=not archived_source,
                detail=(
                    f"{known_row.get('original_filename') or Path(observed).name} "
                    + (
                        "wurde aus dem Archiv in den Tagesbestand verschoben. "
                        "Das Archiv ist schreibgeschützt; bitte die Datei manuell "
                        "an ihren fachlich passenden Archivort zurückverschieben."
                        if archived_source
                        else (
                            "wurde aus einem Ereignis in den Tagesbestand verschoben, "
                            "ohne dass die Ereigniszuordnung geändert wurde."
                        )
                    )
                ),
            )
            matched_central_paths.add(observed)
            misplaced += 1

        groups: dict[str, list[dict[str, Any]]] = {}
        expected_by_group: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            group = _directory_group(
                str(
                    row.get("expected_relative_path")
                    or row.get("current_relative_path")
                    or ""
                )
            )
            expected_by_group.setdefault(group, []).append(row)
        for row in deleted_rows:
            group = _directory_group(
                str(
                    row.get("expected_relative_path")
                    or row.get("current_relative_path")
                    or ""
                )
            )
            groups.setdefault(group, []).append(row)

        directory_notice_file_ids: set[int] = set()
        for group, removed in groups.items():
            expected_group = expected_by_group.get(group) or []
            group_path = central_root / group if group else central_root
            if (
                group
                and not group_path.exists()
                and len(removed) == len(expected_group)
            ):
                directory_notice_file_ids.update(
                    int(row["file_id"])
                    for row in removed
                )
                record_notice(
                    connection,
                    notice_key=(
                        f"central-directory-deleted:{library_id}:{group}:"
                        + timestamp[:19]
                    ),
                    kind="central_directory_deleted",
                    root_kind="central_stock",
                    title="Tages-/Zeitordner gelöscht",
                    detail=(
                        f"„{group}“ wurde außerhalb von Bibliothekar gelöscht. "
                        f"{len(removed)} Datei"
                        + ("" if len(removed) == 1 else "en")
                        + " wurden aus dem Bestand übernommen."
                    ),
                    job_id=str(removed[0]["job_id"]),
                    relative_path=group,
                    repairable=False,
                    action_required=False,
                    group_key="deletion_notice",
                    details={
                        "directory": group,
                        "deleted_file_count": len(removed),
                    },
                    now=timestamp,
                )

        for row in deleted_rows:
            file_id = int(row["file_id"])
            job_id = str(row["job_id"])
            family_id = (
                int(row["family_id"])
                if row.get("family_id") is not None
                else None
            )
            relative = str(
                row.get("current_relative_path")
                or row.get("expected_relative_path")
                or ""
            )
            connection.execute(
                """INSERT INTO audit_log(
                       job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'central_file_deletion_confirmed','file',?,?,?)""",
                (
                    job_id,
                    str(file_id),
                    json.dumps(
                        {
                            "library_id": library_id,
                            "family_id": family_id,
                            "family_key": str(row.get("family_key") or ""),
                            "last_relative_path": relative,
                            "sha256": str(row.get("sha256") or ""),
                            "confirmed_after_scans": int(
                                row["confirmed_after_scans"]
                            ),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
            # Einzeldateilöschungen sind ab 0.41.2 kein sichtbarer Hinweis.
            resolve_notice_key(
                connection,
                f"placement:{file_id}",
                now=timestamp,
            )
            connection.execute(
                "DELETE FROM files WHERE id=?",
                (file_id,),
            )
            if family_id is not None:
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM files WHERE family_id=?",
                    (family_id,),
                ).fetchone()[0]
                if int(remaining or 0) == 0:
                    connection.execute(
                        "DELETE FROM file_families WHERE id=?",
                        (family_id,),
                    )

    return {
        "ready": True,
        "expected_file_count": len(rows),
        "physical_file_count": len(actual),
        "pending_missing_count": len(pending),
        "deleted_file_count": len(deleted_rows),
        "misplaced_file_count": misplaced,
        "modified_file_count": modified,
        "trash_file_count": int(trash_state.get("file_count") or 0),
    }
