"""Synthetic subprocess adapter; never use against an installed application."""
import guards  # Existing scratch/database/network audit boundary.
import sys,os,json,time
from pathlib import Path
from app import main,sd_recheck as sr
from app.database import claim_next_job,get_job
from app.library_context import resolve_library_context

case=Path(sys.argv[1]);mode=sys.argv[2];point=sys.argv[3];evidence=Path(sys.argv[4]);evidence.mkdir(parents=True,exist_ok=True)
data=json.loads((case/'sd-case.json').read_text());db=Path(data['database'])
context=resolve_library_context(case/'registry.sqlite3','main')
main.DATABASE_FILE=db;main.REGISTRY_DATABASE_FILE=case/'registry.sqlite3';main.WORKSPACE_PATH=context.workspace_root
main.MAIN_LIBRARY_CONTEXT=context;main.LOG_PATH=case/'logs';main.REMOVABLE_ROOT=case/'removable'
main.CONFIG_PATH=case/'settings.json';main.WORKER_STOP.clear()
sr.read_only=lambda path:True  # Explicit synthetic mount model, no real mounts.

def pause():
    (evidence/'reached').write_text(point)
    while True:time.sleep(.05)
if mode=='enqueue':
    with __import__('app.root_operations',fromlist=['admission']).admission(context):
        job=sr.enqueue(db,source=case/'removable/CARD',source_root=case/'removable',device='CARD',
            working=Path(data['working']),label='Synthetic SD',request_id=str(__import__('uuid').uuid4()))
    print(json.dumps({'id':job['id']}));raise SystemExit(0)
if mode=='restart':
    class NoThread:
        def __init__(self,*args,**kwargs):pass
        def start(self):pass
        def is_alive(self):return True
        def join(self,*a,**k):pass
    # Run the real startup/recovery; schedule jobs explicitly for determinism.
    # This adapter suppresses only concurrent test scheduling, not recovery.
    main.Thread=NoThread
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert main.WORKSPACE_LAYOUT_ERROR is None,main.WORKSPACE_LAYOUT_ERROR
if point=='hash':
    original=sr.source_manifest
    def before_hash(*a,**kw):pause();return original(*a,**kw)
    sr.source_manifest=before_hash
if point=='handoff':
    original=sr._insert
    def before_commit(connection,**kw):
        result=original(connection,**kw)
        if kw['operation']=='folder_import':pause()
        return result
    sr._insert=before_commit
if point=='after_handoff':
    original=sr.run
    def after_commit(*a,**kw):result=original(*a,**kw);pause();return result
    sr.run=after_commit
job=claim_next_job(db)
if job:main.process_claimed_job(job,library_context=context)
print(json.dumps({'job':get_job(db,job['id']) if job else None,'startup_error':main.DATABASE_INITIALIZATION_ERROR},default=str))
