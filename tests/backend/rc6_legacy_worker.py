"""Real idle worker, synthetic paths; model process/container lifecycle locally."""
import guards
import json,os,sys,time
from pathlib import Path
case=Path(sys.argv[1]);output=Path(sys.argv[2]);mode=sys.argv[3]
for k,v in {'KAMERA_WORKSPACE':case/'workspace','KAMERA_CONFIG':case/'settings.json','KAMERA_DATABASE_DIR':case/'database','KAMERA_REGISTRY_DATABASE':case/'database/registry.sqlite3','KAMERA_ARCHIVE_ROOT':case/'archive','KAMERA_LOG_DIR':case/'logs'}.items():os.environ[k]=str(v)
from app import main,root_operations as ro
from app.managed_storage_health import inspect_storage
main.DATABASE_FILE=case/'database/main.sqlite3';main.MAIN_LIBRARY_CONTEXT=main.build_main_library_context()
if mode=='live':
    # Hold the real worker at its first claim, with an actual SQLite reader
    # open. All startup and admission code is real; only scheduling is fixed.
    original=main.claim_next_job
    def at_claim(database,*a,**kw):
        import sqlite3,threading
        connection=sqlite3.connect(Path(database).as_uri()+'?mode=ro',uri=True)
        connection.execute('BEGIN');connection.execute('SELECT COUNT(*) FROM jobs').fetchone()
        output.with_suffix('.claim').write_text('real worker admitted; SQLite reader open')
        threading.Event().wait(40)
        connection.close()
        return original(database,*a,**kw)
    main.claim_next_job=at_claim
if mode=='live':
    # This fixture represents an old format-1 installation. RC11 deliberately
    # requires an explicit administrative provenance decision before upgrade.
    from app import storage_admin
    proof=storage_admin.inspect(main.WORKSPACE_PATH,main.DATABASE_FILE,scope='control')
    storage_admin.adopt(main.WORKSPACE_PATH,main.DATABASE_FILE,proof['token'],'ADOPT RC10 BOOTSTRAP','synthetic consistent legacy backup',scope='control')
main.startup_database()
if mode=='live':
    assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert main.WORKER_THREAD and main.WORKER_THREAD.is_alive()
    until=time.monotonic()+15
    while not output.with_suffix('.claim').exists():
        assert time.monotonic()<until,'worker claim boundary not reached';time.sleep(.02)
    output.write_text(json.dumps({'worker_alive':True,'state':ro._read(ro._control_location(main.WORKSPACE_PATH)/'state.json')}))
    until=time.monotonic()+40
    while not output.with_suffix('.observe').exists():
        assert time.monotonic()<until,'parent did not complete synthetic wipe';time.sleep(.02)
    result=inspect_storage(main.WORKSPACE_PATH,database=main.DATABASE_FILE)
    output.with_suffix('.observed').write_text(json.dumps(result))
    while True:time.sleep(.05)
else:
    from fastapi.testclient import TestClient
    client=TestClient(main.app)
    before=client.get('/api/settings/storage-health').json()
    if mode=='confirm':
        assert before.get('can_setup_again'),before
        result=client.post('/api/settings/storage-initialize',json={'confirmation':'SET UP AGAIN','token':before['setup_token']})
        assert result.status_code==200,result.text
        main._mount_read_only=lambda path:True  # Synthetic local archive, not a native RO mount.
        payload={'display_name':'Recovered Camera','work_root':'','archive_root':str(case/'archive'),'default_library_id':'recovered-camera'}
        check=client.post('/api/libraries/check',json=payload);assert check.json()['valid'],check.text
        created=client.post('/api/libraries',json={k:v for k,v in payload.items() if k!='default_library_id'})
        assert created.status_code==201,created.text
        assert main.WORKER_THREAD.is_alive()
        result={'health':result.json(),'check':check.json(),'library':created.json(),'worker_alive':True}
    else:result={'health':before,'error':main.DATABASE_INITIALIZATION_ERROR,'database_exists':main.DATABASE_FILE.exists()}
    output.write_text(json.dumps(result));print(json.dumps(result))
    main.WORKER_STOP.set()
    if main.WORKER_THREAD:main.WORKER_THREAD.join(timeout=5)
