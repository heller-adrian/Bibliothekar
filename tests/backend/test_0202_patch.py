from pathlib import Path

from app.database import initialize_database, database_connection
from app.event_reassignment import list_event_reassignments
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML

NOW='2026-09-10T10:00:00+00:00'


def test_same_no_event_collection_is_target_for_its_removed_july_family(tmp_path: Path):
    db=tmp_path/'db.sqlite3'
    initialize_database(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done','sd_import','CARD',?,?)",(NOW,NOW))
        fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','F','F','complete','2026-07-22T10:00:00','high')").lastrowid)
        c.execute("INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model) VALUES ('src','j','parent','Ohne Ereignis','2026-07-21T00:00:00','2026-07-25T23:59:59',0,'07 - Ohne Ereignis','planned',?,?,'no_event',0,1,'segments')",(NOW,NOW))
        c.execute("INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('src','j',?,?)",(fid,NOW))
        c.commit()
    state=list_event_reassignments(db,'j','src')
    assert state['new_no_event_supported'] is False
    assert any(t['event_id']=='src' and t['month_key']=='2026-07' for t in state['targets'])


def test_0202_ui_contracts_present():
    assert 'Vorschau einblenden' in WORKSPACE_HTML
    assert 'Vorschau ausblenden' in WORKSPACE_HTML
    assert 'dialogPreview.hidden' in WORKSPACE_HTML
    assert 'task.startsWith("reassign:")' in WORKSPACE_HTML
    assert '/events?job=' in WORKSPACE_HTML
    assert 'reassignment_segments' in EVENTS_HTML
    assert 'id="no-event-segments"' in EVENTS_HTML
    assert '＋ Tagessegment hinzufügen' in EVENTS_HTML
    assert 'existing-segment-static' in WORKSPACE_HTML
