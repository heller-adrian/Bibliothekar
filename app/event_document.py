"""Portable Ereignisbeschreibung: ``event.json``.

Angewendete Ereignisse erhalten im gemeinsamen Arbeitsbereich eine
portable ``event.json`` (Name, Zeitraum, Struktur, Dateifamilien,
Prüfsummen und Ordneroptionen). Für den bearbeitbaren App-Zustand ist
SQLite maßgeblich; Änderungen werden über eine dauerhaft protokollierte
Aufgabe in die portable Datei nachgeführt. Fremde oder beschädigte
Ereignisdokumente werden dabei nicht blind überschrieben.

Das Modul ist bewusst ohne Seiteneffekt auf SQLite *schreibend* gehalten:
Es baut und schreibt Dokumente, lädt sie ein und erkennt Abweichungen.
Das eigentliche Nachführen des Index passiert in ``event_editing``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator
from contextlib import nullcontext
import sqlite3
import hashlib
import json
import os

from app.database import database_connection
from app.event_access import event_family_rows, event_file_rows, event_source_jobs
from app.event_layout import ensure_event_layout_snapshot
from app.event_leaf_layouts import effective_leaf_layouts

from app.workspace_layout import shared_work_root

EVENT_DOCUMENT_VERSION = 3
EVENT_DOCUMENT_FILENAME = "event.json"


class EventDocumentError(RuntimeError):
    pass


def event_document_path(
    workspace_root: Path,
    year: str,
    folder_name: str,
) -> Path:
    """Pfad einer event.json aus Jahr + Ereignisordnername."""

    work_root = shared_work_root(Path(workspace_root))
    return work_root / str(year)[:4] / str(folder_name) / EVENT_DOCUMENT_FILENAME


def _iso_date(value: Any) -> str:
    return str(value or "")[:10]


def _iso_time(value: Any) -> str:
    raw = str(value or "")
    return raw[11:16] if len(raw) >= 16 else ""


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _families_of_event(
    connection: Any,
    job_id: str,
    event_id: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            ff.id AS family_id,
            ff.family_key,
            ff.selected_capture_time,
            ff.capture_time_confidence,
            COUNT(f.id) AS file_count,
            COALESCE(SUM(f.size_bytes), 0) AS total_size_bytes
        FROM file_families AS ff
        JOIN event_assignments AS ea ON ea.family_id = ff.id
        JOIN events AS assigned ON assigned.id = ea.event_id
        JOIN files AS f ON f.family_id = ff.id AND f.job_id = ff.job_id
        WHERE COALESCE(assigned.parent_event_id,assigned.id) = ?
          AND ea.family_id IS NOT NULL
        GROUP BY ff.id
        ORDER BY ff.selected_capture_time, ff.id
        """,
        (event_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def build_event_document_from_db(
    database_path: Path,
    workspace_root: Path,
    job_id: str,
    event_id: str,
    *,
    include_archived: bool = False,
    transaction_connection: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Eines Ereignisses aus dem lebhaften SQLite-Zustand bauen.

    Gibt ``None`` zurück, wenn das Ereignis unbekannt ist oder kein
    angewendetes Ereignis mit mindestens einer zugeordneten Familie ist
    (nur dann existiert ein Ereignisordner).
    """

    with (
        database_connection(database_path)
        if transaction_connection is None
        else nullcontext(transaction_connection)
    ) as connection:
        event = connection.execute(
            "SELECT * FROM events WHERE id = ? AND parent_event_id IS NULL",
            (event_id,),
        ).fetchone()

        if event is None or str(event["event_level"]) != "parent":
            return None

        status = str(event["status"])
        if status == "archived":
            if not include_archived:
                return None
        elif status != "applied" or event["archived_at"]:
            return None

        children = [dict(r) for r in connection.execute("SELECT * FROM events WHERE parent_event_id=? ORDER BY start_datetime,id", (event_id,))]
        child_dict = children[0] if children else None
        segments = [dict(r) for r in connection.execute("SELECT * FROM event_time_segments WHERE event_id=? ORDER BY start_datetime,id", (event_id,))]
        from app.event_timeline import normal_event_ranges
        occupancy = normal_event_ranges(connection,event_id) if event['event_kind']=='event' else [(x['start_datetime'],x['end_datetime']) for x in segments]

        families = event_family_rows(connection, event_id)
        files = event_file_rows(connection, event_id)
        sources = event_source_jobs(connection, event_id)
        layout_state = ensure_event_layout_snapshot(
            connection, event_id, now=datetime.now(timezone.utc).isoformat()
        )
        leaf_layouts = list(effective_leaf_layouts(connection, event_id).values())

        assignment_day_rows = connection.execute(
            """
            SELECT assigned.id AS assigned_event_id,
                   assigned.parent_event_id,
                   COALESCE(ff.selected_capture_time, direct_ff.selected_capture_time) AS selected_capture_time
            FROM event_assignments AS ea
            JOIN events AS assigned ON assigned.id = ea.event_id
            LEFT JOIN file_families AS ff ON ff.id = ea.family_id
            LEFT JOIN files AS direct_file ON direct_file.id = ea.file_id
            LEFT JOIN file_families AS direct_ff ON direct_ff.id = direct_file.family_id
            WHERE (assigned.id = ? OR assigned.parent_event_id = ?)
            """,
            (event_id, event_id),
        ).fetchall()

        root_kind = "camera_archive" if status == "archived" else "shared_workspace"
        inventory_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_inventory_files'"
        ).fetchone()
        inventory_rows = (
            [
                dict(r) for r in connection.execute(
                    """SELECT relative_path,filename,size_bytes,sha256,asset_kind,
                              known_file_id,family_id,event_relative_path
                       FROM event_inventory_files
                       WHERE event_id=? AND root_kind=?
                       ORDER BY event_relative_path""",
                    (event_id, root_kind),
                ).fetchall()
            ]
            if inventory_table is not None
            else []
        )
        file_rows = files

    if not families:
        return None

    entries: list[dict[str, Any]] = []

    if inventory_rows:
        for row in inventory_rows:
            relative_path = str(row.get("relative_path") or "")
            if not relative_path:
                continue
            entries.append({
                "relative_path": relative_path,
                "filename": str(row.get("filename") or PurePosixPath(relative_path).name),
                "size_bytes": int(row.get("size_bytes") or 0),
                "sha256": str(row.get("sha256") or ""),
                "asset_kind": str(row.get("asset_kind") or "other"),
                "family_id": row.get("family_id"),
                "known_file_id": row.get("known_file_id"),
                "ordered": True,
            })
    else:
        for row in file_rows:
            relative_path = str(row["current_relative_path"] or "")
            if not relative_path:
                continue
            parts = PurePosixPath(relative_path).parts
            ordered = bool(parts)
            entries.append({
                "relative_path": relative_path,
                "filename": parts[-1] if ordered else str(row["original_filename"]),
                "size_bytes": int(row["size_bytes"] or 0),
                "sha256": str(row["sha256_current"] or row["sha256_original"] or ""),
                "asset_kind": "camera_original",
                "family_id": row.get("family_id"),
                "known_file_id": row.get("id"),
                "ordered": ordered,
            })

    if not entries:
        return None

    preserve_day_folders = bool(event["preserve_day_folders"])

    structure_lines = [
        str(_iso_date(event["start_datetime"]))[:4],
        f"└── {event['folder_name']}",
    ]
    for child in children:
        if child['folder_name']:
            structure_lines.append(f"    └── {child['folder_name']}")
    days_by_event: dict[str, set[str]] = {}
    for row in assignment_day_rows:
        capture = str(row["selected_capture_time"] or "")
        day_key = capture[:10]
        if len(day_key) != 10:
            continue
        days_by_event.setdefault(str(row["assigned_event_id"]), set()).add(day_key)

    day_keys = sorted(days_by_event.get(str(event_id), set()))
    structure_children = [
        {
            **child,
            "day_keys": sorted(days_by_event.get(str(child["id"]), set())),
        }
        for child in children
    ]

    from app.structure_view import render_structure
    structure_lines = render_structure(
        str(event["start_datetime"])[:4],
        event["folder_name"],
        day_keys,
        structure_children,
        preserve_day_folders,
        layout_state=layout_state,
        leaf_layouts=leaf_layouts,
        parent_event_id=event_id,
    )
    return {
        "document_version": EVENT_DOCUMENT_VERSION,
        "source": "kamera-automatisierung",
        "source_app_version": None,
        "event": {
            "id": str(event["id"]),
            "name": str(event["name"]),
            "event_kind": str(event["event_kind"] or "event"),
            "start_date": _iso_date(event["start_datetime"]),
            "end_date": _iso_date(event["end_datetime"]),
            "start_datetime": str(event['start_datetime']),
            "end_datetime": str(event['end_datetime']),
            "start_time": _iso_time(event['start_datetime']),
            "end_time": _iso_time(event['end_datetime']),
            "uses_time_range": _iso_time(event['start_datetime']) != '00:00' or _iso_time(event['end_datetime']) != '23:59',
            "time_model_version": int(event['time_model_version']),
            "occupied_intervals": [{'start_datetime':a,'end_datetime':b} for a,b in occupancy],
            "preserve_day_folders": preserve_day_folders,
            "folder_name": str(event["folder_name"]),
            "status": str(event["status"]),
            "applied_at": event["applied_at"],
            "edited_at": event["edited_at"],
            "revision": int(event["revision"] or 1),
            "notes": str(event["notes"] or ""),
        },
        "source_jobs": [
            {
                "job_id": str(row["job_id"]),
                "source_label": str(row.get("source_label") or row["job_id"]),
            }
            for row in sources
        ],
        "folder_layout": {
            "structure_enabled": bool(layout_state["structure_enabled"]),
            "input_path": str(layout_state["input_path"]),
            "layout": layout_state["layout"],
            "revision": int(layout_state["revision"]),
        },
        **({"leaf_folder_layouts": leaf_layouts} if leaf_layouts else {}),
        "child_events": children,
        "no_event_segments": segments,
        "child_event": (
            {
                "id": str(child_dict["id"]),
                "name": str(child_dict["name"]),
                "folder_name": str(child_dict["folder_name"]),
                "start_datetime": str(child_dict["start_datetime"]),
                "end_datetime": str(child_dict["end_datetime"]),
            }
            if child_dict is not None
            else None
        ),
        "families": [
            {
                "family_id": int(row["family_id"]),
                "family_key": str(row["family_key"]),
                "selected_capture_time": row["selected_capture_time"],
                "capture_time_confidence": row["capture_time_confidence"],
                "file_count": int(row["file_count"]),
                "total_size_bytes": int(row["total_size_bytes"]),
            }
            for row in families
        ],
        "files": entries,
        "structure": "\n".join(structure_lines),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": "kamera-automatisierung event.json",
    }


def write_event_document(
    workspace_root: Path,
    document: dict[str, Any],
    *,
    app_version: str | None = None,
    require_existing_directory: bool = False,
) -> Path:
    """Ein Ereignisdokument atomar in seinen Ordner schreiben."""

    event = dict(document.get("event") or {})
    year = str(event.get("start_date") or "")[:4]
    folder_name = str(event.get("folder_name") or "")

    if not year or not folder_name:
        raise EventDocumentError("Für die event.json fehlen Jahr oder Ereignisordner.")
    if "/" in folder_name or "\\" in folder_name or folder_name in {".", ".."}:
        raise EventDocumentError("Ungültiger Ereignisordnername für event.json.")

    if app_version:
        document = dict(document)
        document["source_app_version"] = app_version
        document["generated_at"] = datetime.now(timezone.utc).isoformat()

    path = event_document_path(workspace_root, year, folder_name)
    if require_existing_directory:
        if not path.parent.is_dir():
            raise EventDocumentError("Der vorhandene Ereignisordner fehlt.")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    encoded = payload.encode("utf-8")
    digest_prefix = hashlib.sha256(encoded).hexdigest()[:12]

    target = path.resolve(strict=False)
    work_root = (shared_work_root(Path(workspace_root))).resolve(strict=False)
    try:
        target.relative_to(work_root)
    except ValueError as error:
        raise EventDocumentError("Der event.json-Pfad verlässt den Arbeitsbereich.") from error

    tmp = path.with_name(f"{EVENT_DOCUMENT_FILENAME}.tmp.{digest_prefix}")
    try:
        with tmp.open("wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
        _fsync_directory(path.parent)
    finally:
        tmp.unlink(missing_ok=True)

    return target


def read_event_document(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def discover_event_documents(workspace_root: Path) -> Iterator[Path]:
    work_root = shared_work_root(Path(workspace_root))
    if not work_root.is_dir():
        return
    yield from sorted(work_root.glob(f"*/*/{EVENT_DOCUMENT_FILENAME}"))


def load_event_document(workspace_root: Path, event_id: str) -> dict[str, Any] | None:
    """Ein Dokument über die Ereignis-ID laden (durchsucht den Arbeitsbereich)."""

    for path in discover_event_documents(workspace_root):
        try:
            document = read_event_document(path)
        except (OSError, ValueError):
            continue
        if str((document.get("event") or {}).get("id") or "") == str(event_id):
            return document
    return None


def event_document_matches_db(
    database_path: Path,
    workspace_root: Path,
    job_id: str,
    event_id: str,
    document: dict[str, Any],
) -> dict[str, Any]:
    """Gleiche ein Dokument mit dem SQLite-Zustand ab (nur lesend).

    Liefert eine Liste der Felder, in denen sich Dokument und Index
    unterscheiden – Grundlage für „event.json ist führend, SQLite wird
    nachgeführt".
    """

    try:
        fresh = build_event_document_from_db(database_path, workspace_root, job_id, event_id)
    except Exception:
        return {"ok": False, "mismatches": ["db_unverfügbar"]}

    if fresh is None:
        # SQLite kennt das Ereignis nicht mehr als angewendet – dann ist das
        # Dokument überholt.
        return {"ok": False, "mismatches": ["nicht_mehr_anewendet"]}

    drift: list[str] = []
    doc_event = document.get("event") or {}
    fresh_event = fresh["event"]

    for key in ("id", "name", "event_kind", "start_date", "end_date",
                 "uses_time_range", "preserve_day_folders", "folder_name",
                 "revision", "status", "start_datetime", "end_datetime",
                 "time_model_version", "occupied_intervals"):
        if str(doc_event.get(key)) != str(fresh_event.get(key)):
            drift.append(str(key))

    for key in ("document_version", "source_jobs", "folder_layout", "child_events", "no_event_segments", "structure", "files"):
        if document.get(key) != fresh.get(key):
            drift.append(key)
    # New events may have independent parent/child/day layout snapshots.
    # Keep old documents compatible, but do not ignore drift once such a
    # snapshot exists on either side.
    if "leaf_folder_layouts" in document or "leaf_folder_layouts" in fresh:
        if document.get("leaf_folder_layouts") != fresh.get("leaf_folder_layouts"):
            drift.append("leaf_folder_layouts")

    doc_families = {int(f.get("family_id")) for f in document.get("families") or []}
    fresh_families = {int(f["family_id"]) for f in fresh["families"]}
    if doc_families != fresh_families:
        drift.append("families")

    return {"ok": not drift, "mismatches": drift, "fresh": fresh}


def sync_event_document_after_change(
    database_path: Path,
    workspace_root: Path,
    job_id: str,
    event_id: str,
) -> None:
    """
    Nach dem Sortieren (oder anderen Änderungen) das portable event.json 
    aus dem aktuellen SQLite-Zustand neu schreiben, um die Synchronität zu wahren.
    """
    document = build_event_document_from_db(database_path, workspace_root, job_id, event_id)
    if document:
        write_event_document(workspace_root, document)

