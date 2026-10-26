"""RC10 live-container exercise on isolated writable volumes (never an NAS)."""
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

image=os.environ['IMAGE']
root=Path(os.environ['RUNNER_TEMP'])/'bibliothekar-rc10-acceptance'
for name in ('config','database','logs','workspace','archive'):
    (root/name).mkdir(parents=True,exist_ok=True)
(root/'workspace'/'.DS_Store').write_bytes(b'Synthetic macOS Finder metadata')
original=b'Preexisting independent archive: never adopt, move or overwrite'
(root/'archive'/'original.JPG').write_bytes(original)
subprocess.run(['sudo','chown','-R','568:568',str(root)],check=True)
container='bibliothekar-rc10-qa'

def docker(*argv):
    command=subprocess.run(['docker',*argv],text=True,capture_output=True,timeout=120)
    assert command.returncode==0,command.stdout+command.stderr
    return command.stdout

args=['create','--name',container,'--read-only','--tmpfs','/tmp:size=64m,mode=1777',
      '-p','127.0.0.1:18317:8080']
for k,v in {'KAMERA_SOURCE_HELPER_ENABLED':'false',
            'BIBLIOTHEKAR_ADMIN_PASSWORD':'synthetic-rc-build-smoke-password',
            'KAMERA_CONFIG':'/config/settings.json','KAMERA_DATABASE_DIR':'/database',
            'KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3',
            'KAMERA_LOG_DIR':'/logs','KAMERA_WORKSPACE':'/workspace',
            'KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library'}.items():
    args+=['-e',k+'='+v]
for name,dest in [('config','/config'),('database','/database'),('logs','/logs'),
                  ('workspace','/workspace'),('archive','/main-library:ro')]:
    args+=['-v',str(root/name)+':'+dest]
docker(*args,image)

def connect():
    base='http://127.0.0.1:18317'
    jar=http.cookiejar.CookieJar()
    browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for i in range(100):
        try:
            with browser.open(base+'/healthz',timeout=3) as result:
                assert result.status==200
            break
        except (OSError,AssertionError):
            if i==99:raise
            time.sleep(1)
    def api(path,payload=None,expect=200,text=False,csrf=True):
        headers={'Origin':base}
        if payload is not None:
            headers['Content-Type']='application/json'
            if csrf:
                headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        req=urllib.request.Request(base+path,
                    data=None if payload is None else json.dumps(payload).encode(),
                    headers=headers)
        try:response=browser.open(req,timeout=45)
        except urllib.error.HTTPError as e:response=e
        with response:
            body=response.read().decode()
            assert response.status==expect,(path,response.status,body)
            return body if text else json.loads(body)
    api('/auth/login',{'password':'synthetic-rc-build-smoke-password'},csrf=False)
    return api

report={}
try:
    docker('start',container)
    api=connect()
    health=api('/api/settings/storage-health')
    assert health['ready'] and not health['issues'],health
    assert api('/api/libraries')['libraries']==[]
    assert 'Set up your first library' in api('/',text=True)
    assert (root/'workspace'/'.DS_Store').read_bytes()==b'Synthetic macOS Finder metadata'
    assert (root/'archive'/'original.JPG').read_bytes()==original
    report['new_install_dsstore_archive']='PASS'
    checked=api('/api/libraries/check',{'display_name':'RC10 Camera Library',
               'work_root':'','archive_root':'/main-library',
               'default_library_id':'rc10-main'})
    assert checked['valid'],checked
    created=api('/api/libraries',{'display_name':'RC10 Camera Library',
               'work_root':'','archive_root':'/main-library'},expect=201)
    docker('restart',container)
    api=connect()
    health=api('/api/settings/storage-health')
    assert health['ready'] and len(api('/api/libraries')['libraries'])==1,health
    report['onboarding_and_restart']='PASS'
    trash=root/'workspace'/'Trash'
    assert trash.is_dir()
    docker('stop',container)
    shutil.rmtree(trash)
    docker('start',container)
    api=connect()
    damaged=api('/api/settings/storage-health')
    assert not damaged['ready'] and not damaged['can_initialize'],damaged
    assert any(row['key']=='trash_directory_name' and row['status']=='missing'
               for row in damaged['folders']),damaged
    page=api('/',text=True)
    assert 'id="storage-recovery-open"' in page and 'data-key="trash_directory_name"' in page,page[:4000]
    assert api('/api/settings/storage-replace',{'key':'trash_directory_name',
                    'confirmation':'wrong'},expect=409)
    fixed=api('/api/settings/storage-replace',{'key':'trash_directory_name',
               'confirmation':'I ACCEPT MISSING FILES'})
    assert fixed['replaced'] and fixed['loss_recorded'],fixed
    docker('restart',container)
    api=connect()
    assert api('/api/settings/storage-health')['ready']
    assert len(api('/api/libraries')['libraries'])==1
    assert (root/'archive'/'original.JPG').read_bytes()==original
    report['confirmed_trash_replacement_restart']='PASS'
    import sqlite3
    from pathlib import Path
    registry=root/'database'/'global.sqlite3'
    with sqlite3.connect(registry) as db:
        work=Path(db.execute('SELECT work_root FROM libraries WHERE is_registered=1 LIMIT 1').fetchone()[0])
    # Map container /workspace back into our isolated host scratch directory.
    if work.is_relative_to(Path('/workspace')):
        host_work=root/'workspace'/work.relative_to('/workspace')
        assert host_work.is_dir()
        docker('stop',container)
        shutil.rmtree(host_work)
        docker('start',container)
        api=connect()
        affected=api('/api/settings/storage-health')
        matching=[v for v in affected['folders'] if v['key'].startswith('library_work_root:')]
        assert len(matching)==1 and matching[0]['status']=='missing',affected
        restored=api('/api/settings/storage-replace',{'key':matching[0]['key'],
                      'confirmation':'I ACCEPT MISSING FILES'})
        assert restored['replaced'],restored
        docker('restart',container)
        api=connect()
        assert api('/api/settings/storage-health')['ready']
        assert len(api('/api/libraries')['libraries'])==1
        report['registered_library_work_root_replacement']='PASS'
    else:
        raise AssertionError('First library work area escaped the managed workspace')
    (root/'rc10-evidence.json').write_text(json.dumps(report,indent=2,sort_keys=True))
    print(json.dumps(report,indent=2,sort_keys=True))
finally:
    print(docker('logs',container)[-12000:])
    docker('rm','-f',container)
