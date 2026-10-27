"""One fully isolated RC12 process; real auth/CSRF, no production paths."""
import json
import os
from pathlib import Path
import sys
base=Path(sys.argv[1]).absolute();case=sys.argv[2]
a=base/'appdata';w=base/'workspace';archive=base/'archive';second=base/'archive-second'
for path in (a,w,archive,second):path.mkdir(exist_ok=True)
(archive/'photo.JPG').write_bytes(b'RC12 immutable source')
os.environ.update(KAMERA_APPDATA=str(a),KAMERA_WORKSPACE=str(w),KAMERA_ARCHIVE_ROOT=str(archive),
                  KAMERA_POOL_PROBE=str(w),KAMERA_SOURCE_HELPER_ENABLED='false',BIBLIOTHEKAR_ADMIN_PASSWORD='isolated-rc12-test-password')
for key in ('KAMERA_CONFIG','KAMERA_DATABASE_DIR','KAMERA_REGISTRY_DATABASE','KAMERA_LOG_DIR','KAMERA_REMOVABLE_ROOT','KAMERA_REMOVABLE_MOUNT_ROOT'):
    os.environ.pop(key,None)
os.environ.pop('BIBLIOTHEKAR_AUTH_TEST_BYPASS',None)
from app import appdata, main as m, root_operations as ro
from app.managed_storage_health import inspect_storage
from app.storage_config import ENGLISH_STORAGE_DEFAULTS as NAMES
from fastapi.testclient import TestClient
m._mount_read_only=lambda path:True  # Synthetic unit archive; real RO bind mounts are required by Docker QA.
m._start_runtime_workers=lambda:None  # Workers are tested with original supervisor in Docker.
if case=='technical':
    for name in NAMES.values():(w/name).mkdir()
if case=='legacy-lock':
    p=w/'Metadata Correction/.trash-deletions';p.mkdir(parents=True);(p/'.lock').write_bytes(b'')
if case=='foreign':(w/'unknown.JPG').write_bytes(b'preserve')
if case=='symlink':(w/'Trash').symlink_to(archive,target_is_directory=True)
if case=='broad':a.chmod(0o777)
appdata.prepare()
initial=inspect_storage(w,database=m.DATABASE_FILE)
if case in ('legacy-lock','foreign','symlink'):
    assert not initial['can_initialize'],initial
    assert initial['state']=='AMBIGUOUS',initial
    m.startup_database();assert m.DATABASE_INITIALIZATION_ERROR
else:
    assert initial['state']=='FRESH' and initial['can_initialize'],initial
    m.startup_database();assert m.DATABASE_INITIALIZATION_ERROR is None,m.DATABASE_INITIALIZATION_ERROR
client=TestClient(m.app,base_url='http://127.0.0.1')
assert client.get('/api/settings/storage-health').status_code==401
assert client.post('/auth/login',json={'password':'isolated-rc12-test-password'},headers={'Origin':'http://127.0.0.1'}).status_code==200
headers={'Origin':'http://127.0.0.1','X-Bibliothekar-CSRF':client.cookies.get('bibliothekar_csrf')}
def post(path,payload,status=200):
    r=client.post(path,json=payload,headers=headers);assert r.status_code==status,(path,r.status_code,r.text);return r.json()
if case in ('legacy-lock','foreign','symlink'):
    assert 'Storage recovery' in client.get('/').text
    assert client.get('/api/settings/storage-health').json()['state']=='AMBIGUOUS'
else:
    assert 'id="create"' in client.get('/').text
    assert m.api_storage_health()['ready']
    own=ro._control_location(w);state=ro._read(own/'state.json');nonce=state['storage_initialization']['reservation_id']
    assert state['format']==3 and not list(own.glob('operation-*.json'))
    library=post('/api/libraries',{'display_name':'RC12 Test','work_root':'','archive_root':str(archive)},201)['library']
    m.startup_database();assert m.DATABASE_INITIALIZATION_ERROR is None,m.DATABASE_INITIALIZATION_ERROR
    assert ro._read(own/'state.json')['storage_initialization']['reservation_id']==nonce
    if case in ('restore','replace','inode','pending'):
        target=w/'Trash';old=w/'saved-trash';target.rename(old)
        if case=='inode':target.mkdir()
        if case=='pending':ro._write(own/'operation-unknown.json',{'preserve':'unresolved'})
        health=m.api_storage_health();assert health['state']=='DEGRADED' and not health['ready'],health
        page=client.get('/').text
        assert ('class="storage-replace"' in page) == (case!='pending'),page
        assert client.post('/api/settings/storage-replace',json={'key':'trash_directory_name','confirmation':'I ACCEPT MISSING FILES'}).status_code==403
        if case=='restore':
            old.rename(target);post('/api/settings/storage-recheck',{})
            assert ro._read(own/'state.json')['bindings'][str(target)]==[target.stat().st_dev,target.stat().st_ino]
        elif case=='pending':
            post('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'I ACCEPT MISSING FILES'},409)
            assert not target.exists() and (own/'operation-unknown.json').exists()
        else:
            post('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'WRONG'},409)
            result=post('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'I ACCEPT MISSING FILES'})
            assert result['loss_recorded'] and not result['restart_required'],result
            assert ro._read(own/'state.json')['storage_replacements'][-1]['loss_assumed']
        if case!='pending':
            assert m.api_storage_health()['ready'],m.api_storage_health()
            post('/api/libraries',{'display_name':'After recovery','work_root':'','archive_root':str(second)},201)
    if case in ('missing-db','missing-state'):
        path=m.DATABASE_FILE if case=='missing-db' else own/'state.json'
        path.rename(path.with_name(path.name+'.saved'))
        health=m.api_storage_health();assert not health['ready'] and not health['can_initialize'],health
        assert health['issues'][0]['code']=='installation_history_missing',health
        assert client.get('/').status_code==200
        post('/api/settings/storage-recheck',{},409)
        assert not path.exists()
    if case=='second-instance':
        other=base/'second-appdata';other.mkdir()
        os.environ['KAMERA_APPDATA']=str(other)
        health=inspect_storage(w,database=m.DATABASE_FILE)
        assert not health['ready'] and health['issues'][0]['code']=='workspace_claim_conflict',health
        os.environ['KAMERA_APPDATA']=str(a)
    if case=='missing-mount':
        state=ro._read(own/'state.json');state['mounts'][str(w/'Trash')]={'target':'lost-dataset'};ro._write(own/'state.json',state)
        (w/'Trash').rename(w/'old-trash')
        health=m.api_storage_health();assert not health['ready'] and any(i['code']=='mount_identity_changed' for i in health['issues']),health
        post('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'I ACCEPT MISSING FILES'},409)
        assert not (w/'Trash').exists()
assert (archive/'photo.JPG').read_bytes()==b'RC12 immutable source'
m.shutdown_worker()
print(json.dumps({'case':case,'status':'PASS','initial':initial['state']}))
