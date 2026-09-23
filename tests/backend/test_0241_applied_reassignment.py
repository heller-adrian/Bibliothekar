import inspect
from pathlib import Path

import pytest

from app.database import (
    database_connection,
    delete_planned_event,
    initialize_database,
    list_global_tasks,
)
from app.event_mutation import (
    begin_mutation,
    cancel_mutation,
    capture_job_event_state,
    set_mutation_target,
)
from app.event_reassignment import (
    EventReassignmentError,
    assign_event_reassignments,
    list_event_reassignments,
)
from app.events_ui import EVENTS_HTML
from app.main import (
    _applied_edit_is_metadata_only,
    _no_event_normal_conflicts,
    api_update_event,
)
from app.workspace_ui import WORKSPACE_HTML
from tests.backend.test_0170_transactions import _simple_applied
from tests.backend.test_0172_reassignment_target_state import _make_applied

NOW = "2026-09-21T01:00:00+00:00"


def test_0241_cancel_mutation_preserves_durable_fk_evidence(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    family_id = _simple_applied(db)

    with database_connection(db) as c:
        file_id = int(c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (
                   'j',?,'orig/F1.JPG','2026/07-19 - Original/Alle/F1.JPG',
                   'F1.JPG','.JPG','jpeg',3,?,?,'2026-07-19T10:00:00',
                   'DateTimeOriginal','high','not_required','not_requested',
                   ?,?,'shared_workspace'
               )""",
            (family_id, "0" * 64, "0" * 64, NOW, NOW),
        ).lastrowid)
        c.execute(
            """INSERT INTO sort_runs(
                   id,job_id,event_id,plan_token,status,phase,source_root,target_root,
                   file_count,verified_file_count,move_count,moved_file_count,
                   directory_count,created_directory_count,total_size_bytes,
                   verified_bytes,moved_bytes,error_message,details_json,
                   created_at,started_at,updated_at,completed_at,run_kind
               ) VALUES (
                   'historic-run','j','e','historic-token','applied','historisch',
                   '/source','/target',1,1,1,1,1,1,3,3,3,NULL,'{}',
                   ?,?,?,?,'initial'
               )""",
            (NOW, NOW, NOW, NOW),
        )
        c.execute(
            """INSERT INTO event_archive_verified_file_locations(
                   event_id,family_id,file_id,relative_path,verified_at,updated_at
               ) VALUES ('e',?,?, '2026/07-19 - Original/Alle/F1.JPG',?,?)""",
            (family_id, file_id, NOW, NOW),
        )

        original = capture_job_event_state(c, "j")
        mutation_id = begin_mutation(
            c,
            job_id="j",
            anchor_event_id="e",
            mutation_kind="edit",
            affected_event_ids=["e"],
            original_state=original,
            status="pending_apply",
        )
        c.execute(
            "UPDATE events SET name='Geändert',folder_name='07-19 - Geändert',resort_required=1 WHERE id='e'"
        )
        set_mutation_target(
            c,
            mutation_id,
            capture_job_event_state(c, "j"),
            status="pending_apply",
        )
        c.commit()

    with database_connection(db) as c:
        c.execute("BEGIN IMMEDIATE")
        result = cancel_mutation(c, mutation_id, "j")
        c.commit()

    assert result["status"] == "cancelled"
    assert result["restored_root_event_ids"] == ["e"]
    with database_connection(db) as c:
        event = c.execute(
            "SELECT name,folder_name,resort_required FROM events WHERE id='e'"
        ).fetchone()
        assert tuple(event) == ("Original", "07-19 - Original", 0)
        assert c.execute(
            "SELECT COUNT(*) FROM sort_runs WHERE id='historic-run'"
        ).fetchone()[0] == 1
        location = c.execute(
            """SELECT relative_path FROM event_archive_verified_file_locations
               WHERE event_id='e' AND file_id=?""",
            (file_id,),
        ).fetchone()
        assert location is not None
        assert location["relative_path"] == "2026/07-19 - Original/Alle/F1.JPG"


def test_0241_single_child_to_whole_period_is_structural():
    context = {
        "event": {
            "status": "applied",
            "applied_at": NOW,
            "event_kind": "event",
            "start_datetime": "2026-07-19T00:00:00",
            "end_datetime": "2026-07-19T23:59:59",
            "uses_time_range": 0,
            "preserve_day_folders": 0,
        },
        "child_event": {
            "id": "child",
            "name": "Abend",
            "start_datetime": "2026-07-19T18:00:00",
            "end_datetime": "2026-07-19T20:00:59",
        },
        "child_events": [{
            "id": "child",
            "name": "Abend",
            "start_datetime": "2026-07-19T18:00:00",
            "end_datetime": "2026-07-19T20:00:59",
        }],
    }
    payload = {
        "event_kind": "event",
        "start_date": "2026-07-19",
        "end_date": "2026-07-19",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "child_segments": [],
    }
    assert _applied_edit_is_metadata_only(context, payload) is False


def test_0241_no_event_day_folder_toggle_is_structural():
    context = {
        "event": {
            "status": "applied",
            "applied_at": NOW,
            "event_kind": "no_event",
            "preserve_day_folders": 0,
        },
        "time_segments": [{
            "day_key": "2026-07-19",
            "start_time": "10:00",
            "end_time": "11:00",
        }],
    }
    payload = {
        "event_kind": "no_event",
        "preserve_day_folders": True,
        "no_event_segments": [{
            "day_key": "2026-07-19",
            "start_time": "10:00",
            "end_time": "11:00",
        }],
    }
    assert _applied_edit_is_metadata_only(context, payload) is False


def test_0241_no_event_edit_detects_named_event_occupancy(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        c.execute(
            """INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at)
               VALUES ('j','sd_import','manual','completed','done',?,?)""",
            (NOW, NOW),
        )
        c.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,timeline_model
               ) VALUES (
                   'no','j','parent','Ohne Ereignis','2026-07-19T10:00:00',
                   '2026-07-19T11:00:59',0,'07 - Ohne Ereignis','applied',
                   ?,?,'no_event',0,1,?,'segments'
               )""",
            (NOW, NOW, NOW),
        )
        c.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,timeline_model
               ) VALUES (
                   'named','j','parent','Mittag','2026-07-19T12:00:00',
                   '2026-07-19T13:00:59',0,'07-19 - Mittag','applied',
                   ?,?,'event',0,1,?,'continuous'
               )""",
            (NOW, NOW, NOW),
        )
        conflicts = _no_event_normal_conflicts(
            c,
            "j",
            "no",
            [{
                "day_key": "2026-07-19",
                "start_time": "10:00",
                "end_time": "14:00",
                "start_datetime": "2026-07-19T10:00:00",
                "end_datetime": "2026-07-19T14:00:59",
            }],
        )
    assert len(conflicts) == 1
    assert conflicts[0]["event_id"] == "named"
    assert "_no_event_normal_conflicts" in inspect.getsource(api_update_event)


def _delete_applied_evening_with_wrong_target(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    family_ids = _make_applied(db)
    with database_connection(db) as c:
        c.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,timeline_model
               ) VALUES (
                   'wrong','j','parent','Falscher Tag','2026-07-20T00:00:00',
                   '2026-07-20T23:59:59',0,'07-20 - Falscher Tag','applied',
                   ?,?,'event',0,1,?,'continuous'
               )""",
            (NOW, NOW, NOW),
        )
        c.commit()
    delete_planned_event(db, "j", "b")
    # This isolated reassignment fixture has no source file operation.
    with database_connection(db) as c:
        c.execute("UPDATE events SET resort_required=0 WHERE id='b'")
    state = list_event_reassignments(db, "j", "b")
    return db, family_ids, state


