"""Queue and per-event receipts for the Archive page's two bulk actions."""

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

from app.archive_transfer import ArchiveVerificationError
from app.database import database_connection
from app.root_operations import RootOperationError
from app.ssd_release import SsdReleaseError, release_event_ssd, verify_archive_for_release

ACTIVE = {"queued", "running"}
NO_EVENTS = "Keine geeigneten Ereignisse zur Archivprüfung."
NO_VERIFIED = "Keine Arbeitsbereiche aus dieser Prüfung können freigegeben werden. Prüfe die Ereignisse erneut."
INELIGIBLE = "Das Ereignis kann derzeit nicht geprüft oder freigegeben werden."
STALE = "Die Archivprüfung ist nicht mehr aktuell. Prüfe das Ereignis erneut."
INTERRUPTED = "Freigabe unterbrochen. Prüfe die verbleibenden Ereignisse und bestätige die Freigabe erneut."
RESUME_UNAVAILABLE = "Für diesen Sammelauftrag gibt es keine eindeutig zugeordnete Freigabe zur Fortsetzung."
FAILED_VERIFICATION = "Die Archivprüfung ist fehlgeschlagen. Der Arbeitsbereich wurde nicht freigegeben."
RELEASED = "Arbeitsbereich freigegeben"
VERIFIED = "Vollständig geprüft"


