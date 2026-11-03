from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

from app.database import database_connection
from app.safe_transfer import SafeTransferError, move_verified_no_overwrite, sha256_file


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


def _root_for_kind(
    root_kind: str,
    *,
    central_root: Path,
    library_work_root: Path,
) -> Path:
    if root_kind == "central_stock":
        return central_root.resolve(strict=False)
    if root_kind == "shared_workspace":
        return library_work_root.resolve(strict=False)
    raise ExternalChangeError(
        "Archivänderungen werden nicht automatisch geschrieben. "
        "Bitte die angezeigte Datei im Archiv manuell korrigieren."
    )


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
    action_required: bool = False,
    group_key: str = "",
    details: dict[str, Any] | None = None,
    now: str | None = None,
) -> str:
    timestamp = now or _now()
    payload = json.dumps(details or {}, ensure_ascii=False, sort_keys=True)
    existing = connection.execute(
        """SELECT id,status,details_json,acknowledged_at,action_required
           FROM external_change_notices WHERE notice_key=?""",
        (str(notice_key),),
    ).fetchone()

    if existing is None:
        notice_id = "EXT_" + uuid.uuid4().hex.upper()
        connection.execute(
            """INSERT INTO external_change_notices(
                   id,notice_key,kind,root_kind,job_id,event_id,file_id,
                   relative_path,title,detail,repairable,details_json,status,
                   created_at,updated_at,completed_at,
                   action_required,acknowledged_at,group_key)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'open', ?, ?, NULL, ?, NULL, ?)""",
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
                int(bool(action_required)),
                str(group_key or ""),
            ),
        )
        return notice_id

    notice_id = str(existing["id"])
    prior_status = str(existing["status"] or "")
    same_payload = str(existing["details_json"] or "{}") == payload

    # Ein bereits weggeklickter reiner Hinweis bleibt erledigt, solange genau
    # derselbe Zustand erneut beobachtet wird. Echte Konsistenzfehler bleiben
    # dagegen offen; ein neuer/geänderter Zustand öffnet den Dialog erneut.
    if (
        not action_required
        and prior_status == "dismissed"
        and same_payload
    ):
        return notice_id

    acknowledged = (
        existing["acknowledged_at"]
        if (
            action_required
            and prior_status == "open"
            and same_payload
            and int(existing["action_required"] or 0) == 1
        )
        else None
    )
    connection.execute(
        """UPDATE external_change_notices
           SET kind=?,root_kind=?,job_id=?,event_id=?,file_id=?,
               relative_path=?,title=?,detail=?,repairable=?,details_json=?,
               status='open',updated_at=?,completed_at=NULL,
               action_required=?,acknowledged_at=?,group_key=?
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
            int(bool(action_required)),
            acknowledged,
            str(group_key or ""),
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
    result["action_required"] = bool(result.get("action_required"))
    result["acknowledged"] = bool(result.get("acknowledged_at"))
    return result


def list_external_change_state(database_path: Path) -> dict[str, Any]:
    with database_connection(database_path) as connection:
        rows = [
            dict(row)
            for row in connection.execute(
                """SELECT * FROM external_change_notices
                   WHERE status='open'
                   ORDER BY action_required DESC,created_at,id"""
            ).fetchall()
        ]

    notices: list[dict[str, Any]] = []
    for row in rows:
        try:
            details = json.loads(str(row.pop("details_json") or "{}"))
        except json.JSONDecodeError:
            details = {}
        row["details"] = details
        row["repairable"] = bool(row.get("repairable"))
        row["action_required"] = bool(row.get("action_required"))
        row["acknowledged"] = bool(row.get("acknowledged_at"))
        notices.append(row)

    required = [row for row in notices if row["action_required"]]
    unseen_required = [row for row in required if not row["acknowledged"]]
    informational = [row for row in notices if not row["action_required"]]
    unseen_info = [row for row in informational if not row["acknowledged"]]

    return {
        "required": required,
        "required_count": len(required),
        "unseen_required": unseen_required,
        "unseen_required_count": len(unseen_required),
        "informational": informational,
        "informational_count": len(informational),
        "unseen_informational": unseen_info,
        "unseen_informational_count": len(unseen_info),
    }


def acknowledge_external_notices(
    database_path: Path,
    notice_ids: list[str],
) -> dict[str, Any]:
    ids = [str(value) for value in notice_ids if str(value)]
    if not ids:
        return list_external_change_state(database_path)
    timestamp = _now()
    placeholders = ",".join("?" for _ in ids)
    with database_connection(database_path) as connection:
        rows = connection.execute(
            f"""SELECT id,action_required,details_json FROM external_change_notices
                WHERE id IN ({placeholders}) AND status='open'""",
            tuple(ids),
        ).fetchall()
        for row in rows:
            try:
                details = json.loads(str(row["details_json"] or "{}"))
            except json.JSONDecodeError:
                details = {}
            if (
                int(row["action_required"] or 0)
                and bool(details.get("force_repair"))
            ):
                # Zwingende Konsistenzfehler dürfen nicht per „Ignorieren“
                # versteckt werden.
                continue
            if int(row["action_required"] or 0):
                connection.execute(
                    """UPDATE external_change_notices
                       SET acknowledged_at=?,updated_at=?
                       WHERE id=?""",
                    (timestamp, timestamp, str(row["id"])),
                )
            else:
                connection.execute(
                    """UPDATE external_change_notices
                       SET status='dismissed',acknowledged_at=?,
                           updated_at=?,completed_at=?
                       WHERE id=?""",
                    (
                        timestamp,
                        timestamp,
                        timestamp,
                        str(row["id"]),
                    ),
                )
    return list_external_change_state(database_path)


def dismiss_external_notice(database_path: Path, notice_id: str) -> dict[str, Any]:
    acknowledge_external_notices(database_path, [notice_id])
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
    observed_kind = str(
        details.get("observed_root_kind")
        or notice.get("root_kind")
        or ""
    )
    expected_kind = str(
        details.get("expected_root_kind")
        or notice.get("root_kind")
        or ""
    )
    source_root = _root_for_kind(
        observed_kind,
        central_root=central_root,
        library_work_root=library_work_root,
    )
    target_root = _root_for_kind(
        expected_kind,
        central_root=central_root,
        library_work_root=library_work_root,
    )

    observed_rel = _safe_relative(details.get("observed_relative_path"))
    expected_rel = _safe_relative(details.get("expected_relative_path"))
    source = (source_root / observed_rel).resolve(strict=False)
    target = (target_root / expected_rel).resolve(strict=False)
    try:
        source.relative_to(source_root)
        target.relative_to(target_root)
    except ValueError as exc:
        raise ExternalChangeError("Reparaturpfad verlässt den verwalteten Bestand.") from exc

    expected_size = int(details.get("size_bytes") or 0)
    expected_sha = str(details.get("sha256") or "")

    source_exists = source.is_file()
    target_exists = target.is_file()
    already_restored = False

    # 0.41.4: Ein Nutzer darf eine fehlgeschlagene automatische Reparatur
    # jederzeit selbst im Finder/SMB erledigen. Beim erneuten Prüfen wird ein
    # bereits am exakten Sollort liegender, byte-identischer Bestand deshalb
    # als erfolgreich wiederhergestellt übernommen.
    if not source_exists and target_exists:
        if expected_size and int(target.stat().st_size) != expected_size:
            raise ExternalChangeError(
                "Am erwarteten Sollort liegt bereits eine Datei mit abweichender Größe."
            )
        if expected_sha and sha256_file(target) != expected_sha:
            raise ExternalChangeError(
                "Am erwarteten Sollort liegt bereits eine Datei mit abweichender SHA-256-Summe."
            )
        already_restored = True
    elif not source_exists:
        raise ExternalChangeError(
            "Die verschobene Datei wurde am beobachteten Ort nicht mehr gefunden "
            "und liegt auch nicht am erwarteten Sollort."
        )
    elif target.exists() or target.is_symlink():
        raise ExternalChangeError(
            "Der erwartete Sollort ist bereits belegt. Bitte die dortige Datei prüfen; "
            "Bibliothekar überschreibt niemals vorhandene Dateien."
        )
    else:
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
        if notice.get("file_id") is not None:
            file_id = int(notice["file_id"])
            connection.execute(
                "DELETE FROM central_missing_file_observations WHERE file_id=?",
                (file_id,),
            )
            connection.execute(
                "DELETE FROM event_missing_file_observations WHERE file_id=?",
                (file_id,),
            )
            connection.execute(
                """UPDATE files
                   SET current_relative_path=?,
                       current_root_kind=?,
                       updated_at=?
                   WHERE id=?""",
                (
                    expected_rel.as_posix(),
                    (
                        "shared_workspace"
                        if expected_kind == "central_stock"
                        else expected_kind
                    ),
                    timestamp,
                    file_id,
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
                        "observed_root_kind": observed_kind,
                        "expected_root_kind": expected_kind,
                        "observed_relative_path": observed_rel.as_posix(),
                        "expected_relative_path": expected_rel.as_posix(),
                        "already_restored_manually": already_restored,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                timestamp,
            ),
        )
    return get_external_notice(database_path, notice_id)



def accept_external_file_rename(
    database_path: Path,
    notice_id: str,
    *,
    library_work_root: Path,
) -> dict[str, Any]:
    """Explicitly adopt a hash-verified *filename* rename in an applied event.

    No archive writes, no new directory roles, no change to camera bytes.
    The verified filesystem IST is committed only after a human action.
    """
    from app.root_operations import validate_active_roots
    from app.event_document_sync import queue_event_document_sync
    import stat

    notice = get_external_notice(database_path, notice_id)
    if notice.get("status") != "open" or notice.get("kind") != "file_rename":
        raise ExternalChangeError("Kein offener Auftrag für eine Dateiumbenennung.")
    if notice.get("root_kind") != "shared_workspace":
        raise ExternalChangeError(
            "Archivnamen dürfen nur über den manuellen Archivprüfweg geändert werden."
        )
    details = dict(notice.get("details") or {})
    expected = _safe_relative(details.get("expected_relative_path"))
    observed = _safe_relative(details.get("observed_relative_path"))
    if expected.parent != observed.parent or expected.name == observed.name:
        raise ExternalChangeError(
            "Nur eine reine Dateiumbenennung kann hier übernommen werden. "
            "Kombinierte Verschiebungen bitte gesondert prüfen."
        )
    root = library_work_root.resolve(strict=True)
    old_candidate, new_candidate = root / expected, root / observed
    validate_active_roots()
    if old_candidate.exists() or old_candidate.is_symlink():
        raise ExternalChangeError(
            "Der ursprüngliche Name ist wieder belegt. Bitte Bestand erneut prüfen."
        )
    if new_candidate.is_symlink():
        raise ExternalChangeError("Symbolische Links sind als Kameradatei unzulässig.")
    source = new_candidate.resolve(strict=True)
    if not source.is_relative_to(root) or not stat.S_ISREG(source.stat().st_mode):
        raise ExternalChangeError("Umbenannte Datei liegt nicht im verwalteten Bestand.")
    expected_size = int(details.get("size_bytes") or 0)
    expected_sha = str(details.get("sha256") or "")
    if (
        not expected_sha
        or source.stat().st_size != expected_size
        or sha256_file(source) != expected_sha
    ):
        raise ExternalChangeError(
            "Dateiinhalt oder Größe ist nicht mehr identisch. Erneut prüfen."
        )
    if notice.get("file_id") is None or not notice.get("event_id"):
        raise ExternalChangeError("Die eindeutige Dateizuordnung fehlt.")

    stamp = _now()
    with database_connection(database_path) as connection:
        file_id = int(notice["file_id"])
        row = connection.execute(
            """SELECT job_id,current_relative_path,current_root_kind
               FROM files WHERE id=?""", (file_id,),
        ).fetchone()
        if (
            row is None
            or str(row["current_relative_path"]) != expected.as_posix()
            or str(row["current_root_kind"]) != "shared_workspace"
        ):
            raise ExternalChangeError(
                "Die katalogisierte Datei hat sich verändert. Bitte erneut prüfen."
            )
        event_id = str(notice["event_id"])
        event = connection.execute(
            "SELECT id,job_id,status FROM events WHERE id=?", (event_id,),
        ).fetchone()
        if event is None or str(event["status"]) != "applied":
            raise ExternalChangeError("Das Ereignis ist nicht mehr im anwendbaren Zustand.")
        validate_active_roots()
        if sha256_file(source) != expected_sha:
            raise ExternalChangeError("Datei wurde während der Prüfung verändert.")
        connection.execute(
            """UPDATE files SET current_relative_path=?,updated_at=?
               WHERE id=? AND current_relative_path=?""",
            (observed.as_posix(), stamp, file_id, expected.as_posix()),
        )
        connection.execute(
            """UPDATE events SET revision=revision+1,updated_at=?,edited_at=?
               WHERE id=?""", (stamp, stamp, event_id),
        )
        revision = connection.execute(
            "SELECT revision FROM events WHERE id=?", (event_id,),
        ).fetchone()[0]
        queue_event_document_sync(
            connection, str(event["job_id"]), event_id, int(revision), now=stamp
        )
        connection.execute(
            """UPDATE external_change_notices
               SET status='resolved',updated_at=?,completed_at=?
               WHERE id=? AND status='open'""",
            (stamp, stamp, str(notice_id)),
        )
        connection.execute(
            """INSERT INTO audit_log(
                   job_id,action,entity_type,entity_id,details_json,created_at)
               VALUES (?,'manual_file_rename_accepted','file',?,?,?)""",
            (
                str(row["job_id"]), str(file_id),
                json.dumps(
                    {"old": expected.as_posix(), "new": observed.as_posix(),
                     "sha256": expected_sha}, sort_keys=True,
                ), stamp,
            ),
        )
    return get_external_notice(database_path, notice_id)

def repair_external_conflicts(
    database_path: Path,
    *,
    central_root: Path,
    library_work_root: Path,
) -> dict[str, Any]:
    state = list_external_change_state(database_path)
    repaired: list[str] = []
    skipped: list[dict[str, str]] = []
    affected_applied_events: set[str] = set()
    for notice in state["required"]:
        if not bool(notice.get("repairable")):
            skipped.append({
                "id": str(notice["id"]),
                "reason": "Archiv/RO oder nicht eindeutig automatisch reparierbar.",
                "expected_root_kind": str((notice.get("details") or {}).get("expected_root_kind") or ""),
                "expected_relative_path": str((notice.get("details") or {}).get("expected_relative_path") or ""),
                "observed_root_kind": str((notice.get("details") or {}).get("observed_root_kind") or notice.get("root_kind") or ""),
                "observed_relative_path": str((notice.get("details") or {}).get("observed_relative_path") or notice.get("relative_path") or ""),
            })
            continue
        try:
            repair_external_notice(
                database_path,
                str(notice["id"]),
                central_root=central_root,
                library_work_root=library_work_root,
            )
            repaired.append(str(notice["id"]))
            if (
                str(notice.get("event_id") or "")
                and str((notice.get("details") or {}).get("expected_root_kind") or notice.get("root_kind")) == "shared_workspace"
            ):
                affected_applied_events.add(str(notice["event_id"]))
        except ExternalChangeError as error:
            details = dict(notice.get("details") or {})
            skipped.append({
                "id": str(notice["id"]),
                "reason": str(error),
                "expected_root_kind": str(details.get("expected_root_kind") or ""),
                "expected_relative_path": str(details.get("expected_relative_path") or ""),
                "observed_root_kind": str(details.get("observed_root_kind") or notice.get("root_kind") or ""),
                "observed_relative_path": str(details.get("observed_relative_path") or notice.get("relative_path") or ""),
            })
    restored_directories: dict[str, list[str]] = {}
    if affected_applied_events:
        from app.manual_structure_undo import restore_applied_event_directories
        # Each file move was SHA-256 verified and performed without overwrite.
        # Now reconstruct the *entire* saved folder skeleton, not just a
        # moved file's parent (e.g. missing empty child Export / Sorted).
        try:
            restored_directories = restore_applied_event_directories(
                database_path, library_work_root, affected_applied_events
            )
        except (ExternalChangeError, ValueError, OSError) as error:
            skipped.append({
                "id": "directory-restoration",
                "reason": str(error),
                "expected_root_kind": "shared_workspace",
                "expected_relative_path": "",
                "observed_root_kind": "shared_workspace",
                "observed_relative_path": "",
            })
    return {
        "repaired_ids": repaired,
        "repaired_count": len(repaired),
        "restored_directories": restored_directories,
        "skipped": skipped,
        "state": list_external_change_state(database_path),
    }
