from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML
from app.database import list_global_tasks


def test_events_page_has_search_and_pagination():
    assert 'id="event-search"' in EVENTS_HTML
    assert 'id="event-load-more"' in EVENTS_HTML
    assert '/api/events/search' in EVENTS_HTML


def test_workspace_has_task_reassignment_and_existing_no_event_action():
    assert 'id="task-reassign-dialog"' in WORKSPACE_HTML
    assert 'Zu bestehendem Ohne Ereignis' in WORKSPACE_HTML
    assert '/no-event/assign-existing' in WORKSPACE_HTML


def test_events_script_no_broken_literal_newlines():
    assert r'error.message + "\n\n" + lines.join("\n")' in EVENTS_HTML


def test_search_events_and_expand_existing_no_event(tmp_path):
    from pathlib import Path
    from app.database import (
        database_connection, initialize_database, create_planned_event,
        search_events, assign_free_families_to_existing_no_event,
    )
    from app.event_structure import build_event_preview

    db=tmp_path/'db.sqlite3'
    initialize_database(db)
    now='2026-09-08T01:00:00'
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done','sd_import',?,?)",(now,now))
        f1=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','A','A','complete','2026-07-15T09:00:00','high')").lastrowid
        f2=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','B','B','complete','2026-07-16T10:00:00','high')").lastrowid
        c.commit()
    preview=build_event_preview({'event_kind':'no_event','no_event_segments':[{'day_key':'2026-07-15','start_time':'08:00','end_time':'12:00'}]},[{'family_id':f1,'selected_capture_time':'2026-07-15T09:00:00'}])
    created=create_planned_event(db,'j',preview)
    eid=created['parent_event']['id']
    result=assign_free_families_to_existing_no_event(db,'j',eid,[{'day_key':'2026-07-16','start_time':'09:00','end_time':'11:00'}])
    assert result['assigned_family_count']==1
    found=search_events(db,'Ohne',25,0)
    assert found['matching_count']==1
    assert found['events'][0]['id']==eid
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM event_time_segments WHERE event_id=?",(eid,)).fetchone()[0]==2
