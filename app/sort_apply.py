from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json
import os
import stat
import uuid

from app.database import database_connection
from app.job_readiness import job_sort_readiness
from app.sort_plan import (
    SortPlanError,
    build_event_sort_plan,
)


class SortApplyError(RuntimeError):
    """Raised when a confirmed sort run cannot finish safely."""


CONFIRMATION_PHRASE = "SORTIERUNG ANWENDEN"

ACTIVE_RUN_STATUSES = {
    "queued",
    "verifying",
    "moving",
    "finalizing",
    "rolling_back",
    "interrupted",
}

TERMINAL_RUN_STATUSES = {
    "applied",
    "rolled_back",
    "failed",
    "interrupted",
}


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


def _safe_relative(value: Any) -> Path:
    raw = str(value or "").strip().replace("\\", "/")
    path = Path(raw)

    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SortApplyError(
            "Ein Sortierpfad ist nicht sicher relativ: " + raw
        )

    return path


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY

    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY

    descriptor = os.open(path, flags)

    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _json_details(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def _load_json(value: Any) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _run_dict(row: Any) -> dict[str, Any]:
    result = dict(row)
    result["details"] = _load_json(result.pop("details_json", None))

    file_count = int(result.get("file_count") or 0)
    verified_count = int(result.get("verified_file_count") or 0)
    move_count = int(result.get("move_count") or 0)
    moved_count = int(result.get("moved_file_count") or 0)

    if result.get("status") == "applied":
        progress_percent = 100
    elif result.get("status") == "verifying" and file_count:
        progress_percent = min(
            49,
            round(verified_count / file_count * 49),
        )
    elif result.get("status") in {"moving", "finalizing"}:
        progress_percent = 50 + (
            round(moved_count / move_count * 45)
            if move_count
            else 45
        )
    else:
        progress_percent = 0

    result["progress_percent"] = progress_percent
    result["terminal"] = result.get("status") in TERMINAL_RUN_STATUSES
    return result


def get_sort_run(
    database_path: Path,
    job_id: str,
    run_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM sort_runs
            WHERE id = ?
              AND job_id = ?
            """,
            (run_id, job_id),
        ).fetchone()
        if row is not None:
            return _run_dict(row)

        # A successfully confirmed delete removes the source event. Historical
        # schema 005 ties sort_runs.event_id to it with ON DELETE CASCADE, so the
        # just-finished run can disappear at commit time. Only an explicit
        # workspace_reconciliation_applied audit receipt is accepted as proof of
        # success; an arbitrary missing run remains missing.
        receipt_row = connection.execute(
            """SELECT details_json,created_at
               FROM audit_log
               WHERE job_id=? AND entity_type='sort_run' AND entity_id=?
                 AND action='workspace_reconciliation_applied'
               ORDER BY id DESC LIMIT 1""",
            (job_id, run_id),
        ).fetchone()
        if receipt_row is None:
            return None
        details = _load_json(receipt_row["details_json"])
        completed_at = str(receipt_row["created_at"] or "")
        synthetic = {
            "id": run_id,
            "job_id": job_id,
            "event_id": str(details.get("anchor_event_id") or ""),
            "plan_token": str(details.get("plan_token") or ""),
            "status": "applied",
            "phase": "Gemeinsamer Arbeitsbereich-Abgleich abgeschlossen",
            "source_root": str(details.get("source_root") or ""),
            "target_root": str(details.get("target_root") or ""),
            "file_count": int(details.get("file_count") or 0),
            "verified_file_count": int(details.get("verified_file_count") or details.get("file_count") or 0),
            "move_count": int(details.get("move_count") or 0),
            "moved_file_count": int(details.get("moved_file_count") or details.get("move_count") or 0),
            "directory_count": int(details.get("directory_count") or 0),
            "created_directory_count": int(details.get("created_directory_count") or 0),
            "total_size_bytes": int(details.get("total_size_bytes") or 0),
            "verified_bytes": int(details.get("verified_bytes") or details.get("total_size_bytes") or 0),
            "moved_bytes": int(details.get("moved_bytes") or 0),
            "error_message": None,
            "details_json": json.dumps(details, ensure_ascii=False, sort_keys=True),
            "created_at": completed_at,
            "started_at": completed_at,
            "updated_at": completed_at,
            "completed_at": completed_at,
            "run_kind": str(details.get("run_kind") or "reapply"),
        }
        return _run_dict(synthetic)


def latest_event_sort_run(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        row = connection.execute(
            """
            SELECT *
            FROM sort_runs
            WHERE job_id = ?
              AND event_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (job_id, event_id),
        ).fetchone()

    return _run_dict(row) if row is not None else None


def mark_incomplete_sort_runs_interrupted(
    database_path: Path,
) -> int:
    now = _now()

    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """
            UPDATE sort_runs
            SET status = 'interrupted',
                phase = 'Unterbrochen – manuelle Prüfung erforderlich',
                error_message = COALESCE(
                    error_message,
                    'Der Dienst wurde während einer Sortierung beendet.'
                ),
                updated_at = ?
            WHERE status IN (
                'queued',
                'verifying',
                'moving',
                'finalizing',
                'rolling_back'
            )
            """,
            (now,),
        )

    return int(cursor.rowcount or 0)


