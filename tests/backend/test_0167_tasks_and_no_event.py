from pathlib import Path

from app.database import (
    database_connection,
    initialize_database,
    create_planned_event,
    list_no_event_month_targets,
    list_global_tasks,
    assign_free_families_to_existing_no_event,
)
from app.event_structure import build_event_preview
from app.event_reassignment import assign_event_reassignments, list_event_reassignments
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML

NOW = "2026-09-08T02:00:00"


def seed_job(db: Path, job_id: str, label: str):
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) "
            "VALUES (?, 'sd_import','manual','completed','done','sd_import',?,?,?)",
            (job_id, label, NOW, NOW),
        )
        c.commit()


def add_family(db: Path, job_id: str, key: str, ts: str):
    with database_connection(db) as c:
        fid = c.execute(
            "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) "
            "VALUES (?,?,?,'complete',?,'high')",
            (job_id, key, key, ts),
        ).lastrowid
        c.commit()
        return fid


def create_no_event(db: Path, job_id: str, fid: int, day: str, start="08:00", end="12:00"):
    preview = build_event_preview(
        {"event_kind": "no_event", "no_event_segments": [{"day_key": day, "start_time": start, "end_time": end}]},
        [{"family_id": fid, "selected_capture_time": f"{day}T09:00:00"}],
    )
    return create_planned_event(db, job_id, preview)["parent_event"]


def test_reassignment_offers_monthly_no_event_from_other_job_and_new_no_event(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    seed_job(db, "old", "OLD")
    seed_job(db, "new", "NEW")
    old_fid = add_family(db, "old", "OLD1", "2026-07-15T09:00:00")
    existing = create_no_event(db, "old", old_fid, "2026-07-15")
    new_fid = add_family(db, "new", "NEW1", "2026-07-24T22:32:28")
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision) "
            "VALUES ('src','new','parent','Quelle','2026-07-24T00:00:00','2026-07-24T23:59:59',0,'07-24 - Quelle','planned',?,?,'event',0,1)",
            (NOW, NOW),
        )
        c.execute(
            "INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('src','new',?,?)",
            (new_fid, NOW),
        )
        c.commit()

    state = list_event_reassignments(db, "new", "src")
    assert state["new_no_event_supported"] is False
    assert len(state["targets"]) == 1
    assert state["targets"][0]["event_id"] == existing["id"]
    assert state["targets"][0]["month_key"] == "2026-07"
    assert state["targets"][0]["same_job"] is False

    result = assign_event_reassignments(
        db, "new", "src", [new_fid], target_mode="existing_no_event", target_event_id=existing["id"]
    )
    assert result["pending_family_count"] == 0
    assert result["target"]["folder_name"] == "07 - Ohne Ereignis"
    assert result["target"]["linkage_kind"] == "planned_extension"
    with database_connection(db) as c:
        row = c.execute("SELECT job_id,event_kind,linked_event_id,folder_name FROM events WHERE id=?", (result["target"]["event_id"],)).fetchone()
        assert row["job_id"] == "new"
        assert row["event_kind"] == "no_event"
        assert row["linked_event_id"] == existing["id"]
        assert row["folder_name"] == "07 - Ohne Ereignis"


def test_normal_sort_can_extend_cross_job_month_collection(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    seed_job(db, "a", "A")
    seed_job(db, "b", "B")
    fa = add_family(db, "a", "A1", "2026-07-15T09:00:00")
    existing = create_no_event(db, "a", fa, "2026-07-15")
    fb = add_family(db, "b", "B1", "2026-07-24T10:00:00")

    targets = list_no_event_month_targets(db, ["2026-07"], prefer_job_id="b")
    assert len(targets) == 1 and targets[0]["id"] == existing["id"]
    result = assign_free_families_to_existing_no_event(
        db, "b", existing["id"], [{"day_key": "2026-07-24", "start_time": "09:00", "end_time": "11:00"}]
    )
    assert result["assigned_family_count"] == 1
    assert result["cross_job"] is True
    with database_connection(db) as c:
        e = c.execute("SELECT job_id,folder_name,linkage_kind FROM events WHERE id=?", (result["event_id"],)).fetchone()
        assert e["job_id"] == "b"
        assert e["folder_name"] == "07 - Ohne Ereignis"
        assert e["linkage_kind"] == "planned_extension"
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id=? AND family_id=?", (result["event_id"], fb)).fetchone()[0] == 1


def test_global_task_button_stays_visible_and_planned_and_free_tasks_exist(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    seed_job(db, "j", "CARD")
    fid = add_family(db, "j", "FREE", "2026-08-01T10:00:00")
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision) "
            "VALUES ('p','j','parent','Plan','2026-08-02T00:00:00','2026-08-02T23:59:59',0,'08-02 - Plan','planned',?,?,'event',0,1)",
            (NOW, NOW),
        )
        c.commit()
    tasks = list_global_tasks(db)
    kinds = {t["kind"] for t in tasks}
    assert "planned_apply" in kinds
    assert "unassigned_families" in kinds
    for html in (EVENTS_HTML, WORKSPACE_HTML):
        assert ".global-task-badge.hidden" in html
        assert "Keine offenen Aufgaben" in html


def test_reassignment_ui_has_new_no_event_and_event_spacing():
    # 0.25 removes the target selector: assignment happens through workspace cards.
    assert 'In Aufnahmen öffnen' in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert 'id="reassignment-apply"' not in EVENTS_HTML
    assert 'segment.start_time' in EVENTS_HTML and 'segment.end_time' in EVENTS_HTML
    assert 'segment.family_count' in EVENTS_HTML and 'segment.file_count' in EVENTS_HTML

