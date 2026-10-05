from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat

from app.database import database_connection
from app.external_changes import record_notice, resolve_notice_key
from app.storage_config import storage_paths


SENTINEL_NAME = ".bibliothekar-central-stock-v1"
IGNORED_TOP_LEVEL = {".incoming"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative(value: Any) -> Path | None:
    raw = str(value or "").replace("\\", "/").strip("/")
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        return None
    return path


def _free_rows(connection: Any, excluded_family_ids: set[int]) -> list[dict[str, Any]]:
    params: list[Any] = []
    excluded_sql = ""
    if excluded_family_ids:
        placeholders = ",".join("?" for _ in excluded_family_ids)
        excluded_sql = f" AND ff.id NOT IN ({placeholders})"
        params.extend(sorted(excluded_family_ids))

    rows = connection.execute(
        f"""SELECT f.id AS file_id,f.job_id,f.family_id,
                   f.current_relative_path,f.original_filename,
                   f.size_bytes,
                   COALESCE(f.sha256_current,f.sha256_original,'') AS sha256,
                   ff.family_key,ff.selected_capture_time
            FROM files f
            JOIN file_families ff ON ff.id=f.family_id
            WHERE f.current_root_kind='shared_workspace'
              AND COALESCE(TRIM(f.current_relative_path),'')<>''
              AND f.current_relative_path<>'Später zuordnen'
              AND f.current_relative_path NOT LIKE 'Später zuordnen/%'
              AND NOT EXISTS (
                  SELECT 1 FROM event_assignments ea
                  JOIN events assigned ON assigned.id=ea.event_id
                  JOIN events root ON root.id=COALESCE(assigned.parent_event_id,assigned.id)
                  WHERE ea.family_id=ff.id
                    AND root.status IN ('draft','planned','applied','archived')
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
    return [dict(row) for row in rows]


def _ensure_root_identity(central_root: Path, rows: list[dict[str, Any]]) -> tuple[bool, str]:
    if not central_root.is_dir():
        return False, "Der zentrale Sicherungsbestand ist nicht erreichbar."
    sentinel = central_root / SENTINEL_NAME
    if sentinel.is_file():
        return True, ""
    if not rows:
        return True, ""

    found_known = False
    for row in rows[:256]:
        relative = _safe_relative(row.get("current_relative_path"))
        if relative is None:
            continue
        if (central_root / relative).is_file():
            found_known = True
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
            name for name in dirnames
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
    if parts[0] == "Freigewordene Archivdateien":
        take = min(3, max(1, len(parts) - 1))
        return PurePosixPath(*parts[:take]).as_posix()
    if parts[0] == "Ohne_Datum":
        return "Ohne_Datum"
    if len(parts) >= 3 and len(parts[0]) == 4 and parts[0].isdigit():
        return PurePosixPath(parts[0], parts[1]).as_posix()
    return PurePosixPath(*parts[:-1]).as_posix() if len(parts) > 1 else parts[0]


def reconcile_central_free_stock(
    database_path: Path,
    workspace_root: Path,
    *,
    library_id: str,
    excluded_family_ids: set[int] | None = None,
) -> dict[str, Any]:
    timestamp = _now()
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
    if not rows:
        return {
            "ready": True,
            "expected_file_count": 0,
            "pending_missing_count": 0,
            "deleted_file_count": 0,
            "misplaced_file_count": 0,
        }

    actual = _actual_files(central_root)
    actual_by_relative = {str(item["relative_path"]): item for item in actual}
    expected_paths = {
        str(row.get("current_relative_path") or "").replace("\\", "/").strip("/")
        for row in rows
    }
    untracked_by_size: dict[int, list[dict[str, Any]]] = {}
    for item in actual:
        if str(item["relative_path"]) in expected_paths:
            continue
        untracked_by_size.setdefault(int(item["size_bytes"]), []).append(item)
    hash_cache: dict[str, str] = {}

    deleted_rows: list[dict[str, Any]] = []
    pending: list[int] = []
    misplaced = 0
    modified = 0

    with database_connection(database_path) as connection:
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
            relative = str(row.get("current_relative_path") or "").replace("\\", "/").strip("/")
            expected_size = int(row.get("size_bytes") or 0)
            expected_sha = str(row.get("sha256") or "")
            actual_item = actual_by_relative.get(relative)

            if actual_item is not None:
                if int(actual_item["size_bytes"]) != expected_size:
                    connection.execute(
                        "DELETE FROM central_missing_file_observations WHERE file_id=?",
                        (file_id,),
                    )
                    record_notice(
                        connection,
                        notice_key=f"central-modified:{job_id}:{file_id}",
                        kind="central_file_modified",
                        root_kind="central_stock",
                        title="Datei im Tagesbestand verändert",
                        detail=f"{relative} besitzt nicht mehr die erwartete Dateigröße.",
                        job_id=job_id,
                        file_id=file_id,
                        relative_path=relative,
                        repairable=False,
                        details={
                            "expected_relative_path": relative,
                            "expected_size_bytes": expected_size,
                            "actual_size_bytes": int(actual_item["size_bytes"]),
                        },
                        now=timestamp,
                    )
                    modified += 1
                    continue
                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )
                resolve_notice_key(connection, f"central-misplaced:{job_id}:{file_id}", now=timestamp)
                resolve_notice_key(connection, f"central-modified:{job_id}:{file_id}", now=timestamp)
                resolve_notice_key(connection, f"central-ambiguous:{job_id}:{file_id}", now=timestamp)
                continue

            matches: list[dict[str, Any]] = []
            if expected_sha:
                for candidate in untracked_by_size.get(expected_size, []):
                    key = str(candidate["path"])
                    digest = hash_cache.get(key)
                    if digest is None:
                        digest = _sha256_file(Path(candidate["path"]))
                        hash_cache[key] = digest
                    if digest == expected_sha:
                        matches.append(candidate)

            if len(matches) == 1:
                observed = str(matches[0]["relative_path"])
                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )
                record_notice(
                    connection,
                    notice_key=f"central-misplaced:{job_id}:{file_id}",
                    kind="central_file_misplaced",
                    root_kind="central_stock",
                    title="Datei außerhalb ihres Tagesordners",
                    detail=f"{Path(relative).name} liegt unter „{observed}“ statt unter „{relative}“.",
                    job_id=job_id,
                    file_id=file_id,
                    relative_path=observed,
                    repairable=True,
                    details={
                        "expected_relative_path": relative,
                        "observed_relative_path": observed,
                        "size_bytes": expected_size,
                        "sha256": expected_sha,
                    },
                    now=timestamp,
                )
                misplaced += 1
                continue

            if len(matches) > 1:
                connection.execute(
                    "DELETE FROM central_missing_file_observations WHERE file_id=?",
                    (file_id,),
                )
                record_notice(
                    connection,
                    notice_key=f"central-ambiguous:{job_id}:{file_id}",
                    kind="central_file_ambiguous",
                    root_kind="central_stock",
                    title="Dateiposition ist mehrdeutig",
                    detail=f"{Path(relative).name} fehlt am erwarteten Ort; mehrere byte-identische Kandidaten wurden gefunden.",
                    job_id=job_id,
                    file_id=file_id,
                    relative_path=relative,
                    repairable=False,
                    details={
                        "expected_relative_path": relative,
                        "candidate_paths": [str(item["relative_path"]) for item in matches],
                        "size_bytes": expected_size,
                        "sha256": expected_sha,
                    },
                    now=timestamp,
                )
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

        groups: dict[str, list[dict[str, Any]]] = {}
        expected_by_group: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            expected_by_group.setdefault(
                _directory_group(str(row.get("current_relative_path") or "")),
                [],
            ).append(row)
        for row in deleted_rows:
            groups.setdefault(
                _directory_group(str(row.get("current_relative_path") or "")),
                [],
            ).append(row)

        directory_notice_file_ids: set[int] = set()
        for group, removed in groups.items():
            expected_group = expected_by_group.get(group) or []
            group_path = central_root / group if group else central_root
            if group and not group_path.exists() and len(removed) == len(expected_group) and len(removed) >= 2:
                directory_notice_file_ids.update(int(row["file_id"]) for row in removed)
                record_notice(
                    connection,
                    notice_key=f"central-directory-deleted:{library_id}:{group}",
                    kind="central_directory_deleted",
                    root_kind="central_stock",
                    title="Tages-/Zeitordner extern gelöscht",
                    detail=f"„{group}“ wurde außerhalb von Bibliothekar gelöscht · {len(removed)} Dateien.",
                    job_id=str(removed[0]["job_id"]),
                    relative_path=group,
                    repairable=False,
                    details={
                        "directory": group,
                        "deleted_file_count": len(removed),
                        "deleted_files": [str(row.get("current_relative_path") or "") for row in removed],
                    },
                    now=timestamp,
                )

        for row in deleted_rows:
            file_id = int(row["file_id"])
            job_id = str(row["job_id"])
            family_id = int(row["family_id"]) if row.get("family_id") is not None else None
            relative = str(row.get("current_relative_path") or "")
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
                            "confirmed_after_scans": int(row["confirmed_after_scans"]),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    timestamp,
                ),
            )
            if file_id not in directory_notice_file_ids:
                record_notice(
                    connection,
                    notice_key=f"central-file-deleted:{job_id}:{file_id}",
                    kind="central_file_deleted",
                    root_kind="central_stock",
                    title="Datei extern gelöscht",
                    detail=f"„{relative}“ wurde außerhalb von Bibliothekar gelöscht.",
                    job_id=job_id,
                    file_id=file_id,
                    relative_path=relative,
                    repairable=False,
                    details={
                        "deleted_relative_path": relative,
                        "size_bytes": int(row.get("size_bytes") or 0),
                        "sha256": str(row.get("sha256") or ""),
                    },
                    now=timestamp,
                )
            connection.execute("DELETE FROM files WHERE id=?", (file_id,))
            if family_id is not None:
                remaining = connection.execute(
                    "SELECT COUNT(*) FROM files WHERE family_id=?",
                    (family_id,),
                ).fetchone()[0]
                if int(remaining or 0) == 0:
                    connection.execute("DELETE FROM file_families WHERE id=?", (family_id,))

    return {
        "ready": True,
        "expected_file_count": len(rows),
        "physical_file_count": len(actual),
        "pending_missing_count": len(pending),
        "deleted_file_count": len(deleted_rows),
        "misplaced_file_count": misplaced,
        "modified_file_count": modified,
    }
