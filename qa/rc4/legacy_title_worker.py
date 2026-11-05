"""Synthetic process adapter for the unchanged manual archive workflow."""
import guards
import sys,json,time,os
from pathlib import Path
from contextlib import contextmanager
from app.database import initialize_database,database_connection
from app import event_change_apply as apply,archive_staging

case=Path(sys.argv[1]);point=sys.argv[2];marker=Path(sys.argv[3])
data=json.loads(case.read_text());db,ws,archive=map(Path,[data['db'],data['workspace'],data['archive']]);cr=data['change']
def pause():
    marker.write_text(json.dumps({'pid':os.getpid(),'boundary':point}))
    while True:time.sleep(.03)
if point=='before-commit':
    original=apply.database_connection
    @contextmanager
    def traced(*a,**kw):
        with original(*a,**kw) as c:
            def trace(sql):
                if 'UPDATE event_change_requests SET status' in sql and 'aenderbar_archiviert' in sql:pause()
            c.set_trace_callback(trace)
            yield c
    apply.database_connection=traced
if point=='after-commit':
    original=archive_staging.cleanup_archive_change_staging
    def after(*a,**kw):pause();return original(*a,**kw)
    archive_staging.cleanup_archive_change_staging=after
initialize_database(db)
with database_connection(db) as c:state=c.execute('SELECT status FROM event_change_requests WHERE id=?',(cr,)).fetchone()[0]
if state=='aenderbar_bestaetigt':apply.finish_event_change(db,cr,archive,ws)
with database_connection(db) as c:
    event=dict(c.execute("SELECT * FROM events WHERE id='e'").fetchone())
    assert event['name']=='Final'
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
print(json.dumps({'name':event['name'],'revision':event['revision'],'folder':event['folder_name']}))