def test_0241_reassignment_rejects_partial_atomic_segment(tmp_path: Path):
    db, family_ids, state = _delete_applied_evening_with_wrong_target(tmp_path)
    assert len(state["reassignment_segments"]) == 1
    with pytest.raises(EventReassignmentError, match="vollständig"):
        assign_event_reassignments(
            db,
            "j",
            "b",
            [family_ids[4]],
            target_mode="new_event",
            new_event_name="Teilsegment darf nicht entstehen",
            segments=state["reassignment_segments"],
        )


def test_0241_reassignment_rejects_simple_target_outside_segment(tmp_path: Path):
    db, family_ids, state = _delete_applied_evening_with_wrong_target(tmp_path)
    with pytest.raises(EventReassignmentError, match="Zielereignisses"):
        assign_event_reassignments(
            db,
            "j",
            "b",
            family_ids[4:],
            target_mode="existing_event",
            target_event_id="wrong",
            segments=state["reassignment_segments"],
        )


def test_0241_reassignment_tasks_use_canonical_exact_segment_ui(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    _make_applied(db)
    delete_planned_event(db, "j", "b")
    task = next(item for item in list_global_tasks(db) if item["kind"] == "reassignment")
    assert task["href"].startswith("/events?job=")
    assert "&task=reassign:" in task["href"]

    assert 'task.startsWith("reassign:")' in EVENTS_HTML
    assert "In Aufnahmen öffnen" in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert "runAutomaticReapply" not in EVENTS_HTML

    assert 'task.startsWith("reassign:")' in WORKSPACE_HTML
    assert "/events?job=" in WORKSPACE_HTML
    assert "runAutomaticTaskReapply" not in WORKSPACE_HTML


def test_0241_applied_reconcile_requires_visible_confirmation():
    assert "Bitte den angezeigten Nachsortierplan prüfen und ausdrücklich bestätigen." in EVENTS_HTML
    assert "Bitte den Nachsortierplan prüfen und ausdrücklich bestätigen." in EVENTS_HTML
    assert 'id="sort-apply-confirmation"' in EVENTS_HTML
    assert 'id="sort-apply-button"' in EVENTS_HTML
    assert "Die ausdrückliche Bestätigung fehlt." in EVENTS_HTML
