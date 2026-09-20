"""Change-Request-Workflow fuer archivierte Ereignisse.

Ermoglicht das strukturelle Bearbeiten bereits archivierter Ereignisse
ueber einen ueberwachten Prozess:

    1.  aenderbar_vorschlagen — App berechnet neuen Zustand und erzeugt
        einen Aenderungsauftrag (event_change_requests).
    2.  Aenderungspfade anzeigen — pro Datei: alter Pfad → neuer Pfad.
    3.  Aenderungsbestaetigung — Benutzer bestaetigt, dass die
        Dateibewegungen manuell durchgefuehrt wurden.
    4.  Archivierung abschließen — Ereignis wird mit neuer Struktur
        neu archiviert.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.database import database_connection
from app.archive_locations import resolve_archived_file_relative_path, ArchiveLocationError


class EventChangeRequestError(ValueError):
    pass


def _compute_event_plan(
    database_path: Path,
    job_id: str,
    event_id: str,
    preview: dict[str, Any],
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Berechne den manuellen Archiv-Aenderungsplan dateigenau.

    Die Kamerabibliothek wird hier ausschliesslich beschrieben. ``old_path``
    und ``new_path`` sind echte relative Pfade innerhalb der Kamerabibliothek;
    es werden weder Platzhalter noch physische Dateioperationen erzeugt.
    """
    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND job_id = ?",
            (event_id, job_id),
        ).fetchone()
        if event is None:
            raise EventChangeRequestError("Ereignis wurde nicht gefunden.")
        if str(event["archived_at"] or "").strip() == "":
            raise EventChangeRequestError(
                "Nur archivierte Ereignisse koennen ueber einen manuellen Aenderungsauftrag geaendert werden."
            )

        assigned_rows = connection.execute(
            """
            SELECT DISTINCT ea.family_id
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            WHERE assigned.job_id = ?
              AND COALESCE(assigned.parent_event_id, assigned.id) = ?
              AND ea.family_id IS NOT NULL
              AND assigned.status IN ('draft','planned','applied','archived')
            """,
            (job_id, event_id),
        ).fetchall()
        current_family_ids = {int(r["family_id"]) for r in assigned_rows}
        if "selected_family_ids" in preview:
            requested_ids = sorted({int(v) for v in preview.get("selected_family_ids", [])})
        else:
            requested_ids = sorted(current_family_ids)
        requested_set = set(requested_ids)
        relevant_ids = sorted(current_family_ids | requested_set)

        if not relevant_ids:
            raise EventChangeRequestError("Der Aenderungsauftrag enthaelt keine Dateifamilien.")

        placeholders = ",".join("?" for _ in relevant_ids)
        rows = connection.execute(
            f"""
            SELECT f.id AS file_id, f.family_id, f.current_relative_path,
                   f.original_relative_path, f.size_bytes,
                   f.sha256_current, f.sha256_original,
                   ff.family_key, ff.selected_capture_time
            FROM files f
            JOIN file_families ff ON ff.id = f.family_id AND ff.job_id = f.job_id
            WHERE f.job_id = ? AND f.family_id IN ({placeholders})
            ORDER BY ff.selected_capture_time, ff.id, f.current_relative_path, f.id
            """,
            (job_id, *relevant_ids),
        ).fetchall()

    parent_folder = str(preview.get("parent_folder") or "").strip()
    child_folder = str(preview.get("child_folder") or "").strip()
    child_segments = list(preview.get("child_segments") or [])
    normalized_child_segments=[]
    for segment in child_segments:
        name=str(segment.get("name") or "").strip()
        start=str(segment.get("start_time") or "")
        end=str(segment.get("end_time") or "")
        if not name or len(start)!=5 or len(end)!=5 or start>=end:
            raise EventChangeRequestError("Mindestens ein Unterereignis ist unvollständig oder ungültig.")
        normalized_child_segments.append({"id":segment.get("id"),"name":name,"start_time":start,"end_time":end,
            "folder":f"{start.replace(':','-')} - {end.replace(':','-')} - {name}"})
    normalized_child_segments.sort(key=lambda s:(s["start_time"],s["end_time"],s["name"]))
    for left,right in zip(normalized_child_segments,normalized_child_segments[1:]):
        if left["end_time"] >= right["start_time"]:
            raise EventChangeRequestError("Unterereignisse dürfen sich zeitlich nicht überschneiden.")
    preserve_day_folders = bool(preview.get("preserve_day_folders"))
    start_date = str(preview.get("start_date") or str(event["start_datetime"] or "")[:10])
    year = start_date[:4]
    if len(year) != 4 or not year.isdigit():
        raise EventChangeRequestError("Aus dem neuen Ereignisbeginn konnte kein Jahr ermittelt werden.")
    if not parent_folder:
        raise EventChangeRequestError("Der neue Ereignisordner fehlt.")

    removed_family_ids = current_family_ids - requested_set
    added_family_ids = requested_set - current_family_ids
    file_plans: list[dict[str, Any]] = []

    for row in rows:
        family_id = int(row["family_id"])
        stored_path = str(row["current_relative_path"] or row["original_relative_path"] or "").replace("\\", "/").lstrip("/")
        filename = Path(stored_path).name
        if not filename:
            raise EventChangeRequestError(f"Dateiname fuer Datei {row['file_id']} fehlt.")
        old_path = stored_path
        if archive_root is not None:
            fallback_anchor = "/".join([str(event["start_datetime"] or "")[:4], str(event["folder_name"] or "").strip()]).strip("/")
            try:
                old_path = resolve_archived_file_relative_path(
                    database_path,
                    archive_root,
                    event_id=str(event_id),
                    family_id=family_id,
                    filename=filename,
                    fallback_anchor=fallback_anchor,
                    file_id=int(row["file_id"]),
                )
            except ArchiveLocationError as exc:
                raise EventChangeRequestError(str(exc)) from exc

        new_path = ""
        if family_id in requested_set:
            parts = [year, parent_folder]
            capture=str(row["selected_capture_time"] or "")[:19]
            if normalized_child_segments:
                matching=[s for s in normalized_child_segments if f"{start_date}T{s['start_time']}:00" <= capture <= f"{str(preview.get('end_date') or start_date)}T{s['end_time']}:59"]
                if len(matching) != 1:
                    raise EventChangeRequestError(f"Familie {family_id} passt in kein eindeutiges Unterereignis.")
                parts.append(matching[0]["folder"])
            elif child_folder:
                parts.append(child_folder)
            day_key = str(row["selected_capture_time"] or "")[:10]
            if preserve_day_folders:
                if len(day_key) != 10:
                    raise EventChangeRequestError(
                        f"Fuer Datei {row['file_id']} fehlt das Aufnahmedatum fuer den Tagesordner."
                    )
                parts.append(day_key)
            parts.extend(["Alle", filename])
            new_path = "/".join(parts)
            action = "keep" if old_path == new_path else "move"
        else:
            # Eine herausfallende Familie darf niemals geloescht werden. Solange
            # kein neues Ereignis gewaehlt wurde, bleibt sie als offene manuelle
            # Neu-Zuordnung im Auftrag und kann nicht abgeschlossen werden.
            action = "delete"

        file_plans.append({
            "file_id": int(row["file_id"]),
            "family_id": family_id,
            "family_key": str(row["family_key"] or ""),
            "old_path": old_path,
            "new_path": new_path,
            "action": action,
            "expected_size_bytes": int(row["size_bytes"] or 0),
            "expected_sha256": str(row["sha256_current"] or row["sha256_original"] or ""),
        })

    lines = [
        f"{year} — Archiv-Aenderungsplan (manuell)",
        f"└── {parent_folder}",
    ]
    if normalized_child_segments:
        for index,segment in enumerate(normalized_child_segments):
            connector="└──" if index == len(normalized_child_segments)-1 else "├──"
            lines.append(f"    {connector} {segment['folder']}")
    elif child_folder:
        lines.append(f"    └── {child_folder}")
    lines.extend(["", f"Dateien im Auftrag: {len(file_plans)}"])
    if removed_family_ids:
        lines.append(
            f"Offen neu zuzuordnen: {len(removed_family_ids)} Familien (werden niemals geloescht)."
        )

    return {
        "families_with_plans": file_plans,
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
        "diff_summary": {
            "removed_count": len(removed_family_ids),
            "added_count": len(added_family_ids),
            "kept_count": len(requested_set & current_family_ids),
            "total_changes": sum(1 for item in file_plans if item["action"] != "keep"),
            "file_count": len(file_plans),
        },
    }


