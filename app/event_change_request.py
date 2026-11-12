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
from pathlib import Path, PurePosixPath
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
        from app.event_leaf_layouts import stored_leaf_layouts
        old_leaves = stored_leaf_layouts(connection, event_id)
        saved_layout = connection.execute(
            "SELECT 1 FROM event_folder_layouts WHERE event_id=?", (event_id,)
        ).fetchone()
        from app.event_layout import ensure_event_layout_snapshot
        current_layout_state = ensure_event_layout_snapshot(
            connection,
            event_id,
            now=datetime.now(timezone.utc).isoformat(),
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

    from app.event_layout import layout_paths, layout_role_paths, normalize_layout, validate_input_path
    from app.physical_state import organization_path_for_event_relative

    layout_explicit = bool(preview.get("_folder_layout_explicit"))
    current_root = PurePosixPath(str(event["start_datetime"])[:4], str(event["folder_name"]))
    configured_exports = layout_role_paths(current_layout_state["layout"], "export")
    requested_layout_state: dict[str, Any] | None = None
    requested_layout_paths: set[str] = set()
    if layout_explicit:
        raw_layout = preview.get("folder_layout")
        if not isinstance(raw_layout, dict):
            raise EventChangeRequestError("Die gewünschte Ereignisstruktur fehlt.")
        normalized_layout = normalize_layout(
            raw_layout.get("layout") or current_layout_state["layout"]
        )
        requested_enabled = bool(raw_layout.get("structure_enabled", True))
        requested_input = validate_input_path(
            normalized_layout,
            raw_layout.get("input_path", current_layout_state["input_path"]),
            structure_enabled=requested_enabled,
        )
        requested_layout_state = {
            "structure_enabled": requested_enabled,
            "input_path": requested_input,
            "layout": normalized_layout,
        }
        requested_layout_paths = set(layout_paths(normalized_layout))

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
        normalized_child_segments=normalize_subevents(
            preview['subevents'],
            f"{preview['start_date']}T{preview.get('start_time') or '00:00'}:00",
            f"{preview['end_date']}T{preview.get('end_time') or '23:59'}:59",
            naming=preview.get("folder_naming"),
        )
        normalized_child_segments=[{**s,'folder':s['folder_name']} for s in normalized_child_segments]
    preserve_day_folders = bool(preview.get("preserve_day_folders"))
    start_date = str(preview.get("start_date") or str(event["start_datetime"] or "")[:10])
    year = start_date[:4]
    if len(year) != 4 or not year.isdigit():
        raise EventChangeRequestError("Aus dem neuen Ereignisbeginn konnte kein Jahr ermittelt werden.")
    if not parent_folder:
        raise EventChangeRequestError("Der neue Ereignisordner fehlt.")

    target_leaves = {}
    child_folders = {
        str(segment["id"]): segment["folder"]
        for segment in normalized_child_segments if segment.get("id")
    }
    for key, leaf in old_leaves.items():
        owner, _, day = key.partition("@")
        if owner != event_id and owner not in child_folders:
            continue
        if bool(day) != preserve_day_folders or (day and not start_date <= day <= str(preview.get("end_date") or start_date)):
            continue
        if requested_layout_state is not None and all(
            leaf[field] == current_layout_state[field] for field in requested_layout_state
        ):
            leaf = {**leaf, **requested_layout_state}
        prefix = "/".join(part for part in (child_folders.get(owner, ""), day) if part)
        target_leaves[key] = {**leaf, "leaf_prefix": prefix}
    old_leaves_by_prefix = sorted(
        old_leaves.values(), key=lambda leaf: -len(leaf["leaf_prefix"])
    )

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

    if inventory is not None:
        # Für bereits archivierte Familien wird die Zugehörigkeit zum neuen
        # Zeitraum aus dem frisch inventarisierten physischen Archivbestand
        # abgeleitet. Die UI übermittelt selected_family_ids weiterhin als
        # Transparenz-/Kompatibilitätswert, darf aber keinen älteren DB-Zeitwert
        # gegen eine belastbare live gelesene Aufnahmezeit durchsetzen.
        live_times_by_family: dict[int, set[str]] = {}
        for item in inventory.get("files") or []:
            if item.get("known_file_id") is None or item.get("family_id") is None:
                continue
            capture = str(item.get("selected_capture_time") or "")[:19]
            if capture:
                live_times_by_family.setdefault(int(item["family_id"]), set()).add(capture)

        conflicts = {
            family_id: sorted(values)
            for family_id, values in live_times_by_family.items()
            if len(values) > 1
        }
        if conflicts:
            family_id = sorted(conflicts)[0]
            raise EventChangeRequestError(
                "Die real gelesenen Kameraoriginale einer Archivfamilie besitzen "
                f"widersprüchliche Aufnahmezeiten (Familie {family_id}). "
                "Die Archivänderung wurde sicherheitshalber gestoppt."
            )

        physical_with_time = {
            family_id: next(iter(values))
            for family_id, values in live_times_by_family.items()
            if len(values) == 1
        }
        unresolved_current = current_family_ids - set(physical_with_time)
        derived_current = {
            family_id
            for family_id, capture in physical_with_time.items()
            if family_id in current_family_ids and capture_belongs(capture)
        }
        # Ohne belastbare Live-Zeit bleibt die bisher explizit übermittelte
        # Auswahl bestehen; wir entfernen eine Familie in diesem Sonderfall
        # niemals nur aufgrund fehlender Metadaten.
        derived_current |= requested_set & unresolved_current
        requested_set = (requested_set - current_family_ids) | derived_current
        requested_ids = sorted(requested_set)
        removed_family_ids = current_family_ids - requested_set
        added_family_ids = requested_set - current_family_ids

    def target_for(
        *,
        filename: str,
        capture: str | None,
        branch: str,
        old_event_relative_path: str,
    ) -> str | None:
        value = str(capture or "")[:19]
        safe_branch = branch if branch in {"All", "Sorted", "Alle", "Sortiert", "Export"} else ""

        def organization_path(target_leaf: dict[str, Any] | None = None) -> str:
            if target_leaf is not None:
                if not target_leaf["structure_enabled"]:
                    return ""
                for old_leaf in old_leaves_by_prefix:
                    prefix = old_leaf["leaf_prefix"]
                    if not old_event_relative_path or (prefix and not old_event_relative_path.startswith(prefix + "/")):
                        continue
                    relative = old_event_relative_path.removeprefix(prefix + "/") if prefix else old_event_relative_path
                    observed = organization_path_for_event_relative(relative, old_leaf)
                    if observed in layout_paths(target_leaf["layout"]):
                        return observed
                    if PurePosixPath(relative).parent == PurePosixPath(".") and not target_leaf["input_path"]:
                        return ""
                    break
                exports = layout_role_paths(target_leaf["layout"], "export")
                return exports[0] if branch == "Export" and exports else str(target_leaf["input_path"])
            if requested_layout_state is None:
                if saved_layout is None:
                    return safe_branch
                if not current_layout_state["structure_enabled"]:
                    return ""
                if old_event_relative_path:
                    return organization_path_for_event_relative(old_event_relative_path, current_layout_state)
                if branch == "Export" and configured_exports:
                    return configured_exports[0]
                return str(current_layout_state["input_path"] or "")
            if not bool(requested_layout_state["structure_enabled"]):
                return ""
            # OFF -> ON is intentionally simple in 0.28.3: no historical
            # placement restoration; everything enters the chosen input.
            if not bool(current_layout_state.get("structure_enabled")):
                return str(requested_layout_state["input_path"] or "")
            observed = organization_path_for_event_relative(
                old_event_relative_path,
                current_layout_state,
            )
            if observed and observed in requested_layout_paths:
                return observed
            return str(requested_layout_state["input_path"] or "")

        parts = [year, parent_folder]

        if value and capture_belongs(value):
            owner = event_id
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
                    owner = str(matching[0].get("id") or owner)
            elif child_folder:
                parts.append(child_folder)

            if preserve_day_folders:
                day_key = value[:10]
                if len(day_key) != 10:
                    return None
                parts.append(day_key)

            key = owner + ("@" + value[:10] if preserve_day_folders else "")
            organization = organization_path(target_leaves.get(key))
            if organization:
                parts.extend(PurePosixPath(organization).parts)
            parts.append(filename)
            return "/".join(parts)

        # Ohne belastbare Aufnahmezeit darf nichts in neue Tages-/Unterereignis-
        # Strukturen geraten. Bei einer reinen Ereignisordner-Änderung ist die
        # Lage dennoch eindeutig: Layout-Edits verwenden Organisation/Input,
        # Legacy-Aufträge behalten weiterhin ihre vollständige interne Lage.
        if not normalized_child_segments and not child_folder and not preserve_day_folders:
            if requested_layout_state is not None:
                organization = organization_path(target_leaves.get(event_id))
                if organization:
                    parts.extend(PurePosixPath(organization).parts)
                parts.append(filename)
                return "/".join(parts)
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
        if not incoming_workspace and not old_event_relative:
            path = PurePosixPath(old_path)
            if path.is_relative_to(current_root):
                old_event_relative = path.relative_to(current_root).as_posix()
        if not branch:
            for part in PurePosixPath(old_event_relative).parts[:-1]:
                if part in {"All", "Sorted", "Alle", "Sortiert", "Export"}:
                    branch = part
                    break
        if not branch:
            branch = "Alle"

        new_path = ""
        if family_id in requested_set:
            capture = str(
                observed.get("selected_capture_time")
                if observed is not None
                else row["selected_capture_time"] or ""
            )[:19]
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
            "planned_capture_time": str(
                observed.get("selected_capture_time")
                if observed is not None
                else row["selected_capture_time"] or ""
            )[:19],
        })

    reserved_archive_targets: set[str] = {
        str(item.get("new_path") or "").casefold()
        for item in file_plans
        if str(item.get("new_path") or "")
    }

    def reserve_archive_asset_target(candidate: str, asset_kind: str) -> str:
        key = str(candidate).casefold()
        if key not in reserved_archive_targets:
            reserved_archive_targets.add(key)
            return str(candidate)
        if asset_kind != "export":
            return str(candidate)

        path = PurePosixPath(str(candidate))
        suffix = path.suffix
        stem = path.name[:-len(suffix)] if suffix else path.name
        base = f"{stem}_Export"
        index = 0
        while True:
            name = (
                f"{base}{suffix}"
                if index == 0
                else f"{base}_{index:03d}{suffix}"
            )
            proposed = path.parent / name
            proposed_key = proposed.as_posix().casefold()
            if proposed_key not in reserved_archive_targets:
                reserved_archive_targets.add(proposed_key)
                return proposed.as_posix()
            index += 1

    if inventory is not None:
        from app.event_document import EVENT_DOCUMENT_FILENAME
        for item in inventory["files"]:
            if item.get("known_file_id") is not None:
                continue
            if str(item.get("filename") or "") == EVENT_DOCUMENT_FILENAME:
                # event.json wird als kanonische Ereignisbeschreibung separat
                # aus dem neuen SOLL-Zustand erzeugt und darf nicht gleichzeitig
                # als normales Bestands-Asset geplant werden.
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

            # Familienlose normale Fremddateien gehören dem Nutzer und
            # werden grundsätzlich nur als Hinweis inventarisiert. Exporte
            # bleiben eine verwaltete Produktrolle; familiengebundene XMP/
            # Sidecars folgen weiterhin ihrer Kamerafamilie.
            if family_id is None and asset_kind != "export":
                candidate = None
                action = "keep"
                new_path = old_path
                advisory = True
                advisory_reason = "unmanaged_user_file"
            else:
                advisory = False
                advisory_reason = ""
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
                    candidate = reserve_archive_asset_target(candidate, asset_kind)
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
                "advisory": advisory,
                "advisory_reason": advisory_reason,
            })

    # Freigewordene Archivbestände sind globaler SSD-Bestand. Wenn eine
    # solche Familie wieder direkt in ein archiviertes Ereignis aufgenommen
    # wird, gehören ihre XMP-/Exportdateien genauso zum neuen SOLL wie die
    # Kameraoriginale. released_archive_assets ist hierfür der dauerhafte,
    # SHA-256-geprüfte Herkunftsnachweis.
    if added_family_ids:
        placeholders = ",".join("?" for _ in sorted(added_family_ids))
        with database_connection(database_path) as connection:
            incoming_assets = [
                dict(row)
                for row in connection.execute(
                    f"""SELECT asset.*,ff.selected_capture_time,
                               ff.capture_time_confidence
                        FROM released_archive_assets asset
                        JOIN file_families ff ON ff.id=asset.family_id
                        WHERE asset.family_id IN ({placeholders})
                        ORDER BY asset.family_id,asset.id""",
                    tuple(sorted(added_family_ids)),
                ).fetchall()
            ]

        camera_targets_by_file_id = {
            int(item["file_id"]): str(item.get("new_path") or "")
            for item in file_plans
            if item.get("file_id") is not None
            and str(item.get("new_path") or "")
        }
        camera_targets_by_family: dict[int, list[str]] = {}
        for item in file_plans:
            if (
                item.get("family_id") is None
                or not str(item.get("new_path") or "")
            ):
                continue
            camera_targets_by_family.setdefault(
                int(item["family_id"]), []
            ).append(str(item["new_path"]))

        for item in incoming_assets:
            family_id = int(item["family_id"])
            old_path = str(item.get("current_relative_path") or "")
            filename = PurePosixPath(old_path.replace("\\", "/")).name
            if not filename:
                raise EventChangeRequestError(
                    "Eine freigewordene Zusatzdatei besitzt keinen Dateinamen."
                )
            asset_kind = str(item.get("asset_kind") or "other")
            capture = str(item.get("selected_capture_time") or "")[:19] or None
            source_file_id = item.get("source_file_id")
            candidate = None

            # XMP/abgeleitete Begleitdateien folgen bevorzugt exakt dem
            # zugehörigen Kameraoriginal. Dadurch bleiben Tages-, Unterereignis-
            # und benutzerdefinierte Organisationsordner konsistent.
            if asset_kind != "export" and source_file_id is not None:
                camera_target = camera_targets_by_file_id.get(int(source_file_id))
                if camera_target:
                    candidate = (
                        PurePosixPath(camera_target).parent / filename
                    ).as_posix()

            if candidate is None and asset_kind != "export":
                family_targets = camera_targets_by_family.get(family_id) or []
                if family_targets:
                    candidate = (
                        PurePosixPath(sorted(family_targets)[0]).parent / filename
                    ).as_posix()

            if candidate is None:
                candidate = target_for(
                    filename=filename,
                    capture=capture,
                    branch="Export" if asset_kind == "export" else "Alle",
                    old_event_relative_path="",
                )

            if not candidate:
                raise EventChangeRequestError(
                    "Eine freigewordene Zusatzdatei lässt sich nicht eindeutig "
                    "in die neue Archivstruktur einordnen: " + filename
                )

            candidate = reserve_archive_asset_target(candidate, asset_kind)
            asset_plans.append({
                "asset_kind": asset_kind,
                "source_file_id": source_file_id,
                "family_id": family_id,
                "old_path": old_path,
                "new_path": candidate,
                "action": "move",
                "expected_size_bytes": int(item.get("size_bytes") or 0),
                "expected_sha256": str(item.get("sha256") or ""),
                "selected_capture_time": capture,
                "capture_time_confidence": str(
                    item.get("capture_time_confidence") or "missing"
                ),
                "advisory": False,
                "advisory_reason": "",
                "source_root_kind": "shared_workspace",
                "workspace_original_path": old_path,
                "released_archive_asset_id": int(item["id"]),
            })

    # 0.28.5: Byte-identische XMP-/Exportdateien derselben Familie und Rolle
    # sind keine zusätzlichen Pflichtobjekte. Eine kanonische Repräsentation
    # bleibt verwaltet; weitere identische Kopien werden sichtbar als Hinweis
    # geführt und dürfen liegen bleiben, umbenannt oder gelöscht werden.
    duplicate_groups: dict[tuple[int, str, int, str], list[dict[str, Any]]] = {}
    for asset in asset_plans:
        family_id = asset.get("family_id")
        kind = str(asset.get("asset_kind") or "")
        digest = str(asset.get("expected_sha256") or "")
        if (
            family_id is None
            or kind not in {"xmp", "export"}
            or not digest
            or bool(asset.get("advisory"))
        ):
            continue
        key = (
            int(family_id),
            kind,
            int(asset.get("expected_size_bytes") or 0),
            digest,
        )
        duplicate_groups.setdefault(key, []).append(asset)

    for group in duplicate_groups.values():
        if len(group) < 2:
            continue
        canonical = min(
            group,
            key=lambda item: (
                len(Path(str(item.get("old_path") or "")).stem),
                str(item.get("old_path") or "").casefold(),
            ),
        )
        for asset in group:
            if asset is canonical:
                continue
            asset["advisory"] = True
            asset["advisory_reason"] = "redundant_duplicate"
            asset["action"] = "keep"
            asset["new_path"] = str(asset.get("old_path") or "")

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
    unresolved_assets = sum(
        1 for item in asset_plans
        if not bool(item.get("advisory")) and item["action"] == "unresolved"
    )
    advisory_assets = sum(1 for item in asset_plans if bool(item.get("advisory")))
    if unresolved_assets:
        lines.append(
            f"Nicht eindeutig zuordenbare verwaltete Sidecars: {unresolved_assets}"
        )
    if advisory_assets:
        lines.append(
            f"Zusätzliche nicht verwaltete Dateien (nur Hinweis): {advisory_assets}"
        )

    return {
        "families_with_plans": file_plans,
        "assets_with_plans": asset_plans,
        "selected_family_ids": sorted(requested_set),
        "folder_layout_state": requested_layout_state,
        "target_leaf_layouts": list(target_leaves.values()) if old_leaves else None,
        "normalized_subevents": normalized_child_segments if preview.get("subevents") else None,
        "structure_lines": lines,
        "structure_text": "\n".join(lines),
        "inventory_summary": inventory.get("summary") if inventory is not None else None,
        "diff_summary": {
            "removed_count": len(removed_family_ids),
            "added_count": len(added_family_ids),
            "kept_count": len(requested_set & current_family_ids),
            "total_changes": (
                sum(1 for item in file_plans if item["action"] != "keep")
                + sum(
                    1 for item in asset_plans
                    if not bool(item.get("advisory"))
                    and item["action"] != "keep"
                )
            ),
            "file_count": len(file_plans) + sum(
                1 for item in asset_plans if not bool(item.get("advisory"))
            ),
            "camera_file_count": len(file_plans),
            "asset_file_count": sum(
                1 for item in asset_plans if not bool(item.get("advisory"))
            ),
            "unresolved_asset_count": unresolved_assets,
            "advisory_asset_count": advisory_assets,
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
            "SELECT day_key FROM file_families WHERE id = ?",
            (family_id,),
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
    guided_structure_change_id: str | None = None,
) -> dict[str, Any]:
    """Change-Request fuer ein archiviertes Ereignis vorschlagen.

    Erzeugt einen neuen Aenderungsauftrag ohne die Datenbank zu veraendern.
    Gibt den ChangeRequest mit berechneten Aenderungspfaden zurueck.
    """
    import json
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()

    # 0.27.2: Unterereignis-IDs werden bereits im Vorschlag stabilisiert.
    # Dadurch kann die vorbereitete event.json exakt denselben SOLL-Zustand
    # beschreiben, der beim Abschluss in SQLite geschrieben wird.
    preview = dict(preview)
    preview.pop("target_leaf_layouts", None)
    if preview.get("subevents"):
        stable_subevents = []
        for item in preview.get("subevents") or []:
            segment = dict(item)
            if not str(segment.get("id") or "").strip():
                segment["id"] = "EVENT_" + uuid.uuid4().hex.upper()
            stable_subevents.append(segment)
        preview["subevents"] = stable_subevents

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
        from app.archive_recovery import assert_not_quarantined
        try:
            assert_not_quarantined(connection, event_id)
        except ValueError as error:
            raise EventChangeRequestError(str(error)) from error
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
    requested_layout_state = plan.get("folder_layout_state")
    target_leaf_layouts = plan.get("target_leaf_layouts")
    normalized_subevents = plan.get("normalized_subevents")
    if normalized_subevents is not None:
        preview["subevents"] = normalized_subevents
    if target_leaf_layouts is not None:
        preview["target_leaf_layouts"] = target_leaf_layouts
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
        if guided_structure_change_id:
            from app.event_structure_changes import validate_guided_structure_edit
            validate_guided_structure_edit(
                connection, event_id, guided_structure_change_id, preview,
                expected_root_kind="camera_archive",
            )
        from app.event_timeline import assert_editable_normal, continuous_event_overlaps, no_event_segment_overlaps
        from app.archive_reassignment_segments import proposed_ranges
        if preview.get('child_segments'):
            raise EventChangeRequestError('Getrennte Belegungssegmente sind für normale Ereignisse nicht zulässig.')
        if preview.get('event_kind','event') == 'event':
            assert_editable_normal(connection,event_id)
        for a,b in proposed_ranges(preview):
            if continuous_event_overlaps(connection,job_id,a,b,exclude_event_id=event_id) or no_event_segment_overlaps(connection,job_id,a,b,exclude_event_id=event_id):
                raise EventChangeRequestError('Die Änderung überschneidet sich mit belegter Zeit. Bitte zuerst das andere Ereignis bearbeiten.')
        from app.archive_recovery import assert_not_quarantined
        try:
            assert_not_quarantined(connection, event_id)
        except ValueError as error:
            raise EventChangeRequestError(str(error)) from error
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
                folder_structure_enabled, folder_input_path, folder_layout_json,
                status, version, proposed_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                (
                    int(bool(requested_layout_state["structure_enabled"]))
                    if requested_layout_state is not None else None
                ),
                (
                    str(requested_layout_state["input_path"])
                    if requested_layout_state is not None else None
                ),
                (
                    json.dumps(requested_layout_state["layout"], ensure_ascii=False, sort_keys=True)
                    if requested_layout_state is not None else None
                ),
                initial_status,
                version,
                now,
                now,
                now,
            ),
        )

        if target_leaf_layouts is not None:
            connection.execute(
                "UPDATE event_change_requests SET target_leaf_layouts_json=? WHERE id=?",
                (json.dumps(target_leaf_layouts, ensure_ascii=False), cr_id),
            )

        connection.execute('UPDATE event_change_requests SET time_model_version=2, guided_structure_change_id=? WHERE id=?',(guided_structure_change_id,cr_id))
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
                    source_root_kind, workspace_original_path, planned_capture_time,
                    confirmed, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
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
                    str(family_plan.get("planned_capture_time") or ""),
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
                    advisory,advisory_reason,planned_capture_time,
                    source_root_kind,workspace_original_path,
                    workspace_staging_path,released_archive_asset_id,
                    created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                    int(bool(asset.get("advisory"))),
                    str(asset.get("advisory_reason") or ""),
                    str(asset.get("selected_capture_time") or "")[:19],
                    str(asset.get("source_root_kind") or "camera_archive"),
                    str(asset.get("workspace_original_path") or ""),
                    str(asset.get("workspace_staging_path") or ""),
                    asset.get("released_archive_asset_id"),
                    now,
                    now,
                ),
            )

        connection.commit()

    # Der Hilfsbereich wird erst im expliziten Vorbereitungsschritt
    # materialisiert. Nach dem INSERT kann 0.27.2 aber auch die projizierte
    # event.json in die Planungsantwort einbeziehen.
    final_preparation = preparation
    if archive_root is not None and workspace_path is not None:
        try:
            from app.archive_staging import describe_archive_change_staging_for_request
            final_preparation = describe_archive_change_staging_for_request(
                database_path, archive_root, cr_id
            )
        except Exception:
            final_preparation = preparation

    # Rueckgabe mit Plan
    return {
        "change_request_id": cr_id,
        "event_id": event_id,
        "version": version,
        "status": initial_status,
        "plan": plan,
        "family_count": len(plan["families_with_plans"]),
        "diff_summary": plan["diff_summary"],
        "preparation_required": bool(final_preparation.get("required")),
        "preparation": final_preparation,
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
        released_asset_map = {
            (
                int(row["family_id"]) if row["family_id"] is not None else None,
                str(row["current_relative_path"] or ""),
            ): dict(row)
            for row in connection.execute(
                """SELECT id,family_id,current_relative_path
                   FROM released_archive_assets
                   ORDER BY id"""
            ).fetchall()
        }
        asset_rows = []
        for row in connection.execute(
            "SELECT * FROM event_change_asset_reviews WHERE change_request_id=? ORDER BY id",
            (cr_id,),
        ).fetchall():
            item = dict(row)
            item["review_kind"] = "asset"
            legacy_key = (
                int(item["family_id"]) if item.get("family_id") is not None else None,
                str(item.get("old_path") or ""),
            )
            legacy_released = released_asset_map.get(legacy_key)
            if (
                str(item.get("source_root_kind") or "camera_archive")
                    == "camera_archive"
                and not str(item.get("workspace_original_path") or "").strip()
                and item.get("released_archive_asset_id") is None
                and legacy_released is not None
            ):
                # Offene 0.32.7-Aufträge wurden durch Migration 042 mit dem
                # Default camera_archive ergänzt. Ihre tatsächliche Herkunft
                # lässt sich noch eindeutig aus dem Release-Journal ableiten.
                item["source_root_kind"] = "shared_workspace"
                item["workspace_original_path"] = str(item.get("old_path") or "")
                item["released_archive_asset_id"] = int(legacy_released["id"])
            item["file_id"] = None
            item["confirmed"] = 0
            legacy_advisory = bool(
                item.get("family_id") is None
                and str(item.get("asset_kind") or "other") != "export"
                and str(item.get("action") or "") == "keep"
                and str(item.get("old_path") or "")
                    == str(item.get("new_path") or "")
            )
            item["advisory"] = bool(item.get("advisory")) or legacy_advisory
            if item["advisory"] and not str(item.get("advisory_reason") or ""):
                item["advisory_reason"] = "unmanaged_user_file"
            asset_rows.append(item)
    return camera_rows + asset_rows


def propose_archived_event_deletion(
    database_path: Path,
    job_id: str,
    event_id: str,
    *,
    archive_root: Path | None = None,
) -> dict[str, Any]:
    """Create a complete read-only deletion request for an archived event.

    The current archive tree is authoritative. Managed XMP/export/sidecar
    assets are released together with their camera family. Unresolved files
    block deletion instead of being silently left behind.
    """
    now = datetime.now(timezone.utc).isoformat()

    inventory: dict[str, Any] | None = None
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
            "SELECT * FROM events WHERE id=? AND job_id=?", (event_id, job_id)
        ).fetchone()
        if event is None:
            raise EventChangeRequestError("Ereignis wurde nicht gefunden.")
        if not event["archived_at"]:
            raise EventChangeRequestError(
                "Nur archivierte Ereignisse benötigen diesen manuellen Löschauftrag."
            )
        from app.archive_recovery import assert_not_quarantined
        try:
            assert_not_quarantined(connection, event_id)
        except ValueError as error:
            raise EventChangeRequestError(str(error)) from error
        existing = connection.execute(
            """SELECT id FROM event_change_requests
               WHERE event_id=? AND status IN ('aenderbar_vorschlagen','aenderbar_bestaetigt')
               ORDER BY version DESC LIMIT 1""",
            (event_id,),
        ).fetchone()
        if existing is not None:
            raise EventChangeRequestError(
                "Für dieses Ereignis ist bereits ein offener Änderungsauftrag vorhanden."
            )

        assigned = connection.execute(
            """SELECT DISTINCT ea.family_id
               FROM event_assignments ea JOIN events e ON e.id=ea.event_id
               WHERE COALESCE(e.parent_event_id,e.id)=?
                 AND ea.family_id IS NOT NULL ORDER BY ea.family_id""",
            (event_id,),
        ).fetchall()
        family_ids = [int(r["family_id"]) for r in assigned]
        if not family_ids:
            raise EventChangeRequestError(
                "Dem archivierten Ereignis sind keine Familien zugeordnet."
            )

        camera_rows: list[dict[str, Any]] = []
        asset_rows: list[dict[str, Any]] = []

        if inventory is not None:
            from app.event_document import EVENT_DOCUMENT_FILENAME

            unresolved: list[str] = []
            for item in inventory.get("files") or []:
                filename = str(item.get("filename") or "")
                if filename == EVENT_DOCUMENT_FILENAME:
                    continue

                known_file_id = item.get("known_file_id")
                family_id = item.get("family_id")
                if family_id is not None:
                    family_id = int(family_id)

                if known_file_id is not None:
                    if family_id not in family_ids:
                        unresolved.append(str(item.get("relative_path") or filename))
                        continue
                    camera_rows.append({
                        "file_id": int(known_file_id),
                        "family_id": family_id,
                        "old_path": str(item.get("relative_path") or ""),
                        "expected_size_bytes": int(item.get("size_bytes") or 0),
                        "expected_sha256": str(item.get("sha256") or ""),
                        "planned_capture_time": str(item.get("selected_capture_time") or "")[:19],
                    })
                    continue

                if family_id is None or family_id not in family_ids:
                    unresolved.append(str(item.get("relative_path") or filename))
                    continue

                asset_rows.append({
                    "family_id": family_id,
                    "source_file_id": item.get("source_file_id"),
                    "asset_kind": str(item.get("asset_kind") or "other"),
                    "old_path": str(item.get("relative_path") or ""),
                    "expected_size_bytes": int(item.get("size_bytes") or 0),
                    "expected_sha256": str(item.get("sha256") or ""),
                    "planned_capture_time": str(item.get("selected_capture_time") or "")[:19],
                })

            if unresolved:
                raise EventChangeRequestError(
                    "Das archivierte Ereignis enthält nicht eindeutig zuordenbare "
                    "Dateien. Löschung abgebrochen: " + " | ".join(unresolved[:10])
                )
        else:
            placeholders = ",".join("?" for _ in family_ids)
            camera_rows = [
                {
                    "file_id": int(row["file_id"]),
                    "family_id": int(row["family_id"]),
                    "old_path": str(
                        row["current_relative_path"]
                        or row["original_relative_path"]
                        or ""
                    ).replace("\\", "/").lstrip("/"),
                    "expected_size_bytes": int(row["size_bytes"] or 0),
                    "expected_sha256": str(
                        row["sha256_current"] or row["sha256_original"] or ""
                    ),
                    "planned_capture_time": str(row["selected_capture_time"] or "")[:19],
                }
                for row in connection.execute(
                    f"""SELECT f.id AS file_id,f.family_id,
                               f.current_relative_path,f.original_relative_path,
                               f.size_bytes,f.sha256_current,f.sha256_original,
                               f.selected_capture_time
                        FROM files f
                        WHERE f.family_id IN ({placeholders})
                        ORDER BY f.family_id,f.id""",
                    tuple(family_ids),
                ).fetchall()
            ]

        version_row = connection.execute(
            "SELECT COALESCE(MAX(version),0) AS v FROM event_change_requests WHERE event_id=?",
            (event_id,),
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
                cr_id,event_id,job_id,str(event["name"]),
                "Ereignis löschen; alle verwalteten Archivdateien sicher zurückholen.",
                str(event["folder_name"]),None,0,int(bool(event["preserve_day_folders"])),
                str(event["start_datetime"] or "")[:10],
                str(event["end_datetime"] or "")[:10],
                None,None,str(event["event_kind"] or "event"),None,
                json.dumps([],ensure_ascii=False),
                json.dumps(family_ids,ensure_ascii=False),
                len(camera_rows) + len(asset_rows),
                len(family_ids),
                "aenderbar_vorschlagen",version,now,now,now,
            ),
        )

        for row in camera_rows:
            connection.execute(
                """INSERT INTO event_change_file_reviews(
                       change_request_id,family_id,file_id,old_path,new_path,action,
                       expected_size_bytes,expected_sha256,planned_capture_time,
                       confirmed,created_at,updated_at)
                   VALUES (?,?,?,?,?,'delete',?,?,?,0,?,?)""",
                (
                    cr_id,row["family_id"],row["file_id"],row["old_path"],"",
                    row["expected_size_bytes"],row["expected_sha256"],
                    str(row.get("planned_capture_time") or ""),now,now,
                ),
            )

        for row in asset_rows:
            connection.execute(
                """INSERT INTO event_change_asset_reviews(
                       change_request_id,asset_kind,source_file_id,family_id,
                       old_path,new_path,action,expected_size_bytes,expected_sha256,
                       advisory,advisory_reason,planned_capture_time,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'unresolved',?,?,0,'',?,?,?)""",
                (
                    cr_id,row["asset_kind"],row.get("source_file_id"),row["family_id"],
                    row["old_path"],"",row["expected_size_bytes"],
                    row["expected_sha256"],
                    str(row.get("planned_capture_time") or ""),now,now,
                ),
            )

        connection.commit()

    return {
        "status": "change_request_created",
        "pending_delete": True,
        "archive_read_only": True,
        "change_request_id": cr_id,
        "event_id": event_id,
        "event_name": str(event["name"]),
        "released_family_count": len(family_ids),
        "released_file_count": len(camera_rows) + len(asset_rows),
        "released_asset_count": len(asset_rows),
        "reassignment_required": True,
        "message": (
            "Manueller Löschauftrag erstellt. Kamera- und Zusatzdateien werden "
            "vollständig in den zentralen Rückkehrbestand aufgenommen."
        ),
    }

