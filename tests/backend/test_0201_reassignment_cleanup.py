from pathlib import Path

from app.database import initialize_database, database_connection, list_global_tasks
from app.event_reassignment import list_event_reassignments
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION

NOW='2026-09-10T00:30:00+00:00'


def seed(db: Path):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done','sd_import','CARD',?,?)",(NOW,NOW))
        fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','F','F','complete','2026-07-22T10:00:00','high')").lastrowid)
        c.execute("INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model) VALUES ('src','j','parent','Ohne Ereignis','2026-07-21T00:00:00','2026-07-21T23:59:59',0,'07 - Ohne Ereignis','planned',?,?,'no_event',0,1,'segments')",(NOW,NOW))
        c.execute("INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('src','j',?,?)",(fid,NOW))
        c.commit()
    return fid


def test_version_0202():
    assert APP_VERSION == '0.25.0'


def test_stale_pending_reassignment_disappears_when_family_is_assigned_again(tmp_path):
    db=tmp_path/'db.sqlite3'
    fid=seed(db)
    before=list_event_reassignments(db,'j','src')
    assert before['family_count']==1
    with database_connection(db) as c:
        c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('src',?,NULL,'manual',?)",(fid,NOW))
        c.commit()
    after=list_event_reassignments(db,'j','src')
    assert after['family_count']==0
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM event_reapply_removed_families WHERE target_event_id IS NULL").fetchone()[0]==0


def test_reassignment_task_counts_as_one_work_item(tmp_path):
    db=tmp_path/'db.sqlite3'
    seed(db)
    tasks=list_global_tasks(db)
    task=next(t for t in tasks if t['kind']=='reassignment')
    assert task['count']==1
    assert task['family_count']==1


def test_existing_month_blocks_second_no_event_target(tmp_path):
    db=tmp_path/'db.sqlite3'
    fid=seed(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model) VALUES ('other','j','parent','Ohne Ereignis','2026-07-01T00:00:00','2026-07-01T23:59:59',0,'07 - Ohne Ereignis','archived',?,?,'no_event',0,1,'segments')",(NOW,NOW))
        c.commit()
    state=list_event_reassignments(db,'j','src')
    assert state['targets']
    assert state['new_no_event_supported'] is False


def test_all_reassignment_windows_use_day_groups_and_locked_month_ui():
    # 0.25 removes the target selector: assignment happens through workspace cards.
    assert 'In Aufnahmen öffnen' in EVENTS_HTML
    assert 'id="reassignment-target"' not in EVENTS_HTML
    assert 'id="reassignment-apply"' not in EVENTS_HTML
    assert 'segment.start_time' in EVENTS_HTML and 'segment.end_time' in EVENTS_HTML
    assert 'segment.family_count' in EVENTS_HTML and 'segment.file_count' in EVENTS_HTML


def test_existing_no_event_preview_contains_real_folder_structure():
    assert '├── Alle' in WORKSPACE_HTML
    assert '├── Sortiert' in WORKSPACE_HTML
    assert '└── Export' in WORKSPACE_HTML

