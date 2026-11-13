from __future__ import annotations

"""Portable event.json for a not-yet-finished manual archive change.

The camera archive stays strictly read-only.  This module only builds a
stable representation of the requested SOLL state so that archive_staging can
write it below Arbeitsbereich/Später zuordnen.  The user copies the file into
the archive and the final verification checks it by size and SHA-256.
"""

from pathlib import PurePosixPath
from typing import Any
import hashlib
import json

from app.database import database_connection
from app.event_document import EVENT_DOCUMENT_FILENAME, EVENT_DOCUMENT_VERSION
from app.structure_view import render_structure


SOURCE_APP_VERSION = "0.27.5"


class ArchiveChangeDocumentError(RuntimeError):
    pass


def _loads(value: Any, default: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except Exception:
        return default


def _event_bounds(cr: dict[str, Any], no_event_segments: list[dict[str, Any]]) -> tuple[str, str]:
    if str(cr.get("event_kind") or "event") == "no_event":
        if not no_event_segments:
            raise ArchiveChangeDocumentError("Für „Ohne Ereignis“ fehlen die Zeitsegmente.")
        return (
            str(no_event_segments[0]["start_datetime"])[:19],
            str(no_event_segments[-1]["end_datetime"])[:19],
        )
    start_date = str(cr.get("start_date") or "")
    end_date = str(cr.get("end_date") or "")
    if bool(cr.get("uses_time_range")):
        return (
            f"{start_date}T{str(cr.get('start_time') or '00:00')}:00",
            f"{end_date}T{str(cr.get('end_time') or '23:59')}:59",
        )
    return (f"{start_date}T00:00:00", f"{end_date}T23:59:59")


def _normalise_children(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in raw:
        child_id = str(item.get("id") or "").strip()
        if not child_id:
            raise ArchiveChangeDocumentError(
                "Ein vorbereitetes Unterereignis besitzt noch keine stabile ID."
            )
        start = str(item.get("start_datetime") or "")
        end = str(item.get("end_datetime") or "")
        if len(start) == 16:
            start += ":00"
        if len(end) == 16:
            end += ":59"
        name = str(item.get("name") or "Unterereignis")
        folder = str(item.get("folder_name") or item.get("folder") or "").strip()
        if not folder and item.get('create_subfolder') is not False:
            folder = (
                f"{start[5:16].replace('T',' ').replace(':','-')} - "
                f"{end[5:16].replace('T',' ').replace(':','-')} - {name}"
            )
        result.append({
            "id": child_id,
            "name": name,
            "folder_name": folder,
            "start_datetime": start[:19],
            "end_datetime": end[:19],
            "event_level": "child",
            "event_kind": "event",
            "status": "archived",
        })
    return sorted(result, key=lambda item: (item["start_datetime"], item["id"]))


def build_projected_archive_event_document(
    database_path,
    cr_id: str,
) -> dict[str, Any] | None:
    with database_connection(database_path) as connection:
        cr_row = connection.execute(
            "SELECT * FROM event_change_requests WHERE id=?", (cr_id,)
        ).fetchone()
        if cr_row is None:
            raise ArchiveChangeDocumentError("Änderungsauftrag wurde nicht gefunden.")
        cr = dict(cr_row)
        if bool(cr.get("delete_event") or 0):
            return None

        event_row = connection.execute(
            "SELECT * FROM events WHERE id=? AND job_id=?",
            (str(cr["event_id"]), str(cr["job_id"])),
        ).fetchone()
        if event_row is None:
            raise ArchiveChangeDocumentError("Archiviertes Ereignis wurde nicht gefunden.")
        event = dict(event_row)

        from app.event_layout import (
            ensure_event_layout_snapshot,
            normalize_layout,
            validate_input_path,
        )
        current_layout = ensure_event_layout_snapshot(
            connection,
            str(cr["event_id"]),
            now=str(cr.get("proposed_at") or cr.get("created_at") or ""),
        )
        if cr.get("folder_layout_json") is not None:
            requested_layout = normalize_layout(
                _loads(cr.get("folder_layout_json"), current_layout["layout"])
            )
            requested_enabled = bool(cr.get("folder_structure_enabled"))
            requested_input = validate_input_path(
                requested_layout,
                cr.get("folder_input_path") or "",
                structure_enabled=requested_enabled,
            )
            projected_layout_state = {
                "structure_enabled": requested_enabled,
                "input_path": requested_input,
                "layout": requested_layout,
                "revision": int(current_layout.get("revision") or 1) + 1,
            }
        else:
            projected_layout_state = {
                "structure_enabled": bool(current_layout["structure_enabled"]),
                "input_path": str(current_layout["input_path"]),
                "layout": current_layout["layout"],
                "revision": int(current_layout.get("revision") or 1),
            }

        selected_ids = sorted({
            int(value)
            for value in _loads(cr.get("selected_family_ids"), [])
        })
        family_rows: list[dict[str, Any]] = []
        if selected_ids:
            placeholders = ",".join("?" for _ in selected_ids)
            family_rows = [
                dict(row)
                for row in connection.execute(
                    f"""SELECT id AS family_id,family_key,selected_capture_time,
                               capture_time_confidence
                        FROM file_families
                        WHERE id IN ({placeholders})
                        ORDER BY selected_capture_time,id""",
                    tuple(selected_ids),
                ).fetchall()
            ]

        review_rows = [
            dict(row)
            for row in connection.execute(
                """SELECT * FROM event_change_file_reviews
                   WHERE change_request_id=?
                     AND action<>'delete'
                   ORDER BY family_id,id""",
                (cr_id,),
            ).fetchall()
        ]

    no_event_segments = list(_loads(cr.get("no_event_segments"), []))
    if str(cr.get("event_kind") or "event") == "no_event":
        from app.event_timeline import normalize_no_event_segments
        try:
            no_event_segments = normalize_no_event_segments(no_event_segments)
        except Exception as exc:
            raise ArchiveChangeDocumentError(
                "Die vorbereiteten „Ohne Ereignis“-Zeitsegmente sind ungültig."
            ) from exc
    children = _normalise_children(list(_loads(cr.get("child_segments_json"), [])))
    start_datetime, end_datetime = _event_bounds(cr, no_event_segments)
    preserve_day_folders = bool(cr.get("preserve_day_folders"))
    selected_set = set(selected_ids)

    reviews_by_family: dict[int, list[dict[str, Any]]] = {}
    file_entries: list[dict[str, Any]] = []
    for row in review_rows:
        family_id = int(row["family_id"])
        if family_id not in selected_set:
            continue
        final_path = str(row.get("new_path") or row.get("old_path") or "").replace("\\", "/").strip("/")
        if not final_path:
            continue
        reviews_by_family.setdefault(family_id, []).append(row)
        parts = PurePosixPath(final_path).parts
        file_entries.append({
            "relative_path": final_path,
            "filename": parts[-1],
            "size_bytes": int(row.get("expected_size_bytes") or 0),
            "sha256": str(row.get("expected_sha256") or ""),
            "ordered": "Alle" in parts,
        })

    family_entries = []
    day_by_family: dict[int, str] = {}
    for row in family_rows:
        family_id = int(row["family_id"])
        members = reviews_by_family.get(family_id, [])
        capture = str(row.get("selected_capture_time") or "")
        if len(capture) >= 10:
            day_by_family[family_id] = capture[:10]
        family_entries.append({
            "family_id": family_id,
            "family_key": str(row.get("family_key") or ""),
            "selected_capture_time": row.get("selected_capture_time"),
            "capture_time_confidence": row.get("capture_time_confidence"),
            "file_count": len(members),
            "total_size_bytes": sum(int(member.get("expected_size_bytes") or 0) for member in members),
        })

    parent_days: set[str] = set()
    child_days: dict[str, set[str]] = {str(child["id"]): set() for child in children}
    for row in family_rows:
        family_id = int(row["family_id"])
        capture = str(row.get("selected_capture_time") or "")[:19]
        day = day_by_family.get(family_id)
        if not day:
            continue
        owner = next(
            (
                child for child in children
                if str(child["start_datetime"]) <= capture <= str(child["end_datetime"])
            ),
            None,
        )
        if owner is None:
            parent_days.add(day)
        else:
            child_days[str(owner["id"])].add(day)

    structure_children = [
        {**child, "day_keys": sorted(child_days.get(str(child["id"]), set()))}
        for child in children
    ]
    year = str(cr.get("start_date") or start_datetime)[:4]
    folder_name = str(cr.get("parent_folder") or "")
    target_leaves = _loads(cr.get("target_leaf_layouts_json"), [])
    structure_lines = render_structure(
        year,
        folder_name,
        sorted(parent_days),
        structure_children,
        preserve_day_folders,
        layout_state=projected_layout_state,
        leaf_layouts=target_leaves,
        parent_event_id=str(event["id"]),
    )

    occupied_intervals = (
        [
            {
                "start_datetime": str(segment.get("start_datetime") or "")[:19],
                "end_datetime": str(segment.get("end_datetime") or "")[:19],
            }
            for segment in no_event_segments
        ]
        if str(cr.get("event_kind") or "event") == "no_event"
        else [{"start_datetime": start_datetime, "end_datetime": end_datetime}]
    )

    generated_at = str(cr.get("proposed_at") or cr.get("created_at") or "")
    return {
        "document_version": EVENT_DOCUMENT_VERSION,
        "source": "kamera-automatisierung",
        "source_app_version": SOURCE_APP_VERSION,
        "event": {
            "id": str(event["id"]),
            "name": str(cr.get("event_name") or event.get("name") or ""),
            "event_kind": str(cr.get("event_kind") or event.get("event_kind") or "event"),
            "start_date": start_datetime[:10],
            "end_date": end_datetime[:10],
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "start_time": start_datetime[11:16],
            "end_time": end_datetime[11:16],
            "uses_time_range": bool(cr.get("uses_time_range")),
            "time_model_version": 2,
            "occupied_intervals": occupied_intervals,
            "preserve_day_folders": preserve_day_folders,
            "folder_name": folder_name,
            "status": "archived",
            "applied_at": event.get("applied_at"),
            "archived_at": event.get("archived_at"),
            "edited_at": generated_at,
            "revision": int(event.get("revision") or 1) + 1,
            "notes": str(cr.get("notes") or ""),
        },
        "folder_layout": projected_layout_state,
        **({"leaf_folder_layouts": target_leaves} if target_leaves else {}),
        "child_events": structure_children,
        "no_event_segments": no_event_segments,
        "child_event": structure_children[0] if len(structure_children) == 1 else None,
        "families": family_entries,
        "files": sorted(file_entries, key=lambda item: item["relative_path"]),
        "structure": "\n".join(structure_lines),
        "generated_at": generated_at,
        "generated_by": "kamera-automatisierung event.json · Archivänderung",
    }


def projected_archive_event_document_spec(database_path, cr_id: str) -> dict[str, Any] | None:
    document = build_projected_archive_event_document(database_path, cr_id)
    if document is None:
        return None
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    encoded = payload.encode("utf-8")
    event = document["event"]
    target = PurePosixPath(
        str(event["start_date"])[:4],
        str(event["folder_name"]),
        EVENT_DOCUMENT_FILENAME,
    ).as_posix()
    return {
        "target_relative_path": target,
        "payload": payload,
        "size_bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest(),
    }
