"""Sicherer Abschluss manueller Änderungen an archivierten Ereignissen.

Die Kamerabibliothek ist für diesen Workflow strikt read-only. Die App prüft
nur, ob der Benutzer die angekündigten Verschiebungen manuell korrekt
ausgeführt hat, und aktualisiert anschließend ausschließlich die Datenbank.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.database import database_connection
from app.archive_reassignment import apply_archive_reassignment_targets
from app.event_timeline import normalize_no_event_segments, replace_event_segments
from app.archive_locations import (
    ArchiveLocationError,
    archive_path_without_symlinks,
    record_family_anchor,
    record_verified_file_location,
)


class EventChangeApplyError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _safe_archive_path(archive_root: Path, relative_value: Any) -> Path:
    raw = str(relative_value or "").strip().replace("\\", "/")
    try:
        return archive_path_without_symlinks(archive_root, raw)
    except ArchiveLocationError as exc:
        raise EventChangeApplyError(str(exc)) from exc


def confirm_event_change(database_path: Path, cr_id: str) -> dict[str, Any]:
    """Markiere einen vorgeschlagenen Auftrag als bereit zur manuellen Ausführung.

    Diese Bestätigung verändert keine Datei und ist keine Behauptung, dass die
    Dateioperationen bereits erledigt wurden.
    """
    from app.event_change_request import get_event_change_request

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] != "aenderbar_vorschlagen":
        raise EventChangeApplyError(
            f"Änderungsauftrag hat Status '{cr['status']}'. Nicht bestätigbar."
        )

    now = _now()
    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE event_change_requests SET status = 'aenderbar_bestaetigt', "
            "confirmed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, cr_id),
        )
        connection.commit()

    return {
        "status": "bestaetigt",
        "change_request_id": cr_id,
        "confirmed_at": now,
        "message": "Auftrag bereit. Die Kamerabibliothek wurde nicht verändert.",
    }


def cancel_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Abort only while the original archive state is still provably intact.

    A proposal can be cancelled freely because no manual action has been
    confirmed yet. Once confirmed, every original file must still exist with
    the expected size/SHA and no distinct target path may already exist.
    """
    from app.event_change_request import get_event_change_files

    now = _now()
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT status FROM event_change_requests WHERE id = ?", (cr_id,)
        ).fetchone()
        if row is None:
            raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
        status = str(row["status"])
        if status not in ("aenderbar_vorschlagen", "aenderbar_bestaetigt"):
            raise EventChangeApplyError(
                f"Status '{status}' erlaubt keinen Abbruch."
            )

    if status == "aenderbar_bestaetigt":
        if archive_root is None:
            raise EventChangeApplyError(
                "Ein bestätigter Archivauftrag kann nur nach Prüfung des ursprünglichen Archivzustands verworfen werden."
            )
        root = archive_root.expanduser().resolve(strict=False)
        reviews = get_event_change_files(database_path, cr_id)
        if not reviews:
            raise EventChangeApplyError("Der Änderungsauftrag enthält keine Dateien.")

        for review in reviews:
            old_rel = str(review.get("old_path") or "")
            new_rel = str(review.get("new_path") or "")
            expected_size = int(review.get("expected_size_bytes") or 0)
            expected_sha = str(review.get("expected_sha256") or "").strip()
            if not expected_sha:
                raise EventChangeApplyError(
                    "Abbruch gesperrt: Für mindestens eine Archivdatei fehlt die gespeicherte SHA-256-Summe."
                )

            old_path = _safe_archive_path(root, old_rel)
            if not old_path.is_file():
                raise EventChangeApplyError(
                    "Abbruch gesperrt: Der ursprüngliche Archivzustand ist nicht mehr vollständig vorhanden."
                )
            if expected_size and int(old_path.stat().st_size) != expected_size:
                raise EventChangeApplyError(
                    "Abbruch gesperrt: Eine ursprüngliche Archivdatei hat eine abweichende Größe."
                )
            if _sha256_file(old_path) != expected_sha:
                raise EventChangeApplyError(
                    "Abbruch gesperrt: Eine ursprüngliche Archivdatei hat eine abweichende SHA-256-Summe."
                )

            action = str(review.get("action") or "")
            if action in {"move", "merge"} and new_rel and new_rel != old_rel:
                new_path = _safe_archive_path(root, new_rel)
                if new_path.exists() or new_path.is_symlink():
                    raise EventChangeApplyError(
                        "Abbruch gesperrt: Am neuen Archivpfad wurden bereits manuelle Änderungen erkannt. "
                        "Bitte zuerst den alten Archivzustand vollständig wiederherstellen."
                    )

    with database_connection(database_path) as connection:
        connection.execute(
            "UPDATE event_change_requests SET status = 'aenderbar_abgebrochen', "
            "cancelled_at = ?, updated_at = ? WHERE id = ?",
            (now, now, cr_id),
        )
        connection.commit()
    return {"status": "abgebrochen", "change_request_id": cr_id}


