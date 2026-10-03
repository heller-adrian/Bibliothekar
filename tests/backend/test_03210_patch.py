from __future__ import annotations

import hashlib
from pathlib import Path

from app.database import (
    create_planned_event,
    database_connection,
    delete_planned_event,
    initialize_database,
)
from app.event_suggestions import list_event_suggestions
from app.folder_import import build_folder_import_plan
from app.free_stock_layout import FreeStockLayoutError, canonical_free_directory
from app.sort_plan import build_event_sort_plan
from app.sort_apply import (
    CONFIRMATION_PHRASE,
    execute_sort_run,
    prepare_sort_run,
)
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)


NOW_OLD = "2026-10-03T08:00:00+00:00"
NOW_NEW = "2026-10-03T09:00:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _insert_job(connection, job_id: str, created_at: str) -> None:
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,working_path,
               created_at,updated_at
           )
           VALUES (?,'sd_import','approved_sd','completed','organized_verified',
                   'folder_import','/workspace/SD-Kartensicherungen',?,?)""",
        (job_id, created_at, created_at),
    )


def _insert_family_file(
    database: Path,
    central: Path,
    *,
    job_id: str,
    key: str,
    capture: str,
    filename: str,
    data: bytes,
) -> int:
    relative = f"2026/2026-07-20/{filename}"
    digest = _sha(data)
    with database_connection(database) as connection:
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               )
               VALUES (?,?,?,'complete',?,'high')""",
            (job_id, key, key, capture),
        ).lastrowid)
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at
               )
               VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,
                       'DateTimeOriginal','high','not_required','not_requested',
                       'shared_workspace',?,?)""",
            (
                job_id,
                family_id,
                relative,
                relative,
                filename,
                len(data),
                digest,
                digest,
                capture,
                NOW_OLD,
                NOW_OLD,
            ),
        )
    target = central / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return family_id


def _event_preview(family_ids: list[int]) -> dict:
    return {
        "event_kind": "event",
        "event_name": "Test 1",
        "start_date": "2026-07-20",
        "end_date": "2026-07-20",
        "start_time": "14:00",
        "end_time": "15:00",
        "uses_time_range": True,
        "preserve_day_folders": False,
        "parent_folder": "07-20 - Test 1",
        "child_folder": None,
        "child_event_name": None,
        "selected_family_ids": family_ids,
        "structure_lines": [],
    }


def test_03210_initial_apply_renormalizes_free_stock_from_all_backups(
    tmp_path: Path,
    monkeypatch,
):
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    central = workspace / "SD-Kartensicherungen"
    work = tmp_path / "library-work"
    compatibility = tmp_path / "compatibility"
    central.mkdir(parents=True)
    work.mkdir()
    compatibility.mkdir()
    (compatibility / "SD-Kartensicherungen").symlink_to(
        central,
        target_is_directory=True,
    )
    (compatibility / "Arbeitsbereich").symlink_to(
        work,
        target_is_directory=True,
    )
    initialize_database(database)

    with database_connection(database) as connection:
        _insert_job(connection, "FIRST", NOW_OLD)
        _insert_job(connection, "SECOND", NOW_OLD)

    first_before = _insert_family_file(
        database, central, job_id="FIRST", key="first-before",
        capture="2026-07-20T10:00:00", filename="FIRST_BEFORE.JPG", data=b"1-before",
    )
    first_event = _insert_family_file(
        database, central, job_id="FIRST", key="first-event",
        capture="2026-07-20T14:30:00", filename="FIRST_EVENT.JPG", data=b"1-event",
    )
    first_after = _insert_family_file(
        database, central, job_id="FIRST", key="first-after",
        capture="2026-07-20T16:00:00", filename="FIRST_AFTER.JPG", data=b"1-after",
    )
    second_before = _insert_family_file(
        database, central, job_id="SECOND", key="second-before",
        capture="2026-07-20T11:00:00", filename="SECOND_BEFORE.JPG", data=b"2-before",
    )
    second_event = _insert_family_file(
        database, central, job_id="SECOND", key="second-event",
        capture="2026-07-20T14:45:00", filename="SECOND_EVENT.JPG", data=b"2-event",
    )
    second_after = _insert_family_file(
        database, central, job_id="SECOND", key="second-after",
        capture="2026-07-20T17:00:00", filename="SECOND_AFTER.JPG", data=b"2-after",
    )

    created = create_planned_event(
        database,
        "FIRST",
        _event_preview([first_event, second_event]),
    )
    event_id = str(created["parent_event"]["id"])

    plan = build_event_sort_plan(
        database,
        "FIRST",
        event_id,
        compatibility,
    )
    assert plan["summary"]["ready"] is True, plan["blockers"]

    by_family = {
        int(row["family_id"]): row
        for row in plan["files"]
        if row.get("family_id") is not None
    }
    assert {
        first_before,
        first_event,
        first_after,
        second_before,
        second_event,
        second_after,
    } <= set(by_family)

    assert by_family[second_before]["destination_relative_path"].startswith(
        "2026/2026-07-20 · 00-00–13-59/"
    )
    assert by_family[second_after]["destination_relative_path"].startswith(
        "2026/2026-07-20 · 15-01–23-59/"
    )
    assert not any(
        str(by_family[family_id]["destination_relative_path"]).startswith(
            "2026/2026-07-20/"
        )
        for family_id in (
            first_before,
            first_after,
            second_before,
            second_after,
        )
    )


def test_03210_later_import_uses_existing_free_interval_folder(tmp_path: Path):
    database = tmp_path / "kamera.sqlite3"
    central = tmp_path / "central"
    central.mkdir()
    initialize_database(database)
    with database_connection(database) as connection:
        _insert_job(connection, "FIRST", NOW_OLD)
        connection.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,time_model_version,applied_at
               )
               VALUES ('EVENT','FIRST','parent','Test 1',
                       '2026-07-20T14:00:00','2026-07-20T15:00:59',
                       0,'07-20 - Test 1','applied',?,?,'event',2,?)""",
            (NOW_OLD, NOW_OLD, NOW_OLD),
        )

    capture = "2026-07-20T16:00:00"
    data = b"later-free"
    entries = [{
        "relative_path": "DCIM/IMG_0001.JPG",
        "size_bytes": len(data),
        "sha256": _sha(data),
    }]
    analysis = {
        "files": [{
            "relative_path": "DCIM/IMG_0001.JPG",
            "filename": "IMG_0001.JPG",
            "family_key": "later-free",
            "media_type": "jpeg",
            "selected_capture_time": capture,
            "capture_time_confidence": "high",
            "camera_make": "FUJIFILM",
            "camera_model": "X-E5",
        }],
        "families": [{
            "family_key": "later-free",
            "selected_capture_time": capture,
            "capture_time_confidence": "high",
        }],
    }

    def resolve_directory(value: str) -> Path | None:
        try:
            with database_connection(database) as connection:
                return Path(str(canonical_free_directory(
                    connection,
                    value,
                    physical=True,
                )))
        except FreeStockLayoutError:
            return None

    plan, excluded, _ = build_folder_import_plan(
        entries,
        analysis,
        central,
        destination_directory_callback=resolve_directory,
    )
    assert excluded == []
    assert len(plan) == 1
    assert Path(plan[0]["destination_relative_path"]).parent.as_posix() == (
        "2026/2026-07-20 · 15-01–23-59"
    )


