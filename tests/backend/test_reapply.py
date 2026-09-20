import hashlib
from pathlib import Path

import pytest

from app.database import database_connection, initialize_database
from app.event_reapply import prepare_reapply_sort_run
from app.sort_apply import CONFIRMATION_PHRASE, SortApplyError
from app.sort_plan import build_event_sort_plan


NOW = "2026-09-21T00:00:00+00:00"


@pytest.fixture
def test_reapply_env(tmp_path: Path):
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereich"
    work.mkdir(parents=True)

    db_path = tmp_path / "reapply.db"
    initialize_database(db_path)

    rel = "2023/01-01 - Reapply Event/Alle/IMG.JPG"
    payload = b"reapply-success"
    source = work / rel
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    with database_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   created_at,updated_at
               ) VALUES (
                   'REAPPLY_JOB','sd_import','manual','completed','event_sort_applied',
                   'folder_import','TEST',?,?
               )""",
            (NOW, NOW),
        )
        family_id = int(conn.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (
                   'REAPPLY_JOB','fam_reapply','IMG','complete',
                   '2023-01-01T10:00:00','high'
               )"""
        ).lastrowid)
        conn.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,resort_required
               ) VALUES (
                   'evt_reapply','REAPPLY_JOB','parent','Reapply Event',
                   '2023-01-01T00:00:00','2023-01-01T23:59:59',0,
                   '01-01 - Reapply Event','applied',?,?,'event',0,1,?,1
               )""",
            (NOW, NOW, NOW),
        )
        conn.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('evt_reapply',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )
        conn.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (
                   'REAPPLY_JOB',?,'orig/IMG.JPG',?,'IMG.JPG','.JPG','jpeg',?,
                   ?,?,'2023-01-01T10:00:00','DateTimeOriginal','high',
                   'not_required','not_requested',?,?,'shared_workspace'
               )""",
            (family_id, rel, len(payload), digest, digest, NOW, NOW),
        )
        conn.commit()

    return {
        "workspace": workspace,
        "db_path": db_path,
        "job_id": "REAPPLY_JOB",
        "event_id": "evt_reapply",
    }


def test_prepare_reapply_success(test_reapply_env):
    ws = test_reapply_env["workspace"]
    db = test_reapply_env["db_path"]
    job_id = test_reapply_env["job_id"]
    event_id = test_reapply_env["event_id"]

    plan = build_event_sort_plan(
        db,
        job_id,
        event_id,
        ws,
        allow_reapply=True,
    )
    assert plan["summary"]["ready"] is True
    assert plan["summary"]["file_count"] == 1

    run = prepare_reapply_sort_run(
        db,
        job_id,
        event_id,
        ws,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )

    assert run["run_kind"] == "reapply"
    assert run["id"].startswith("RSORT_")
    assert run["status"] == "queued"

    with database_connection(db) as conn:
        operation = conn.execute(
            "SELECT status FROM sort_operations WHERE sort_run_id=?",
            (run["id"],),
        ).fetchone()
    assert operation is not None
    assert operation["status"] == "already_at_target"


def test_prepare_reapply_rejects_wrong_confirmation(test_reapply_env):
    with pytest.raises(SortApplyError, match="Bestätigung"):
        prepare_reapply_sort_run(
            test_reapply_env["db_path"],
            test_reapply_env["job_id"],
            test_reapply_env["event_id"],
            test_reapply_env["workspace"],
            expected_plan_token="irrelevant",
            confirmation_phrase="NEIN",
        )
