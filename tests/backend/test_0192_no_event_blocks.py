from app.database import initialize_database, database_connection, list_no_event_month_targets
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def seed_noevent(db):
    initialize_database(db)
    now='2026-09-09T18:00:00+00:00'
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        for eid, month, status in [('jul','2026-07','planned'),('aug','2026-08','archived')]:
            c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                         VALUES (?,?, 'parent','Ohne Ereignis',?,?,0,?,?,?,?,'no_event',0,1,'segments')""",
                      (eid,'j',f'{month}-21T00:00:00',f'{month}-22T23:59:59',f'{month[5:7]} - Ohne Ereignis',status,now,now))
            for day in ('21','22'):
                c.execute("""INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
                             VALUES (?,?,?,?,?,?,?,?,?,?)""",
                          (eid,'j',f'{month}-{day}','00:00','23:59',f'{month}-{day}T00:00:00',f'{month}-{day}T23:59:59','user',now,now))
        c.commit()


def test_empty_month_filter_lists_all_canonical_noevent_targets(tmp_path):
    db=tmp_path/'db.sqlite3'; seed_noevent(db)
    targets=list_no_event_month_targets(db,[],prefer_job_id='j')
    assert [t['month_key'] for t in targets] == ['2026-08','2026-07']
    assert targets[0]['status']=='archived'
    assert len(targets[1]['segments'])==2


def test_workspace_has_collapsed_timeblocks_and_manual_target_picker():
    assert 'id="no-event-range-details"' in WORKSPACE_HTML
    assert '<details id="no-event-range-details" class="card"' in WORKSPACE_HTML
    assert 'Zeitblock ${index+1}' in WORKSPACE_HTML
    assert 'Noch keine Zeitblöcke.' in WORKSPACE_HTML
    assert 'Neue Monats-Sammlung / noch kein Ziel' in WORKSPACE_HTML
    assert '＋ Zeitblock hinzufügen' in WORKSPACE_HTML
    assert 'Fehlende Tagessegmente ergänzen' in WORKSPACE_HTML
    assert 'noEventTargetCache.find' in WORKSPACE_HTML
    assert 'Ein noch unvollständiges Datum darf nicht' in WORKSPACE_HTML


def test_event_editor_uses_segment_envelope_and_responsive_remove():
    assert 'const noEventRangeStart = noEventDays.length ? noEventDays[0]' in EVENTS_HTML
    assert 'const noEventRangeEnd = noEventDays.length ? noEventDays[noEventDays.length - 1]' in EVENTS_HTML
    assert 'grid-template-columns:minmax(0,2fr) minmax(0,1fr) minmax(0,1fr) 120px' in EVENTS_HTML
    assert 'edit-noevent-range-apply' in EVENTS_HTML
