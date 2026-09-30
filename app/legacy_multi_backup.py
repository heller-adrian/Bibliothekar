"""Safe 0.28 normalization for legacy multi-backup follow-up events.

Only purely database-planned planned_extension rows are folded automatically.
Any hint that physical work may already have happened leaves the legacy event
untouched for an explicit maintenance reconcile.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import hashlib
import json
import os
import stat

from app.database import database_connection
from app.event_access import event_file_rows, register_source_jobs, sync_event_source_jobs
from app.workspace_layout import shared_work_root


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root_children(connection: Any, event_id: str) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            """SELECT * FROM events
               WHERE parent_event_id=?
               ORDER BY start_datetime,id""",
            (event_id,),
        ).fetchall()
    ]


def _event_tree_ids(connection: Any, event_id: str) -> list[str]:
    return [
        str(row["id"])
        for row in connection.execute(
            """WITH RECURSIVE tree(id) AS (
                   SELECT id FROM events WHERE id=?
                   UNION ALL
                   SELECT e.id FROM events e JOIN tree t ON e.parent_event_id=t.id
               )
               SELECT id FROM tree""",
            (event_id,),
        ).fetchall()
    ]


def _has_physical_evidence(connection: Any, legacy: dict[str, Any]) -> bool:
    legacy_id = str(legacy["id"])
    if connection.execute(
        "SELECT 1 FROM sort_runs WHERE event_id=? LIMIT 1",
        (legacy_id,),
    ).fetchone():
        return True
    if connection.execute(
        """SELECT 1 FROM event_mutations
           WHERE anchor_event_id=? OR instr(affected_event_ids_json,?)>0
           LIMIT 1""",
        (legacy_id, legacy_id),
    ).fetchone():
        return True
    if connection.execute(
        "SELECT 1 FROM event_change_requests WHERE event_id=? LIMIT 1",
        (legacy_id,),
    ).fetchone():
        return True

    tree_ids = _event_tree_ids(connection, legacy_id)
    if not tree_ids:
        return False
    ph = ",".join("?" for _ in tree_ids)
    if connection.execute(
        f"""SELECT 1 FROM event_assignments
            WHERE event_id IN ({ph}) AND file_id IS NOT NULL LIMIT 1""",
        tuple(tree_ids),
    ).fetchone():
        return True

    family_ids = [
        int(row["family_id"])
        for row in connection.execute(
            f"""SELECT DISTINCT family_id FROM event_assignments
                WHERE event_id IN ({ph}) AND family_id IS NOT NULL""",
            tuple(tree_ids),
        ).fetchall()
    ]
    if not family_ids:
        return False
    fp = ",".join("?" for _ in family_ids)
    return connection.execute(
        f"""SELECT 1 FROM files
            WHERE family_id IN ({fp})
              AND current_root_kind='shared_workspace'
              AND (
                    current_relative_path LIKE '%/Ergänzungen/%'
                 OR current_relative_path LIKE 'Ergänzungen/%'
                 OR current_relative_path LIKE '%/Nachträge/%'
                 OR current_relative_path LIKE 'Nachträge/%'
              )
            LIMIT 1""",
        tuple(family_ids),
    ).fetchone() is not None


def _merge_no_event_segments(
    connection: Any,
    target_id: str,
    legacy_id: str,
    anchor_job_id: str,
    now: str,
) -> None:
    rows = connection.execute(
        """SELECT day_key,start_datetime,end_datetime
           FROM event_time_segments
           WHERE event_id IN (?,?)
           ORDER BY day_key,start_datetime,id""",
        (target_id, legacy_id),
    ).fetchall()
    by_day: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        by_day.setdefault(str(row["day_key"]), []).append(
            (str(row["start_datetime"])[:19], str(row["end_datetime"])[:19])
        )

    merged: list[tuple[str, str, str]] = []
    for day, intervals in sorted(by_day.items()):
        current: list[list[str]] = []
        for start, end in sorted(set(intervals)):
            if current and start <= current[-1][1]:
                current[-1][1] = max(current[-1][1], end)
            else:
                current.append([start, end])
        merged.extend((day, start, end) for start, end in current)

    connection.execute(
        "DELETE FROM event_time_segments WHERE event_id=?",
        (target_id,),
    )
    connection.executemany(
        """INSERT INTO event_time_segments(
               event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,
               source,created_at,updated_at
           ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [
            (
                target_id, anchor_job_id, day, start[11:16], end[11:16],
                start, end, "migration", now, now,
            )
            for day, start, end in merged
        ],
    )
    if merged:
        connection.execute(
            """UPDATE events
               SET start_datetime=?,end_datetime=?,timeline_model='segments',
                   updated_at=?
               WHERE id=?""",
            (
                min(start for _day, start, _end in merged),
                max(end for _day, _start, end in merged),
                now,
                target_id,
            ),
        )