def test_03210_later_in_range_family_still_creates_event_suggestion(
    tmp_path: Path,
):
    database = tmp_path / "kamera.sqlite3"
    central = tmp_path / "central"
    central.mkdir()
    initialize_database(database)
    with database_connection(database) as connection:
        _insert_job(connection, "FIRST", NOW_OLD)
        _insert_job(connection, "LATER", NOW_NEW)
        connection.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,time_model_version,applied_at
               )
               VALUES ('EVENT','FIRST','parent','Test 1',
                       '2026-07-20T14:00:00','2026-07-20T15:00:59',
                       0,'07-20 - Test 1','applied',?,?,'event',2,?)""",
            (NOW_OLD, NOW_OLD, NOW_OLD),
        )

    in_range = _insert_family_file(
        database, central, job_id="LATER", key="later-in",
        capture="2026-07-20T14:30:00", filename="LATER_IN.JPG", data=b"later-in",
    )
    _insert_family_file(
        database, central, job_id="LATER", key="later-out",
        capture="2026-07-20T16:00:00", filename="LATER_OUT.JPG", data=b"later-out",
    )

    suggestions = list_event_suggestions(database, "LATER")
    assert len(suggestions) == 1
    assert suggestions[0]["target_event_id"] == "EVENT"
    assert suggestions[0]["target_status"] == "applied"
    assert suggestions[0]["family_ids"] == [in_range]



def test_03210_delete_partial_day_merges_central_intervals_across_backups(
    tmp_path: Path,
    monkeypatch,
):
    """Deleting an applied slice must merge central-stock edge folders again."""
    monkeypatch.setenv(
        "KAMERA_CONFIG",
        str(tmp_path / "config" / "settings.json"),
    )
    database = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    central = workspace / "SD-Kartensicherungen"
    work = tmp_path / "library-work"
    compatibility = tmp_path / "compatibility"
    central.mkdir(parents=True)
    work.mkdir()
    compatibility.mkdir()
    (compatibility / "SD-Kartensicherungen").symlink_to(
        central,
        target_is_directory=True,
    )
    (compatibility / "Arbeitsbereich").symlink_to(
        work,
        target_is_directory=True,
    )
    initialize_database(database)

    with database_connection(database) as connection:
        _insert_job(connection, "FIRST", NOW_OLD)
        _insert_job(connection, "SECOND", NOW_OLD)

    family_ids = {
        "first_before": _insert_family_file(
            database, central, job_id="FIRST", key="first-before",
            capture="2026-07-20T11:00:57",
            filename="FIRST_BEFORE.JPG", data=b"1-before",
        ),
        "first_event": _insert_family_file(
            database, central, job_id="FIRST", key="first-event",
            capture="2026-07-20T14:30:00",
            filename="FIRST_EVENT.JPG", data=b"1-event",
        ),
        "first_after": _insert_family_file(
            database, central, job_id="FIRST", key="first-after",
            capture="2026-07-20T22:14:23",
            filename="FIRST_AFTER.JPG", data=b"1-after",
        ),
        "second_before": _insert_family_file(
            database, central, job_id="SECOND", key="second-before",
            capture="2026-07-20T11:01:04",
            filename="SECOND_BEFORE.JPG", data=b"2-before",
        ),
        "second_event": _insert_family_file(
            database, central, job_id="SECOND", key="second-event",
            capture="2026-07-20T14:45:00",
            filename="SECOND_EVENT.JPG", data=b"2-event",
        ),
        "second_after": _insert_family_file(
            database, central, job_id="SECOND", key="second-after",
            capture="2026-07-20T22:14:25",
            filename="SECOND_AFTER.JPG", data=b"2-after",
        ),
    }

    created = create_planned_event(
        database,
        "FIRST",
        _event_preview([
            family_ids["first_event"],
            family_ids["second_event"],
        ]),
    )
    event_id = str(created["parent_event"]["id"])

    initial_plan = build_event_sort_plan(
        database,
        "FIRST",
        event_id,
        compatibility,
    )
    assert initial_plan["summary"]["ready"] is True, initial_plan["blockers"]
    initial_run = prepare_sort_run(
        database,
        "FIRST",
        event_id,
        compatibility,
        expected_plan_token=initial_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(database, initial_run["id"], compatibility)

    before_split = central / "2026" / "2026-07-20 · 00-00–13-59"
    after_split = central / "2026" / "2026-07-20 · 15-01–23-59"
    assert before_split.is_dir()
    assert after_split.is_dir()
    assert not (central / "2026" / "2026-07-20").exists()

    prepared = delete_planned_event(database, "FIRST", event_id)
    assert prepared["pending_delete"] is True

    delete_plan = build_workspace_reconcile_plan(
        database,
        "FIRST",
        event_id,
        compatibility,
    )
    assert delete_plan["summary"]["ready"] is True, delete_plan["blockers"]
    by_family = {
        int(row["family_id"]): row
        for row in delete_plan["files"]
        if row.get("family_id") is not None
    }
    assert set(family_ids.values()) <= set(by_family)
    assert {
        str(by_family[fid]["physical_source_kind"])
        for fid in (
            family_ids["first_before"],
            family_ids["first_after"],
            family_ids["second_before"],
            family_ids["second_after"],
        )
    } == {"central_stock"}
    for fid in family_ids.values():
        assert Path(
            str(by_family[fid]["destination_relative_path"])
        ).parent.as_posix() == "2026/2026-07-20"

    delete_run = prepare_workspace_reconcile_run(
        database,
        "FIRST",
        event_id,
        compatibility,
        expected_plan_token=delete_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(
        database,
        delete_run["id"],
        compatibility,
    )

    merged = central / "2026" / "2026-07-20"
    assert merged.is_dir()
    assert len(list(merged.glob("*.JPG"))) == 6
    assert not before_split.exists()
    assert not after_split.exists()
    with database_connection(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id=?",
            (event_id,),
        ).fetchone()[0] == 0
