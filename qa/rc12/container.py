"""Real UID568 Linux container, one appdata bind, RO archives, no ACL bypass.
POSIX ACL inheritance tests kernel access. Native TrueNAS ACLs remain NOT_RUN.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

image=os.environ['IMAGE'];source=Path(__file__).resolve().parents[2]
root=Path(os.environ['RUNNER_TEMP'])/'rc12-container';root.mkdir()
logs=Path(os.environ['RUNNER_TEMP'])/'rc12-container-logs';logs.mkdir()
report={'source':os.environ['GITHUB_SHA'],'image':image,'cases':[],
 'native_truenas_acl':{'status':'NOT_RUN','reason':'Actual Linux POSIX ACL inheritance is not native TrueNAS/OpenZFS/NFSv4'}}

def command(*args,check=True):
    r=subprocess.run(args,capture_output=True,text=True,timeout=180)
    if check:assert r.returncode==0,r.stdout+r.stderr
    return r.stdout if check else r

def docker(*args,**kwargs):return command('docker',*args,**kwargs)

def save(): (Path(os.environ['RUNNER_TEMP'])/'rc12-evidence.json').write_text(json.dumps(report,indent=2))

def client(port):
    host='http://127.0.0.1:'+str(port);jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for i in range(120):
        try:
            with browser.open(host+'/login',timeout=3) as r:assert r.status==200
            break
        except (OSError,AssertionError):
            if i==119:raise
            time.sleep(.25)
    def api(path,payload=None,expect=200,raw=False):
        headers={'Origin':host}
        if payload is not None:
            headers['Content-Type']='application/json'
            if path!='/auth/login':headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        req=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:r=browser.open(req,timeout=45)
        except urllib.error.HTTPError as error:r=error
        with r:
            body=r.read().decode();assert r.status==expect,(path,r.status,body)
            return body if raw else json.loads(body)
    api('/auth/login',{'password':'isolated-rc12-container-password'})
    return api


def case(label,boundary='',foreign_owner=False,denied=False,helper=False,technical=False):
    base=root/label;base.mkdir()
    for name in ('appdata','workspace','archive','archive-second','evidence'):(base/name).mkdir()
    (base/'archive/original.JPG').write_bytes(b'RC12 read-only photo')
    before=hashlib.sha256((base/'archive/original.JPG').read_bytes()).hexdigest()
    (base/'workspace/.DS_Store').write_bytes(b'Finder metadata')
    if technical:
        for name in ('SD Card Backups','Library Workspaces','Metadata Correction','Trash'):(base/'workspace'/name).mkdir()
    command('sudo','chown','-R','568:568',str(base))
    if foreign_owner or denied:
        command('sudo','chown','3000:0',str(base/'appdata'))
        command('sudo','chmod','0700',str(base/'appdata'))
        if not denied:
            command('sudo','setfacl','-m','u:568:rwx,u:3001:rwx,g::---,m::rwx,o::---,d:u::rwx,d:u:568:rwx,d:u:3001:rwx,d:g::---,d:m::rwx,d:o::---',str(base/'appdata'))
    name='bibliothekar-rc12-'+label
    env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_POOL_PROBE':'/workspace',
         'KAMERA_SOURCE_HELPER_ENABLED':'true' if helper else 'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568',
         'BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-rc12-container-password','PYTHONPATH':'/qa-code:/opt/kamera'}
    if boundary:env['RC11_QA_BOUNDARY']=boundary
    opts=['--read-only','--tmpfs','/tmp:size=64m,mode=1777']
    if helper:opts+=['--privileged']
    for key,value in env.items():opts+=['-e',key+'='+value]
    for src,dst in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('archive-second','/archive-second:ro'),('evidence','/qa-evidence')]:
        opts+=['-v',str(base/src)+':'+dst]
    opts+=['-v',str(source/'qa/rc11')+':/qa-code:ro']
    result={'label':label,'boundary':boundary,'foreign_owner':foreign_owner,'helper':helper}
    try:
        docker('create','--name',name,*opts,'-p','127.0.0.1:18318:8080',image);docker('start',name)
        if boundary:
            for i in range(240):
                if (base/'evidence/checkpoint.json').exists() and docker('inspect','-f','{{.State.Running}}',name).strip()=='false':break
                time.sleep(.25)
            assert (base/'evidence/checkpoint.json').exists(),docker('logs',name)
            result['crash']=json.loads((base/'evidence/checkpoint.json').read_text());assert result['crash']['uid']==568
            docker('start',name)
        api=client(18318)
        if denied:
            h=api('/api/settings/storage-health');assert not h['ready'] and not h['can_initialize'],h
            assert not (base/'appdata/database/kamera.sqlite3').exists()
            assert not (base/'workspace/Trash').exists()
            assert 'Storage recovery' in api('/',raw=True)
            # Explicit test administrator restores actual access, never application chmod/chown.
            command('sudo','setfacl','-m','u:568:rwx,d:u::rwx,d:u:568:rwx,d:g::---,d:m::rwx,d:o::---',str(base/'appdata'))
            api('/api/settings/storage-recheck',{})
        health=api('/api/settings/storage-health');assert health['ready'] and health['state']=='READY',health
        assert health['security_model']=='host_managed'
        assert 'id="create"' in api('/',raw=True) and api('/api/libraries')['libraries']==[]
        if foreign_owner:
            assert (base/'appdata').stat().st_uid==3000
            result['host_acl']=command('sudo','getfacl','-pn',str(base/'appdata'))
        statecode="import json,hashlib;from pathlib import Path;p=Path('/appdata/database/.bibliothekar-root-control')/hashlib.sha256(b'/workspace').hexdigest();print(json.dumps({'state':json.loads((p/'state.json').read_text()),'operations':[x.name for x in p.glob('operation-*.json')]}))"
        snapshot=json.loads(docker('exec','--user','568:568',name,'python','-c',statecode));nonce=snapshot['state']['storage_initialization']['reservation_id']
        assert snapshot['state']['format']==3 and not snapshot['operations']
        assert not (base/'workspace/Metadata Correction/.trash-deletions/.lock').exists()
        first=api('/api/libraries',{'display_name':'RC12 First','work_root':'','archive_root':'/main-library'},expect=201)
        assert first['library']['is_registered']
        docker('restart',name);api=client(18318)
        assert api('/api/settings/storage-health')['ready'] and len(api('/api/libraries')['libraries'])==1
        # Actual storage fault -> authenticated repair UI -> both recovery paths.
        trash=base/'workspace/Trash';trash.rename(base/'workspace/trash-original')
        h=api('/api/settings/storage-health');assert h['state']=='DEGRADED' and not h['ready'],h
        page=api('/',raw=True);assert 'storage-replace' in page and 'Expected folder identity' in page
        (base/'workspace/trash-original').rename(trash);api('/api/settings/storage-recheck',{})
        assert api('/api/settings/storage-health')['ready']
        trash.rename(base/'workspace/trash-lost')
        api('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'WRONG'},expect=409)
        replaced=api('/api/settings/storage-replace',{'key':'trash_directory_name','confirmation':'I ACCEPT MISSING FILES'})
        assert replaced['loss_recorded'] and not replaced['restart_required'],replaced
        api('/api/libraries',{'display_name':'After repair','work_root':'','archive_root':'/archive-second'},expect=201)
        if helper:
            assert docker('exec',name,'python','-c',"import urllib.request,json;r=json.load(urllib.request.urlopen('http://127.0.0.1:8090/healthz'));assert r['mount_root']=='/appdata/removable-sources'").strip()==''
            actual=docker('exec',name,'findmnt','-n','-o','FSTYPE,TARGET,PROPAGATION','--target','/appdata/removable-sources')
            assert 'tmpfs' in actual and 'private' in actual,actual
            write=docker('exec','--user','568:568',name,'touch','/appdata/removable-sources/web-must-not-write',check=False)
            assert write.returncode!=0,write
            result['kernel_removable_mount']=actual.strip()
        # Another appdata instance with same workspace must refuse ownership.
        other=base/'other-appdata';other.mkdir();command('sudo','chown','568:568',str(other))
        conflict=docker('run','--rm','--user','568:568','-e','KAMERA_APPDATA=/appdata','-e','KAMERA_WORKSPACE=/workspace',
                        '-v',str(other)+':/appdata','-v',str(base/'workspace')+':/workspace','--entrypoint','python',image,
                        '-c',"from app.appdata import prepare;prepare();from app.managed_storage_health import inspect_storage;r=inspect_storage('/workspace',database='/appdata/database/kamera.sqlite3');assert not r['ready'] and any(i['code']=='workspace_claim_conflict' for i in r['issues']),r")
        assert not conflict.strip()
        docker('restart',name);api=client(18318);assert api('/api/settings/storage-health')['ready']
        assert hashlib.sha256((base/'archive/original.JPG').read_bytes()).hexdigest()==before
        result.update(status='PASS',first_library_created=True,following_mutation=True,restarted=True,repair_restored=True,repair_replaced=True,archives_unchanged=True,reservation_id=nonce)
        report['cases'].append(result);save();print(json.dumps(result),flush=True)
    finally:
        r=docker('logs',name,check=False);(logs/(label+'.log')).write_text(r.stdout+r.stderr)
        docker('rm','-f',name,check=False)

try:
    case('fresh')
    case('uid3000-acl',foreign_owner=True)
    case('technical-dirs',technical=True)
    case('access-denied',denied=True)
    case('removable-runtime',foreign_owner=True,helper=True)
    for boundary in ['instance-intent','claim-linked','claim-unlinked','instance-ready','reservation','folders','config','database','registry','recovery','private-lock','prepared','completion-receipt','completed','operation-archive','finished-receipt','operation-unlink','uncommitted-state']:
        case('crash-'+boundary,boundary=boundary)
finally:save()