def _verify_recovery_copy(path: Path, expected_size: int, expected_sha256: str) -> None:
    try:
        info = os.lstat(path)
    except FileNotFoundError as exc:
        raise SortApplyError("Datei fehlt bei der Wiederherstellung: " + str(path)) from exc
    if not stat.S_ISREG(info.st_mode):
        raise SortApplyError("Wiederherstellung verweigert nicht-reguläre Datei: " + str(path))
    if int(info.st_size) != int(expected_size):
        raise SortApplyError("Dateigröße weicht bei der Wiederherstellung ab: " + str(path))
    if not expected_sha256:
        raise SortApplyError("Gespeicherte SHA-256-Summe fehlt für: " + str(path))
    if _sha256_file(path) != str(expected_sha256):
        raise SortApplyError("SHA-256-Summe weicht bei der Wiederherstellung ab: " + str(path))


def recover_interrupted_sort_runs(database_path: Path) -> dict[str, int]:
    """Safely roll interrupted sort/reconcile runs back to their DB IST paths.

    SQLite path finalization and the run status are committed atomically. Thus a
    run that is still interrupted after startup has not committed its new file
    paths. The journaled source path is therefore the only safe automatic
    recovery target. Ambiguous filesystem states remain blocked for manual
    inspection instead of being guessed.
    """
    with database_connection(database_path) as connection:
        runs = [
            dict(row) for row in connection.execute(
                """SELECT * FROM sort_runs
                   WHERE status='interrupted'
                   ORDER BY created_at,id"""
            ).fetchall()
        ]

    recovered = 0
    blocked = 0

    for run in runs:
        run_id = str(run["id"])
        source_root = Path(str(run["source_root"])).resolve(strict=False)
        target_root = Path(str(run["target_root"])).resolve(strict=False)
        with database_connection(database_path) as connection:
            camera_operations = [
                {**dict(row), "_operation_kind": "camera"}
                for row in connection.execute(
                    """SELECT * FROM sort_operations
                       WHERE sort_run_id=?
                       ORDER BY sequence_number,id""",
                    (run_id,),
                ).fetchall()
            ]
            asset_operations = [
                {**dict(row), "_operation_kind": "asset"}
                for row in connection.execute(
                    """SELECT * FROM sort_asset_operations
                       WHERE sort_run_id=?
                       ORDER BY sequence_number,id""",
                    (run_id,),
                ).fetchall()
            ]
            operations = sorted(
                [*camera_operations, *asset_operations],
                key=lambda row: (int(row["sequence_number"]), int(row["id"])),
            )

        try:
            for operation in reversed(operations):
                source_rel = _safe_relative(operation["source_relative_path"])
                destination_rel = _safe_relative(operation["destination_relative_path"])
                operation_source_root = (
                    target_root
                    if str(operation.get("source_root_kind") or "job_root") == "shared_workspace"
                    else source_root
                )
                source = operation_source_root.joinpath(*source_rel.parts)
                destination = target_root.joinpath(*destination_rel.parts)
                expected_size = int(operation["expected_size_bytes"])
                expected_sha = str(operation["expected_sha256"] or "").strip()

                if source == destination or str(operation.get("status") or "") == "already_at_target":
                    _verify_recovery_copy(source, expected_size, expected_sha)
                    continue

                source_exists = source.exists() or source.is_symlink()
                destination_exists = destination.exists() or destination.is_symlink()

                if source_exists and not destination_exists:
                    _verify_recovery_copy(source, expected_size, expected_sha)
                elif destination_exists and not source_exists:
                    _verify_recovery_copy(destination, expected_size, expected_sha)
                    _rollback_one(source, destination)
                    _verify_recovery_copy(source, expected_size, expected_sha)
                elif source_exists and destination_exists:
                    source_info = os.lstat(source)
                    destination_info = os.lstat(destination)
                    if (
                        not stat.S_ISREG(source_info.st_mode)
                        or not stat.S_ISREG(destination_info.st_mode)
                        or int(source_info.st_dev) != int(destination_info.st_dev)
                        or int(source_info.st_ino) != int(destination_info.st_ino)
                    ):
                        raise SortApplyError(
                            "Wiederherstellung ist mehrdeutig: Quelle und Ziel existieren als verschiedene Dateien: "
                            + str(source) + " / " + str(destination)
                        )
                    _verify_recovery_copy(source, expected_size, expected_sha)
                    _rollback_one(source, destination)
                else:
                    raise SortApplyError(
                        "Wiederherstellung ist nicht möglich, weil Quelle und Ziel fehlen: "
                        + str(source)
                    )

                with database_connection(database_path) as connection:
                    table = (
                        "sort_asset_operations"
                        if operation.get("_operation_kind") == "asset"
                        else "sort_operations"
                    )
                    connection.execute(
                        f"""UPDATE {table}
                            SET status='rolled_back',rolled_back_at=?,error_message=NULL
                            WHERE sort_run_id=? AND id=?""",
                        (_now(), run_id, int(operation["id"])),
                    )

            now = _now()
            with database_connection(database_path) as connection:
                connection.execute(
                    """UPDATE sort_runs
                       SET status='rolled_back',
                           phase='Unterbrochener Lauf sicher zurückgesetzt – erneut starten möglich',
                           error_message=NULL,completed_at=?,updated_at=?
                       WHERE id=? AND status='interrupted'""",
                    (now, now, run_id),
                )
                connection.execute(
                    """INSERT INTO audit_log(
                           job_id,action,entity_type,entity_id,details_json,created_at
                       ) VALUES (?,'interrupted_sort_run_recovered','sort_run',?,?,?)""",
                    (
                        str(run["job_id"]),
                        run_id,
                        _json_details({"recovery":"rollback_to_journaled_source","run_kind":str(run.get("run_kind") or "initial")}),
                        now,
                    ),
                )
            recovered += 1

        except Exception as exc:
            blocked += 1
            now = _now()
            with database_connection(database_path) as connection:
                connection.execute(
                    """UPDATE sort_runs
                       SET phase='Unterbrochen – automatische Wiederherstellung nicht eindeutig',
                           error_message=?,updated_at=?
                       WHERE id=? AND status='interrupted'""",
                    (str(exc), now, run_id),
                )

    return {"recovered": recovered, "blocked": blocked}


