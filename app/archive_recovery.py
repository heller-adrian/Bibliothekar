"""Non-destructive escape hatch for an unrecoverable manual archive reversal.

An emergency stop is NOT a successful reversal, deletion, file release or
reassignment. It quarantines the event and preserves evidence until a separate
full original-state verification permits its controlled reopening.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

from app.database import database_connection
from app.archive_reversal import (
    _request_context, _safe_archive_path, _matches,
    _manifest_path, _read_json, reversal_active,
    verify_archive_reversal, ArchiveReversalError,
)

FORCE_PHRASE = "NOTFALLABBRUCH"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def assert_not_quarantined(connection: Any, event_id: str) -> None:
    row = connection.execute(
        """SELECT id FROM archive_recovery_incidents
           WHERE event_id=? AND status='manual_review' LIMIT 1""",
        (event_id,),
    ).fetchone()
    if row is not None:
        raise ValueError(
            "Dieses Archivereignis ist wegen eines erzwungenen Abbruchs zur "
            "manuellen Klärung gesperrt. Originalbestand prüfen, fehlende "
            "Dateien klären und den Wiederherstellungsfall zuerst abschließen."
        )


def read_recovery_incident(db: Path, event_id: str) -> dict[str, Any] | None:
    with database_connection(db) as connection:
        row = connection.execute(
            """SELECT * FROM archive_recovery_incidents
               WHERE event_id=? AND status='manual_review'
               ORDER BY created_at DESC LIMIT 1""", (event_id,)
        ).fetchone()
    if row is None:
        return None
    item = dict(row)
    item["snapshot"] = json.loads(item.pop("snapshot_json"))
    return item


def _snapshot(db: Path, archive_root: Path, cr_id: str) -> dict[str, Any]:
    cr, _event, rows = _request_context(db, cr_id)
    files = []
    for row in rows:
        if not str(row.get("expected_sha256") or ""):
            continue
        old_rel = str(row.get("old_path") or "")
        new_rel = str(row.get("new_path") or "")
        expected_sha = str(row["expected_sha256"])
        expected_size = int(row.get("expected_size_bytes") or 0)
        locations = []
        for rel in dict.fromkeys([old_rel, new_rel]):
            if not rel:
                continue
            try:
                if _matches(_safe_archive_path(archive_root, rel), expected_size, expected_sha):
                    locations.append(rel)
            except (OSError, ArchiveReversalError):
                pass
        files.append({
            "file_id": row.get("file_id"),
            "family_id": row.get("family_id"),
            "old_path": old_rel,
            "new_path": new_rel,
            "expected_size_bytes": expected_size,
            "expected_sha256": expected_sha,
            "confirmed_archive_paths": locations,
            "missing_from_known_paths": not bool(locations),
        })
    try:
        verification = verify_archive_reversal(db, archive_root, Path(str(cr["working_path"])), cr_id)
    except Exception:
        # The caller provides workspace separately for the authoritative result.
        verification = None
    return {"files": files, "request_status": cr["status"], "verification": verification}


def force_stop_reversal(
    db: Path, archive_root: Path, workspace: Path, cr_id: str,
    *, phrase: str, reason: str,
) -> dict[str, Any]:
    if phrase != FORCE_PHRASE:
        raise ValueError("Zur Bestätigung exakt NOTFALLABBRUCH eingeben.")
    if len(reason.strip()) < 8:
        raise ValueError("Bitte den Grund für den Notfallabbruch beschreiben.")
    if not reversal_active(workspace, cr_id):
        raise ValueError("Für diesen Auftrag ist kein Rückänderungsauftrag aktiv.")
    cr, _event, rows = _request_context(db, cr_id)
    if str(cr["status"]) != "aenderbar_bestaetigt":
        raise ValueError("Nur ein bestätigter aktiver Archivauftrag kann notfallmäßig beendet werden.")

    # Read-only live evidence is gathered before any DB status transition.
    observed = []
    for row in rows:
        sha = str(row.get("expected_sha256") or "")
        size = int(row.get("expected_size_bytes") or 0)
        paths = {}
        for name in ("old_path", "new_path"):
            rel = str(row.get(name) or "")
            if not rel or not sha:
                continue
            try:
                paths[name] = {"path": rel, "matches_sha256": _matches(
                    _safe_archive_path(archive_root, rel), size, sha
                )}
            except (ArchiveReversalError, OSError):
                paths[name] = {"path": rel, "matches_sha256": False}
        observed.append({"review_kind": row.get("review_kind"),
                         "file_id": row.get("file_id"),
                         "family_id": row.get("family_id"),
                         "expected_sha256": sha,
                         "expected_size_bytes": size, "locations": paths})
    try:
        verification = verify_archive_reversal(db, archive_root, workspace, cr_id)
    except Exception as error:
        verification = {"complete": False, "problems": [
            {"kind": "verification_error", "message": str(error)}
        ]}
    try:
        manifest = _read_json(_manifest_path(workspace, cr_id))
    except Exception as error:
        manifest = {"unreadable_manifest": str(error)}
    now = _now()
    incident_id = "INC_" + uuid.uuid4().hex
    snapshot = {
        "manifest": manifest, "verification": verification,
        "file_evidence": observed, "reason": reason.strip(),
        "note": "Quarantäne: NICHT als erfolgreich wiederhergestellt behandeln.",
    }
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        current = connection.execute(
            "SELECT status FROM event_change_requests WHERE id=?", (cr_id,)
        ).fetchone()
        if current is None or str(current["status"]) != "aenderbar_bestaetigt":
            raise ValueError("Der Änderungsauftrag hat sich zwischenzeitlich verändert.")
        assert_not_quarantined(connection, str(cr["event_id"]))
        connection.execute(
            """INSERT INTO archive_recovery_incidents
               (id,change_request_id,event_id,job_id,status,reason,
                snapshot_json,created_at)
               VALUES(?,?,?,?,'manual_review',?,?,?)""",
            (incident_id, cr_id, cr["event_id"], cr["job_id"], reason.strip(),
             json.dumps(snapshot, ensure_ascii=False), now),
        )
        connection.execute(
            """UPDATE event_change_requests SET status='aenderbar_abgebrochen',
               cancelled_at=?,updated_at=? WHERE id=?""", (now, now, cr_id)
        )
        connection.execute(
            """INSERT INTO audit_log(job_id,action,entity_type,entity_id,
               details_json,created_at) VALUES(?,'archive_emergency_stop','event',?,?,?)""",
            (cr["job_id"], cr["event_id"],
             json.dumps({"incident_id": incident_id, "reason": reason.strip()},
                        ensure_ascii=False), now),
        )
    return {
        "status": "manual_review", "incident_id": incident_id,
        "event_id": str(cr["event_id"]),
        "change_request_id": cr_id,
        "verification_complete": bool(verification.get("complete")),
        "message": ("Rückänderungsauftrag beendet. Archiv und Datenbank wurden "
                    "NICHT als konsistent bestätigt. Das Ereignis bleibt bis "
                    "zur gesonderten Bestandsklärung gesperrt."),
    }


def resolve_recovery_incident(
    db: Path, archive_root: Path, workspace: Path, event_id: str,
) -> dict[str, Any]:
    incident = read_recovery_incident(db, event_id)
    if incident is None:
        raise ValueError("Kein offener Wiederherstellungsfall gefunden.")
    cr_id = str(incident["change_request_id"])
    verification = verify_archive_reversal(db, archive_root, workspace, cr_id)
    if not verification["complete"]:
        return {"resolved": False, "problems": verification["problems"],
                "message": "Originalzustand weiterhin nicht vollständig geprüft."}
    with database_connection(db) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """UPDATE archive_recovery_incidents
               SET status='resolved',resolved_at=? WHERE id=? AND status='manual_review'""",
            (_now(), incident["id"]),
        )
    # Cleanup deliberately separate: do not make success dependent on removing
    # old helper files; preserves evidence until operator decides to clean it.
    return {"resolved": True, "problems": [],
            "message": "Originalarchiv verifiziert; Ereignis wieder bearbeitbar."}
