from app.database import initialize_database, database_connection, list_no_event_month_targets
from app.workspace_ui import WORKSPACE_HTML


def test_no_event_target_returns_existing_segments(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    now='2026-09-09T16:00:00+00:00'
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                     VALUES ('ne','j','parent','Ohne Ereignis','2026-07-21T00:00:00','2026-07-21T23:59:59',0,'07 - Ohne Ereignis','planned',?,?,'no_event',0,1,'segments')""",(now,now))
        c.execute("""INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
                     VALUES ('ne','j','2026-07-21','00:00','23:59','2026-07-21T00:00:00','2026-07-21T23:59:59','user',?,?)""",(now,now))
        c.commit()
    targets=list_no_event_month_targets(db,['2026-07'],prefer_job_id='j')
    assert len(targets)==1
    assert targets[0]['status']=='planned'
    assert targets[0]['segments']==[{
        'day_key':'2026-07-21','start_time':'00:00','end_time':'23:59',
        'start_datetime':'2026-07-21T00:00:00','end_datetime':'2026-07-21T23:59:59'
    }]


def test_workspace_unifies_no_event_entry_point():
    assert 'id="existing-no-event-button" type="button" hidden' in WORKSPACE_HTML
    assert 'autoAttachExistingNoEventCollection' in WORKSPACE_HTML
    assert 'loadEventNamingSettings' in WORKSPACE_HTML
    assert 'noEventLabel' in WORKSPACE_HTML
    assert 'data-locked' in WORKSPACE_HTML
    assert '· NEU' in WORKSPACE_HTML
    assert 'activeNoEventTarget ? newSegments : allSegments' in WORKSPACE_HTML