# Apply the same release prerequisites to the queue and to the actual
# deletion, with additional batch exclusions for an open change or recovery.
_CANDIDATES = """
    SELECT e.job_id, e.id AS event_id, e.name AS event_name,
           (SELECT v.id FROM event_archive_verifications v
            WHERE v.event_id=e.id AND v.job_id=e.job_id
            ORDER BY v.created_at DESC, v.id DESC LIMIT 1) AS latest_proof
      FROM events e
     WHERE e.status='applied' AND e.parent_event_id IS NULL
       AND coalesce(e.resort_required, 0)=0 AND coalesce(e.pending_delete, 0)=0
       AND NOT EXISTS (SELECT 1 FROM event_ssd_releases r
                       WHERE r.event_id=e.id AND r.job_id=e.job_id AND r.status='completed')
       AND NOT EXISTS (SELECT 1 FROM event_reapply_removed_families p
                       WHERE p.job_id=e.job_id AND p.target_event_id IS NULL)
       AND NOT EXISTS (SELECT 1 FROM event_mutations m WHERE m.job_id=e.job_id
                       AND m.status IN ('pending_reassignment','pending_apply','manual_archive'))
       AND NOT EXISTS (SELECT 1 FROM event_change_requests c WHERE c.event_id=e.id
                       AND c.status NOT IN ('aenderbar_archiviert','aenderbar_abgebrochen'))
       AND NOT EXISTS (SELECT 1 FROM archive_recovery_incidents a
                       WHERE a.event_id=e.id AND a.status='manual_review')
       AND NOT EXISTS (SELECT 1 FROM ssd_release_tasks t WHERE t.event_id=e.id
                       AND t.status IN ('queued','running'))
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _items(connection, batch_id):
    return [dict(row) for row in connection.execute(
        """SELECT item.*, proof.file_count, proof.verified_file_count,
                  proof.missing_file_count, proof.mismatched_file_count
           FROM archive_batch_items item LEFT JOIN event_archive_verifications proof
                ON proof.id=item.verification_id
           WHERE item.batch_id=? ORDER BY item.position""", (batch_id,),
    )]


def _eligible(connection, job_id, event_id):
    return connection.execute(_CANDIDATES + " AND e.job_id=? AND e.id=?", (job_id, event_id)).fetchone()


def require_current_proof(connection, job_id, event_id, verification_id, archive_root, previous_release_checks=()):
    event = _eligible(connection, job_id, event_id)
    if event is None:
        raise SsdReleaseError(INELIGIBLE)
    proof = connection.execute(
        """SELECT status,archive_root FROM event_archive_verifications
           WHERE id=? AND job_id=? AND event_id=?""", (verification_id, job_id, event_id),
    ).fetchone()
    if (event["latest_proof"] not in (verification_id, *previous_release_checks) or not proof or proof["status"] != "verified"
            or proof["archive_root"] != str(archive_root.resolve())):
        raise SsdReleaseError(STALE)


def _release_items(connection, batch_id):
    return connection.execute(
        """SELECT e.job_id,e.event_id,e.event_name,i.verification_id
             FROM (""" + _CANDIDATES + """) e JOIN archive_batch_items i
               ON i.job_id=e.job_id AND i.event_id=e.event_id
             JOIN event_archive_verifications v ON v.id=i.verification_id
            WHERE i.batch_id=? AND i.status='verified' AND v.id=e.latest_proof AND v.status='verified'
            ORDER BY i.position""", (batch_id,),
    ).fetchall()


def _latest(connection):
    return connection.execute(
        "SELECT * FROM archive_batches ORDER BY created_at DESC,id DESC LIMIT 1",
    ).fetchone()


def enqueue(database, kind, verification_batch_id=None):
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = _latest(connection)
        if previous and previous["status"] in ACTIVE:
            if previous["kind"] != kind or previous["verification_batch_id"] != verification_batch_id:
                raise ValueError("Ein Archiv-Sammelauftrag läuft bereits.")
            return _describe(connection, previous)
        if kind == "release":
            if previous and previous["kind"] == kind and previous["verification_batch_id"] == verification_batch_id:
                return _describe(connection, previous)
            if not previous or previous["kind"] != "verify" or previous["id"] != verification_batch_id:
                raise ValueError(NO_VERIFIED)
            events = _release_items(connection, verification_batch_id)
        else:
            events = connection.execute(_CANDIDATES + " ORDER BY e.created_at DESC,e.id").fetchall()
        if not events:
            raise ValueError(NO_VERIFIED if kind == "release" else NO_EVENTS)
        batch_id, now = uuid4().hex, _now()
        connection.execute(
            "INSERT INTO archive_batches VALUES (?, ?, ?, 'queued', ?, ?)",
            (batch_id, kind, verification_batch_id, now, now),
        )
        connection.executemany(
            """INSERT INTO archive_batch_items (batch_id,position,job_id,event_id,event_name,status,verification_id)
               VALUES (?, ?, ?, ?, ?, 'queued', ?)""",
            ((batch_id, position, event["job_id"], event["event_id"], event["event_name"],
              event["verification_id"] if kind == "release" else None) for position, event in enumerate(events)),
        )
        return _describe(connection, _latest(connection))


def _describe(connection, row, *, details=True):
    batch = dict(row)
    counts = dict(connection.execute(
        "SELECT status,count(*) FROM archive_batch_items WHERE batch_id=? GROUP BY status", (row["id"],),
    ).fetchall())
    total = sum(counts.values())
    completed = total - sum(counts.get(state, 0) for state in ACTIVE)
    successes = counts.get("verified", 0) + counts.get("released", 0)
    batch.update(total=total, processed=completed, successful=successes,
                 progress_percent=round(100 * completed / total) if total else 0)
    if details:
        batch["items"] = _items(connection, row["id"])
    return batch


def dashboard(database, batch_id=None):
    with database_connection(database) as connection:
        latest = _latest(connection)
        row = latest if batch_id is None else connection.execute(
            "SELECT * FROM archive_batches WHERE id=?", (batch_id,),
        ).fetchone()
        release_count = len(_release_items(connection, latest["id"])) if (
            latest and latest["kind"] == "verify" and latest["status"] not in ACTIVE
        ) else 0
        candidates = connection.execute("SELECT count(*) FROM (" + _CANDIDATES + ")").fetchone()[0]
        return {"batch": _describe(connection, row) if row else None,
                "active": bool(latest and latest["status"] in ACTIVE), "candidate_count": candidates,
                "active_kind": latest["kind"] if latest and latest["status"] in ACTIVE else None,
                "release_ready_count": release_count, "verification_batch_id": latest["id"] if release_count else None}


def visible_batches(database, limit=8):
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with database_connection(database) as connection:
        return [_describe(connection, row, details=False) for row in connection.execute(
            """SELECT * FROM archive_batches
               WHERE status!='completed' OR updated_at>=?
               ORDER BY (status='completed'),created_at DESC LIMIT ?""", (cutoff, limit),
        )]


def _finish_item(connection, item, state, message, verification_id=None):
    batch_id, position = item["batch_id"], item["position"]
    connection.execute(
        """UPDATE archive_batch_items SET status=?,message=?,verification_id=coalesce(?,verification_id)
           WHERE batch_id=? AND position=? AND status='running'""",
        (state, message, verification_id, batch_id, position),
    )
    progress = {row[0] for row in connection.execute(
        "SELECT DISTINCT status FROM archive_batch_items WHERE batch_id=?", (batch_id,),
    )}
    status = "running" if progress & ACTIVE else "failed" if progress & {"failed", "skipped"} else "completed"
    connection.execute("UPDATE archive_batches SET status=?,updated_at=? WHERE id=?", (status, _now(), batch_id))


def _new_proof_id():
    return "ARCHIVE_" + uuid4().hex.upper()


def _record_release_check(connection, item):
    key = item["batch_id"], item["position"]
    stored = connection.execute(
        "SELECT release_checks_json FROM archive_batch_items WHERE batch_id=? AND position=?", key,
    ).fetchone()
    previous = tuple(json.loads(stored[0]))
    proof_id = _new_proof_id()
    connection.execute(
        "UPDATE archive_batch_items SET release_checks_json=? WHERE batch_id=? AND position=?",
        (json.dumps((*previous, proof_id)), *key),
    )
    return proof_id, previous


def process_next(database, workspace, archive):
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        batch = _latest(connection)
        if batch is None or batch["status"] not in ACTIVE:
            return False
        item = connection.execute(
            """SELECT * FROM archive_batch_items
               WHERE batch_id=? AND status='queued'
                 AND NOT EXISTS (SELECT 1 FROM archive_batch_items WHERE batch_id=? AND status='running')
               ORDER BY position LIMIT 1""", (batch["id"], batch["id"]),
        ).fetchone()
        if item is None:
            return False
        verification_id = item["verification_id"]
        if batch["kind"] == "verify" and verification_id is None:
            verification_id = _new_proof_id()
        release_check = _record_release_check(connection, item)[0] if batch["kind"] == "release" else None
        connection.execute(
            "UPDATE archive_batch_items SET status='running',verification_id=? WHERE batch_id=? AND position=?",
            (verification_id, batch["id"], item["position"]),
        )
        connection.execute("UPDATE archive_batches SET status='running',updated_at=? WHERE id=?", (_now(), batch["id"]))
        eligible = _eligible(connection, item["job_id"], item["event_id"])

    if eligible is None:
        state, message = "skipped", INELIGIBLE
    elif batch["kind"] == "verify" and item["verification_id"] and eligible["latest_proof"] != verification_id:
        state, message = "skipped", STALE
    else:
        try:
            target = (database, workspace(), archive, item["job_id"], item["event_id"])
            if batch["kind"] == "verify":
                result = verify_archive_for_release(*target, resume_pending_release=True, verification_id=verification_id)
                state, message = ("verified", VERIFIED) if result.get("verified") else ("failed", FAILED_VERIFICATION)
            else:
                outcome = release_event_ssd(*target, required_verification_id=item["verification_id"],
                                            batch_id=batch["id"], verification_id=release_check)
                state, message = ("released", RELEASED) if outcome["released"] else ("failed", outcome["message"])
        except (ArchiveVerificationError, SsdReleaseError, RootOperationError, OSError, ValueError) as error:
            state, message = "failed", str(error)
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _finish_item(connection, item, state, message, verification_id)
    return True


def resumable_release(database, library_id, batch_id, reservations):
    """Match the exact abandoned file operation and its previously confirmed batch item."""
    if len(reservations) != 1:
        return None
    record = reservations[0]
    ids = record.get("ids", {})
    if (record["live"] or not record["qualified"] or record.get("kind") != "ssd"
            or record.get("library") != library_id or record.get("database") != str(database.absolute())
            or set(ids) != {"batch_id", "job_id", "event_id", "function"}
            or ids["function"] != "app.ssd_release.release_event_ssd" or ids["batch_id"] != batch_id):
        return None
    with database_connection(database) as connection:
        batch = _latest(connection)
        if not batch or batch["id"] != batch_id or batch["kind"] != "release":
            return None
        item = connection.execute(
            """SELECT * FROM archive_batch_items WHERE batch_id=? AND job_id=? AND event_id=?
               AND status IN ('running','failed','interrupted') AND verification_id IS NOT NULL""",
            (batch_id, ids["job_id"], ids["event_id"]),
        ).fetchone()
    return (record["path"], dict(item)) if item else None


def resume_release(database, workspace, archive, item):
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        proof_id, previous = _record_release_check(connection, item)
        connection.execute(
            "UPDATE archive_batch_items SET status='running',message=NULL WHERE batch_id=? AND position=?",
            (item["batch_id"], item["position"]),
        )
        connection.execute("UPDATE archive_batches SET status='running',updated_at=? WHERE id=?",
                           (_now(), item["batch_id"]))
    # The existing file operation reacquires its original reservation and
    # checks all originals again. Older in-flight proof IDs only identify
    # this batch's attempts; they never substitute for the fresh SHA checks.
    release_event_ssd(database, workspace, archive, item["job_id"], item["event_id"],
                      required_verification_id=item["verification_id"], batch_id=item["batch_id"],
                      verification_id=proof_id, previous_release_checks=previous)
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _finish_item(connection, item, "released", RELEASED)
        connection.execute(
            "UPDATE archive_batches SET status='interrupted' WHERE id=? AND status='running'", (item["batch_id"],),
        )


def recover_batches(database):
    """Lost release watches require a new, explicit verification and release."""
    with database_connection(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        batches = connection.execute("SELECT * FROM archive_batches WHERE status='running'").fetchall()
        for batch in batches:
            items = connection.execute(
                "SELECT * FROM archive_batch_items WHERE batch_id=? AND status='running'", (batch["id"],),
            ).fetchall()
            for item in items:
                done = connection.execute(
                    """SELECT 1 FROM event_ssd_releases
                       WHERE job_id=? AND event_id=? AND status='completed'""",
                    (item["job_id"], item["event_id"]),
                ).fetchone()
                if batch["kind"] == "verify":
                    proof = connection.execute(
                        "SELECT status FROM event_archive_verifications WHERE id=?", (item["verification_id"],),
                    ).fetchone()
                    if proof and proof["status"] == "failed":
                        _finish_item(connection, item, "failed", FAILED_VERIFICATION)
                        continue
                    if proof and proof["status"] == "verified" and done:
                        _finish_item(connection, item, "verified", VERIFIED)
                        continue
                    # Reuse a fully persisted proof after a crash between
                    # verification and recording its outcome in the batch.
                    connection.execute(
                        "UPDATE archive_batch_items SET status='queued',verification_id=? WHERE batch_id=? AND position=?",
                        (item["verification_id"] if proof and proof["status"] == "verified" else None,
                         batch["id"], item["position"]),
                    )
                    continue
                _finish_item(connection, item, "released" if done else "interrupted", RELEASED if done else INTERRUPTED)
            if batch["kind"] == "release" and any(item["status"] in ACTIVE | {"interrupted"} for item in _items(connection, batch["id"])):
                connection.execute("UPDATE archive_batches SET status='interrupted',updated_at=? WHERE id=?",
                                   (_now(), batch["id"]))
