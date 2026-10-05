from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

from app.database import database_connection
from app.safe_transfer import SafeTransferError, move_verified_no_overwrite


class ExternalChangeError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_relative(value: Any) -> Path:
    raw = str(value or "").replace("\\", "/").strip("/")
    path = Path(raw)
    if (
        not raw
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ExternalChangeError("Unsicherer relativer Dateipfad: " + raw)
    return path


def record_notice(
    connection: Any,
    *,
    notice_key: str,
    kind: str,
    root_kind: str,
    title: str,
    detail: str,
    job_id: str | None = None,
    event_id: str | None = None,
    file_id: int | None = None,
    relative_path: str = "",
    repairable: bool = False,
    details: dict[str, Any] | None = None,
    now: str | None = None,
) -> str:
    timestamp = now or _now()
    existing = connection.execute(
        "SELECT id FROM external_change_notices WHERE notice_key=?",
        (str(notice_key),),
    ).fetchone()
    payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    if existing is None:
        notice_id = "EXT_" + uuid.uuid4().hex.upper()
        connection.execute(
            """INSERT INTO external_change_notices(
                   id,notice_key,kind,root_kind,job_id,event_id,file_id,
                   relative_path,title,detail,repairable,details_json,status,
                   created_at,updated_at,completed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'open', ?, ?, NULL)""",
            (
                notice_id,
                str(notice_key),
                str(kind),
                str(root_kind),
                job_id,
                event_id,
                file_id,
                str(relative_path or ""),
                str(title),
                str(detail),
                int(bool(repairable)),
                payload,
                timestamp,
                timestamp,
            ),
        )
        return notice_id

    notice_id = str(existing["id"])
    connection.execute(
        """UPDATE external_change_notices
           SET kind=?,root_kind=?,job_id=?,event_id=?,file_id=?,
               relative_path=?,title=?,detail=?,repairable=?,details_json=?,
               status='open',updated_at=?,completed_at=NULL
           WHERE id=?""",
        (
            str(kind),
            str(root_kind),
            job_id,
            event_id,
            file_id,
            str(relative_path or ""),
            str(title),
            str(detail),
            int(bool(repairable)),
            payload,
            timestamp,
            notice_id,
        ),
    )
    return notice_id


def resolve_notice_key(
    connection: Any,
    notice_key: str,
    *,
    now: str | None = None,
) -> None:
    timestamp = now or _now()
    connection.execute(
        """UPDATE external_change_notices
           SET status='resolved',updated_at=?,completed_at=?
           WHERE notice_key=? AND status='open'""",
        (timestamp, timestamp, str(notice_key)),
    )


def get_external_notice(database_path: Path, notice_id: str) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM external_change_notices WHERE id=?",
            (str(notice_id),),
        ).fetchone()
    if row is None:
        raise ExternalChangeError("Hinweis wurde nicht gefunden.")
    result = dict(row)
    try:
        result["details"] = json.loads(str(result.pop("details_json") or "{}"))
    except json.JSONDecodeError:
        result["details"] = {}
    result["repairable"] = bool(result.get("repairable"))
    return result


def dismiss_external_notice(database_path: Path, notice_id: str) -> dict[str, Any]:
    timestamp = _now()
    with database_connection(database_path) as connection:
        cursor = connection.execute(
            """UPDATE external_change_notices
               SET status='dismissed',updated_at=?,completed_at=?
               WHERE id=? AND status='open'""",
            (timestamp, timestamp, str(notice_id)),
        )
        if int(cursor.rowcount or 0) != 1:
            row = connection.execute(
                "SELECT id FROM external_change_notices WHERE id=?",
                (str(notice_id),),
            ).fetchone()
            if row is None:
                raise ExternalChangeError("Hinweis wurde nicht gefunden.")
    return get_external_notice(database_path, notice_id)


def repair_external_notice(
    database_path: Path,
    notice_id: str,
    *,
    central_root: Path,
    library_work_root: Path,
) -> dict[str, Any]:
    notice = get_external_notice(database_path, notice_id)
    if str(notice.get("status")) != "open":
        return notice
    if not bool(notice.get("repairable")):
        raise ExternalChangeError(
            "Diese externe Änderung kann aus Sicherheitsgründen nicht automatisch zurückgesetzt werden."
        )

    details = dict(notice.get("details") or {})
    root_kind = str(notice.get("root_kind") or "")
    if root_kind == "central_stock":
        root = central_root.resolve(strict=False)
    elif root_kind == "shared_workspace":
        root = library_work_root.resolve(strict=False)
    else:
        raise ExternalChangeError(
            "Archivänderungen werden nicht automatisch geschrieben. "
            "Bitte die angezeigte Datei im Archiv manuell zurückverschieben."
        )

    observed_rel = _safe_relative(details.get("observed_relative_path"))
    expected_rel = _safe_relative(details.get("expected_relative_path"))
    source = (root / observed_rel).resolve(strict=False)
    target = (root / expected_rel).resolve(strict=False)
    try:
        source.relative_to(root)
        target.relative_to(root)
    except ValueError as exc:
        raise ExternalChangeError("Reparaturpfad verlässt den verwalteten Bestand.") from exc

    expected_size = int(details.get("size_bytes") or 0)
    expected_sha = str(details.get("sha256") or "")
    if not source.is_file():
        raise ExternalChangeError("Die verschobene Datei wurde am beobachteten Ort nicht mehr gefunden.")
    if target.exists() or target.is_symlink():
        raise ExternalChangeError("Der ursprüngliche Zielpfad ist bereits belegt.")

    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        move_verified_no_overwrite(
            source,
            target,
            expected_size=expected_size,
            expected_sha256=expected_sha,
        )
    except SafeTransferError as error:
        raise ExternalChangeError(str(error)) from error

    timestamp = _now()
    with database_connection(database_path) as connection:
        if str(notice.get("kind")) == "central_file_misplaced" and notice.get("file_id") is not None:
            connection.execute(
                "DELETE FROM central_missing_file_observations WHERE file_id=?",
                (int(notice["file_id"]),),
            )
        if str(notice.get("kind")) == "cross_event_move" and notice.get("file_id") is not None:
            connection.execute(
                """DELETE FROM event_missing_file_observations
                   WHERE event_id=? AND root_kind=? AND file_id=?""",
                (
                    str(notice.get("event_id") or ""),
                    root_kind,
                    int(notice["file_id"]),
                ),
            )
        connection.execute(
            """UPDATE external_change_notices
               SET status='repaired',updated_at=?,completed_at=?
               WHERE id=?""",
            (timestamp, timestamp, str(notice_id)),
        )
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'external_change_repaired','external_change',?,?,?)""",
            (
                notice.get("job_id"),
                str(notice_id),
                json.dumps(
                    {
                        "kind": notice.get("kind"),
                        "observed_relative_path": observed_rel.as_posix(),
                        "expected_relative_path": expected_rel.as_posix(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                timestamp,
            ),
        )
    return get_external_notice(database_path, notice_id)
