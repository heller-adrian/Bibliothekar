from pathlib import Path

from app.database import database_connection, get_event_edit_context, initialize_database
from app.events_ui import EVENTS_HTML
from app.main import APP_VERSION
from app.ssd_release import SsdReleaseError

NOW='2026-09-10T20:00:00+00:00'


def test_version_0205():
    assert APP_VERSION == '0.23.0'


def test_editor_context_returns_all_child_time_segments(tmp_path: Path):
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done',?,?)",(NOW,NOW))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,timeline_model)
                     VALUES ('p','j',NULL,'parent','Test 20','2026-07-20T00:00:00','2026-07-20T23:59:59',0,'07-20 - Test 20','applied',?,?, 'event',0,1,?,'continuous')""",(NOW,NOW,NOW))
        for eid,name,start,end in [('c1','Mittag','11:00','15:00'),('c2','Nachmittag - Abend','15:01','23:59')]:
            c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,timeline_model)
                         VALUES (?,?, 'p','child',?,?,?,1,?, 'applied',?,?, 'event',0,1,?,'continuous')""",
                      (eid,'j',name,f'2026-07-20T{start}:00',f'2026-07-20T{end}:59',f'{start.replace(":","-")} - {end.replace(":","-")} - {name}',NOW,NOW,NOW))
        c.commit()
    ctx=get_event_edit_context(db,'j','p')
    assert [x['name'] for x in ctx['child_events']] == ['Mittag','Nachmittag - Abend']


def test_events_ui_has_multi_segment_editor_and_merged_reassignment_actions():
    assert 'Zeitsegmente / Unterereignisse' in EVENTS_HTML
    assert 'data-child-segment' in EVENTS_HTML
    assert 'child_segments' in EVENTS_HTML
    assert 'Die Änderung bleibt bis zur Neu-Zuordnung im sicheren Schwebezustand' in EVENTS_HTML
    assert 'In Sortieren öffnen' in EVENTS_HTML
    assert 'Änderung verwerfen' in EVENTS_HTML
