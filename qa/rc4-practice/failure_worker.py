"""Synthetic-only SIGKILL adapter for failed-restore completion."""
import guards
import sys,os,json,time
from pathlib import Path
from app import trash_failure as tf,trash_import as ti
from app.database import initialize_database,database_connection

case=Path(sys.argv[1]);boundary=sys.argv[2];marker=Path(sys.argv[3])
data=json.loads(case.read_text());db=Path(data['db']);ws=Path(data['workspace']);jid=data['job_id']
def pause(point):
    if point==boundary:
        marker.write_text(json.dumps({'pid':os.getpid(),'boundary':point}))
        while True:time.sleep(.03)
tf.checkpoint=pause
initialize_database(db)
if boundary=='recover':
    Path(str(marker)+'.'+str(os.getpid())).write_text('ready')
    deadline=time.monotonic()+15
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
    assert marker.exists(),'parallel release absent'
if boundary=='none':
    from app import main
    from app.library_context import resolve_library_context
    ctx=resolve_library_context(db.parent/'registry.sqlite3','main')
    main.DATABASE_FILE=db;main.REGISTRY_DATABASE_FILE=db.parent/'registry.sqlite3';main.WORKSPACE_PATH=ws
    main.MAIN_LIBRARY_CONTEXT=ctx;main.CONFIG_PATH=db.parent/'settings.json';main.LOG_PATH=db.parent/'logs'
    class NoThread:
        def __init__(self,*a,**kw):pass
        def start(self):pass
        def is_alive(self):return True
        def join(self,*a,**kw):pass
    main.Thread=NoThread  # Only suppress concurrent scheduling, not startup recovery.
    # stdout is this adapter's JSON protocol. Preserve real startup diagnostics
    # on stderr, which the caller already retains alongside the JSON result.
    from contextlib import redirect_stdout
    with redirect_stdout(sys.stderr):main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert main.WORKSPACE_LAYOUT_ERROR is None,main.WORKSPACE_LAYOUT_ERROR
    # The actual startup must complete the verified failed attempt itself.
    assert tf.validate_finalized(None,ws,jid)
result=tf.recover_failed_restores(db,ws)[0]
if boundary=='recover' and result['status']=='blocked':
    assert result['message']=='Ein anderer Vorgang verwendet diesen Bereich. Bitte kurz warten und erneut versuchen.'
    print(json.dumps({'result':result}));sys.exit(0)
assert tf.validate_finalized(None,ws,jid)
assert not ti.protected_trash_paths(None,ws)
with database_connection(db) as c:
    row=c.execute('SELECT * FROM jobs WHERE id=?',(jid,)).fetchone()
    assert row['state']=='failed' and row['error_message']==data['error']
    assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not c.execute('PRAGMA foreign_key_check').fetchall()
    audits=c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_restore_failed_finalized'").fetchone()[0]
print(json.dumps({'result':result,'audit_count':audits,'journal':tf.read_journal(ws,jid)}))
