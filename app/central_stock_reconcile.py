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
from app.trash import reconcile_trash_inventory, serialized_trash_operation


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


def _pending_no_event_family_ids(connection: Any) -> set[int]:
    """Assignments added by a saved edit are SOLL until its physical apply.

    Only the original mutation snapshot establishes that the family was free.
    Existing event members remain subject to the usual misplaced-file check.
    """
    incoming: set[int] = set()
    mutations = connection.execute(
        """SELECT m.anchor_event_id,m.original_state_json FROM event_mutations m
           JOIN events e ON e.id=m.anchor_event_id
           WHERE m.status='pending_apply' AND m.mutation_kind='edit'
             AND e.status='applied' AND e.event_kind='no_event'
             AND e.resort_required=1"""
    ).fetchall()
    for mutation in mutations:
        state = json.loads(str(mutation['original_state_json']))
        old_events = state['events']
        old_assignments = state['event_assignments']
        anchor = str(mutation['anchor_event_id'])
        if not any(str(e['id']) == anchor and e['status'] == 'applied'
                   and not e.get('parent_event_id') for e in old_events):
            raise ValueError('pending_event_physical_snapshot_invalid: ' + anchor)
        old_families = {int(a['family_id']) for a in old_assignments if a.get('family_id') is not None}
        for assignment in old_assignments:
            if assignment.get('file_id') is not None:
                row = connection.execute('SELECT family_id FROM files WHERE id=?', (assignment['file_id'],)).fetchone()
                if row and row['family_id'] is not None:
                    old_families.add(int(row['family_id']))
        current = connection.execute(
            'SELECT family_id FROM event_assignments WHERE event_id=? AND family_id IS NOT NULL',
            (anchor,),
        ).fetchall()
        incoming.update(int(a['family_id']) for a in current if int(a['family_id']) not in old_families)
    return incoming


