from app.event_structure import build_event_preview
from app.workspace_ui import WORKSPACE_HTML


def fam(fid, day, time="12:00:00"):
    return {
        "family_id": fid,
        "family_key": f"F{fid}",
        "selected_capture_time": f"{day}T{time}",
        "day_key": day,
        "has_date": True,
        "file_count": 2,
        "total_size_bytes": 1,
        "review_required_count": 0,
    }


def test_no_event_preserve_day_folders_is_real_structure():
    preview = build_event_preview(
        {
            "event_kind": "no_event",
            "event_name": "Ohne Ereignis",
            "preserve_day_folders": True,
            "no_event_segments": [
                {"day_key": "2026-07-21", "start_time": "00:00", "end_time": "23:59"},
                {"day_key": "2026-07-22", "start_time": "10:00", "end_time": "18:00"},
            ],
        },
        [fam(1, "2026-07-21"), fam(2, "2026-07-22", "12:00:00")],
    )
    assert preview["preserve_day_folders"] is True
    assert "2026-07-21" in preview["structure_text"]
    assert "2026-07-22" in preview["structure_text"]
    assert preview["structure_text"].count("Alle") == 2


def test_normal_event_range_is_canonical_not_old_day_selection():
    preview = build_event_preview(
        {
            "event_kind": "event",
            "event_name": "Mehrtag",
            "start_date": "2026-07-20",
            "end_date": "2026-07-21",
            "uses_time_range": False,
            "preserve_day_folders": True,
            # UI started from only one selected day; range was then extended.
            "selected_day_keys": ["2026-07-20"],
        },
        [fam(1, "2026-07-20"), fam(2, "2026-07-21")],
    )
    assert preview["selected_family_count"] == 2
    assert preview["selected_day_keys"] == ["2026-07-20", "2026-07-21"]
    assert "2026-07-21" in preview["structure_text"]


def test_workspace_has_segment_generator_and_preserve_toggle_for_no_event():
    assert "Zeitspanne" in WORKSPACE_HTML
    assert "· Auswahlhilfe" in WORKSPACE_HTML
    assert "no-event-range-fields" in WORKSPACE_HTML
    assert "syncNoEventRangeDisplayFromSegments" in WORKSPACE_HTML
    assert "syncNoEventSegmentsFromRange" in WORKSPACE_HTML
    assert "base.preserve_day_folders = preserveDayFolders.checked" in WORKSPACE_HTML

from app.database import initialize_database, database_connection, create_planned_event


def test_new_time_event_can_reuse_existing_planned_parent(tmp_path):
    db=tmp_path/'db.sqlite3'
    initialize_database(db)
    now='2026-09-09T03:00:00+00:00'
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','F1','F1','complete','2026-07-19T20:00:00','high')").lastrowid)
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                     VALUES ('parent','j','parent','Tag 19','2026-07-19T00:00:00','2026-07-19T23:59:59',0,'07-19 - Tag 19','planned',?,?,'event',0,1,'continuous')""",(now,now))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                     VALUES ('child1','j','parent','child','Früh','2026-07-19T17:00:00','2026-07-19T19:00:59',1,'17-00 - 19-00 - Früh','planned',?,?,'event',0,1,'continuous')""",(now,now))
        c.commit()
    preview={
        'event_kind':'event','event_name':'Tag 19','parent_folder':'07-19 - Tag 19',
        'child_event_name':'Abend','child_folder':'19-01 - 22-00 - Abend','uses_time_range':True,
        'preserve_day_folders':False,'start_date':'2026-07-19','end_date':'2026-07-19',
        'start_time':'19:01','end_time':'22:00','selected_family_ids':[fid],'selected_day_keys':['2026-07-19'],
        'selected_file_count':0,'selected_family_count':1,'structure_lines':[],
        'existing_parent_event_id':'parent',
    }
    result=create_planned_event(db,'j',preview)
    assert result['parent_event']['id']=='parent'
    assert result['child_event'] is None
    assert result['parent_event']['start_datetime']=='2026-07-19T17:00:00'
    assert result['parent_event']['end_datetime']=='2026-07-19T22:00:59'
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM events WHERE parent_event_id='parent'").fetchone()[0]==1
        assert c.execute("SELECT event_id FROM event_assignments WHERE family_id=?",(fid,)).fetchone()[0]=='parent'

