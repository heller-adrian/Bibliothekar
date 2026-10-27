"""Actual Linux supervisor/uid568/HTTP/RO-mount acceptance. No image publication.
Only newly created RUNNER_TEMP directories are mounted. No NAS is contacted.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

image=os.environ['IMAGE'];runroot=Path(os.environ['RUNNER_TEMP'])/'rc11-container-acceptance';runroot.mkdir()
code=Path(__file__).resolve().parent
# Tests/fixtures is mounted as a separate QA file; not included in the image.
shutil.copyfile(code.parents[1]/'tests/fixtures/rc11/truenas-rc10.json',runroot/'truenas-rc10.json')
logdir=Path(os.environ['RUNNER_TEMP'])/'rc11-container-logs';logdir.mkdir(exist_ok=True)
report={'source':os.environ.get('GITHUB_SHA'),'image':image,'cases':[],
        'native_truenas_acl':{'status':'NOT_RUN','reason':'Ubuntu Docker bind mounts do not provide a TrueNAS native NFSv4 ACL dataset; no synthetic PASS'}}

def docker(*args,check=True):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=180)
    if check:assert result.returncode==0,result.stdout+result.stderr
    return result.stdout if check else result

def hashes(path):return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}

def api_client():
    host='http://127.0.0.1:18317';jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for attempt in range(90):
        try:
            with browser.open(host+'/login',timeout=3) as response:assert response.status==200
            break
        except (OSError,AssertionError):
            if attempt==89:raise
            time.sleep(.25)
    def api(path,payload=None,expect=200,raw=False):
        headers={'Origin':host}
        if payload is not None:
            headers['Content-Type']='application/json'
            if path!='/auth/login':headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        req=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:response=browser.open(req,timeout=45)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read().decode();assert response.status==expect,(path,response.status,body)
            return body if raw else json.loads(body)
    api('/auth/login',{'password':'synthetic-rc11-container-password'})
    return api


def case(label,boundary='',legacy=False,legacy_completed=False,unsafe_private=False):
    base=runroot/label;base.mkdir()
    for name in ('config','database','logs','workspace','archive','archive-secondary','evidence','sources'):(base/name).mkdir()
    (base/'workspace/.DS_Store').write_bytes(b'Finder synthetic metadata')
    for name in ('archive','archive-secondary'):
        for n in range(3):(base/name/f'original-{n}.JPG').write_bytes(b'synthetic photo '+bytes([n]))
    subprocess.run(['sudo','chown','-R','568:568',str(base)],check=True)
    subprocess.run(['sudo','chmod','0770',str(base/'workspace')],check=True)
    before={name:hashes(base/name) for name in ('archive','archive-secondary')}
    container='bibliothekar-rc11-'+label
    env={'KAMERA_SOURCE_HELPER_ENABLED':'true','BIBLIOTHEKAR_ADMIN_PASSWORD':'synthetic-rc11-container-password',
         'KAMERA_CONFIG':'/config/settings.json','KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/bibliothekar-global.sqlite3',
         'KAMERA_LOG_DIR':'/logs','KAMERA_WORKSPACE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_POOL_PROBE':'/workspace',
         'KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','RC11_QA_SYNTHETIC':'true','PYTHONPATH':'/qa-code:/opt/kamera'}
    if boundary:env['RC11_QA_BOUNDARY']=boundary
    if legacy_completed:env['RC11_QA_LEGACY_COMPLETED']='true'
    opts=['--read-only','--tmpfs','/tmp:size=64m,mode=1777']
    for key,value in env.items():opts+=['-e',key+'='+value]
    mounts=[('workspace','/workspace'),('config','/config'),('database','/database'),('logs','/logs'),('archive','/main-library:ro'),('archive-secondary','/archive-secondary:ro'),('evidence','/qa-evidence'),('sources','/sources/nas:ro')]
    for name,dest in mounts:opts+=['-v',str(base/name)+':'+dest]
    opts+=['-v',str(code)+':/qa-code:ro','-v',str(runroot/'truenas-rc10.json')+':/qa-rc10.json:ro']
    result={'label':label,'boundary':boundary,'legacy':legacy}
    try:
        if legacy:
            docker('run','--rm',*opts,'--entrypoint','python',image,'/qa-code/seed_rc10.py')
            # A read-only inspection followed by an explicit, exact evidence decision.
            inspected=json.loads(docker('run','--rm','--user','568:568',*opts,'--entrypoint','python',image,'-m','app.storage_admin','inspect'))
            assert inspected['operation']['reservation_id']=='9c2ab846562a4fb6aee39e2d08edeee6'
            adopted=docker('run','--rm','--user','568:568',*opts,'--entrypoint','python',image,'-m','app.storage_admin','adopt','--token',inspected['token'],'--confirmation','ADOPT RC10 BOOTSTRAP','--backup-reference','isolated synthetic fixture backup',check=boundary!='adoption-receipt')
            if boundary=='adoption-receipt':
                assert adopted.returncode!=0 and (base/'evidence/checkpoint.json').exists(),adopted.stdout+adopted.stderr
                result['crash']=json.loads((base/'evidence/checkpoint.json').read_text())
        if unsafe_private:subprocess.run(['sudo','chmod','0777',str(base/'database')],check=True)
        docker('create','--name',container,*opts,'-p','127.0.0.1:18317:8080',image)
        docker('start',container)
        if boundary and boundary!='adoption-receipt':
            until=time.monotonic()+60
            while time.monotonic()<until:
                running=docker('inspect','-f','{{.State.Running}}',container).strip()
                if running=='false':break
                time.sleep(.25)
            assert (base/'evidence/checkpoint.json').exists(),docker('logs',container)
            checkpoint=json.loads((base/'evidence/checkpoint.json').read_text())
            assert checkpoint['uid']==568 and checkpoint['gid']==568,checkpoint
            result['crash']=checkpoint
            assert docker('inspect','-f','{{.State.Running}}',container).strip()=='false'
            docker('start',container)
        api=api_client()
        health=api('/api/settings/storage-health')
        if unsafe_private:
            assert not health['ready'] and not health['can_initialize'],health
            assert any(i['code']=='private_acl_untrusted_write' and i['path']=='/database' for i in health['issues']),health
            assert not list((base/'workspace').glob('Trash'))
            assert not list((base/'database').glob('*.sqlite3'))
            result['unsafe_private_blocked']=True
            docker('stop',container)
            # Explicit synthetic administrator action, never application ACL repair.
            subprocess.run(['sudo','chmod','0700',str(base/'database')],check=True)
            docker('start',container);api=api_client();health=api('/api/settings/storage-health')
        assert health['ready'] and not health['issues'],health
        assert api('/api/libraries')['libraries']==[]
        page=api('/',raw=True);assert 'id="create"' in page and 'id="name"' in page
        own=base/'database/.bibliothekar-root-control'/hashlib.sha256(b'/workspace').hexdigest()
        state=json.loads((own/'state.json').read_text());nonce=state['storage_initialization']['reservation_id']
        assert state['format']==2 and state['storage_initialization']['phase']=='completed'
        assert (own/'trash-recovery.lock').is_file()
        assert not list(own.glob('operation-*.json'))
        assert (own/('bootstrap-completed-'+nonce+'.json')).exists()
        if legacy:
            original=json.loads((base/'evidence/rc10-original.json').read_text())
            assert state['bindings']==original['bindings'] and nonce==original['reservation_id']
            adopted=[json.loads(p.read_text()) for p in own.glob('rc11-adoption-*.json')]
            assert any(base64.b64decode(r['material']['state']).decode()==original['state'] for r in adopted)
            lock=base/'workspace/Metadata Correction/.trash-deletions/.lock'
            assert lock.stat().st_gid==0 and lock.stat().st_mode & 0o777==0o770 and lock.read_bytes()==b''
        else:assert not (base/'workspace/Metadata Correction/.trash-deletions/.lock').exists()
        created=api('/api/libraries',{'display_name':'RC11 Camera','work_root':'','archive_root':'/main-library'},expect=201)
        assert created['library']['is_registered']
        # Second actual library creation proves a following F14 root mutation.
        second=api('/api/libraries',{'display_name':'RC11 Second','work_root':'','archive_root':'/archive-secondary'},expect=201)
        assert second['library']['library_id']!=created['library']['library_id']
        docker('restart',container);api=api_client()
        assert api('/api/settings/storage-health')['ready'] and len(api('/api/libraries')['libraries'])==2
        assert 'id="create"' not in api('/',raw=True)
        assert before=={name:hashes(base/name) for name in before}
        result.update(status='PASS',first_library_created=True,following_mutation=True,restarted=True,reservation_id=nonce,archives_unchanged=True)
        report['cases'].append(result)
        (Path(os.environ['RUNNER_TEMP'])/'rc11-evidence.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(result),flush=True)
    finally:
        logs=docker('logs',container,check=False)
        (logdir/(label+'.log')).write_text(logs.stdout+logs.stderr)
        docker('rm','-f',container,check=False)

try:
    case('new')
    case('unsafe-private',unsafe_private=True)
    for boundary in ['reservation','folders','config','database','registry','recovery','private-lock','prepared','completion-receipt','completed','operation-archive','finished-receipt','operation-unlink','uncommitted-state']:
        case('crash-'+boundary,boundary=boundary)
    case('rc10-migration',legacy=True)
    case('rc10-adoption-crash',legacy=True,boundary='adoption-receipt')
    case('rc10-completed-gap',legacy=True,legacy_completed=True,boundary='control-format')
finally:
    (Path(os.environ['RUNNER_TEMP'])/'rc11-evidence.json').write_text(json.dumps(report,indent=2))