def prepare_sort_run(
    database_path: Path,
    job_id: str,
    event_id: str,
    workspace_path: Path,
    *,
    expected_plan_token: str,
    confirmation_phrase: str,
) -> dict[str, Any]:
    if confirmation_phrase != CONFIRMATION_PHRASE:
        raise SortApplyError(
            "Die ausdrückliche Bestätigung für die Sortierung fehlt."
        )

    plan = build_event_sort_plan(
        database_path,
        job_id,
        event_id,
        workspace_path,
        verify_sha256=False,
    )

    if not bool(plan["summary"]["ready"]):
        raise SortApplyError(
            "Der Sortierplan besitzt Blocker und darf nicht angewendet werden."
        )

    if str(plan["plan_token"]) != str(expected_plan_token):
        raise SortApplyError(
            "Der Sortierplan ist nicht mehr aktuell. Bitte erneut prüfen."
        )

    job_ready, job_blocker = job_sort_readiness(plan["job"])
    if not job_ready:
        raise SortApplyError(job_blocker)

    run_id = "SORT_" + uuid.uuid4().hex.upper()
    now = _now()
    summary = plan["summary"]

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        event = connection.execute(
            """
            SELECT status, applied_at, archived_at
            FROM events
            WHERE id = ?
              AND job_id = ?
              AND event_level = 'parent'
            """,
            (event_id, job_id),
        ).fetchone()

        if event is None:
            raise SortApplyError("Ereignis wurde nicht gefunden.")

        if (
            str(event["status"]) not in {"draft", "planned"}
            or event["applied_at"] is not None
            or event["archived_at"] is not None
        ):
            raise SortApplyError(
                "Nur eine noch nicht angewendete Planung kann sortiert werden."
            )

        active = connection.execute(
            """
            SELECT id, status
            FROM sort_runs
            WHERE event_id = ?
              AND status IN (
                    'queued',
                    'verifying',
                    'moving',
                    'finalizing',
                    'rolling_back',
                    'interrupted'
                  )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (event_id,),
        ).fetchone()

        if active is not None:
            raise SortApplyError(
                "Für dieses Ereignis existiert bereits ein aktiver oder "
                "unterbrochener Sortierlauf: "
                + str(active["id"])
            )

        connection.execute(
            """
            INSERT INTO sort_runs (
                id,
                job_id,
                event_id,
                plan_token,
                status,
                phase,
                source_root,
                target_root,
                file_count,
                verified_file_count,
                move_count,
                moved_file_count,
                directory_count,
                created_directory_count,
                total_size_bytes,
                verified_bytes,
                moved_bytes,
                error_message,
                details_json,
                created_at,
                started_at,
                updated_at,
                completed_at
            )
            VALUES (
                ?, ?, ?, ?,
                'queued',
                'Wartet auf vollständige SHA-256-Prüfung',
                ?, ?, ?, 0, ?, 0, ?, 0, ?, 0, 0,
                NULL, ?, ?, NULL, ?, NULL
            )
            """,
            (
                run_id,
                job_id,
                event_id,
                str(plan["plan_token"]),
                str(plan["source_root"]),
                str(plan["target_root"]),
                int(summary["file_count"]),
                int(summary["move_count"]),
                int(summary["directory_count"]),
                int(summary["total_size_bytes"]),
                _json_details({
                    "event_name": str(plan["event"]["name"]),
                    "structure_text": str(plan["structure_text"]),
                    "planned_directories": [
                        str(row["relative_path"])
                        for row in plan["directories"]
                    ],
                    "created_directories": [],
                    "removed_empty_source_directories": [],
                }),
                now,
                now,
            ),
        )

        operations = []

        for sequence, entry in enumerate(plan["files"], start=1):
            status_value = (
                "already_at_target"
                if entry["status"] == "already_at_target"
                else "planned"
            )

            operations.append((
                run_id,
                sequence,
                int(entry["file_id"]),
                str(entry["source_relative_path"]),
                str(entry["destination_relative_path"]),
                int(entry["expected_size_bytes"]),
                str(entry["stored_sha256"]),
                str(entry.get("current_root_kind") or "job_root"),
                status_value,
            ))

        connection.executemany(
            """
            INSERT INTO sort_operations (
                sort_run_id,
                sequence_number,
                file_id,
                source_relative_path,
                destination_relative_path,
                expected_size_bytes,
                expected_sha256,
                source_root_kind,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            operations,
        )

        asset_operations = []
        sequence_offset = len(plan["files"])
        for asset_index, entry in enumerate(plan.get("assets") or [], start=1):
            status_value = (
                "already_at_target"
                if entry["status"] == "already_at_target"
                else "planned"
            )
            asset_operations.append((
                run_id,
                sequence_offset + asset_index,
                str(entry.get("asset_kind") or "other"),
                entry.get("family_id"),
                entry.get("source_file_id"),
                str(entry["source_relative_path"]),
                str(entry["destination_relative_path"]),
                int(entry["expected_size_bytes"]),
                str(entry["stored_sha256"]),
                str(entry.get("source_root_kind") or "shared_workspace"),
                status_value,
            ))

        connection.executemany(
            """
            INSERT INTO sort_asset_operations (
                sort_run_id, sequence_number, asset_kind, family_id,
                source_file_id, source_relative_path, destination_relative_path,
                expected_size_bytes, expected_sha256, source_root_kind, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            asset_operations,
        )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (?, 'sort_run_queued', 'sort_run', ?, ?, ?)
            """,
            (
                job_id,
                run_id,
                _json_details({
                    "event_id": event_id,
                    "plan_token": str(plan["plan_token"]),
                    "file_count": int(summary["file_count"]),
                    "move_count": int(summary["move_count"]),
                }),
                now,
            ),
        )

    run = get_sort_run(database_path, job_id, run_id)

    if run is None:
        raise SortApplyError("Sortierlauf konnte nicht angelegt werden.")

    return run


def _update_run(
    database_path: Path,
    run_id: str,
    **values: Any,
) -> None:
    if not values:
        return

    values["updated_at"] = _now()
    assignments = ", ".join(f"{key} = ?" for key in values)
    parameters = [*values.values(), run_id]

    with database_connection(database_path) as connection:
        connection.execute(
            f"UPDATE sort_runs SET {assignments} WHERE id = ?",
            parameters,
        )


def _update_operation(
    database_path: Path,
    run_id: str,
    file_id: int,
    **values: Any,
) -> None:
    assignments = ", ".join(f"{key} = ?" for key in values)
    parameters = [*values.values(), run_id, file_id]

    with database_connection(database_path) as connection:
        connection.execute(
            f"""
            UPDATE sort_operations
            SET {assignments}
            WHERE sort_run_id = ?
              AND file_id = ?
            """,
            parameters,
        )


def _update_asset_operation(
    database_path: Path,
    run_id: str,
    source_relative_path: str,
    **values: Any,
) -> None:
    assignments = ", ".join(f"{key} = ?" for key in values)
    parameters = [*values.values(), run_id, source_relative_path]

    with database_connection(database_path) as connection:
        connection.execute(
            f"""
            UPDATE sort_asset_operations
            SET {assignments}
            WHERE sort_run_id = ?
              AND source_relative_path = ?
            """,
            parameters,
        )


def _created_directory_candidates(
    plan: dict[str, Any],
) -> list[Path]:
    target_root = Path(plan["target_root"]).resolve(strict=False)
    candidates: set[Path] = set()

    for row in plan["directories"]:
        directory = Path(row["absolute_path"]).resolve(strict=False)

        if not _is_relative_to(directory, target_root):
            raise SortApplyError(
                "Ein geplanter Ordner verlässt den Arbeitsbestand."
            )

        current = directory

        while current != target_root:
            if not current.exists():
                candidates.add(current)

            current = current.parent

    return sorted(candidates, key=lambda path: len(path.parts))


def _create_directories(
    plan: dict[str, Any],
    created: list[Path],
) -> None:
    for directory in _created_directory_candidates(plan):
        try:
            directory.mkdir()
            created.append(directory)
            _fsync_directory(directory.parent)
        except FileExistsError:
            if not directory.is_dir():
                raise SortApplyError(
                    "Ein geplanter Ordnerpfad wurde zwischenzeitlich belegt: "
                    + str(directory)
                )


def _assert_source_identity(
    source: Path,
    entry: dict[str, Any],
) -> os.stat_result:
    source_stat = os.lstat(source)

    if not stat.S_ISREG(source_stat.st_mode):
        raise SortApplyError(
            "Quelle ist keine reguläre Datei: " + str(source)
        )

    expected = (
        int(entry["source_device"]),
        int(entry["source_inode"]),
        int(entry["source_mtime_ns"]),
        int(entry["expected_size_bytes"]),
    )
    actual = (
        int(source_stat.st_dev),
        int(source_stat.st_ino),
        int(source_stat.st_mtime_ns),
        int(source_stat.st_size),
    )

    if actual != expected:
        raise SortApplyError(
            "Eine Quelldatei wurde nach der Vorschau verändert: "
            + str(source)
        )

    return source_stat


def _move_without_overwrite(
    source: Path,
    destination: Path,
    entry: dict[str, Any],
) -> None:
    source_stat = _assert_source_identity(source, entry)

    if destination.exists() or destination.is_symlink():
        raise SortApplyError(
            "Am Ziel ist zwischenzeitlich ein Eintrag entstanden: "
            + str(destination)
        )

    os.link(
        source,
        destination,
        follow_symlinks=False,
    )

    destination_stat = os.lstat(destination)

    if (
        int(destination_stat.st_dev) != int(source_stat.st_dev)
        or int(destination_stat.st_ino) != int(source_stat.st_ino)
    ):
        destination.unlink(missing_ok=True)
        raise SortApplyError(
            "Der sichere Link-Schritt konnte nicht bestätigt werden: "
            + str(destination)
        )

    source_check = os.lstat(source)

    if (
        int(source_check.st_dev) != int(destination_stat.st_dev)
        or int(source_check.st_ino) != int(destination_stat.st_ino)
    ):
        destination.unlink(missing_ok=True)
        raise SortApplyError(
            "Die Quelldatei änderte sich während der Verschiebung: "
            + str(source)
        )

    try:
        source.unlink()
    except Exception:
        destination.unlink(missing_ok=True)
        _fsync_directory(destination.parent)
        raise


def _rollback_one(
    source: Path,
    destination: Path,
) -> None:
    source_exists = source.exists() or source.is_symlink()
    destination_exists = destination.exists() or destination.is_symlink()

    if destination_exists and not source_exists:
        source.parent.mkdir(parents=True, exist_ok=True)
        os.link(
            destination,
            source,
            follow_symlinks=False,
        )
        source_stat = os.lstat(source)
        destination_stat = os.lstat(destination)

        if (
            int(source_stat.st_dev) != int(destination_stat.st_dev)
            or int(source_stat.st_ino) != int(destination_stat.st_ino)
        ):
            source.unlink(missing_ok=True)
            raise SortApplyError(
                "Rollback-Link konnte nicht bestätigt werden: " + str(source)
            )

        destination.unlink()
        _fsync_directory(source.parent)
        _fsync_directory(destination.parent)
        return

    if destination_exists and source_exists:
        source_stat = os.lstat(source)
        destination_stat = os.lstat(destination)

        if (
            int(source_stat.st_dev) == int(destination_stat.st_dev)
            and int(source_stat.st_ino) == int(destination_stat.st_ino)
        ):
            destination.unlink()
            _fsync_directory(destination.parent)
            return

        raise SortApplyError(
            "Rollback-Konflikt: Quelle und Ziel existieren mit verschiedenen Inodes."
        )

    if source_exists and not destination_exists:
        return

    raise SortApplyError(
        "Rollback nicht möglich, weil Quelle und Ziel fehlen: " + str(source)
    )


def _remove_empty_source_directories(
    plan: dict[str, Any],
) -> list[Path]:
    source_root = Path(plan["source_root"]).resolve(strict=False)
    target_root = Path(plan["target_root"]).resolve(strict=False)
    candidates: set[Path] = set()

    for entry in [*plan["files"], *(plan.get("assets") or [])]:
        if entry["status"] != "move":
            continue

        entry_source_root = (
            target_root
            if str(
                entry.get("current_root_kind")
                or entry.get("source_root_kind")
                or "job_root"
            ) == "shared_workspace"
            else source_root
        )
        current = Path(entry["source_absolute_path"]).parent

        while current != entry_source_root and _is_relative_to(current, entry_source_root):
            candidates.add(current)
            current = current.parent

    removed: list[Path] = []

    for directory in sorted(
        candidates,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
            removed.append(directory)
            _fsync_directory(directory.parent)
        except OSError:
            pass

    return removed


def _remove_created_empty_directories(created: list[Path]) -> None:
    for directory in sorted(
        created,
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
            _fsync_directory(directory.parent)
        except OSError:
            pass


def _record_verified_progress(
    database_path: Path,
    run_id: str,
    file_id: int,
    size_bytes: int,
) -> None:
    now = _now()

    with database_connection(database_path) as connection:
        connection.execute(
            """
            UPDATE sort_operations
            SET status = CASE
                    WHEN status = 'planned' THEN 'verified'
                    ELSE status
                END,
                verified_at = COALESCE(verified_at, ?)
            WHERE sort_run_id = ?
              AND file_id = ?
            """,
            (now, run_id, file_id),
        )

        connection.execute(
            """
            UPDATE sort_runs
            SET verified_file_count = verified_file_count + 1,
                verified_bytes = verified_bytes + ?,
                phase = 'SHA-256-Prüfung der Quelldateien',
                updated_at = ?
            WHERE id = ?
            """,
            (size_bytes, now, run_id),
        )


def _record_verified_asset_progress(
    database_path: Path,
    run_id: str,
    source_relative_path: str,
    size_bytes: int,
) -> None:
    now = _now()

    with database_connection(database_path) as connection:
        connection.execute(
            """
            UPDATE sort_asset_operations
            SET status = CASE
                    WHEN status = 'planned' THEN 'verified'
                    ELSE status
                END,
                verified_at = COALESCE(verified_at, ?)
            WHERE sort_run_id = ?
              AND source_relative_path = ?
            """,
            (now, run_id, source_relative_path),
        )
        connection.execute(
            """
            UPDATE sort_runs
            SET verified_file_count = verified_file_count + 1,
                verified_bytes = verified_bytes + ?,
                phase = 'SHA-256-Prüfung der Quelldateien',
                updated_at = ?
            WHERE id = ?
            """,
            (size_bytes, now, run_id),
        )


def _finalize_database(
    database_path: Path,
    run_id: str,
    plan: dict[str, Any],
    created_directories: list[Path],
    removed_directories: list[Path],
) -> None:
    now = _now()
    job_id = str(plan["job"]["id"])
    event_id = str(plan["event"]["id"])

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")

        run = connection.execute(
            """
            SELECT status, plan_token, run_kind
            FROM sort_runs
            WHERE id = ?
              AND job_id = ?
              AND event_id = ?
            """,
            (run_id, job_id, event_id),
        ).fetchone()

        if run is None or str(run["status"]) != "finalizing":
            raise SortApplyError(
                "Der Sortierlauf ist beim Abschluss nicht mehr gültig."
            )

        if str(run["plan_token"]) != str(plan["plan_token"]):
            raise SortApplyError(
                "Der Sortierplan änderte sich vor dem Datenbankabschluss."
            )

        is_reapply = str(run["run_kind"] or "initial") == "reapply"

        event = connection.execute(
            """
            SELECT status, applied_at, archived_at, resort_required, pending_delete
            FROM events
            WHERE id = ?
              AND job_id = ?
              AND event_level = 'parent'
            """,
            (event_id, job_id),
        ).fetchone()

        if is_reapply:
            if (
                event is None
                or str(event["status"]) != "applied"
                or event["archived_at"] is not None
            ):
                raise SortApplyError(
                    "Das Ereignis ist beim Abschluss der Nachsortierung "
                    "nicht mehr im angewendeten Zustand."
                )
        else:
            if (
                event is None
                or str(event["status"]) not in {"draft", "planned"}
                or event["applied_at"] is not None
                or event["archived_at"] is not None
            ):
                raise SortApplyError(
                    "Das Ereignis ist beim Abschluss nicht mehr anwendbar."
                )

        for entry in plan["files"]:
            connection.execute(
                """
                UPDATE files
                SET current_relative_path = ?,
                    current_root_kind = 'shared_workspace',
                    sha256_current = ?,
                    updated_at = ?
                WHERE id = ?
                  AND job_id = ?
                """,
                (
                    str(entry["destination_relative_path"]),
                    str(entry["stored_sha256"]),
                    now,
                    int(entry["file_id"]),
                    job_id,
                ),
            )

        for asset in plan.get("assets") or []:
            released_asset_id = asset.get("released_archive_asset_id")
            if released_asset_id is not None:
                connection.execute(
                    "DELETE FROM released_archive_assets WHERE id=? AND job_id=?",
                    (int(released_asset_id), job_id),
                )

        if is_reapply:
            pending_delete = bool(event["pending_delete"] or 0)
            if pending_delete:
                # Alle ehemaligen Familien wurden vor dem Lauf bereits einem
                # sicheren Ziel zugeordnet. Nach der verifizierten Dateibewegung
                # kann das nun leere Quellereignis vollständig verschwinden.
                connection.execute(
                    """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                       VALUES (?,'event_deleted_after_reapply','event',?,?,?)""",
                    (job_id, event_id, json.dumps({"run_id": run_id, "files_verified": len(plan["files"])}, ensure_ascii=False, sort_keys=True), now),
                )
                connection.execute("DELETE FROM events WHERE id=? AND job_id=?", (event_id, job_id))
                action = "event_deleted_after_reapply"
                phase = "Ereignis gelöscht; Dateien vollständig neu zugeordnet und geprüft"
            else:
                # Der Nachsortierlauf ändert die Struktur im Arbeitsbereich,
                # der Status des Ereignisses bleibt 'applied'.
                connection.execute(
                    """
                    UPDATE events
                    SET updated_at = ?, resort_required = 0
                    WHERE job_id = ?
                      AND (
                            id = ?
                            OR parent_event_id = ?
                          )
                    """,
                    (now, job_id, event_id, event_id),
                )
                connection.execute(
                    "DELETE FROM event_reapply_removed_families WHERE event_id = ?",
                    (event_id,),
                )
                action = "event_sort_reapplied"
                phase = "Nachsortierung vollständig angewendet und geprüft"
        else:
            connection.execute(
                """
                UPDATE events
                SET status = 'applied',
                    applied_at = ?,
                    updated_at = ?
                WHERE job_id = ?
                  AND (
                        id = ?
                        OR parent_event_id = ?
                      )
                """,
                (now, now, job_id, event_id, event_id),
            )

            connection.execute(
                """
                UPDATE jobs
                SET state = 'completed',
                    stage = 'event_sort_applied',
                    progress_message = 'Ereignissortierung vollständig angewendet und geprüft.',
                    error_message = NULL,
                    updated_at = ?,
                    finished_at = COALESCE(finished_at, ?)
                WHERE id = ?
                """,
                (now, now, job_id),
            )
            action = "event_sort_applied"
            phase = "Sortierung vollständig angewendet und geprüft"

            # 0.17.1: a coordinated edit between still-planned events remains
            # locked/cancellable until every affected event has been applied.
            from app.event_mutation import maybe_complete_planned_cascade_after_initial_apply
            maybe_complete_planned_cascade_after_initial_apply(connection, job_id)

        from app.event_reassignment import finalize_reconciled_deleted_sources
        finalize_reconciled_deleted_sources(connection, event_id, now)

        details = {
            "event_name": str(plan["event"]["name"]),
            "structure_text": str(plan["structure_text"]),
            "created_directories": [
                str(path) for path in created_directories
            ],
            "removed_empty_source_directories": [
                str(path) for path in removed_directories
            ],
            "file_count": int(plan["summary"]["file_count"]),
            "camera_file_count": int(
                plan["summary"].get("camera_file_count")
                or len(plan["files"])
            ),
            "asset_count": int(
                plan["summary"].get("asset_count")
                or len(plan.get("assets") or [])
            ),
            "xmp_count": int(plan["summary"].get("xmp_count") or 0),
            "move_count": int(plan["summary"]["move_count"]),
            "total_size_bytes": int(
                plan["summary"]["total_size_bytes"]
            ),
            "run_kind": "reapply" if is_reapply else "initial",
        }

        connection.execute(
            """
            UPDATE sort_runs
            SET status = 'applied',
                phase = ?,
                created_directory_count = ?,
                details_json = ?,
                updated_at = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                phase,
                len(created_directories),
                _json_details(details),
                now,
                now,
                run_id,
            ),
        )

        connection.execute(
            """
            INSERT INTO audit_log (
                job_id,
                action,
                entity_type,
                entity_id,
                details_json,
                created_at
            )
            VALUES (?, ?, 'event', ?, ?, ?)
            """,
            (
                job_id,
                action,
                event_id,
                _json_details({
                    "sort_run_id": run_id,
                    "plan_token": str(plan["plan_token"]),
                    **details,
                }),
                now,
            ),
        )

    # SQLite und Dateisystem sind an dieser Stelle bereits konsistent
    # abgeschlossen. Ein nachgelagerter Fehler beim portablen event.json darf
    # deshalb niemals den äußeren Dateisystem-Rollback auslösen; sonst würden
    # die Dateien zurückbewegt, während der DB-Commit bestehen bleibt.
    try:
        from app.event_document import sync_event_document_after_change

        sync_event_document_after_change(
            database_path,
            Path(plan["workspace_root"]),
            job_id,
            event_id,
        )
    except Exception as error:
        warning = "event.json konnte nach erfolgreicher Sortierung nicht aktualisiert werden: " + str(error)
        # Auch die Warnungsprotokollierung ist best effort: Nach dem bereits
        # erfolgreichen Commit darf kein sekundärer Fehler einen Rollback der
        # physischen Dateien mehr auslösen.
        try:
            with database_connection(database_path) as connection:
                row = connection.execute(
                    "SELECT details_json FROM sort_runs WHERE id = ?",
                    (run_id,),
                ).fetchone()
                details_after = _load_json(row["details_json"] if row is not None else None)
                details_after["event_document_sync_error"] = warning
                connection.execute(
                    """UPDATE sort_runs
                       SET phase = ?, error_message = ?, details_json = ?, updated_at = ?
                       WHERE id = ? AND status = 'applied'""",
                    (
                        "Sortierung angewendet; event.json muss neu erzeugt werden",
                        warning,
                        _json_details(details_after),
                        _now(),
                        run_id,
                    ),
                )
                connection.execute(
                    """INSERT INTO audit_log(
                           job_id, action, entity_type, entity_id, details_json, created_at
                       ) VALUES (?,'event_document_sync_failed','event',?,?,?)""",
                    (
                        job_id,
                        event_id,
                        _json_details({"sort_run_id": run_id, "error": str(error)}),
                        _now(),
                    ),
                )
        except Exception:
            pass


def execute_sort_run(
    database_path: Path,
    run_id: str,
    workspace_path: Path,
    *,
    test_fail_after_moves: int | None = None,
) -> None:
    with database_connection(database_path) as connection:
        run_row = connection.execute(
            """
            SELECT *
            FROM sort_runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    if run_row is None:
        raise SortApplyError("Sortierlauf wurde nicht gefunden.")

    run = dict(run_row)
    job_id = str(run["job_id"])
    event_id = str(run["event_id"])
    expected_plan_token = str(run["plan_token"])
    created_directories: list[Path] = []
    moved_entries: list[dict[str, Any]] = []

    try:
        _update_run(
            database_path,
            run_id,
            status="verifying",
            phase="SHA-256-Prüfung der Quelldateien",
            started_at=_now(),
            verified_file_count=0,
            verified_bytes=0,
        )

        plan = build_event_sort_plan(
            database_path,
            job_id,
            event_id,
            workspace_path,
            verify_sha256=True,
            allow_reapply=str(run.get("run_kind") or "initial") == "reapply",
            verification_callback=lambda file_id, size_bytes: (
                _record_verified_progress(
                    database_path,
                    run_id,
                    file_id,
                    size_bytes,
                )
            ),
            asset_verification_callback=lambda source_relative_path, size_bytes: (
                _record_verified_asset_progress(
                    database_path,
                    run_id,
                    source_relative_path,
                    size_bytes,
                )
            ),
        )

        if str(plan["plan_token"]) != expected_plan_token:
            raise SortApplyError(
                "Der Sortierplan ist seit der Bestätigung nicht mehr aktuell."
            )

        if not bool(plan["summary"]["ready"]):
            messages = "; ".join(
                str(item.get("message") or item.get("code"))
                for item in plan["blockers"][:5]
            )
            raise SortApplyError(
                "Die vollständige Prüfung erkannte Blocker: " + messages
            )

        if str(run.get("run_kind") or "initial") == "reapply":
            _update_run(
                database_path,
                run_id,
                phase="Nachsortierung: SHA-256-Prüfung abgeschlossen",
            )

        _update_run(
            database_path,
            run_id,
            status="moving",
            phase="Zielordner werden angelegt",
        )

        _create_directories(
            plan,
            created_directories,
        )
        _update_run(
            database_path,
            run_id,
            created_directory_count=len(created_directories),
            details_json=_json_details({
                "event_name": str(plan["event"]["name"]),
                "structure_text": str(plan["structure_text"]),
                "planned_directories": [
                    str(row["relative_path"])
                    for row in plan["directories"]
                ],
                "created_directories": [
                    str(path) for path in created_directories
                ],
                "removed_empty_source_directories": [],
            }),
        )

        moved_count = 0
        moved_bytes = 0

        for entry in plan["files"]:
            file_id = int(entry["file_id"])

            if entry["status"] == "already_at_target":
                continue

            source = Path(entry["source_absolute_path"])
            destination = Path(entry["destination_absolute_path"])

            _move_without_overwrite(
                source,
                destination,
                entry,
            )

            moved_entries.append({**entry, "_operation_kind": "camera"})
            _fsync_directory(source.parent)
            _fsync_directory(destination.parent)
            moved_count += 1
            moved_bytes += int(entry["expected_size_bytes"])
            now = _now()

            _update_operation(
                database_path,
                run_id,
                file_id,
                status="moved",
                moved_at=now,
            )

            destination_checksum = _sha256_file(destination)

            if destination_checksum != str(entry["stored_sha256"]):
                raise SortApplyError(
                    "Die Prüfsumme am Ziel stimmt nach der Verschiebung nicht: "
                    + str(destination)
                )

            _update_operation(
                database_path,
                run_id,
                file_id,
                status="destination_verified",
                destination_verified_at=_now(),
            )

            _update_run(
                database_path,
                run_id,
                phase=(
                    f"Dateien werden verschoben und geprüft "
                    f"({moved_count}/{int(plan['summary']['move_count'])})"
                ),
                moved_file_count=moved_count,
                moved_bytes=moved_bytes,
            )

            if (
                test_fail_after_moves is not None
                and moved_count >= test_fail_after_moves
            ):
                raise SortApplyError(
                    "Absichtlich ausgelöster Testfehler nach Verschiebung."
                )

        for entry in plan.get("assets") or []:
            if entry["status"] == "already_at_target":
                continue

            source = Path(entry["source_absolute_path"])
            destination = Path(entry["destination_absolute_path"])

            _move_without_overwrite(source, destination, entry)

            moved_entries.append({**entry, "_operation_kind": "asset"})
            _fsync_directory(source.parent)
            _fsync_directory(destination.parent)
            moved_count += 1
            moved_bytes += int(entry["expected_size_bytes"])
            now = _now()

            _update_asset_operation(
                database_path,
                run_id,
                str(entry["source_relative_path"]),
                status="moved",
                moved_at=now,
            )

            destination_checksum = _sha256_file(destination)
            if destination_checksum != str(entry["stored_sha256"]):
                raise SortApplyError(
                    "Die Prüfsumme am XMP-Ziel stimmt nach der Verschiebung nicht: "
                    + str(destination)
                )

            _update_asset_operation(
                database_path,
                run_id,
                str(entry["source_relative_path"]),
                status="destination_verified",
                destination_verified_at=_now(),
            )

            _update_run(
                database_path,
                run_id,
                phase=(
                    f"Dateien werden verschoben und geprüft "
                    f"({moved_count}/{int(plan['summary']['move_count'])})"
                ),
                moved_file_count=moved_count,
                moved_bytes=moved_bytes,
            )

            if (
                test_fail_after_moves is not None
                and moved_count >= test_fail_after_moves
            ):
                raise SortApplyError(
                    "Absichtlich ausgelöster Testfehler nach Verschiebung."
                )

        removed_directories = _remove_empty_source_directories(plan)

        _update_run(
            database_path,
            run_id,
            status="finalizing",
            phase="SQLite-Zuordnungen werden abschließend aktualisiert",
        )

        _finalize_database(
            database_path,
            run_id,
            plan,
            created_directories,
            removed_directories,
        )
        if str(run.get("run_kind") or "initial") == "reapply":
            try:
                from app.applied_neutralization import cleanup_empty_neutral_directories
                cleanup_empty_neutral_directories(workspace_path)
            except Exception:
                pass

    except Exception as error:
        message = str(error)

        try:
            _update_run(
                database_path,
                run_id,
                status="rolling_back",
                phase="Fehler erkannt – bereits verschobene Dateien werden zurückgesetzt",
                error_message=message,
            )
        except Exception:
            pass

        rollback_errors: list[str] = []

        for entry in reversed(moved_entries):
            source = Path(entry["source_absolute_path"])
            destination = Path(entry["destination_absolute_path"])

            try:
                _rollback_one(source, destination)
                if entry.get("_operation_kind") == "asset":
                    _update_asset_operation(
                        database_path,
                        run_id,
                        str(entry["source_relative_path"]),
                        status="rolled_back",
                        rolled_back_at=_now(),
                    )
                else:
                    _update_operation(
                        database_path,
                        run_id,
                        int(entry["file_id"]),
                        status="rolled_back",
                        rolled_back_at=_now(),
                    )
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
                try:
                    if entry.get("_operation_kind") == "asset":
                        _update_asset_operation(
                            database_path,
                            run_id,
                            str(entry["source_relative_path"]),
                            status="failed",
                            error_message=str(rollback_error),
                        )
                    else:
                        _update_operation(
                            database_path,
                            run_id,
                            int(entry["file_id"]),
                            status="failed",
                            error_message=str(rollback_error),
                        )
                except Exception:
                    pass

        _remove_created_empty_directories(created_directories)

        final_status = "failed" if rollback_errors else "rolled_back"
        final_phase = (
            "Rollback unvollständig – manuelle Prüfung erforderlich"
            if rollback_errors
            else "Fehler vollständig zurückgesetzt"
        )
        combined_error = message

        if rollback_errors:
            combined_error += " | Rollback: " + " | ".join(rollback_errors)

        try:
            _update_run(
                database_path,
                run_id,
                status=final_status,
                phase=final_phase,
                error_message=combined_error,
                completed_at=_now(),
            )
        finally:
            raise SortApplyError(combined_error) from error
