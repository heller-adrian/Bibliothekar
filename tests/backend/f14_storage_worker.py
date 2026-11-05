"""Real startup in a new process; all input paths are synthetic case paths."""
from pathlib import Path
import json,os,signal,sys
case=Path(sys.argv[1]);control=Path(sys.argv[2]);boundary=sys.argv[3]
private=case/'database' if (case/'database').is_dir() else case  # Explicit new-install fixture; historical cases retain their paths.
for key,value in {'KAMERA_WORKSPACE':case/'workspace','KAMERA_CONFIG':case/'settings.json','KAMERA_REGISTRY_DATABASE':private/'registry.sqlite3','KAMERA_DATABASE_DIR':private,'KAMERA_ARCHIVE_ROOT':case/'archive','KAMERA_LOG_DIR':case/'logs'}.items():os.environ[key]=str(value)
from app import main
main.WORKSPACE_PATH=case/'workspace';main.DATABASE_FILE=private/'main.sqlite3';main.REGISTRY_DATABASE_FILE=private/'registry.sqlite3';main.CONFIG_PATH=case/'settings.json';main.LOG_PATH=case/'logs'
class NoScheduler:
    def __init__(self,*a,**k):pass
    def start(self):pass
    def is_alive(self):return False
    def join(self,*a,**k):pass
main.Thread=NoScheduler;main.WORKER_THREAD=None
if main.REGISTRY_DATABASE_FILE.is_file():
    from app.library_registry import get_library
    from app.library_context import resolve_library_context
    if get_library(main.REGISTRY_DATABASE_FILE,'main'):main.MAIN_LIBRARY_CONTEXT=resolve_library_context(main.REGISTRY_DATABASE_FILE,'main')
else:main.MAIN_LIBRARY_CONTEXT=main.build_main_library_context()
from app import managed_storage_health as health
_checked=health.require_storage

def checked(*a,**kw):
    try:return _checked(*a,**kw)
    except Exception:
        import traceback
        (control/'storage-failure-trace.txt').write_text(traceback.format_exc()+'\n'+''.join(traceback.format_stack())+'\n'+json.dumps(health.inspect_storage(*a,database=kw.get('database')),indent=2))
        raise
health.require_storage=checked

actual=Path.mkdir

def mkdir(path,*args,**kwargs):
    result=actual(path,*args,**kwargs)
    if boundary!='none' and path==main.WORKSPACE_PATH/boundary:
        with (control/'checkpoint.json').open('w') as f:
            json.dump({'pid':os.getpid(),'boundary':'after-mkdir','path':str(path)},f);f.flush();os.fsync(f.fileno())
        os.kill(os.getpid(),signal.SIGSTOP)
    return result
Path.mkdir=mkdir
def checkpoint(label):
    with (control/'checkpoint.json').open('w') as f:
        json.dump({'pid':os.getpid(),'boundary':label},f);f.flush();os.fsync(f.fileno())
    os.kill(os.getpid(),signal.SIGSTOP)
if boundary=='unqualified-before-preflight':checkpoint(boundary)
if boundary=='manual-recheck':
    from app.storage_config import storage_paths
    root=storage_paths(main.WORKSPACE_PATH)['backup_root'];retained=case/'manual-restoration-source'
    root.rename(retained)
    main.startup_database()
    assert main._STORAGE_STARTUP_PAUSED and main.DATABASE_INITIALIZATION_ERROR
    assert not root.exists()
    retained.rename(root)
    rechecks=[]
    for _ in range(3):
        rechecks.append(main.api_recheck_storage()['ready'])
        assert main.DATABASE_INITIALIZATION_ERROR is None and not main._STORAGE_STARTUP_PAUSED
    (control/'rechecks.json').write_text(json.dumps(rechecks))
else:
    main.startup_database()
if boundary=='unqualified-after-preflight':checkpoint(boundary)
result={'pid':os.getpid(),'error':main.DATABASE_INITIALIZATION_ERROR,'scheduler_started':False,'method':'real startup body; permanent scheduling suppressed'}
(control/'result.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
