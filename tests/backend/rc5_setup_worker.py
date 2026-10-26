"""Actual startup/reset in a separate process, synthetic fixture paths only."""
from pathlib import Path
import sys,os,json,signal
case=Path(sys.argv[1]);output=Path(sys.argv[2]);mode=sys.argv[3];private=case/'database'
for k,v in {'KAMERA_WORKSPACE':case/'workspace','KAMERA_CONFIG':case/'settings.json','KAMERA_DATABASE_DIR':private,'KAMERA_REGISTRY_DATABASE':private/'registry.sqlite3','KAMERA_ARCHIVE_ROOT':case/'archive','KAMERA_LOG_DIR':case/'logs'}.items():os.environ[k]=str(v)
from app import main,root_operations as ro
from app.managed_storage_health import inspect_storage
main.WORKSPACE_PATH=case/'workspace';main.DATABASE_FILE=private/'main.sqlite3';main.REGISTRY_DATABASE_FILE=private/'registry.sqlite3';main.CONFIG_PATH=case/'settings.json';main.LOG_PATH=case/'logs';main.MAIN_LIBRARY_CONTEXT=main.build_main_library_context()
class NoScheduler:
    def __init__(self,*a,**k):pass
    def start(self):pass
    def is_alive(self):return False
main.Thread=NoScheduler;main.WORKER_THREAD=None
if mode.startswith('reset-'):
    actual=ro._write
    def write(path,value):
        actual(path,value)
        if (mode=='reset-history' and path.name.startswith('setup-history-')) or (mode=='reset-state' and path.name=='state.json' and value.get('setup_reset')):
            output.with_suffix('.checkpoint').write_text(path.name);os.kill(os.getpid(),signal.SIGSTOP)
    ro._write=write
    status=inspect_storage(main.WORKSPACE_PATH,database=main.DATABASE_FILE)
    ro.reset_empty_storage(main.WORKSPACE_PATH,main.DATABASE_FILE,status['setup_token'])
main.startup_database()
if mode=='api-reset':
    assert main.DATABASE_INITIALIZATION_ERROR and main._STORAGE_STARTUP_PAUSED
    from fastapi.testclient import TestClient
    client=TestClient(main.app)
    health=client.get('/api/settings/storage-health').json()
    response=client.post('/api/settings/storage-initialize',json={'confirmation':'SET UP AGAIN','token':health['setup_token']})
    assert response.status_code==200,response.text
result={'error':main.DATABASE_INITIALIZATION_ERROR,'ready':inspect_storage(main.WORKSPACE_PATH,database=main.DATABASE_FILE)['ready'],'onboarding':main._onboarding_required()}
if mode=='onboard' and result['error'] is None:
    # Synthetic local paths are not a native RO mount; model only that platform
    # predicate while exercising the real HTTP onboarding and registry writes.
    main._mount_read_only=lambda path:True
    from fastapi.testclient import TestClient
    client=TestClient(main.app)
    result['onboarding_http']=client.get('/').status_code
    payload={'display_name':'New Camera Library','work_root':str(case/'workspace/Library Workspaces/camera'),'archive_root':str(case/'archive')}
    check=client.post('/api/libraries/check',json=payload);result['check']=check.json()
    created=client.post('/api/libraries',json=payload);result['create_status']=created.status_code;result['created']=created.json()
output.write_text(json.dumps(result));print(json.dumps(result))
