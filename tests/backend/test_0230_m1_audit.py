from pathlib import Path

import pytest

from app.archive_reassignment import ArchiveReassignmentError, _target_for_new_no_event
from app.database import database_connection, initialize_database
from app.event_change_request import EventChangeRequestError, propose_event_change
from app.event_structure import EventPreviewError, build_event_preview
from app.event_timeline import (
    apply_cascade_for_interval,
    continuous_event_overlaps,
    normalize_no_event_segments,
)


NOW = "2026-09-20T12:00:00+00:00"


def _seed_job(connection):
    connection.execute(
        """INSERT INTO jobs(
               id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at
           ) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)""",
        (NOW, NOW),
    )


def _insert_event(
    connection,
    event_id,
    *,
    parent_event_id=None,
    level="parent",
    name="Ereignis",
    start="2026-07-15T00:00:00",
    end="2026-07-15T23:59:59",
    status="planned",
    event_kind="event",
    folder="07-15 - Ereignis",
):
    connection.execute(
        """INSERT INTO events(
               id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,
               preserve_day_folders,revision,applied_at,archived_at,timeline_model
           ) VALUES (?,?,?,?,?,?,?, ?,?,?,?,?, ?,0,1,?,?,?)""",
        (
            event_id,
            "j",
            parent_event_id,
            level,
            name,
            start,
            end,
            1 if level == "child" else 0,
            folder,
            status,
            NOW,
            NOW,
            event_kind,
            NOW if status in {"applied", "archived"} else None,
            NOW if status == "archived" else None,
            "segments" if event_kind == "no_event" else "continuous",
        ),
    )


