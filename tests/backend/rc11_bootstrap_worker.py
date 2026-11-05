"""Fresh process, synthetic paths only. No auth/mount/ACL bypass."""
import json
import os
from pathlib import Path
import sys
import time

base,output=map(lambda s:Path(s).absolute(),sys.argv[1:3]);boundary=sys.argv[3]
assert base.is_dir() and output.is_relative_to(base)
for name in ('workspace','database','config','archive','logs','sources'):(base/name).mkdir(exist_ok=True)
for key,value in {'KAMERA_WORKSPACE':'workspace','KAMERA_DATABASE_DIR':'database',
                  'KAMERA_REGISTRY_DATABASE':'database/bibliothekar-global.sqlite3','KAMERA_CONFIG':'config/settings.json',
                  'KAMERA_ARCHIVE_ROOT':'archive','KAMERA_LOG_DIR':'logs','KAMERA_POOL_PROBE':'workspace',
                  'KAMERA_NAS_SOURCE_ROOT':'sources','KAMERA_REMOVABLE_ROOT':'sources','KAMERA_IMPORT_ROOT':'sources'}.items():os.environ[key]=str(base/value)
os.environ.update(KAMERA_SOURCE_HELPER_ENABLED='false',BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-rc11-test-password')
os.environ.pop('BIBLIOTHEKAR_AUTH_TEST_BYPASS',None)
from app import main as m,root_operations as ro,storage_admin
from app.managed_storage_health import inspect_storage
from fastapi.testclient import TestClient
picture=base/'archive/photo.JPG'
if not picture.exists():picture.write_bytes(b'original independent archive')
original=picture.read_bytes()

def pause(label):
    (output/'checkpoint.json').write_text(json.dumps({'label':label}))
    while True:time.sleep(.05)

original_mkdir=Path.mkdir
def mkdir(self,*a,**kw):
    result=original_mkdir(self,*a,**kw)
    if boundary=='folders' and self==base/'workspace/Trash':pause(boundary)
    return result
if boundary=='folders':Path.mkdir=mkdir
original_unlink=os.unlink
def unlink(path,*a,**kw):
    result=original_unlink(path,*a,**kw)
    if boundary=='operation-unlink' and str(path).split('/')[-1].startswith('operation-') and str(path).endswith('.json'):pause(boundary)
    return result
if boundary=='operation-unlink':os.unlink=unlink

original_replace=os.replace
def replace(src,dst,*a,**kw):
    if boundary=='uncommitted-state' and str(dst)=='state.json':
        fd=os.open(src,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=kw.get('src_dir_fd'))
        with os.fdopen(fd) as stream:value=json.load(stream)
        if value.get('storage_initialization',{}).get('phase')=='prepared':pause(boundary)
    return original_replace(src,dst,*a,**kw)
if boundary=='uncommitted-state':os.replace=replace

def trace(frame,event,arg):
    if event=='call':
        return trace if frame.f_code.co_name in {'ensure_settings_file','initialize_database','initialize_library_registry','recover_trash_restores','_lock','_write'} else None
    if event!='return':return trace
    name=frame.f_code.co_name;file=Path(frame.f_code.co_filename).name
    targets={'ensure_settings_file':'config','initialize_database':'database','initialize_library_registry':'registry','recover_trash_restores':'recovery'}
    if targets.get(name)==boundary:pause(boundary)
    if file=='root_operations.py' and name=='_lock' and boundary=='private-lock' and Path(frame.f_locals['path']).name=='trash-recovery.lock':pause(boundary)
    if file=='root_operations.py' and name=='_write':
        path=Path(frame.f_locals['path']);value=frame.f_locals['value']
        phase=value.get('storage_initialization',{}).get('phase')
        matches=(boundary=='reservation' and path.name.startswith('operation-') and value.get('kind')=='startup'
            or boundary=='prepared' and path.name=='state.json' and phase=='prepared'
            or boundary=='completed' and path.name=='state.json' and phase=='completed'
            or boundary=='completion-receipt' and path.name.startswith('bootstrap-completed-')
            or boundary=='operation-archive' and path.name.startswith('bootstrap-operation-')
            or boundary=='finished-receipt' and path.name.startswith('finished-')
            or boundary=='adoption-receipt' and path.name.startswith('rc11-adoption-')
            or boundary=='control-format' and path.name=='state.json' and value.get('control_migration'))
        if matches:pause(boundary)
    return trace
sys.settrace(trace)
if boundary=='adoption-receipt':
    checked=storage_admin.inspect(base/'workspace',base/'database/kamera.sqlite3')
    storage_admin.adopt(base/'workspace',base/'database/kamera.sqlite3',checked['token'],'ADOPT RC10 BOOTSTRAP','synthetic consistent backup')
m.startup_database();sys.settrace(None)
client=TestClient(m.app,base_url='http://127.0.0.1')
login=client.post('/auth/login',json={'password':'synthetic-rc11-test-password'},headers={'Origin':'http://127.0.0.1'})
assert login.status_code==200,login.text
status=client.get('/api/settings/storage-health').json();page=client.get('/').text
m.shutdown_worker()
mutation=False
if status['ready'] and m.DATABASE_INITIALIZATION_ERROR is None:
    with ro.mutate(base/'workspace',databases=[base/'database/kamera.sqlite3']):pass
    mutation=True
parent=ro._control_location(base/'workspace');state=ro._read(parent/'state.json')
result={'ready':status['ready'],'health':status,'onboarding':'id="create"' in page and 'id="name"' in page,
        'error':m.DATABASE_INITIALIZATION_ERROR,'reservation_id':state.get('storage_initialization',{}).get('reservation_id'),
        'mutation_succeeded':mutation,'bindings':state['bindings'],'active_operations':[p.name for p in parent.glob('operation-*.json')],
        'archive_unchanged':picture.read_bytes()==original,'workspace_lock_created':(base/'workspace/Metadata Correction/.trash-deletions/.lock').exists() and not state.get('control_migration')}
(output/'result.json').write_text(json.dumps(result,indent=2))