def _assignment_target(
    target_id: str,
    target_children: list[dict[str, Any]],
    capture: str,
) -> str:
    for child in target_children:
        if (
            str(child["start_datetime"])[:19]
            <= capture
            <= str(child["end_datetime"])[:19]
        ):
            return str(child["id"])
    return target_id


def _normalize_one(
    connection: Any,
    legacy: dict[str, Any],
    now: str,
) -> dict[str, Any] | None:
    legacy_id = str(legacy["id"])
    target_id = str(legacy.get("linked_event_id") or "")
    if not target_id:
        return None
    target_row = connection.execute(
        """SELECT * FROM events
           WHERE id=? AND parent_event_id IS NULL
             AND COALESCE(TRIM(linkage_kind),'')=''""",
        (target_id,),
    ).fetchone()
    if target_row is None:
        return None
    target = dict(target_row)

    if str(legacy.get("status") or "") not in {"draft", "planned"}:
        return None
    if legacy.get("applied_at") is not None or legacy.get("archived_at") is not None:
        return None
    if str(target.get("status") or "") not in {"draft", "planned"}:
        return None
    if target.get("applied_at") is not None or target.get("archived_at") is not None:
        return None
    if str(legacy.get("event_kind") or "event") != str(target.get("event_kind") or "event"):
        return None
    if _has_physical_evidence(connection, legacy):
        return None

    tree_ids = _event_tree_ids(connection, legacy_id)
    ph = ",".join("?" for _ in tree_ids)
    assignments = connection.execute(
        f"""SELECT DISTINCT ea.family_id,ff.selected_capture_time,ff.job_id
            FROM event_assignments ea
            JOIN file_families ff ON ff.id=ea.family_id
            WHERE ea.event_id IN ({ph}) AND ea.family_id IS NOT NULL
            ORDER BY ff.selected_capture_time,ea.family_id""",
        tuple(tree_ids),
    ).fetchall()

    target_children = _root_children(connection, target_id)
    moved_family_ids: list[int] = []
    source_jobs: set[str] = {str(target["job_id"])}

    for row in assignments:
        family_id = int(row["family_id"])
        capture = str(row["selected_capture_time"] or "")[:19]
        if not capture:
            return None
        assigned_target = _assignment_target(target_id, target_children, capture)
        already = connection.execute(
            """SELECT 1 FROM event_assignments ea
               JOIN events e ON e.id=ea.event_id
               WHERE ea.family_id=?
                 AND COALESCE(e.parent_event_id,e.id)=?
               LIMIT 1""",
            (family_id, target_id),
        ).fetchone()
        connection.execute(
            f"""DELETE FROM event_assignments
                WHERE family_id=? AND event_id IN ({ph})""",
            (family_id, *tree_ids),
        )
        if already is None:
            connection.execute(
                """INSERT INTO event_assignments(
                       event_id,family_id,file_id,assignment_source,created_at
                   ) VALUES (?,?,NULL,'manual',?)""",
                (assigned_target, family_id, now),
            )
        moved_family_ids.append(family_id)
        source_jobs.add(str(row["job_id"]))

    if str(target.get("event_kind") or "event") == "no_event":
        _merge_no_event_segments(
            connection, target_id, legacy_id, str(target["job_id"]), now
        )

    connection.execute(
        "UPDATE events SET revision=revision+1,updated_at=? WHERE id=?",
        (now, target_id),
    )
    sync_event_source_jobs(connection, target_id, created_at=now)
    register_source_jobs(
        connection, target_id, sorted(source_jobs), created_at=now
    )
    connection.execute(
        """INSERT INTO audit_log(
               job_id,action,entity_type,entity_id,details_json,created_at
           ) VALUES (?,'legacy_planned_extension_merged','event',?,?,?)""",
        (
            str(target["job_id"]),
            target_id,
            json.dumps(
                {
                    "legacy_event_id": legacy_id,
                    "legacy_job_id": str(legacy["job_id"]),
                    "family_ids": sorted(moved_family_ids),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            now,
        ),
    )
    connection.execute("DELETE FROM events WHERE id=?", (legacy_id,))
    return {
        "legacy_event_id": legacy_id,
        "target_event_id": target_id,
        "family_ids": sorted(moved_family_ids),
    }


def normalize_unapplied_legacy_extensions(database_path) -> dict[str, Any]:
    """Fold only provably DB-only planned_extension rows into canonical events."""
    now = _now()
    merged: list[dict[str, Any]] = []
    skipped: list[str] = []
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT * FROM events
                   WHERE parent_event_id IS NULL
                     AND linkage_kind='planned_extension'
                   ORDER BY created_at,id"""
            ).fetchall()
        ]
        for legacy in rows:
            connection.execute("SAVEPOINT legacy_merge")
            try:
                result = _normalize_one(connection, legacy, now)
                if result is None:
                    skipped.append(str(legacy["id"]))
                    connection.execute("ROLLBACK TO legacy_merge")
                else:
                    merged.append(result)
                connection.execute("RELEASE legacy_merge")
            except Exception:
                connection.execute("ROLLBACK TO legacy_merge")
                connection.execute("RELEASE legacy_merge")
                skipped.append(str(legacy["id"]))
        connection.commit()
    return {
        "merged": merged,
        "skipped": skipped,
        "merged_count": len(merged),
    }


class LegacyMultiBackupError(ValueError):
    pass


LEGACY_CONFIRMATION_PHRASE = "LEGACY VEREINHEITLICHEN"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _legacy_case(connection: Any, legacy_event_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    legacy_row = connection.execute(
        """SELECT * FROM events
           WHERE id=? AND parent_event_id IS NULL
             AND linkage_kind IN ('planned_extension','applied_followup')""",
        (legacy_event_id,),
    ).fetchone()
    if legacy_row is None:
        raise LegacyMultiBackupError("Legacy-Mehrsicherungsereignis wurde nicht gefunden.")
    legacy = dict(legacy_row)
    target_id = str(legacy.get("linked_event_id") or "")
    target_row = connection.execute(
        """SELECT * FROM events
           WHERE id=? AND parent_event_id IS NULL
             AND COALESCE(TRIM(linkage_kind),'')=''""",
        (target_id,),
    ).fetchone()
    if target_row is None:
        raise LegacyMultiBackupError("Das kanonische Zielereignis des Legacy-Nachtrags fehlt.")
    return legacy, dict(target_row)


def _legacy_source_relative(legacy: dict[str, Any], target: dict[str, Any]) -> PurePosixPath:
    year = str(target.get("start_datetime") or legacy.get("start_datetime") or "")[:4]
    if len(year) != 4 or not year.isdigit():
        raise LegacyMultiBackupError("Das Jahr des Legacy-Ereignisses ist ungültig.")
    folder = str(legacy.get("folder_name") or target.get("folder_name") or "").strip()
    if not folder:
        raise LegacyMultiBackupError("Der Legacy-Ereignisordner fehlt.")
    linkage = str(legacy.get("linkage_kind") or "")
    if linkage == "planned_extension" and str(legacy.get("event_kind") or "") == "no_event":
        return PurePosixPath(year, str(target["folder_name"]))
    if linkage == "planned_extension":
        branch = "Ergänzungen"
    elif linkage == "applied_followup":
        branch = "Nachträge"
    else:
        raise LegacyMultiBackupError("Dieser Legacy-Typ kann nicht im SSD-Arbeitsbereich vereinheitlicht werden.")
    token = str(legacy["job_id"])[-12:]
    return PurePosixPath(year, branch, f"{folder} - {token}")


def _target_relative(target: dict[str, Any]) -> PurePosixPath:
    year = str(target.get("start_datetime") or "")[:4]
    folder = str(target.get("folder_name") or "").strip()
    if len(year) != 4 or not year.isdigit() or not folder:
        raise LegacyMultiBackupError("Das kanonische Ziel besitzt keinen gültigen Ereignispfad.")
    return PurePosixPath(year, folder)


def _path_is_below(path: PurePosixPath, root: PurePosixPath) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _scan_legacy_assets(
    source_root: Path,
    known_sources: set[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    assets: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if not source_root.exists():
        return assets, blockers
    if not source_root.is_dir() or source_root.is_symlink():
        return assets, [{"code": "legacy_source_not_directory", "message": str(source_root)}]

    for current, directories, files in os.walk(source_root, topdown=True, followlinks=False):
        current_path = Path(current)
        safe_directories: list[str] = []
        for name in directories:
            child = current_path / name
            info = os.lstat(child)
            if stat.S_ISLNK(info.st_mode):
                blockers.append({
                    "code": "legacy_symlink_directory",
                    "message": str(child.relative_to(source_root)),
                })
                continue
            if not stat.S_ISDIR(info.st_mode):
                blockers.append({
                    "code": "legacy_unexpected_directory_entry",
                    "message": str(child.relative_to(source_root)),
                })
                continue
            safe_directories.append(name)
        directories[:] = safe_directories

        for name in files:
            path = current_path / name
            if path in known_sources:
                continue
            if name == "event.json" or name == ".DS_Store" or name.startswith("._"):
                continue
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
                blockers.append({
                    "code": "legacy_unexpected_file_entry",
                    "message": str(path.relative_to(source_root)),
                })
                continue
            assets.append({
                "source_absolute_path": str(path),
                "source_tail": path.relative_to(source_root).as_posix(),
                "expected_size_bytes": int(info.st_size),
                "stored_sha256": _sha256_file(path),
            })
    return assets, blockers


def build_legacy_reconcile_plan(
    database_path,
    workspace_path: Path,
    legacy_event_id: str,
) -> dict[str, Any]:
    """Read-only, fully hashed plan for one physical legacy follow-up."""
    work_root = shared_work_root(workspace_path)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    with database_connection(database_path) as connection:
        legacy, target = _legacy_case(connection, legacy_event_id)
        if str(target.get("status") or "") == "archived" or target.get("archived_at") is not None:
            blockers.append({
                "code": "legacy_target_archived",
                "message": (
                    "Das kanonische Ereignis ist bereits archiviert. Bibliothekar "
                    "schreibt nicht in die Kamerabibliothek; diese Legacy-Struktur "
                    "muss über den manuellen Archivänderungsweg vereinheitlicht werden."
                ),
            })
        elif str(target.get("status") or "") != "applied" or target.get("applied_at") is None:
            blockers.append({
                "code": "legacy_target_not_applied",
                "message": "Das kanonische Ziel muss zuerst vollständig angewendet werden.",
            })
        if int(target.get("resort_required") or 0):
            blockers.append({
                "code": "target_resort_required",
                "message": "Für das kanonische Ziel ist bereits eine Nachsortierung offen.",
            })
        for event_id in (legacy_event_id, str(target["id"])):
            if connection.execute(
                """SELECT 1 FROM sort_runs
                   WHERE event_id=? AND status IN (
                     'queued','verifying','moving','finalizing','rolling_back','interrupted'
                   ) LIMIT 1""",
                (event_id,),
            ).fetchone():
                blockers.append({
                    "code": "active_sort_run",
                    "message": f"Für {event_id} existiert ein aktiver oder unterbrochener Sortierlauf.",
                })
            if connection.execute(
                """SELECT 1 FROM event_structure_changes
                   WHERE event_id=? AND status IN ('pending','prepared','verified','blocked')
                   LIMIT 1""",
                (event_id,),
            ).fetchone():
                blockers.append({
                    "code": "open_structure_change",
                    "message": f"Für {event_id} ist eine manuelle Strukturänderung offen.",
                })

        direct = connection.execute(
            """WITH RECURSIVE tree(id) AS (
                   SELECT id FROM events WHERE id=?
                   UNION ALL
                   SELECT e.id FROM events e JOIN tree t ON e.parent_event_id=t.id
               )
               SELECT 1 FROM event_assignments
               WHERE event_id IN (SELECT id FROM tree)
                 AND file_id IS NOT NULL
               LIMIT 1""",
            (legacy_event_id,),
        ).fetchone()
        if direct is not None:
            blockers.append({
                "code": "legacy_direct_file_assignment",
                "message": "Der Legacy-Nachtrag enthält direkte Dateizuordnungen und kann nicht automatisch vereinheitlicht werden.",
            })

        known_rows = event_file_rows(connection, legacy_event_id)
        source_rel = _legacy_source_relative(legacy, target)
        target_rel = _target_relative(target)
        source_root = work_root.joinpath(*source_rel.parts)
        target_root = work_root.joinpath(*target_rel.parts)

        file_operations: list[dict[str, Any]] = []
        known_source_paths: set[Path] = set()
        for row in known_rows:
            current = PurePosixPath(str(row.get("current_relative_path") or "").replace("\\", "/").strip("/"))
            source_path = work_root.joinpath(*current.parts)
            known_source_paths.add(source_path)
            if _path_is_below(current, target_rel):
                tail = current.relative_to(target_rel)
                destination = current
                status = "already_at_target"
            elif _path_is_below(current, source_rel):
                tail = current.relative_to(source_rel)
                destination = target_rel / tail
                status = "move"
            else:
                blockers.append({
                    "code": "known_file_outside_legacy_root",
                    "file_id": int(row["id"]),
                    "message": str(current),
                })
                continue

            expected_size = int(row.get("size_bytes") or 0)
            expected_sha = str(row.get("sha256_current") or row.get("sha256_original") or "")
            if not source_path.is_file() or source_path.is_symlink():
                blockers.append({
                    "code": "legacy_source_missing",
                    "file_id": int(row["id"]),
                    "message": str(current),
                })
                actual_sha = ""
                actual_size = None
            else:
                actual_size = int(source_path.stat().st_size)
                actual_sha = _sha256_file(source_path)
                if actual_size != expected_size:
                    blockers.append({
                        "code": "legacy_source_size_mismatch",
                        "file_id": int(row["id"]),
                        "message": str(current),
                    })
                if not expected_sha or actual_sha != expected_sha:
                    blockers.append({
                        "code": "legacy_source_sha_mismatch",
                        "file_id": int(row["id"]),
                        "message": str(current),
                    })
            destination_path = work_root.joinpath(*destination.parts)
            if status == "move" and destination_path.exists():
                blockers.append({
                    "code": "legacy_target_exists",
                    "file_id": int(row["id"]),
                    "message": destination.as_posix(),
                })
            file_operations.append({
                "file_id": int(row["id"]),
                "family_id": row.get("family_id"),
                "source_relative_path": current.as_posix(),
                "destination_relative_path": destination.as_posix(),
                "source_absolute_path": str(source_path),
                "destination_absolute_path": str(destination_path),
                "expected_size_bytes": expected_size,
                "stored_sha256": expected_sha,
                "actual_sha256": actual_sha,
                "status": status,
            })

        asset_operations, asset_blockers = _scan_legacy_assets(
            source_root, known_source_paths
        )
        blockers.extend(asset_blockers)
        for asset in asset_operations:
            tail = PurePosixPath(asset.pop("source_tail"))
            destination = target_rel / tail
            destination_path = work_root.joinpath(*destination.parts)
            if destination_path.exists():
                blockers.append({
                    "code": "legacy_asset_target_exists",
                    "message": destination.as_posix(),
                })
            asset.update({
                "destination_relative_path": destination.as_posix(),
                "destination_absolute_path": str(destination_path),
                "source_relative_path": PurePosixPath(
                    Path(asset["source_absolute_path"]).relative_to(work_root).as_posix()
                ).as_posix(),
                "status": "move",
            })

        payload = {
            "legacy_event_id": legacy_event_id,
            "target_event_id": str(target["id"]),
            "legacy_revision": int(legacy.get("revision") or 1),
            "target_revision": int(target.get("revision") or 1),
            "files": [
                [
                    item["file_id"],
                    item["source_relative_path"],
                    item["destination_relative_path"],
                    item["stored_sha256"],
                ]
                for item in file_operations
            ],
            "assets": [
                [
                    item["source_relative_path"],
                    item["destination_relative_path"],
                    item["stored_sha256"],
                ]
                for item in asset_operations
            ],
        }
        plan_token = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    if source_root == target_root:
        warnings.append({
            "code": "legacy_shared_root",
            "message": "Legacy- und Zielbestand liegen bereits im selben Ereignisordner; es werden nur SQLite-Zuordnungen vereinheitlicht.",
        })

    return {
        "mode": "legacy_multi_backup_reconcile",
        "legacy_event": legacy,
        "target_event": target,
        "legacy_event_id": legacy_event_id,
        "target_event_id": str(target["id"]),
        "source_root": str(source_root),
        "target_root": str(target_root),
        "plan_token": plan_token,
        "apply_confirmation_phrase": LEGACY_CONFIRMATION_PHRASE,
        "files": file_operations,
        "assets": asset_operations,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "ready": not blockers,
            "file_count": len(file_operations) + len(asset_operations),
            "camera_file_count": len(file_operations),
            "asset_count": len(asset_operations),
            "move_count": sum(item["status"] == "move" for item in file_operations) + len(asset_operations),
            "blocker_count": len(blockers),
            "warning_count": len(warnings),
        },
    }


def _remove_empty_tree(root: Path, stop: Path) -> None:
    if not root.exists() or root == stop:
        return
    event_json = root / "event.json"
    if event_json.is_file() and not event_json.is_symlink():
        try:
            event_json.unlink()
        except OSError:
            pass
    for current, _directories, _files in os.walk(root, topdown=False):
        path = Path(current)
        try:
            path.rmdir()
        except OSError:
            pass
    current = root.parent
    while current != stop and current != current.parent:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def apply_legacy_reconcile(
    database_path,
    workspace_path: Path,
    legacy_event_id: str,
    *,
    expected_plan_token: str,
    confirmation_phrase: str,
) -> dict[str, Any]:
    if confirmation_phrase != LEGACY_CONFIRMATION_PHRASE:
        raise LegacyMultiBackupError("Die ausdrückliche Bestätigung für die Legacy-Vereinheitlichung fehlt.")
    plan = build_legacy_reconcile_plan(database_path, workspace_path, legacy_event_id)
    if not plan["summary"]["ready"]:
        raise LegacyMultiBackupError("Der Legacy-Vereinheitlichungsplan besitzt Blocker.")
    if str(expected_plan_token) != str(plan["plan_token"]):
        raise LegacyMultiBackupError("Der Legacy-Vereinheitlichungsplan ist nicht mehr aktuell.")

    work_root = shared_work_root(workspace_path)
    moved: list[tuple[Path, Path]] = []
    created_dirs: list[Path] = []
    operations = [*plan["files"], *plan["assets"]]
    try:
        for item in operations:
            if item["status"] != "move":
                continue
            source = Path(item["source_absolute_path"])
            destination = Path(item["destination_absolute_path"])
            if destination.exists():
                raise LegacyMultiBackupError("Ein Legacy-Zielpfad ist inzwischen belegt: " + str(destination))
            missing: list[Path] = []
            parent = destination.parent
            while parent != work_root and not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                created_dirs.append(directory)
            if _sha256_file(source) != str(item["stored_sha256"]):
                raise LegacyMultiBackupError("Eine Legacy-Quelldatei hat sich seit der Vorschau verändert: " + str(source))
            source.replace(destination)
            moved.append((source, destination))
            if _sha256_file(destination) != str(item["stored_sha256"]):
                raise LegacyMultiBackupError("SHA-256-Prüfung am Legacy-Ziel ist fehlgeschlagen: " + str(destination))

        now = _now()
        with database_connection(database_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            legacy, target = _legacy_case(connection, legacy_event_id)
            if int(legacy.get("revision") or 1) != int(plan["legacy_event"].get("revision") or 1):
                raise LegacyMultiBackupError("Der Legacy-Nachtrag wurde zwischenzeitlich geändert.")
            if int(target.get("revision") or 1) != int(plan["target_event"].get("revision") or 1):
                raise LegacyMultiBackupError("Das kanonische Ereignis wurde zwischenzeitlich geändert.")

            for item in plan["files"]:
                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?,current_root_kind='shared_workspace',
                           sha256_current=?,updated_at=?
                       WHERE id=?""",
                    (
                        str(item["destination_relative_path"]),
                        str(item["stored_sha256"]),
                        now,
                        int(item["file_id"]),
                    ),
                )

            tree_ids = _event_tree_ids(connection, legacy_event_id)
            ph = ",".join("?" for _ in tree_ids)
            assignments = connection.execute(
                f"""SELECT DISTINCT ea.family_id,ff.selected_capture_time,ff.job_id
                    FROM event_assignments ea
                    JOIN file_families ff ON ff.id=ea.family_id
                    WHERE ea.event_id IN ({ph}) AND ea.family_id IS NOT NULL
                    ORDER BY ff.selected_capture_time,ea.family_id""",
                tuple(tree_ids),
            ).fetchall()
            target_children = _root_children(connection, str(target["id"]))
            source_jobs = {str(target["job_id"])}
            moved_family_ids: list[int] = []
            for row in assignments:
                family_id = int(row["family_id"])
                capture = str(row["selected_capture_time"] or "")[:19]
                assignment_target = _assignment_target(
                    str(target["id"]), target_children, capture
                )
                connection.execute(
                    f"""DELETE FROM event_assignments
                        WHERE family_id=? AND event_id IN ({ph})""",
                    (family_id, *tree_ids),
                )
                exists = connection.execute(
                    """SELECT 1 FROM event_assignments ea
                       JOIN events e ON e.id=ea.event_id
                       WHERE ea.family_id=?
                         AND COALESCE(e.parent_event_id,e.id)=?
                       LIMIT 1""",
                    (family_id, str(target["id"])),
                ).fetchone()
                if exists is None:
                    connection.execute(
                        """INSERT INTO event_assignments(
                               event_id,family_id,file_id,assignment_source,created_at
                           ) VALUES (?,?,NULL,'manual',?)""",
                        (assignment_target, family_id, now),
                    )
                source_jobs.add(str(row["job_id"]))
                moved_family_ids.append(family_id)

            if str(target.get("event_kind") or "") == "no_event":
                _merge_no_event_segments(
                    connection,
                    str(target["id"]),
                    legacy_event_id,
                    str(target["job_id"]),
                    now,
                )

            register_source_jobs(
                connection,
                str(target["id"]),
                sorted(source_jobs),
                created_at=now,
            )
            sync_event_source_jobs(
                connection,
                str(target["id"]),
                created_at=now,
            )
            connection.execute(
                "UPDATE events SET revision=revision+1,updated_at=? WHERE id=?",
                (now, str(target["id"])),
            )
            connection.execute(
                """INSERT INTO audit_log(
                       job_id,action,entity_type,entity_id,details_json,created_at
                   ) VALUES (?,'legacy_multi_backup_reconciled','event',?,?,?)""",
                (
                    str(target["job_id"]),
                    str(target["id"]),
                    json.dumps(
                        {
                            "legacy_event_id": legacy_event_id,
                            "family_ids": sorted(moved_family_ids),
                            "camera_file_count": len(plan["files"]),
                            "asset_count": len(plan["assets"]),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    now,
                ),
            )
            connection.execute("DELETE FROM events WHERE id=?", (legacy_event_id,))
            connection.commit()

    except Exception:
        for source, destination in reversed(moved):
            try:
                if destination.exists() and not source.exists():
                    source.parent.mkdir(parents=True, exist_ok=True)
                    destination.replace(source)
            except OSError:
                pass
        for directory in sorted(created_dirs, key=lambda value: len(value.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        raise

    source_root = Path(plan["source_root"])
    target_root = Path(plan["target_root"])
    if source_root != target_root:
        _remove_empty_tree(source_root, work_root)

    event_document_warning = None
    try:
        from app.event_document import sync_event_document_after_change
        sync_event_document_after_change(
            database_path,
            workspace_path,
            str(plan["target_event"]["job_id"]),
            str(plan["target_event_id"]),
        )
    except Exception as error:
        event_document_warning = str(error)

    return {
        "status": "completed",
        "legacy_event_id": legacy_event_id,
        "target_event_id": str(plan["target_event_id"]),
        "moved_file_count": len(moved),
        "camera_file_count": len(plan["files"]),
        "asset_count": len(plan["assets"]),
        "event_document_warning": event_document_warning,
    }