def _insert_family(connection, key, capture):
    return int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence
               ) VALUES ('j',?,?, 'complete',?,'high')""",
            (key, key, capture),
        ).lastrowid
    )


def test_0230_multisegment_gap_stays_free(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        _seed_job(c)
        _insert_event(c, "root")
        _insert_event(
            c, "morning", parent_event_id="root", level="child",
            name="Morgen", start="2026-07-15T08:00:00", end="2026-07-15T10:00:59",
            folder="08-00 - 10-00 - Morgen",
        )
        _insert_event(
            c, "afternoon", parent_event_id="root", level="child",
            name="Nachmittag", start="2026-07-15T14:00:00", end="2026-07-15T16:00:59",
            folder="14-00 - 16-00 - Nachmittag",
        )

        assert continuous_event_overlaps(
            c, "j", "2026-07-15T11:00:00", "2026-07-15T13:00:59"
        ) == []

        overlaps = continuous_event_overlaps(
            c, "j", "2026-07-15T09:00:00", "2026-07-15T09:30:59"
        )
        assert len(overlaps) == 1
        assert overlaps[0]["id"] == "root"
        assert overlaps[0]["effective_child_id"] == "morning"


def test_0230_cascade_trims_only_overlapping_child_segment(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        _seed_job(c)
        _insert_event(c, "root")
        _insert_event(
            c, "morning", parent_event_id="root", level="child",
            name="Morgen", start="2026-07-15T08:00:00", end="2026-07-15T10:00:59",
            folder="08-00 - 10-00 - Morgen",
        )
        _insert_event(
            c, "afternoon", parent_event_id="root", level="child",
            name="Nachmittag", start="2026-07-15T14:00:00", end="2026-07-15T16:00:59",
            folder="14-00 - 16-00 - Nachmittag",
        )
        morning_family = _insert_family(c, "morning-family", "2026-07-15T09:15:00")
        afternoon_family = _insert_family(c, "afternoon-family", "2026-07-15T14:30:00")
        c.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) "
            "VALUES ('morning',?,NULL,'date_time_range',?)",
            (morning_family, NOW),
        )
        c.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) "
            "VALUES ('afternoon',?,NULL,'date_time_range',?)",
            (afternoon_family, NOW),
        )

        result = apply_cascade_for_interval(
            c,
            "j",
            "new-event",
            "2026-07-15T09:30:00",
            "2026-07-15T11:00:59",
            now=NOW,
        )
        assert result["affected_event_ids"] == ["root"]

        children = c.execute(
            "SELECT id,start_datetime,end_datetime FROM events "
            "WHERE parent_event_id='root' ORDER BY start_datetime"
        ).fetchall()
        assert [(r["id"], r["start_datetime"], r["end_datetime"]) for r in children] == [
            ("morning", "2026-07-15T08:00:00", "2026-07-15T09:29:59"),
            ("afternoon", "2026-07-15T14:00:00", "2026-07-15T16:00:59"),
        ]
        assert c.execute(
            "SELECT COUNT(*) FROM event_assignments WHERE event_id='afternoon' AND family_id=?",
            (afternoon_family,),
        ).fetchone()[0] == 1


def test_0230_archived_new_no_event_cannot_duplicate_month(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        _seed_job(c)
        _insert_event(
            c,
            "noevent",
            name="Ohne Ereignis",
            start="2026-07-01T08:00:00",
            end="2026-07-31T18:00:59",
            status="archived",
            event_kind="no_event",
            folder="07 - Ohne Ereignis",
        )
        fid = _insert_family(c, "free", "2026-07-15T12:30:00")

        with pytest.raises(ArchiveReassignmentError, match="existiert bereits"):
            _target_for_new_no_event(
                c,
                "j",
                [fid],
                "2026-07-15T12:00:00",
                "2026-07-15T13:00:59",
            )


def test_0230_only_one_open_archived_change_request(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        _seed_job(c)
        _insert_event(c, "archived", status="archived")

    import app.event_change_request as module

    monkeypatch.setattr(
        module,
        "_compute_event_plan",
        lambda *args, **kwargs: {
            "families_with_plans": [],
            "diff_summary": {},
        },
    )
    preview = {
        "event_kind": "event",
        "parent_folder": "07-15 - Ereignis",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "start_date": "2026-07-15",
        "end_date": "2026-07-15",
        "selected_day_keys": [],
        "selected_family_ids": [],
        "selected_file_count": 0,
        "selected_family_count": 0,
        "child_segments": [],
    }

    first = propose_event_change(
        db, "j", "archived", preview, event_name="Ereignis"
    )
    assert first["version"] == 1

    with pytest.raises(EventChangeRequestError, match="bereits ein offener Änderungsauftrag"):
        propose_event_change(
            db, "j", "archived", preview, event_name="Ereignis"
        )


def test_0230_zero_length_same_day_ranges_are_rejected():
    families = [{
        "family_id": 1,
        "family_key": "F",
        "selected_capture_time": "2026-07-15T12:00:30",
        "capture_time_confidence": "high",
        "day_key": "2026-07-15",
        "has_date": True,
        "file_count": 1,
        "total_size_bytes": 1,
        "review_required_count": 0,
    }]
    payload = {
        "event_kind": "event",
        "event_name": "Test",
        "start_date": "2026-07-15",
        "end_date": "2026-07-15",
        "uses_time_range": True,
        "child_event_name": "Mittag",
        "start_time": "12:00",
        "end_time": "12:00",
        "preserve_day_folders": False,
        "selected_family_ids": [1],
        "selected_day_keys": ["2026-07-15"],
    }
    with pytest.raises(EventPreviewError, match="muss nach dem Beginn"):
        build_event_preview(payload, families)

    with pytest.raises(Exception, match="muss das Ende nach dem Beginn"):
        normalize_no_event_segments([
            {"day_key": "2026-07-15", "start_time": "12:00", "end_time": "12:00"}
        ])


def test_0230_segmentwise_cascade_and_archived_child_cleanup_are_wired():
    database_source = Path("app/database.py").read_text()
    archive_apply_source = Path("app/event_change_apply.py").read_text()

    assert "cascade_ranges = (" in database_source
    assert "new_definition_ranges" in database_source
    assert "for cascade_start, cascade_end in cascade_ranges:" in database_source

    assert "children = connection.execute(" in archive_apply_source
    assert "for extra in children[1:]:" in archive_apply_source
    assert 'DELETE FROM events WHERE parent_event_id = ?' in archive_apply_source
