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
from app.event_inventory import EventInventoryError, scan_event_inventory


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

    Vor jeder Bearbeitung eines archivierten Ereignisses wird der reale
    Ereignisordner neu eingelesen. Alte DB-Pfade sind nur noch zuletzt
    beobachtete Orte und niemals die aktuelle IST-Wahrheit.
    """
    inventory = None
    if archive_root is not None:
        try:
            inventory = scan_event_inventory(
                database_path,
                archive_root,
                job_id,
                event_id,
                root_kind="camera_archive",
                persist=True,
                update_known_file_locations=True,
            )
        except EventInventoryError as exc:
            raise EventChangeRequestError(str(exc)) from exc

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
            WITH RECURSIVE event_tree(id) AS (
                SELECT id
                FROM events
                WHERE id = ?
                   OR (
                        linked_event_id = ?
                        AND linkage_kind = 'archived_manual'
                        AND status = 'archived'
                      )
                UNION ALL
                SELECT child.id
                FROM events child
                JOIN event_tree parent ON child.parent_event_id = parent.id
            )
            SELECT DISTINCT ea.family_id
            FROM event_assignments ea
            JOIN events assigned ON assigned.id = ea.event_id
            WHERE ea.event_id IN (SELECT id FROM event_tree)
              AND ea.family_id IS NOT NULL
              AND assigned.status IN ('draft','planned','applied','archived')
            """,
            (event_id, event_id),
        ).fetchall()
        assigned_family_ids = {int(r["family_id"]) for r in assigned_rows}
        if inventory is not None:
            current_family_ids = {
                int(item["family_id"])
                for item in inventory["files"]
                if item.get("known_file_id") is not None and item.get("family_id") is not None
            }
        else:
            current_family_ids = assigned_family_ids

        if "selected_family_ids" in preview:
            requested = {int(v) for v in preview.get("selected_family_ids", [])}
            if inventory is not None:
                # 0.27.0: Der reale Archivbestand bleibt die Wahrheit fuer bereits
                # archivierte Familien. Zusaetzlich duerfen aber wirklich freie
                # Familien aus demselben SSD-Auftrag in die neue Definition
                # aufgenommen werden. Logisch noch zugeordnete, im Archiv jedoch
                # manuell entfernte Familien werden dadurch nicht wiederbelebt.
                incoming_requested = requested - assigned_family_ids
                if incoming_requested:
                    incoming_placeholders = ",".join("?" for _ in incoming_requested)
                    occupied = connection.execute(
                        f"""
                        SELECT DISTINCT ea.family_id
                        FROM event_assignments ea
                        JOIN events assigned ON assigned.id=ea.event_id
                        WHERE ea.family_id IN ({incoming_placeholders})
                          AND assigned.status IN ('draft','planned','applied','archived')
                        """,
                        tuple(sorted(incoming_requested)),
                    ).fetchall()
                    occupied_ids = {int(row["family_id"]) for row in occupied}
                    # Bereits anders belegte Familien sind keine SSD-Zuführung.
                    # Sie bleiben aus der Dateiplanung heraus, damit die weiter
                    # unten folgende Ereignis-/Zeitkonfliktprüfung die fachlich
                    # richtige Überschneidung meldet.
                    incoming_requested -= occupied_ids
                requested_ids = sorted(
                    (requested & current_family_ids) | incoming_requested
                )
            else:
                requested_ids = sorted(requested)
        else:
            requested_ids = sorted(current_family_ids)
        requested_set = set(requested_ids)
        relevant_ids = sorted(current_family_ids | requested_set)

        if relevant_ids:
            placeholders = ",".join("?" for _ in relevant_ids)
            rows = connection.execute(
                f"""
                SELECT f.id AS file_id, f.family_id, f.current_relative_path,
                       f.original_relative_path, f.current_root_kind, f.size_bytes,
                       f.sha256_current, f.sha256_original,
                       ff.family_key, ff.selected_capture_time
                FROM files f
                JOIN file_families ff ON ff.id = f.family_id AND ff.job_id = f.job_id
                WHERE f.family_id IN ({placeholders})
                ORDER BY ff.selected_capture_time, ff.id, f.current_relative_path, f.id
                """,
                tuple(relevant_ids),
            ).fetchall()
        else:
            rows = []

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
    if preview.get('subevents'):
        from app.subevents import normalize_subevents
        normalized_child_segments=normalize_subevents(preview['subevents'],
            f"{preview['start_date']}T{preview.get('start_time') or '00:00'}:00",f"{preview['end_date']}T{preview.get('end_time') or '23:59'}:59")
        normalized_child_segments=[{**s,'folder':s['folder_name']} for s in normalized_child_segments]
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
    asset_plans: list[dict[str, Any]] = []

    inventory_by_file_id = {
        int(item["known_file_id"]): item
        for item in (inventory["files"] if inventory is not None else [])
        if item.get("known_file_id") is not None
    }

    end_date = str(preview.get("end_date") or start_date)
    uses_time_range = bool(preview.get("uses_time_range"))

    def capture_belongs(capture: str) -> bool:
        value = str(capture or "")[:19]
        if len(value) < 19:
            return False
        if str(preview.get("event_kind") or "event") == "no_event":
            from app.event_timeline import normalize_no_event_segments
            try:
                segments = normalize_no_event_segments(preview.get("no_event_segments") or [])
            except Exception:
                return False
            return any(
                str(segment["start_datetime"]) <= value <= str(segment["end_datetime"])
                for segment in segments
            )
        lower = (
            f"{start_date}T{str(preview.get('start_time') or '00:00')}:00"
            if uses_time_range else f"{start_date}T00:00:00"
        )
        upper = (
            f"{end_date}T{str(preview.get('end_time') or '23:59')}:59"
            if uses_time_range else f"{end_date}T23:59:59"
        )
        return lower <= value <= upper

    def target_for(
        *,
        filename: str,
        capture: str | None,
        branch: str,
        old_event_relative_path: str,
    ) -> str | None:
        value = str(capture or "")[:19]
        safe_branch = branch if branch in {"Alle", "Sortiert", "Export"} else ""
        parts = [year, parent_folder]

        if value and capture_belongs(value):
            if normalized_child_segments:
                matching = [
                    segment for segment in normalized_child_segments
                    if str(
                        segment.get("start_datetime")
                        or f"{start_date}T{segment['start_time']}:00"
                    ) <= value <= str(
                        segment.get("end_datetime")
                        or f"{end_date}T{segment['end_time']}:59"
                    )
                ]
                if len(matching) > 1:
                    return None
                if matching:
                    parts.append(str(matching[0]["folder"]))
            elif child_folder:
                parts.append(child_folder)

            if preserve_day_folders:
                day_key = value[:10]
                if len(day_key) != 10:
                    return None
                parts.append(day_key)

            if safe_branch:
                parts.append(safe_branch)
            parts.append(filename)
            return "/".join(parts)

        # Ohne belastbare Aufnahmezeit darf nichts in neue Tages-/Unterereignis-
        # Strukturen geraten. Bei einer reinen Ereignisordner-Umbenennung bleibt
        # jedoch die interne relative Lage vollständig erhalten.
        if not normalized_child_segments and not child_folder and not preserve_day_folders:
            suffix = str(old_event_relative_path or "").replace("\\", "/").strip("/")
            if suffix:
                return "/".join([year, parent_folder, suffix])
        return None

    for row in rows:
        file_id = int(row["file_id"])
        family_id = int(row["family_id"])

        observed = inventory_by_file_id.get(file_id)
        incoming_workspace = family_id in added_family_ids
        if inventory is not None and observed is None and not incoming_workspace:
            # Die Datei wurde seit der letzten Archivierung manuell entfernt.
            # Das ist ein legitimer neuer IST-Bestand und erzeugt keinen Auftrag.
            continue

        if incoming_workspace:
            if str(row["current_root_kind"] or "") != "shared_workspace":
                raise EventChangeRequestError(
                    "Eine neu hinzukommende Familie liegt nicht im SSD-Arbeitsbereich."
                )
            stored_path = str(
                row["current_relative_path"] or row["original_relative_path"] or ""
            ).replace("\\", "/").lstrip("/")
            old_event_relative = ""
            branch = ""
            source_root_kind = "shared_workspace"
        else:
            stored_path = str(
                observed["relative_path"]
                if observed is not None
                else row["current_relative_path"] or row["original_relative_path"] or ""
            ).replace("\\", "/").lstrip("/")
            old_event_relative = str(observed.get("event_relative_path") or "") if observed else ""
            branch = str(observed.get("branch") or "") if observed else ""
            source_root_kind = "camera_archive"

        filename = Path(stored_path).name
        if not filename:
            raise EventChangeRequestError(f"Dateiname fuer Datei {row['file_id']} fehlt.")
        old_path = stored_path
        if not branch:
            for part in Path(old_path).parts:
                if part in {"Alle", "Sortiert", "Export"}:
                    branch = part
                    break
        if not branch:
            branch = "Alle"

        new_path = ""
        if family_id in requested_set:
            capture = str(row["selected_capture_time"] or "")[:19]
            candidate = target_for(
                filename=filename,
                capture=capture,
                branch=branch,
                old_event_relative_path=old_event_relative,
            )
            if not candidate:
                raise EventChangeRequestError(
                    f"Datei {filename} lässt sich anhand ihrer Aufnahmezeit nicht eindeutig "
                    "in die neue Ereignisstruktur einordnen."
                )
            new_path = candidate
            action = "keep" if old_path == new_path else "move"
        else:
            # Herausfallende Kamerafamilien bleiben im etablierten
            # Neu-Zuordnungsworkflow. Nichts wird automatisch gelöscht.
            action = "delete"

        file_plans.append({
            "file_id": file_id,
            "family_id": family_id,
            "family_key": str(row["family_key"] or ""),
            "old_path": old_path,
            "new_path": new_path,
            "action": action,
            "expected_size_bytes": int(
                observed["size_bytes"] if observed is not None else row["size_bytes"] or 0
            ),
            "expected_sha256": str(
                observed["sha256"]
                if observed is not None
                else row["sha256_current"] or row["sha256_original"] or ""
            ),
            "source_root_kind": source_root_kind,
            "workspace_original_path": old_path if incoming_workspace else "",
        })

    if inventory is not None:
        for item in inventory["files"]:
            if item.get("known_file_id") is not None:
                continue

            old_path = str(item["relative_path"])
            family_id = (
                int(item["family_id"])
                if item.get("family_id") is not None
                else None
            )
            asset_kind = str(item.get("asset_kind") or "other")
            capture = str(item.get("selected_capture_time") or "")[:19] or None
            branch = str(item.get("branch") or "")
            if asset_kind == "export":
                branch = "Export"

            # Sidecars eines herausfallenden Kameraoriginals folgen dessen
            # Neu-Zuordnung; bis das Ziel gewählt wurde bleibt auch der Sidecar
            # bewusst offen.
            if family_id is not None and family_id in removed_family_ids:
                candidate = None
            elif asset_kind == "other" and not capture:
                candidate = target_for(
                    filename=str(item["filename"]),
                    capture=None,
                    branch=branch,
                    old_event_relative_path=str(item["event_relative_path"]),
                )
            else:
                candidate = target_for(
                    filename=str(item["filename"]),
                    capture=capture,
                    branch=branch,
                    old_event_relative_path=str(item["event_relative_path"]),
                )

            if candidate:
                action = "keep" if candidate == old_path else "move"
                new_path = candidate
            else:
                action = "unresolved"
                new_path = ""

            asset_plans.append({
                "asset_kind": asset_kind,
                "source_file_id": item.get("source_file_id"),
                "family_id": family_id,
                "old_path": old_path,
                "new_path": new_path,
                "action": action,
                "expected_size_bytes": int(item["size_bytes"]),
                "expected_sha256": str(item["sha256"]),
                "selected_capture_time": item.get("selected_capture_time"),
                "capture_time_confidence": item.get("capture_time_confidence"),
            })

    lines = [
        f"{year} — Archiv-Aenderungsplan (manuell)",
        f"└── {parent_folder}",
    ]
    if normalized_child_segments:
        for index, segment in enumerate(normalized_child_segments):
            connector = "└──" if index == len(normalized_child_segments)-1 else "├──"
            lines.append(f"    {connector} {segment['folder']}")
    elif child_folder:
        lines.append(f"    └── {child_folder}")
    lines.extend([
        "",
        f"Kameradateien im Auftrag: {len(file_plans)}",
        f"XMP/Export/weitere aktuelle Dateien: {len(asset_plans)}",
    ])
    if removed_family_ids:
        lines.append(
            f"Offen neu zuzuordnen: {len(removed_family_ids)} Familien (werden niemals geloescht)."
        )
    unresolved_assets = sum(1 for item in asset_plans if item["action"] == "unresolved")
    if unresolved_assets:
        lines.append(
            f"Nicht eindeutig zuordenbare aktuelle Dateien: {unresolved_assets}"
        )

    return {
        "families_with_plans": file_plans,
        "assets_with_plans": asset_plans,
        "selected_family_ids": sorted(requested_set),
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
        "inventory_summary": inventory.get("summary") if inventory is not None else None,
        "diff_summary": {
            "removed_count": len(removed_family_ids),
            "added_count": len(added_family_ids),
            "kept_count": len(requested_set & current_family_ids),
            "total_changes": (
                sum(1 for item in file_plans if item["action"] != "keep")
                + sum(1 for item in asset_plans if item["action"] != "keep")
            ),
            "file_count": len(file_plans) + len(asset_plans),
            "camera_file_count": len(file_plans),
            "asset_file_count": len(asset_plans),
            "unresolved_asset_count": unresolved_assets,
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
    workspace_path: Path | None = None,
) -> dict[str, Any]:
    """Change-Request fuer ein archiviertes Ereignis vorschlagen.

    Erzeugt einen neuen Aenderungsauftrag ohne die Datenbank zu veraendern.
    Gibt den ChangeRequest mit berechneten Aenderungspfaden zurueck.
    """
    import json
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # Fachliche Belegung zuerst prüfen. Eine belegte Familie aus einem anderen
    # archivierten Ereignis darf niemals zuvor als vermeintliche SSD-Zuführung
    # klassifiziert werden.
    with database_connection(database_path) as connection:
        from app.event_timeline import (
            assert_editable_normal,
            continuous_event_overlaps,
            no_event_segment_overlaps,
        )
        from app.archive_reassignment_segments import proposed_ranges
        if preview.get("child_segments"):
            raise EventChangeRequestError(
                "Getrennte Belegungssegmente sind für normale Ereignisse nicht zulässig."
            )
        if preview.get("event_kind", "event") == "event":
            assert_editable_normal(connection, event_id)
        for range_start, range_end in proposed_ranges(preview):
            if (
                continuous_event_overlaps(
                    connection, job_id, range_start, range_end, exclude_event_id=event_id
                )
                or no_event_segment_overlaps(
                    connection, job_id, range_start, range_end, exclude_event_id=event_id
                )
            ):
                raise EventChangeRequestError(
                    "Die Änderung überschneidet sich mit belegter Zeit. "
                    "Bitte zuerst das andere Ereignis bearbeiten."
                )

    # Erst nach der fachlichen Konfliktprüfung wird zwischen bestehendem
    # Archivbestand und wirklich freien SSD-Zuführungen unterschieden.
    plan = _compute_event_plan(database_path, job_id, event_id, preview, archive_root=archive_root)
    preview = dict(preview)
    # Die aktuelle Archiv-Inventur ist für den neuen Zustand maßgeblich.
    # Manuell seit der letzten Archivierung gelöschte Dateien/Familien werden
    # nicht wieder als Sollbestand hineingezwungen.
    planned_selected = plan.get("selected_family_ids")
    if planned_selected is None:
        planned_selected = sorted({
            int(item["family_id"])
            for item in plan.get("families_with_plans", [])
            if item.get("family_id") is not None
        })
    preview["selected_family_ids"] = list(planned_selected)
    preview["selected_family_count"] = len(preview["selected_family_ids"])
    preview["selected_file_count"] = int(
        plan.get("diff_summary", {}).get(
            "file_count",
            len(plan.get("families_with_plans", []))
            + len(plan.get("assets_with_plans", [])),
        )
    )

    preparation = {
        "required": False,
        "missing_directories": [],
        "helper_directories": [],
        "incoming_file_count": 0,
        "prepared_structure_path": "",
    }
    if archive_root is not None:
        from app.archive_staging import describe_archive_change_staging
        preparation = describe_archive_change_staging(
            database_path, archive_root, event_id, preview, plan
        )
    else:
        preparation["required"] = any(
            str(item.get("source_root_kind") or "camera_archive") == "shared_workspace"
            for item in plan.get("families_with_plans") or []
        )
    initial_status = "aenderbar_vorschlagen"

    # ChangeRequest erstellen
    with database_connection(database_path) as connection:
        connection.execute('BEGIN IMMEDIATE')
        from app.event_timeline import assert_editable_normal, continuous_event_overlaps, no_event_segment_overlaps
        from app.archive_reassignment_segments import proposed_ranges
        if preview.get('child_segments'):
            raise EventChangeRequestError('Getrennte Belegungssegmente sind für normale Ereignisse nicht zulässig.')
        if preview.get('event_kind','event') == 'event':
            assert_editable_normal(connection,event_id)
        for a,b in proposed_ranges(preview):
            if continuous_event_overlaps(connection,job_id,a,b,exclude_event_id=event_id) or no_event_segment_overlaps(connection,job_id,a,b,exclude_event_id=event_id):
                raise EventChangeRequestError('Die Änderung überschneidet sich mit belegter Zeit. Bitte zuerst das andere Ereignis bearbeiten.')
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
                json.dumps(preview.get("subevents") or preview.get("child_segments", []), ensure_ascii=False),
                initial_status,
                version,
                now,
                now,
                now,
            ),
        )

        connection.execute('UPDATE event_change_requests SET time_model_version=2 WHERE id=?',(cr_id,))
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
                    source_root_kind, workspace_original_path,
                    confirmed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
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
                    str(family_plan.get("source_root_kind") or "camera_archive"),
                    str(family_plan.get("workspace_original_path") or ""),
                    now,
                    now,
                ),
            )

        for asset in plan.get("assets_with_plans", []):
            connection.execute(
                """
                INSERT INTO event_change_asset_reviews(
                    change_request_id,asset_kind,source_file_id,family_id,
                    old_path,new_path,action,expected_size_bytes,expected_sha256,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    cr_id,
                    str(asset.get("asset_kind") or "other"),
                    asset.get("source_file_id"),
                    asset.get("family_id"),
                    str(asset.get("old_path") or ""),
                    str(asset.get("new_path") or ""),
                    str(asset.get("action") or "unresolved"),
                    int(asset.get("expected_size_bytes") or 0),
                    str(asset.get("expected_sha256") or ""),
                    now,
                    now,
                ),
            )

        connection.commit()

    # 0.27.1: Der Hilfsbereich wird erst im expliziten Vorbereitungsschritt
    # materialisiert. Der Vorschlag bleibt bis dahin rein planend.

    # Rueckgabe mit Plan
    return {
        "change_request_id": cr_id,
        "event_id": event_id,
        "version": version,
        "status": initial_status,
        "plan": plan,
        "family_count": len(plan["families_with_plans"]),
        "diff_summary": plan["diff_summary"],
        "preparation_required": bool(preparation.get("required")),
        "preparation": preparation,
        "prepared_structure_path": "",
        "staged_file_count": 0,
    }


def list_event_change_requests(
    database_path: Path,
    job_id: str | None,
    *,
    event_id: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Aenderungsauftraege fuer ein Ereignis auflisten."""
    with database_connection(database_path) as connection:
        query = "SELECT * FROM event_change_requests WHERE 1=1"
        params: list[Any] = []
        if job_id:
            query += " AND job_id = ?"
            params.append(job_id)

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
    """Alle aktuellen Datei-Arbeitsanweisungen eines Änderungsauftrags."""
    with database_connection(database_path) as connection:
        camera_rows = [
            {**dict(row), "review_kind": "camera"}
            for row in connection.execute(
                "SELECT * FROM event_change_file_reviews WHERE change_request_id=? ORDER BY id",
                (cr_id,),
            ).fetchall()
        ]
        asset_rows = [
            {
                **dict(row),
                "review_kind": "asset",
                "file_id": None,
                "confirmed": 0,
            }
            for row in connection.execute(
                "SELECT * FROM event_change_asset_reviews WHERE change_request_id=? ORDER BY id",
                (cr_id,),
            ).fetchall()
        ]
    return camera_rows + asset_rows


def propose_archived_event_deletion(
    database_path: Path,
    job_id: str,
    event_id: str,
) -> dict[str, Any]:
    """Create a read-only manual deletion request for an archived event.

    Files are never deleted. Every family needs an explicit manual destination
    before the read-only verification may complete.
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
        connection.execute(
            """INSERT INTO event_change_requests(
                   id,event_id,job_id,event_name,notes,parent_folder,child_folder,uses_time_range,
                   preserve_day_folders,start_date,end_date,start_time,end_time,event_kind,child_event_name,
                   selected_day_keys,selected_family_ids,selected_file_count,selected_family_count,
                   status,version,proposed_at,created_at,updated_at,delete_event)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (
                cr_id,event_id,job_id,str(event["name"]),"Ereignis löschen; für alle Familien ein fachliches Ziel wählen.",
                str(event["folder_name"]),None,0,int(bool(event["preserve_day_folders"])),str(event["start_datetime"] or "")[:10],str(event["end_datetime"] or "")[:10],
                None,None,str(event["event_kind"] or "event"),None,json.dumps([],ensure_ascii=False),
                json.dumps(family_ids,ensure_ascii=False),len(files),len(family_ids),"aenderbar_vorschlagen",version,now,now,now,
            ),
        )
        for row in files:
            old_path = str(row["current_relative_path"] or row["original_relative_path"] or "").replace("\\","/").lstrip("/")
            connection.execute(
                """INSERT INTO event_change_file_reviews(
                       change_request_id,family_id,file_id,old_path,new_path,action,
                       expected_size_bytes,expected_sha256,confirmed,created_at,updated_at)
                   VALUES (?,?,?,?,?,'delete',?,?,0,?,?)""",
                (cr_id,int(row["family_id"]),int(row["file_id"]),old_path,"",
                 int(row["size_bytes"] or 0),str(row["sha256_current"] or row["sha256_original"] or ""),now,now),
            )
        connection.commit()
    return {
        "status":"change_request_created","pending_delete":True,"archive_read_only":True,
        "change_request_id":cr_id,"event_id":event_id,"event_name":str(event["name"]),
        "released_family_count":len(family_ids),"released_file_count":len(files),
        "reassignment_required":True,
        "message":"Manueller Löschauftrag erstellt. Alle Familien benötigen ein explizites Ziel; die Kamerabibliothek bleibt read-only.",
    }