def verify_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path,
) -> dict[str, Any]:
    """Prüfe einen manuellen Archiv-Änderungsauftrag rein lesend."""
    from app.event_change_request import get_event_change_request, get_event_change_files

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] not in {"aenderbar_vorschlagen", "aenderbar_bestaetigt"}:
        raise EventChangeApplyError(
            f"Status '{cr['status']}' erlaubt keine Prüfung."
        )

    root = archive_root.expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        raise EventChangeApplyError("Die Kamerabibliothek ist nicht lesbar eingebunden.")

    reviews = get_event_change_files(database_path, cr_id)
    if not reviews:
        raise EventChangeApplyError("Der Änderungsauftrag enthält keine Dateien.")

    now = _now()
    results: list[dict[str, Any]] = []
    ok_count = 0
    open_reassignments = 0

    with database_connection(database_path) as connection:
        for review in reviews:
            action = str(review.get("action") or "")
            expected_size = int(review.get("expected_size_bytes") or 0)
            expected_sha = str(review.get("expected_sha256") or "").strip()
            old_rel = str(review.get("old_path") or "")
            new_rel = str(review.get("new_path") or "")

            status = "pending"
            actual_size = None
            actual_sha = None
            message = None

            if action == "delete":
                # Herausfallende Kamerafamilien werden niemals gelöscht.
                status = "needs_reassignment"
                message = "Familie fällt aus dem Ereignis heraus und muss zuerst einem Zielereignis zugeordnet werden."
                open_reassignments += 1
            elif action == "unresolved":
                status = "needs_assignment"
                message = (
                    "Diese aktuelle XMP-/Export-/Ereignisdatei lässt sich anhand "
                    "der verfügbaren Aufnahmeinformationen noch keinem eindeutigen Ziel zuordnen."
                )
                open_reassignments += 1
            elif not expected_sha:
                status = "missing_sha256"
                message = "Gespeicherte SHA-256-Summe fehlt; die Archivänderung kann nicht verifiziert werden."
            else:
                target_rel = new_rel if action == "move" else (new_rel or old_rel)
                target = _safe_archive_path(root, target_rel)
                if not target.is_file():
                    status = "missing"
                    message = "Datei fehlt am erwarteten Zielpfad."
                else:
                    actual_size = int(target.stat().st_size)
                    if expected_size and actual_size != expected_size:
                        status = "size_mismatch"
                        message = "Dateigröße weicht ab."
                    else:
                        actual_sha = _sha256_file(target)
                        if actual_sha != expected_sha:
                            status = "sha256_mismatch"
                            message = "SHA-256-Summe weicht ab."
                        else:
                            status = "verified"

                if status == "verified" and action == "move" and old_rel != new_rel:
                    old_target = _safe_archive_path(root, old_rel)
                    if old_target.exists():
                        status = "old_path_still_exists"
                        message = "Die Datei liegt zusätzlich noch am alten Pfad."

            if status == "verified":
                ok_count += 1

            table = (
                "event_change_asset_reviews"
                if str(review.get("review_kind") or "camera") == "asset"
                else "event_change_file_reviews"
            )
            connection.execute(
                f"""
                UPDATE {table}
                SET verification_status = ?, actual_size_bytes = ?, actual_sha256 = ?,
                    verified_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, actual_size, actual_sha, now, now, review["id"]),
            )
            results.append({
                "id": review["id"],
                "file_id": review.get("file_id"),
                "family_id": review.get("family_id"),
                "asset_kind": review.get("asset_kind"),
                "review_kind": review.get("review_kind", "camera"),
                "action": action,
                "old_path": old_rel,
                "new_path": new_rel,
                "status": status,
                "message": message,
            })
        connection.commit()

    complete = ok_count == len(reviews) and open_reassignments == 0
    return {
        "change_request_id": cr_id,
        "status": "verified" if complete else "incomplete",
        "complete": complete,
        "file_count": len(reviews),
        "verified_file_count": ok_count,
        "open_reassignment_count": open_reassignments,
        "files": results,
    }


def finish_event_change(
    database_path: Path,
    cr_id: str,
    archive_root: Path,
) -> dict[str, Any]:
    """Prüfe manuelle Dateiänderungen und schließe danach nur die DB ab.

    Es gibt absichtlich keinerlei mkdir/move/unlink/rmtree auf archive_root.
    """
    from app.event_change_request import get_event_change_request

    cr = get_event_change_request(database_path, cr_id)
    if cr is None:
        raise EventChangeApplyError("Änderungsauftrag nicht gefunden.")
    if cr["status"] != "aenderbar_bestaetigt":
        raise EventChangeApplyError(
            f"Status '{cr['status']}' erlaubt keinen Abschluss. Änderungen erst bestätigen."
        )

    verification = verify_event_change(database_path, cr_id, archive_root)
    if not verification["complete"]:
        raise EventChangeApplyError(
            "Die manuelle Archivänderung ist noch nicht vollständig geprüft. "
            f"{verification['verified_file_count']} von {verification['file_count']} Dateien sind korrekt; "
            f"{verification['open_reassignment_count']} Familien benötigen noch eine Neu-Zuordnung."
        )

    selected_ids = sorted({int(v) for v in json.loads(cr["selected_family_ids"] or "[]")})
    delete_event = bool(cr.get("delete_event") or 0)
    if not selected_ids and not delete_event:
        raise EventChangeApplyError("Mindestens eine Dateifamilie muss dem Ereignis zugeordnet bleiben.")

    start_date = str(cr["start_date"])
    end_date = str(cr["end_date"])
    event_kind = str(cr.get("event_kind") or "event")
    no_event_segments = []
    if event_kind == "no_event":
        try:
            no_event_segments = normalize_no_event_segments(json.loads(cr.get("no_event_segments") or "[]"))
        except Exception as exc:
            raise EventChangeApplyError("Die gespeicherten „Ohne Ereignis“-Zeitsegmente sind ungültig.") from exc
        if not no_event_segments:
            raise EventChangeApplyError("Für „Ohne Ereignis“ fehlt mindestens ein Zeitsegment.")
        parent_start = no_event_segments[0]["start_datetime"]
        parent_end = no_event_segments[-1]["end_datetime"]
    else:
        parent_start = f"{start_date}T00:00:00"
        parent_end = f"{end_date}T23:59:59"
    uses_time_range = bool(cr["uses_time_range"]) if event_kind != "no_event" else False
    try:
        child_segments = json.loads(cr.get("child_segments_json") or "[]") if event_kind == "event" else []
    except Exception as exc:
        raise EventChangeApplyError("Die gespeicherten Unterereignisse sind ungültig.") from exc
    start_time = str(cr["start_time"] or "00:00")
    end_time = str(cr["end_time"] or "23:59")
    child_start = f"{start_date}T{start_time}:00"
    child_end = f"{end_date}T{end_time}:59"
    if event_kind == 'event' and uses_time_range:
        parent_start, parent_end = child_start, child_end
    now = _now()

    with database_connection(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND job_id = ?",
            (cr["event_id"], cr["job_id"]),
        ).fetchone()
        if event is None or not event["archived_at"]:
            connection.rollback()
            raise EventChangeApplyError("Das zugrunde liegende archivierte Ereignis fehlt.")

        created_reassignment_events = apply_archive_reassignment_targets(connection, cr, now)

        if delete_event:
            verified_rows = connection.execute(
                """SELECT family_id,file_id,new_path
                   FROM event_change_file_reviews
                   WHERE change_request_id=? AND verification_status='verified'
                   ORDER BY family_id,id""",
                (cr_id,),
            ).fetchall()
            paths_by_family: dict[int, list[str]] = {}
            for review in verified_rows:
                family_id = int(review["family_id"])
                owner = connection.execute(
                    """SELECT COALESCE(assigned.parent_event_id,assigned.id) AS root_id
                       FROM event_assignments assignment
                       JOIN events assigned ON assigned.id=assignment.event_id
                       WHERE assignment.family_id=? AND assigned.status='archived'
                         AND COALESCE(assigned.parent_event_id,assigned.id)<>?
                       LIMIT 1""",
                    (family_id, cr["event_id"]),
                ).fetchone()
                if owner is None or review["file_id"] is None or not review["new_path"]:
                    raise EventChangeApplyError(
                        "Für eine Archivdatei fehlt ein verifiziertes fachliches Ziel."
                    )
                target_id = str(owner["root_id"])
                file_id = int(review["file_id"])
                target_path = str(review["new_path"])
                connection.execute(
                    """UPDATE files SET current_relative_path=?,
                           current_root_kind='camera_archive',updated_at=? WHERE id=?""",
                    (target_path, now, file_id),
                )
                record_verified_file_location(
                    connection, target_id, family_id, file_id, target_path, now,
                )
                paths_by_family.setdefault(family_id, []).append(target_path)
            for family_id, paths in paths_by_family.items():
                owner = connection.execute(
                    """SELECT COALESCE(assigned.parent_event_id,assigned.id) AS root_id
                       FROM event_assignments assignment
                       JOIN events assigned ON assigned.id=assignment.event_id
                       WHERE assignment.family_id=? AND assigned.status='archived'
                         AND COALESCE(assigned.parent_event_id,assigned.id)<>?
                       LIMIT 1""",
                    (family_id, cr["event_id"]),
                ).fetchone()
                record_family_anchor(connection, str(owner["root_id"]), family_id, paths, now)
            # event_change_requests references the event with ON DELETE CASCADE.
            # Persist the durable audit entry first, then remove the event; the
            # completed request and its file-review rows disappear together.
            connection.execute(
                """INSERT INTO audit_log(job_id,action,entity_type,entity_id,details_json,created_at)
                   VALUES (?,'archived_event_deleted_after_manual_move','event_change_request',?,?,?)""",
                (cr["job_id"], cr_id, json.dumps({
                    "archive_read_only": True,
                    "verified_file_count": verification["verified_file_count"],
                    "released_family_ids": selected_ids,
                    "event_id": cr["event_id"],
                }, ensure_ascii=False, sort_keys=True), now),
            )
            connection.execute("DELETE FROM events WHERE id=? AND job_id=?", (cr["event_id"], cr["job_id"]))
            connection.commit()
            return {
                "status":"archiviert", "change_request_id":cr_id, "archive_read_only":True,
                "files_changed_by_app":0, "verified_file_count":verification["verified_file_count"],
                "event_deleted":True,
                "created_reassignment_event_ids": created_reassignment_events,
            }

        connection.execute(
            """
            UPDATE events
            SET name = ?, start_datetime = ?, end_datetime = ?, folder_name = ?,
                event_kind = ?, preserve_day_folders = ?, notes = ?,
                revision = revision + 1, updated_at = ?, edited_at = ?
            WHERE id = ?
            """,
            (
                cr["event_name"], parent_start, parent_end, cr["parent_folder"],
                event_kind, int(bool(cr["preserve_day_folders"])),
                cr["notes"], now, now, cr["event_id"],
            ),
        )

        connection.execute("UPDATE events SET time_model_version=2 WHERE id=?", (cr['event_id'],))
        children = connection.execute(
            "SELECT * FROM events WHERE parent_event_id = ? ORDER BY start_datetime, id",
            (cr["event_id"],),
        ).fetchall()
        child = children[0] if children else None
        if event_kind == "no_event":
            assignment_event_id = str(cr["event_id"])
            if children:
                connection.execute("DELETE FROM events WHERE parent_event_id = ?", (cr["event_id"],))
            replace_event_segments(
                connection,
                event_id=str(cr["event_id"]),
                job_id=str(cr["job_id"]),
                segments=no_event_segments,
                now=now,
                source="cascade",
            )
        elif child_segments:
            connection.execute("DELETE FROM event_assignments WHERE event_id IN (SELECT id FROM events WHERE parent_event_id=?)",(cr["event_id"],))
            connection.execute("DELETE FROM events WHERE parent_event_id=?",(cr["event_id"],))
            created_children=[]
            for segment in child_segments:
                import uuid
                child_id="EVENT_"+uuid.uuid4().hex.upper()
                seg_start=segment.get('start_datetime') or f"{start_date}T{segment['start_time']}:00"; seg_end=segment.get('end_datetime') or f"{end_date}T{segment['end_time']}:59"
                folder=str(segment.get("folder_name") or segment.get("folder") or f"{segment['start_time'].replace(':','-')} - {segment['end_time'].replace(':','-')} - {segment['name']}")
                connection.execute(
                    """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,edited_at,timeline_model)
                       VALUES (?,?,?,'child',?,?,?,1,?,'archived',?,?,'event',?,1,?,?,'',?,'continuous')""",
                    (child_id,cr["job_id"],cr["event_id"],segment["name"],seg_start,seg_end,folder,now,now,
                     int(bool(cr["preserve_day_folders"])),event["applied_at"],event["archived_at"],now),
                )
                created_children.append((child_id,seg_start,seg_end))
            assignment_event_id=None
        elif uses_time_range and cr.get('child_folder'):
            child_name = str(cr.get("child_event_name") or "Unterereignis")
            if child is None:
                import uuid
                child_id = "EVENT_" + uuid.uuid4().hex.upper()
                connection.execute(
                    """
                    INSERT INTO events(id, job_id, parent_event_id, event_level, name,
                       start_datetime, end_datetime, uses_time_range, folder_name, status,
                       created_at, updated_at, event_kind, preserve_day_folders, revision,
                       applied_at, archived_at, notes, edited_at)
                    VALUES (?, ?, ?, 'child', ?, ?, ?, 1, ?, 'archived', ?, ?, 'event', ?, 1, ?, ?, '', ?)
                    """,
                    (child_id, cr["job_id"], cr["event_id"], child_name, child_start, child_end,
                     cr["child_folder"] or "", now, now, int(bool(cr["preserve_day_folders"])),
                     event["applied_at"], event["archived_at"], now),
                )
            else:
                child_id = str(child["id"])
                connection.execute(
                    """
                    UPDATE events SET name = ?, start_datetime = ?, end_datetime = ?,
                        folder_name = ?, preserve_day_folders = ?, revision = revision + 1,
                        updated_at = ?, edited_at = ? WHERE id = ?
                    """,
                    (child_name, child_start, child_end, cr["child_folder"] or "",
                     int(bool(cr["preserve_day_folders"])), now, now, child_id),
                )
                for extra in children[1:]:
                    connection.execute("DELETE FROM events WHERE id = ?", (extra["id"],))
            assignment_event_id = child_id
        else:
            assignment_event_id = str(cr["event_id"])
            if children:
                connection.execute("DELETE FROM events WHERE parent_event_id = ?", (cr["event_id"],))

        connection.execute(
            "DELETE FROM event_assignments WHERE event_id = ? OR event_id IN "
            "(SELECT id FROM events WHERE parent_event_id = ?)",
            (cr["event_id"], cr["event_id"]),
        )
        if child_segments:
            family_rows=connection.execute(
                "SELECT id,selected_capture_time FROM file_families WHERE job_id=? AND id IN (" + ",".join("?" for _ in selected_ids) + ")",
                (cr["job_id"],*selected_ids),
            ).fetchall()
            assignments=[]
            for family in family_rows:
                capture=str(family["selected_capture_time"] or "")[:19]
                matches=[child_id for child_id,a,b in created_children if a <= capture <= b]
                if len(matches)>1 or (not matches and int(cr.get('time_model_version',1))<2):
                    connection.rollback(); raise EventChangeApplyError("Eine archivierte Familie passt in kein eindeutiges Unterereignis.")
                assignments.append((matches[0] if matches else cr['event_id'],int(family["id"]),now))
            connection.executemany(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?,?,NULL,'date_time_range',?)",
                assignments,
            )
        else:
            connection.executemany(
                "INSERT INTO event_assignments(event_id, family_id, file_id, assignment_source, created_at) VALUES (?, ?, NULL, 'date_time_range', ?)",
                [(assignment_event_id, family_id, now) for family_id in selected_ids],
            )
        # 0.19.0: nach erfolgreicher manueller Prüfung den tatsächlich
        # bestätigten stabilen Archivanker je Familie speichern. Alle/Sortiert/
        # Export sind bewusst nicht Teil des Ankers.
        verified_rows = connection.execute(
            """SELECT family_id,file_id,new_path FROM event_change_file_reviews
               WHERE change_request_id=? AND verification_status='verified' AND new_path<>''
               ORDER BY family_id,id""",
            (cr_id,),
        ).fetchall()
        paths_by_family: dict[int, list[str]] = {}
        for row in verified_rows:
            family_id = int(row["family_id"])
            new_path = str(row["new_path"])
            paths_by_family.setdefault(family_id, []).append(new_path)
            if row["file_id"] is not None:
                connection.execute(
                    """UPDATE files
                       SET current_relative_path=?, current_root_kind='camera_archive', updated_at=?
                       WHERE id=?""",
                    (new_path, now, int(row["file_id"])),
                )
        for family_id, verified_paths in paths_by_family.items():
            owner = connection.execute(
                """SELECT COALESCE(parent.id,assigned.id) AS root_event_id
                   FROM event_assignments ea
                   JOIN events assigned ON assigned.id=ea.event_id
                   LEFT JOIN events parent ON parent.id=assigned.parent_event_id
                   WHERE ea.family_id=? AND assigned.status IN ('planned','applied','archived')
                   ORDER BY CASE assigned.status WHEN 'archived' THEN 0 WHEN 'applied' THEN 1 ELSE 2 END
                   LIMIT 1""",
                (family_id,),
            ).fetchone()
            if owner is not None:
                root_event_id = str(owner["root_event_id"])
                record_family_anchor(connection, root_event_id, family_id, verified_paths, now)
                family_verified_rows = [r for r in verified_rows if int(r["family_id"]) == family_id]
                for verified_row in family_verified_rows:
                    file_row = connection.execute(
                        "SELECT file_id,new_path FROM event_change_file_reviews WHERE change_request_id=? AND family_id=? AND new_path=? AND verification_status='verified' LIMIT 1",
                        (cr_id, family_id, str(verified_row["new_path"])),
                    ).fetchone()
                    if file_row is not None and file_row["file_id"] is not None:
                        record_verified_file_location(
                            connection, root_event_id, family_id, int(file_row["file_id"]),
                            str(file_row["new_path"]), now,
                        )

        connection.execute(
            "UPDATE event_change_requests SET status = 'aenderbar_archiviert', "
            "finished_at = ?, updated_at = ? WHERE id = ?",
            (now, now, cr_id),
        )
        connection.execute(
            """
            INSERT INTO audit_log(job_id, action, entity_type, entity_id, details_json, created_at)
            VALUES (?, 'event_change_verified_and_finished', 'event_change_request', ?, ?, ?)
            """,
            (
                cr["job_id"], cr_id,
                json.dumps({
                    "archive_read_only": True,
                    "verified_file_count": verification["verified_file_count"],
                    "selected_family_ids": selected_ids,
                }, ensure_ascii=False, sort_keys=True),
                now,
            ),
        )
        connection.commit()

    return {
        "status": "archiviert",
        "change_request_id": cr_id,
        "archive_read_only": True,
        "files_changed_by_app": 0,
        "verified_file_count": verification["verified_file_count"],
        "created_reassignment_event_ids": created_reassignment_events,
    }
