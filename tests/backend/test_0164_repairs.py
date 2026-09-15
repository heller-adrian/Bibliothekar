from pathlib import Path

from app.database import (
    database_connection,
    initialize_database,
    list_job_events,
    update_event_definition,
)
from app.events_ui import EVENTS_HTML
from app.main import _event_edit_payload_within_new_range

NOW = "2026-09-07T20:20:00"


def _seed_applied(db: Path):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done',?,?)",
            (NOW, NOW),
        )
        c.execute(
            """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,
               revision,applied_at,archived_at,notes,resort_required)
               VALUES ('src','j',NULL,'parent','Alter Name','2026-07-25T00:00:00','2026-07-26T23:59:59',
               0,'07-25 - Alter Name','applied',?,?,'event',0,1,?,NULL,'',0)""",
            (NOW, NOW, NOW),
        )
        ids = []
        for n, capture in [(1, "2026-07-25T11:00:00"), (2, "2026-07-26T11:00:00")]:
            fid = c.execute(
                """INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence)
                   VALUES ('j',?,?, 'complete',?,'high')""",
                (f"fam{n}", f"DSCF{n}", capture),
            ).lastrowid
            c.execute(
                "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('src',?,NULL,'manual',?)",
                (fid, NOW),
            )
            ids.append(fid)
        c.commit()
    return ids


def test_applied_metadata_only_does_not_require_resort(tmp_path):
    db = tmp_path / "db.sqlite3"
    _seed_applied(db)
    result = update_event_definition(
        db, "j", "src", None,
        event_name="Neuer Name", notes="nur Text", expected_revision=1,
    )
    assert result["structural_changed"] is False
    assert result["resort_required"] is False
    assert result["reassignment_required"] is False
    with database_connection(db) as c:
        row = c.execute("SELECT name,folder_name,resort_required,revision FROM events WHERE id='src'").fetchone()
        assert row["name"] == "Neuer Name"
        # Metadatenkorrektur darf den bereits vorhandenen SSD-Ordner nicht umbenennen.
        assert row["folder_name"] == "07-25 - Alter Name"
        assert row["resort_required"] == 0
        assert row["revision"] == 2


def test_shortened_edit_range_drops_old_checked_family_before_preview():
    families = [
        {"family_id": 1, "selected_capture_time": "2026-07-25T11:00:00"},
        {"family_id": 2, "selected_capture_time": "2026-07-26T11:00:00"},
    ]
    payload = {
        "start_date": "2026-07-25", "end_date": "2026-07-25",
        "uses_time_range": False, "selected_family_ids": [1, 2],
        "selected_day_keys": ["2026-07-25", "2026-07-26"],
    }
    normalized = _event_edit_payload_within_new_range(payload, families)
    assert normalized["selected_family_ids"] == [1]
    assert normalized["selected_day_keys"] == []


def test_pending_reassignment_is_visible_after_reload(tmp_path):
    db = tmp_path / "db.sqlite3"
    ids = _seed_applied(db)
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('src','j',?,?)",
            (ids[1], NOW),
        )
        c.commit()
    events = list_job_events(db, "j")
    src = next(e for e in events if e["id"] == "src")
    assert src["pending_reassignment_count"] == 1


def test_reassignment_ui_hides_new_name_for_existing_target_and_has_resume_action():
    assert '.reassignment-new-name[hidden] { display:none !important; }' in EVENTS_HTML
    assert 'data-reassign-workspace=' in EVENTS_HTML
    assert 'In Sortieren öffnen' in EVENTS_HTML
    assert 'const raw = await response.text();' in EVENTS_HTML