def _get_day_key_for_family(
    database_path: Path,
    job_id: str,
    family_id: int,
) -> str | None:
    """Ermittle den day_key einer Familie."""
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT day_key FROM file_families WHERE id = ? AND job_id = ?",
            (family_id, job_id),
        ).fetchone()
        return row["day_key"] if row else None


def propose_event_change(
    database_path: Path,
    job_id: str,
    event_id: str,
    preview: dict[str, Any],
    *,
    event_name: str | None = None,
    notes: str = "",
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Change-Request fuer ein archiviertes Ereignis vorschlagen.

    Erzeugt einen neuen Aenderungsauftrag ohne die Datenbank zu veraendern.
    Gibt den ChangeRequest mit berechneten Aenderungspfaden zurueck.
    """
    import json
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Vorlage berechnen
    plan = _compute_event_plan(database_path, job_id, event_id, preview, archive_root=archive_root)
    if "selected_family_ids" not in preview:
        preview = dict(preview)
        preview["selected_family_ids"] = sorted({
            int(item["family_id"]) for item in plan["families_with_plans"]
        })
        preview["selected_family_count"] = len(preview["selected_family_ids"])
        preview["selected_file_count"] = len(plan["families_with_plans"])

    # ChangeRequest erstellen
    with database_connection(database_path) as connection:
        # Pruefe, ob bereits ein aktiver Auftrag existiert
        existing = connection.execute(
            "SELECT id, version FROM event_change_requests "
            "WHERE event_id = ? AND status IN ('aenderbar_vorschlagen', 'aenderbar_bestaetigt') "
            "ORDER BY version DESC LIMIT 1",
            (event_id,),
        ).fetchone()
        if existing is not None:
            raise EventChangeRequestError(
                "Für dieses Ereignis ist bereits ein offener Änderungsauftrag vorhanden."
            )

        version_row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) AS version FROM event_change_requests WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        version = int(version_row["version"] or 0) + 1

        cr_id = f"cr-{uuid.uuid4().hex[:12]}"

        connection.execute(
            """
            INSERT INTO event_change_requests (
                id, event_id, job_id, event_name, notes,
                parent_folder, child_folder, uses_time_range,
                preserve_day_folders, start_date, end_date,
                start_time, end_time, event_kind, child_event_name,
                selected_day_keys, selected_family_ids,
                selected_file_count, selected_family_count,
                no_event_segments, child_segments_json,
                status, version, proposed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cr_id,
                event_id,
                job_id,
                event_name or "",
                notes,
                preview.get("parent_folder", ""),
                preview.get("child_folder"),
                1 if preview.get("uses_time_range") else 0,
                1 if preview.get("preserve_day_folders", True) else 0,
                preview.get("start_date", ""),
                preview.get("end_date", ""),
                preview.get("start_time"),
                preview.get("end_time"),
                str(preview.get("event_kind") or "event"),
                preview.get("child_event_name"),
                json.dumps(preview.get("selected_day_keys", []), ensure_ascii=False),
                json.dumps(preview.get("selected_family_ids", []), ensure_ascii=False),
                preview.get("selected_file_count", 0),
                preview.get("selected_family_count", 0),
                json.dumps(preview.get("no_event_segments", []), ensure_ascii=False),
                json.dumps(preview.get("child_segments", []), ensure_ascii=False),
                "aenderbar_vorschlagen",
                version,
                now,
                now,
                now,
            ),
        )

        # Datei-Bestaetigungen (loeschen/bewegen/behalten) fuer jede Familie
        for family_plan in plan["families_with_plans"]:
            fid = family_plan["family_id"]
            action = family_plan["action"]
            old_path = family_plan["old_path"]
            new_path = family_plan["new_path"]

            connection.execute(
                """
                INSERT INTO event_change_file_reviews (
                    change_request_id, family_id, file_id, old_path, new_path,
                    action, expected_size_bytes, expected_sha256,
                    confirmed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    cr_id,
                    fid,
                    family_plan.get("file_id"),
                    old_path,
                    new_path,
                    action,
                    int(family_plan.get("expected_size_bytes") or 0),
                    str(family_plan.get("expected_sha256") or ""),
                    now,
                    now,
                ),
            )

        connection.commit()

    # Rueckgabe mit Plan
    return {
        "change_request_id": cr_id,
        "event_id": event_id,
        "version": version,
        "status": "aenderbar_vorschlagen",
        "plan": plan,
        "family_count": len(plan["families_with_plans"]),
        "diff_summary": plan["diff_summary"],
    }


def list_event_change_requests(
    database_path: Path,
    job_id: str,
    *,
    event_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Aenderungsauftraege fuer ein Ereignis auflisten."""
    with database_connection(database_path) as connection:
        query = "SELECT * FROM event_change_requests WHERE job_id = ?"
        params: list[Any] = [job_id]

        if event_id:
            query += " AND event_id = ?"
            params.append(event_id)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY version DESC"

        rows = connection.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_event_change_request(
    database_path: Path,
    cr_id: str,
) -> dict[str, Any] | None:
    """Einen Aenderungsauftrag lesen."""
    with database_connection(database_path) as connection:
        row = connection.execute(
            "SELECT * FROM event_change_requests WHERE id = ?",
            (cr_id,),
        ).fetchone()
        if row is None:
            return None
        return dict(row)


def get_event_change_files(
    database_path: Path,
    cr_id: str,
) -> list[dict[str, Any]]:
    """Datei-Bestaetigungen fuer einen Aenderungsauftrag."""
    with database_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM event_change_file_reviews WHERE change_request_id = ? ORDER BY id",
            (cr_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def propose_archived_event_deletion(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    """Create a read-only manual deletion request for an archived event.

    Files are never deleted. The user is instructed to move every file into a
    neutral ``Später zuordnen/<Jahr>/<Tag - Ereignis>/`` holding area inside
    the camera library. Only after read-only verification is the event row
    removed and its families become free in the index.
    """
    now = datetime.now(timezone.utc).isoformat()
    with database_connection(database_path) as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE id=? AND job_id=?", (event_id, job_id)
        ).fetchone()
        if event is None:
            raise EventChangeRequestError("Ereignis wurde nicht gefunden.")
        if not event["archived_at"]:
            raise EventChangeRequestError("Nur archivierte Ereignisse benötigen diesen manuellen Löschauftrag.")
        existing = connection.execute(
            """SELECT id FROM event_change_requests
               WHERE event_id=? AND status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')
               ORDER BY version DESC LIMIT 1""", (event_id,)
        ).fetchone()
        if existing is not None:
            raise EventChangeRequestError("Für dieses Ereignis ist bereits ein offener Änderungsauftrag vorhanden.")

        assigned = connection.execute(
            """SELECT DISTINCT ea.family_id
               FROM event_assignments ea JOIN events e ON e.id=ea.event_id
               WHERE e.job_id=? AND COALESCE(e.parent_event_id,e.id)=?
                 AND ea.family_id IS NOT NULL ORDER BY ea.family_id""",
            (job_id, event_id),
        ).fetchall()
        family_ids = [int(r["family_id"]) for r in assigned]
        if not family_ids:
            raise EventChangeRequestError("Dem archivierten Ereignis sind keine Familien zugeordnet.")
        placeholders = ",".join("?" for _ in family_ids)
        files = connection.execute(
            f"""SELECT f.id AS file_id,f.family_id,f.current_relative_path,f.original_relative_path,
                       f.size_bytes,f.sha256_current,f.sha256_original,ff.selected_capture_time,ff.family_key
                FROM files f JOIN file_families ff ON ff.id=f.family_id AND ff.job_id=f.job_id
                WHERE f.job_id=? AND f.family_id IN ({placeholders})
                ORDER BY ff.selected_capture_time,ff.id,f.id""",
            (job_id, *family_ids),
        ).fetchall()
        version_row = connection.execute(
            "SELECT COALESCE(MAX(version),0) AS v FROM event_change_requests WHERE event_id=?", (event_id,)
        ).fetchone()
        version = int(version_row["v"] or 0) + 1
        cr_id = f"cr-{uuid.uuid4().hex[:12]}"
        year = str(event["start_datetime"] or "")[:4] or "Unbekannt"
        day = str(event["start_datetime"] or "")[:10]
        safe_name = "".join(c if c not in '/\\\0' else '-' for c in str(event["name"]))
        holding_folder = f"Später zuordnen/{year}/{day} - {safe_name}"
        connection.execute(
            """INSERT INTO event_change_requests(
                   id,event_id,job_id,event_name,notes,parent_folder,child_folder,uses_time_range,
                   preserve_day_folders,start_date,end_date,start_time,end_time,event_kind,child_event_name,
                   selected_day_keys,selected_family_ids,selected_file_count,selected_family_count,
                   status,version,proposed_at,created_at,updated_at,delete_event)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (
                cr_id,event_id,job_id,str(event["name"]),"Ereignis löschen; Dateien manuell nach Später zuordnen verschieben.",
                holding_folder,None,0,0,str(event["start_datetime"] or "")[:10],str(event["end_datetime"] or "")[:10],
                None,None,str(event["event_kind"] or "event"),None,json.dumps([],ensure_ascii=False),
                json.dumps(family_ids,ensure_ascii=False),len(files),len(family_ids),"aenderbar_vorschlagen",version,now,now,now,
            ),
        )
        for row in files:
            old_path = str(row["current_relative_path"] or row["original_relative_path"] or "").replace("\\","/").lstrip("/")
            filename = Path(old_path).name
            new_path = f"{holding_folder}/{filename}"
            connection.execute(
                """INSERT INTO event_change_file_reviews(
                       change_request_id,family_id,file_id,old_path,new_path,action,
                       expected_size_bytes,expected_sha256,confirmed,created_at,updated_at)
                   VALUES (?,?,?,?,?,'move',?,?,0,?,?)""",
                (cr_id,int(row["family_id"]),int(row["file_id"]),old_path,new_path,
                 int(row["size_bytes"] or 0),str(row["sha256_current"] or row["sha256_original"] or ""),now,now),
            )
        connection.commit()
    return {
        "status":"change_request_created","pending_delete":True,"archive_read_only":True,
        "change_request_id":cr_id,"event_id":event_id,"event_name":str(event["name"]),
        "released_family_count":len(family_ids),"released_file_count":len(files),
        "reassignment_required":False,
        "message":"Manueller Löschauftrag erstellt. Die Kamerabibliothek bleibt read-only; verschiebe die Dateien gemäß IST→SOLL und schließe den Auftrag danach ab.",
    }
