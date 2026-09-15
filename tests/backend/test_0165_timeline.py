from pathlib import Path

from app.database import database_connection, initialize_database, list_global_tasks, create_planned_event, update_event_definition
from app.event_structure import build_event_preview
from app.event_reassignment import assign_event_reassignments, list_event_reassignments, EventReassignmentError
from app.event_timeline import list_event_segments, cascade_preview_for_interval

NOW='2026-09-07T20:00:00'

def seed_job(db: Path):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done',?,?)",(NOW,NOW)); c.commit()

def add_family(db: Path, key: str, ts: str):
    with database_connection(db) as c:
        fid=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?,'complete',?,'high')",(key,key,ts)).lastrowid; c.commit(); return fid

def test_migration_016_and_segment_preview(tmp_path):
    db=tmp_path/'db.sqlite3'; seed_job(db)
    f1=add_family(db,'A','2026-07-15T09:00:00'); f2=add_family(db,'B','2026-07-15T15:00:00')
    with database_connection(db) as c:
        cols={r['name'] for r in c.execute('PRAGMA table_info(events)')}
        assert 'timeline_model' in cols
        assert c.execute("SELECT COUNT(*) FROM schema_versions WHERE version=16").fetchone()[0] == 1
    preview=build_event_preview({'event_kind':'no_event','no_event_segments':[{'day_key':'2026-07-15','start_time':'08:00','end_time':'12:00'}]},[
        {'family_id':f1,'selected_capture_time':'2026-07-15T09:00:00'}, {'family_id':f2,'selected_capture_time':'2026-07-15T15:00:00'}])
    assert preview['selected_family_ids']==[f1]

def test_no_event_creation_stores_segments(tmp_path):
    db=tmp_path/'db.sqlite3'; seed_job(db); fid=add_family(db,'A','2026-07-15T09:00:00')
    preview=build_event_preview({'event_kind':'no_event','no_event_segments':[{'day_key':'2026-07-15','start_time':'08:00','end_time':'12:00'}]},[{'family_id':fid,'selected_capture_time':'2026-07-15T09:00:00'}])
    result=create_planned_event(db,'j',preview)
    eid=result['parent_event']['id']; segs=list_event_segments(db,eid)
    assert len(segs)==1 and segs[0]['day_key']=='2026-07-15'
    with database_connection(db) as c:
        assert c.execute('SELECT timeline_model FROM events WHERE id=?',(eid,)).fetchone()[0]=='segments'

def test_normal_event_editor_has_no_family_checkboxes_and_global_widget():
    from app.events_ui import EVENTS_HTML
    from app.main import index
    from app.workspace_ui import WORKSPACE_HTML
    from app.transfer_ui import TRANSFER_HTML
    assert 'name="family_ids"' not in EVENTS_HTML
    assert 'id="no-event-segments"' in EVENTS_HTML
    for html in (EVENTS_HTML,index(),WORKSPACE_HTML,TRANSFER_HTML):
        assert 'global-task-fab' in html

def test_existing_normal_target_accepts_matching_family(tmp_path):
    db=tmp_path/'db.sqlite3'; seed_job(db); fid=add_family(db,'A','2026-07-15T09:00:00')
    with database_connection(db) as c:
        for eid,name,kind in [('src','Quelle','event'),('normal','Normal','event')]:
            c.execute("INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision) VALUES (?, 'j','parent',?,'2026-07-15T00:00:00','2026-07-15T23:59:59',0,?,'planned',?,?,?,0,1)",(eid,name,name,NOW,NOW,kind))
        c.execute("INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('src','j',?,?)",(fid,NOW)); c.commit()
    result=assign_event_reassignments(db,'j','src',[fid],target_mode='existing_event',target_event_id='normal')
    assert result['target']['event_id']=='normal'
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='normal' AND family_id=?",(fid,)).fetchone()[0] == 1

def test_archive_ui_renders_concrete_paths():
    from app.events_ui import EVENTS_HTML
    assert 'Array.isArray(files)' in EVENTS_HTML
    assert '>IST<' in EVENTS_HTML and '>SOLL<' in EVENTS_HTML

def test_cascade_preview_detects_edge_overlap(tmp_path):
    db=tmp_path/'db.sqlite3'; seed_job(db)
    with database_connection(db) as c:
        for eid,name,start,end in [('a','A','2026-07-15T08:00:00','2026-07-15T12:00:59'),('b','B','2026-07-15T12:01:00','2026-07-15T18:00:59')]:
            c.execute("INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision) VALUES (?, 'j','parent',?,'2026-07-15T00:00:00','2026-07-15T23:59:59',0,?,'planned',?,?,'event',0,1)",(eid,name,name,NOW,NOW))
            c.execute("INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision) VALUES (?, 'j',?,'child',?,?,?,1,?,'planned',?,?,'event',0,1)",(eid+'c',eid,name,start,end,name,NOW,NOW))
        c.commit()
    with database_connection(db) as c:
        p=cascade_preview_for_interval(c,'j','a','2026-07-15T08:00:00','2026-07-15T14:00:59')
    assert p['items'] and p['items'][0]['action']=='trim_start'
    assert p['can_apply_automatically'] is True
