from __future__ import annotations

from pathlib import Path
import hashlib

from app.database import (
    database_connection,
    delete_planned_event,
    get_event_edit_context,
    initialize_database,
)
from app.event_layout import ensure_event_layout_snapshot, update_event_layout
from app.planning import list_global_released_archive_groups, list_job_planning_overview
from app.sort_plan import build_event_sort_plan
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from tests.backend.test_0263_event_inventory import NOW, seed_event, seed_job


def _seed_family_file(
    connection,
    *,
    job_id: str,
    stem: str,
    capture: str,
    current_path: str,
    content: bytes,
) -> tuple[int, int]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, stem, stem, capture),
        ).lastrowid
    )
    digest = hashlib.sha256(content).hexdigest()
    file_id = int(
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?, 'DateTimeOriginal',
                         'high','not_required','not_requested',?,?,'shared_workspace')""",
            (
                job_id,
                family_id,
                "DCIM/" + stem + ".JPG",
                current_path,
                stem + ".JPG",
                len(content),
                digest,
                digest,
                capture,
                NOW,
                NOW,
            ),
        ).lastrowid
    )
    return family_id, file_id


def _insert_released_asset(
    connection,
    *,
    job_id: str,
    family_id: int,
    source_file_id: int,
    asset_kind: str,
    current_path: str,
    content: bytes,
) -> int:
    digest = hashlib.sha256(content).hexdigest()
    return int(
        connection.execute(
            """INSERT INTO released_archive_assets(
                   job_id,family_id,source_file_id,asset_kind,current_relative_path,
                   size_bytes,sha256,origin_change_request_id,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,'cr-test',?,?)""",
            (
                job_id,
                family_id,
                source_file_id,
                asset_kind,
                current_path,
                len(content),
                digest,
                NOW,
                NOW,
            ),
        ).lastrowid
    )


def test_0286_deleting_planned_event_restores_archive_release_marker(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    initialize_database(db)
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)

    released_start = "2026-07-23T15:01:00"
    released_end = "2026-07-23T23:59:59"
    current = "Freigewordene Archivdateien/2026/2026-07-23 · 15-01–23-59/A.JPG"

    with database_connection(db) as connection:
        seed_job(connection, "j")
        family_id, _file_id = _seed_family_file(
            connection,
            job_id="j",
            stem="A",
            capture="2026-07-23T18:00:00",
            current_path=current,
            content=b"camera-a",
        )
        seed_event(
            connection,
            status="planned",
            event_id="planned",
            job_id="j",
            folder="07-23 - Planned",
        )
        connection.execute(
            """UPDATE events
               SET start_datetime=?,end_datetime=?
               WHERE id='planned'""",
            (released_start, released_end),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('planned',?,NULL,'date_time_range',?)""",
            (family_id, NOW),
        )
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES ('j',?,?,?,?,1)""",
            (family_id, released_start, released_end, NOW),
        )

    path = work / current
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"camera-a")

    deleted = delete_planned_event(db, "j", "planned")
    assert deleted["released_family_count"] == 1

    with database_connection(db) as connection:
        marker = connection.execute(
            """SELECT released_start_datetime,released_end_datetime,archive_origin
               FROM released_free_families
               WHERE job_id='j' AND family_id=?""",
            (family_id,),
        ).fetchone()
        assert marker is not None
        assert marker["archive_origin"] == 1
        assert marker["released_start_datetime"] == released_start
        assert marker["released_end_datetime"] == released_end

    groups = list_global_released_archive_groups(db)
    assert len(groups) == 1
    assert groups[0]["family_ids"] == [family_id]
    assert groups[0]["start_datetime"] == released_start
    assert groups[0]["end_datetime"] == released_end


def test_0286_released_archive_assets_follow_cross_job_family_and_layout_roles(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    initialize_database(db)
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)
    central = workspace / "SD-Kartensicherungen"

    release_dir = "Freigewordene Archivdateien/2026/2026-07-23"
    camera_rel = release_dir + "/A.JPG"
    xmp_rel = release_dir + "/A.xmp"
    export_rel = release_dir + "/A_Export.jpg"

    with database_connection(db) as connection:
        seed_job(connection, "anchor")
        seed_job(connection, "source")
        seed_event(
            connection,
            status="planned",
            event_id="e",
            job_id="anchor",
            folder="07-23 - Ziel",
        )
        family_id, file_id = _seed_family_file(
            connection,
            job_id="source",
            stem="A",
            capture="2026-07-23T12:00:00",
            current_path=camera_rel,
            content=b"camera",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )
        connection.execute(
            """INSERT INTO released_free_families(
                   job_id,family_id,released_start_datetime,released_end_datetime,
                   created_at,archive_origin
               ) VALUES ('source',?,'2026-07-23T00:00:00',
                         '2026-07-23T23:59:59',?,1)""",
            (family_id, NOW),
        )
        _insert_released_asset(
            connection,
            job_id="source",
            family_id=family_id,
            source_file_id=file_id,
            asset_kind="xmp",
            current_path=xmp_rel,
            content=b"xmp",
        )
        _insert_released_asset(
            connection,
            job_id="source",
            family_id=family_id,
            source_file_id=file_id,
            asset_kind="export",
            current_path=export_rel,
            content=b"export",
        )
        ensure_event_layout_snapshot(connection, "e", now=NOW)
        update_event_layout(
            connection,
            "e",
            structure_enabled=True,
            input_path="Alle",
            layout={
                "version": 2,
                "nodes": [
                    {"id": "input", "name": "Alle", "children": []},
                    {"id": "master", "name": "Master", "role": "export", "children": []},
                ],
            },
            updated_at=NOW,
        )

    for rel, payload in (
        (camera_rel, b"camera"),
        (xmp_rel, b"xmp"),
        (export_rel, b"export"),
    ):
        path = central / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    plan = build_event_sort_plan(db, "anchor", "e", workspace, verify_sha256=True)
    assert plan["summary"]["ready"] is True
    assets = {row["asset_kind"]: row for row in plan["assets"]}
    assert set(assets) == {"xmp", "export"}
    assert assets["xmp"]["destination_relative_path"] == "2026/07-23 - Ziel/Alle/A.xmp"
    assert assets["export"]["destination_relative_path"] == "2026/07-23 - Ziel/Master/A_Export.jpg"


def test_0286_new_xmp_and_lightroom_export_in_free_day_are_picked_up(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    initialize_database(db)
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)

    source_dir = Path("2026") / "07-24"
    stem = "20260724_120000_Fuji-X-E5"
    camera_rel = (source_dir / (stem + ".JPG")).as_posix()

    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(
            connection,
            status="planned",
            event_id="e",
            job_id="j",
            folder="07-24 - Freier Bestand",
        )
        connection.execute(
            """UPDATE events
               SET start_datetime='2026-07-24T00:00:00',
                   end_datetime='2026-07-24T23:59:59'
               WHERE id='e'"""
        )
        family_id, _file_id = _seed_family_file(
            connection,
            job_id="j",
            stem=stem,
            capture="2026-07-24T12:00:00",
            current_path=camera_rel,
            content=b"camera",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )

    physical = work / source_dir
    physical.mkdir(parents=True, exist_ok=True)
    (physical / (stem + ".JPG")).write_bytes(b"camera")
    (physical / (stem + ".xmp")).write_bytes(b"xmp-new")
    (physical / (stem + "_Export_2.jpg")).write_bytes(b"export-new")

    plan = build_event_sort_plan(db, "j", "e", workspace, verify_sha256=True)
    assert plan["summary"]["ready"] is True
    assets = {(row["asset_kind"], Path(row["source_relative_path"]).name): row for row in plan["assets"]}
    assert ("xmp", stem + ".xmp") in assets
    assert ("export", stem + "_Export_2.jpg") in assets
    assert assets[("xmp", stem + ".xmp")]["destination_relative_path"] == (
        "2026/07-24 - Freier Bestand/Alle/" + stem + ".xmp"
    )
    assert assets[("export", stem + "_Export_2.jpg")]["destination_relative_path"] == (
        "2026/07-24 - Freier Bestand/Export/" + stem + "_Export_2.jpg"
    )


def test_0286_planning_and_inspector_show_loose_assets_before_apply(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    initialize_database(db)
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)

    source_dir = Path("2026") / "07-21"
    stem = "20260721_152629_Fuji-X-E5"
    camera_rel = (source_dir / (stem + ".JPG")).as_posix()

    with database_connection(db) as connection:
        seed_job(connection, "j")
        family_id, _file_id = _seed_family_file(
            connection,
            job_id="j",
            stem=stem,
            capture="2026-07-21T15:26:29",
            current_path=camera_rel,
            content=b"camera",
        )

    physical = work / source_dir
    physical.mkdir(parents=True, exist_ok=True)
    (physical / (stem + ".JPG")).write_bytes(b"camera")
    (physical / (stem + ".xmp")).write_bytes(b"xmp")
    (physical / (stem + "_Export.jpg")).write_bytes(b"export")

    # Noch vor jeder Ereignisplanung muss die freie Tageskarte den realen
    # physischen Bestand zeigen: 1 Kamera + XMP + Export.
    overview = list_job_planning_overview(db, "j", workspace_path=workspace)
    day = next(group for group in overview["available_day_groups"] if group["day_key"] == "2026-07-21")
    assert day["family_count"] == 1
    assert day["file_count"] == 3

    with database_connection(db) as connection:
        seed_event(
            connection,
            status="planned",
            event_id="e",
            job_id="j",
            folder="07-21 - Test",
        )
        connection.execute(
            """UPDATE events
               SET start_datetime='2026-07-21T00:00:00',
                   end_datetime='2026-07-21T23:59:59'
               WHERE id='e'"""
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )

    overview = list_job_planning_overview(db, "j", workspace_path=workspace)
    planned = next(group for group in overview["event_groups"] if group["event_id"] == "e")
    assert planned["file_count"] == 3

    context = get_event_edit_context(db, "j", "e", workspace_path=workspace)
    family = next(item for item in context["families"] if item["assigned_here"])
    assert family["file_count"] == 3
    assert family["workspace_asset_count"] == 2
    assert family["live_asset_kinds"] == ["export", "xmp"]


def test_0286_released_archive_assets_are_visible_while_target_is_only_planned(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    initialize_database(db)
    workspace.mkdir()
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)

    stem = "20260723_180000_Fuji-X-E5"
    release_dir = "Freigewordene Archivdateien/2026/2026-07-23"
    camera_rel = release_dir + "/" + stem + ".JPG"
    xmp_rel = release_dir + "/" + stem + ".xmp"
    export_rel = release_dir + "/" + stem + "_Export.jpg"

    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(
            connection,
            status="planned",
            event_id="e",
            job_id="j",
            folder="07-23 - Wiederverwendet",
        )
        family_id, file_id = _seed_family_file(
            connection,
            job_id="j",
            stem=stem,
            capture="2026-07-23T18:00:00",
            current_path=camera_rel,
            content=b"camera",
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )
        _insert_released_asset(
            connection,
            job_id="j",
            family_id=family_id,
            source_file_id=file_id,
            asset_kind="xmp",
            current_path=xmp_rel,
            content=b"xmp",
        )
        _insert_released_asset(
            connection,
            job_id="j",
            family_id=family_id,
            source_file_id=file_id,
            asset_kind="export",
            current_path=export_rel,
            content=b"export",
        )

    for rel, payload in ((camera_rel,b"camera"),(xmp_rel,b"xmp"),(export_rel,b"export")):
        path = work / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    context = get_event_edit_context(db, "j", "e", workspace_path=workspace)
    family = next(item for item in context["families"] if item["assigned_here"])
    assert family["file_count"] == 3
    assert family["live_asset_kinds"] == ["export", "xmp"]

    overview = list_job_planning_overview(db, "j", workspace_path=workspace)
    planned = next(group for group in overview["event_groups"] if group["event_id"] == "e")
    assert planned["file_count"] == 3


def test_0286_subevent_day_controls_keep_calendar_but_enforce_valid_range():
    assert "function nextSubeventDefaults()" in WORKSPACE_HTML
    assert 'subeventDayControl("data-create-child-start-date"' in WORKSPACE_HTML
    assert 'subeventDayControl("data-create-child-end-date"' in WORKSPACE_HTML
    assert "data-create-child-start-month-year" in WORKSPACE_HTML
    assert "data-create-child-end-month-year" in WORKSPACE_HTML
    assert '<input data-create-child-start-date type="date"' not in WORKSPACE_HTML
    assert "data-locked-month=" in WORKSPACE_HTML
    assert "<select data-segment-day" in WORKSPACE_HTML

    assert "function nextEditSubeventDefaults(container)" in EVENTS_HTML
    assert 'editSubeventDayControl("data-child-start-date"' in EVENTS_HTML
    assert 'editSubeventDayControl("data-child-end-date"' in EVENTS_HTML
    assert "data-child-start-month-year" in EVENTS_HTML
    assert "data-child-end-month-year" in EVENTS_HTML
    assert '<input data-child-start-date type="date"' not in EVENTS_HTML
    assert "data-locked-month=" in EVENTS_HTML
    assert "<select data-segment-day" in EVENTS_HTML
