from pathlib import Path

from app.database import database_connection, initialize_database, update_event_definition
from app.event_reassignment import list_event_reassignments, assign_event_reassignments

NOW = "2026-09-07T18:00:00"


def seed(db: Path, *, source_status: str = "planned"):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done',?,?)", (NOW,NOW))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at)
                     VALUES ('src','j',NULL,'parent','Quelle','2026-09-07T00:00:00','2026-09-08T23:59:59',0,'09-07 - Quelle',?,?,?,'event',0,1,?,NULL)""",
                  (source_status, NOW, NOW, NOW if source_status == 'applied' else None))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision)
                     VALUES ('target','j',NULL,'parent','Ohne Ereignis','2026-09-06T09:00:00','2026-09-06T10:30:59',0,'09 - Ohne Ereignis','planned',?,?,'no_event',0,1)""", (NOW,NOW))
        c.execute("""INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
                     VALUES ('target','j','2026-09-07','09:00','10:30','2026-09-06T09:00:00','2026-09-06T10:30:59','user',?,?)""", (NOW,NOW))
        ids=[]
        for n,time in [(1,'2026-09-07T10:00:00'),(2,'2026-09-08T11:00:00')]:
            fid=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(f'f{n}',f'IMG{n}',time)).lastrowid
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('src',?,NULL,'manual',?)",(fid,NOW))
            ids.append(fid)
        c.commit()
    return ids


def edit_drop_second(db: Path, ids):
    return update_event_definition(
        db,'j','src',{
            'selected_family_ids':[ids[0]], 'start_date':'2026-09-07','end_date':'2026-09-07',
            'start_time':'00:00','end_time':'23:59','uses_time_range':False,
            'parent_folder':'09-07 - Quelle','child_folder':'','child_event_name':'',
            'event_kind':'event','preserve_day_folders':False,
        }, event_name='Quelle',notes='',expected_revision=1,
    )


def _segments(db: Path):
    return list_event_reassignments(db, 'j', 'src')['reassignment_segments']


def test_planned_removed_family_must_be_reassigned_and_queue_clears(tmp_path):
    db=tmp_path/'db.sqlite3'; ids=seed(db,source_status='planned')
    result=edit_drop_second(db,ids)
    assert result['reassignment_required'] is True
    assert result['removed_family_ids'] == [ids[1]]
    state=list_event_reassignments(db,'j','src')
    assert [int(f['family_id']) for f in state['families']] == [ids[1]]

    assigned=assign_event_reassignments(db,'j','src',[ids[1]],target_mode='existing_no_event',target_event_id='target',segments=state['reassignment_segments'])
    assert assigned['pending_family_count'] == 0
    assert assigned['source_resort_required'] is False
    with database_connection(db) as c:
        row=c.execute("SELECT event_id FROM event_assignments WHERE family_id=?",(ids[1],)).fetchone()
        assert row['event_id'] == 'target'
        assert c.execute("SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='src'").fetchone()[0] == 0


def test_applied_removed_family_keeps_target_for_reapply(tmp_path):
    db=tmp_path/'db.sqlite3'; ids=seed(db,source_status='applied')
    result=edit_drop_second(db,ids)
    assert result['resort_required'] is True
    assigned=assign_event_reassignments(db,'j','src',[ids[1]],target_mode='existing_no_event',target_event_id='target',segments=_segments(db))
    assert assigned['pending_family_count'] == 0
    assert assigned['source_resort_required'] is True
    with database_connection(db) as c:
        row=c.execute("SELECT target_event_id,target_status,target_folder_name,reassigned_at FROM event_reapply_removed_families WHERE event_id='src' AND family_id=?",(ids[1],)).fetchone()
        assert row['target_event_id'] == 'target'
        assert row['target_status'] == 'planned'
        assert row['target_folder_name'] == '09 - Ohne Ereignis'
        assert row['reassigned_at']


def test_new_event_can_be_created_from_removed_family(tmp_path):
    db=tmp_path/'db.sqlite3'; ids=seed(db,source_status='planned')
    edit_drop_second(db,ids)
    assigned=assign_event_reassignments(db,'j','src',[ids[1]],target_mode='new_event',new_event_name='Neues Ziel',segments=_segments(db))
    assert assigned['pending_family_count'] == 0
    target_id=assigned['target']['event_id']
    with database_connection(db) as c:
        event=c.execute("SELECT name,status FROM events WHERE id=?",(target_id,)).fetchone()
        assert event['name'] == 'Neues Ziel'
        assert event['status'] == 'planned'
        row=c.execute("SELECT COALESCE(e.parent_event_id,e.id) AS root_id FROM event_assignments ea JOIN events e ON e.id=ea.event_id WHERE ea.family_id=?",(ids[1],)).fetchone()
        assert row['root_id'] == target_id


def test_events_and_import_use_archive_background_principle():
    from app.events_ui import EVENTS_HTML
    from app.main import index
    assert 'main {\n      width: min(1120px, 100%);' in EVENTS_HTML
    assert 'background: transparent;' in EVENTS_HTML
    assert 'html, body { background: #090b0d !important;' in EVENTS_HTML
    assert 'html, body { background: #090b0d !important;' in index()