def _free_rows(
    connection: Any,
    excluded_family_ids: set[int],
) -> list[dict[str, Any]]:
    pending = _pending_no_event_family_ids(connection)
    pending_sql = ','.join('?' for _ in pending) or 'NULL'
    params: list[Any] = sorted(pending)
    excluded_sql = ""
    if excluded_family_ids:
        placeholders = ",".join("?" for _ in excluded_family_ids)
        excluded_sql = f" AND ff.id NOT IN ({placeholders})"
        params.extend(sorted(excluded_family_ids))

    rows = connection.execute(
        f"""SELECT f.id AS file_id,f.job_id,f.family_id,
                   f.current_relative_path,f.original_relative_path,
                   f.original_filename,f.size_bytes,f.sha256_original,
                   COALESCE(f.source_size_bytes,f.size_bytes) AS source_size_bytes,
                   COALESCE(f.sha256_current,f.sha256_original,'') AS sha256,
                   ff.family_key,ff.selected_capture_time
            FROM files f
            JOIN file_families ff ON ff.id=f.family_id
            JOIN jobs import_job ON import_job.id=f.job_id
            WHERE f.current_root_kind='shared_workspace'
              AND (import_job.operation!='folder_import' OR import_job.state='completed')
              AND COALESCE(TRIM(f.current_relative_path),'')<>''
              AND f.current_relative_path<>'Später zuordnen'
              AND f.current_relative_path NOT LIKE 'Später zuordnen/%'
              AND f.current_relative_path<>'Assign Later'
              AND f.current_relative_path NOT LIKE 'Assign Later/%'
              AND (ff.id IN ({pending_sql}) OR NOT EXISTS (
                  SELECT 1 FROM event_assignments ea
                  JOIN events assigned ON assigned.id=ea.event_id
                  JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                  WHERE ea.family_id=ff.id
                    AND root.status IN ('applied','archived')
              ))
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
        row["expected_relative_path"] = _expected_free_relative(connection, row)
        result.append(row)
    return result


def _ensure_root_identity(
    central_root: Path,
    rows: list[dict[str, Any]],
) -> tuple[bool, str]:
    # Identity belongs to F14's pinned directory/mount bindings. A content
    # sample or a writable sentinel is neither identity nor proof of a mount.
    # In particular, moving the last media file must not invalidate this root.
    if central_root.is_symlink() or not central_root.is_dir():
        return False, "Der zentrale Sicherungsbestand ist nicht erreichbar."
    validate_active_roots()
    if not os.access(central_root,os.R_OK|os.X_OK):
        return False, "Der zentrale Sicherungsbestand ist nicht lesbar."
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


def _pending_sort_inventory(connection, expected_count):
    # The durable run exists before any move, including crash recovery. Never
    # interpret a placement being changed by this application as external loss.
    runs = [str(row[0]) for row in connection.execute(
        "SELECT id FROM sort_runs WHERE status IN "
        "('queued','verifying','moving','finalizing','rolling_back','interrupted')"
    )]
    if not runs:
        return None
    return {'ready': True, 'postponed': True, 'pending_sort_run_ids': runs,
            'expected_file_count': expected_count, 'pending_missing_count': 0,
            'deleted_file_count': 0, 'misplaced_file_count': 0}


@serialized_trash_operation('workspace_root',qualify_restore=True)
@protect(workspace_arg='workspace_root', database_arg='database_path', kind='inventory', error_type=RuntimeError, durable=False)
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
        deferred = _pending_sort_inventory(connection, len(rows))
        if deferred is not None:
            return deferred

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

    from app.trash_restore import restore_reservations
    reserved_targets={path for record in restore_reservations(workspace_root) for path in record['target_paths']}
    if any(str(row['current_relative_path']) in reserved_targets for row in rows):
        return {'ready':False,'error':'Restore-Konflikt berührt diesen Bestand; Reconciliation gesperrt.','deleted_file_count':0}
    actual = [item for item in _actual_files(central_root) if item['relative_path'] not in reserved_targets]
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

    # Hashing is unbounded filesystem work. Never hold the SQLite writer while
    # doing it: even one slow NAS hash otherwise starves import progress/path
    # publication beyond busy_timeout. Revalidate both snapshots before commit.
    snapshot_rows = rows
    expected = {str(r['expected_relative_path']): r for r in rows}
    search_sizes = {int(r['size_bytes']) for r in rows
                    if str(r['expected_relative_path']) not in actual_by_relative}
    signatures = {}
    for item in actual:
        path = Path(item['path'])
        st = path.stat(follow_symlinks=False)
        signatures[str(path)] = (st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        r = expected.get(str(item['relative_path']))
        if r is None or int(r['size_bytes']) != int(item['size_bytes']) or int(item['size_bytes']) in search_sizes:
            hash_cache[str(path)] = _sha256_file(path)

    def digest_for(item):
        # A cache miss means the snapshot changed; never fall back to hashing
        # under the writer transaction.
        return hash_cache[str(item['path'])]

    with database_connection(database_path) as connection:
        # Recheck after filesystem enumeration. Holding the catalogue writer
        # lock prevents a new sort intent/status commit from racing this scan.
        connection.execute('BEGIN IMMEDIATE')
        deferred = _pending_sort_inventory(connection, len(rows))
        if deferred is not None:
            return deferred
        rows = _free_rows(connection, excluded)
        if rows != snapshot_rows:
            return {'ready':False,'error':'inventory_snapshot_changed','deleted_file_count':0,'pending_missing_count':0}
        current_files={str(i['relative_path']) for i in _actual_files(central_root) if i['relative_path'] not in reserved_targets}
        if current_files!=set(actual_by_relative):
            return {'ready':False,'error':'physical_snapshot_changed','deleted_file_count':0,'pending_missing_count':0}
        for item in actual:
            try:
                st = Path(item['path']).stat(follow_symlinks=False)
                current = (st.st_dev,st.st_ino,st.st_mode,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
            except OSError:
                current = None
            if current != signatures[str(item['path'])]:
                return {'ready':False,'error':'physical_snapshot_changed','deleted_file_count':0,'pending_missing_count':0}
        prior_rows = connection.execute(
            "SELECT file_id,consecutive_misses FROM central_missing_file_observations"
        ).fetchall()
        prior = {
            int(row["file_id"]): int(row["consecutive_misses"] or 0)
            for row in prior_rows
        }


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
                          f.original_filename,f.size_bytes,f.sha256_original,
                   COALESCE(f.source_size_bytes,f.size_bytes) AS source_size_bytes,
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
                            "original_relative_path": str(row.get("original_relative_path") or ""),
                            "sha256_original": str(row.get("sha256_original") or ""),
                            "source_size_bytes": int(row["source_size_bytes"]),
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
