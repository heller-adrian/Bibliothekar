"""Real pre.1 refusal -> blocked restart -> candidate recovery, synthetic data only.

A controlled ExifTool proxy returns the reported DNG refusal on a staging copy.
The input is a generated JPEG named .dng, NOT a real DNG 1.7 original. Read-side
ExifTool requests use the actual installed binary. No production mounts exist.
"""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(os.environ['RUNNER_TEMP'])/'pre2-general';ROOT.mkdir()
SOURCE=Path(__file__).resolve().parents[2]
IMAGE=os.environ['IMAGE'];BASE=os.environ['PRE1_IMAGE']
PASSWORD='isolated-pre2-metadata-test-password'
REPORT={'source':os.environ['GITHUB_SHA'],'base':BASE,'native_truenas':'NOT_RUN','real_DNG_1_7':'NOT_RUN','cases':[]}


def run(*args,check=True,timeout=180):
    r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if check:assert r.returncode==0,r.stdout+r.stderr
    return r.stdout if check else r


def docker(*args,**kw):return run('docker',*args,**kw)


API=r'''
import http.cookiejar,json,time,urllib.request,urllib.error
host='http://127.0.0.1:8080';jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
for n in range(240):
 try:
  with browser.open(host+'/login',timeout=2) as r:assert r.status==200
  break
 except OSError:
  if n==239:raise
  time.sleep(.25)
def api(path,payload=None,expect=200):
 headers={'Origin':host}
 if payload is not None:
  headers['Content-Type']='application/json'
  if path!='/auth/login':headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
 request=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
 try:response=browser.open(request,timeout=30)
 except urllib.error.HTTPError as e:response=e
 with response:
  text=response.read().decode();assert response.status==expect,(path,response.status,text);return json.loads(text)
api('/auth/login',{'password':'isolated-pre2-metadata-test-password'})
'''
SNAPSHOT=r'''
from pathlib import Path
import sqlite3,json,hashlib
from contextlib import closing
from app import metadata_correction as m,root_operations as ro
from app.storage_config import storage_paths
from app.managed_directory_names import directory_name
ws=Path('/workspace');metadata=storage_paths(ws)['metadata_root'];general=metadata/directory_name(metadata,'metadata_general');source=general/'_DSC7386.dng'
with closing(sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True)) as c:
 c.row_factory=sqlite3.Row;tasks=[dict(r) for r in c.execute('SELECT * FROM metadata_corrections ORDER BY created_at,id')]
parent=ro._control_location(ws)
ops=[json.loads(p.read_text()) for p in parent.glob('operation-*.json') if json.loads(p.read_text()).get('kind')=='metadata']
outcomes=[json.loads(p.read_text()) for p in parent.glob('metadata-outcome-*.json')]
print(json.dumps({'tasks':tasks,'ops':ops,'outcomes':outcomes,'source_sha':hashlib.sha256(source.read_bytes()).hexdigest(),
 'source_inode':source.stat().st_ino,'archive':hashlib.sha256(Path('/main-library/untouched.JPG').read_bytes()).hexdigest(),
 'temporaries':[p.name for p in general.iterdir() if '.metadata-' in p.name],
 'journals':[p.name for p in (m.storage_paths(ws)['metadata_root']/'.swap-journals').glob('*.json')]}))
'''
TOOLS=r'''#!/usr/local/bin/python
import os,sys
from pathlib import Path
if '-overwrite_original_in_place' in sys.argv and '.metadata-' in sys.argv[-1] and '_DSC7386.dng' in sys.argv[-1]:
 Path(sys.argv[-1]).write_bytes(Path(sys.argv[-1]).read_bytes()+b'partial staged output')
 sys.stderr.write('Error: [minor] DNG Version 1.7.0.0 not yet tested - '+sys.argv[-1]+'\n')
 sys.exit(1)
os.execv('/usr/bin/exiftool',['/usr/bin/exiftool']+sys.argv[1:])
'''
HOOK=r'''
import os,sys
if os.getuid()==568 and 'uvicorn' in sys.orig_argv and os.environ.get('PRE2_KILL_AFTER_OUTCOME')=='1':
 from app import root_operations as ro
 import signal
 original=ro._write
 def write(path,data):
  original(path,data)
  if path.name.startswith('metadata-outcome-'):os.kill(os.getpid(),signal.SIGKILL)
 ro._write=write
'''


def case(label,*,foreign=False,crash=False):
    root=ROOT/label;root.mkdir()
    for folder in ('appdata','workspace','archive','tools','hooks'):(root/folder).mkdir()
    (root/'tools/exiftool').write_text(TOOLS);(root/'tools/exiftool').chmod(0o755)
    (root/'hooks/sitecustomize.py').write_text(HOOK)
    name='bibliothekar-pre2-'+os.environ['GITHUB_RUN_ID']+'-'+label
    mounts=[]
    for host,target in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('tools','/qa-tools:ro'),('hooks','/qa-hooks:ro')]:mounts+=['-v',str(root/host)+':'+target]
    env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library',
         'KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':PASSWORD,
         'PATH':'/qa-tools:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin'}
    envargs=[value for key,val in env.items() for value in ('-e',key+'='+val)]
    docker('run','--rm','--network','none','-v',str(root)+':/fixture','--entrypoint','python',IMAGE,'-c',
           "from pathlib import Path;import os;r=Path('/fixture');os.chown(r,568,568);[os.chown(r/n,568,568) for n in ('appdata','workspace','archive')];(r/'archive/untouched.JPG').write_bytes(b'independent read-only archive');os.chmod(r/'archive/untouched.JPG',0o644)")
    def create(image,kill=False):
        extra=['-e','PYTHONPATH=/qa-hooks:/opt/kamera','-e','PRE2_KILL_AFTER_OUTCOME=1'] if kill else []
        docker('create','--name',name,'--network','none','--read-only','--tmpfs','/tmp:size=64m,mode=1777',*envargs,*extra,*mounts,image);docker('start',name)
    def api(code,check=True):
        result=docker('exec',name,'python','-c',API+'\n'+code,check=check,timeout=100)
        return json.loads(result) if check else result
    def snap(stopped=False):
        if stopped:return json.loads(docker('run','--rm','--network','none','--user','568:568',*envargs,*mounts,'--entrypoint','python',IMAGE,'-c',SNAPSHOT))
        return json.loads(docker('exec','--user','568:568',name,'python','-c',SNAPSHOT))
    summary={'label':label,'native_write_result':'SIMULATED_DNG_REFUSAL','real_DNG_1_7':'NOT_RUN'}
    try:
        create(BASE)
        api("print(json.dumps(api('/api/libraries',{'display_name':'Main','work_root':'','archive_root':'/main-library'},201)))")
        docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;from PIL import Image;from app.metadata_correction import metadata_area_paths;p=metadata_area_paths(area='general',workspace_root=Path('/workspace'),library_id='main')['root']/'_DSC7386.dng';Image.new('RGB',(16,16),'blue').save(p,format='JPEG')")
        baseline=snap();payload="{'area':'general','relative_path':'_DSC7386.dng','proposed_datetime':'2024-06-23T10:20:21'}"
        api("print(json.dumps(api('/api/metadata-correction/correct',"+payload+",409)))")
        failed=snap();assert len(failed['ops'])==1 and failed['tasks'][0]['status']=='blocked'
        assert failed['source_sha']==baseline['source_sha'] and failed['temporaries']==failed['journals']==[]
        docker('restart',name)
        health=api("print(json.dumps(api('/api/settings/storage-health')))")
        assert not health['ready'] and 'unresolved_reservation' in json.dumps(health),health
        assert snap()['ops']==failed['ops']
        summary['pre1_block_reproduced']=True
        if foreign:docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;from app.metadata_correction import metadata_area_paths;p=metadata_area_paths(area='general',workspace_root=Path('/workspace'),library_id='main')['root']/'_DSC7386.dng';p.write_bytes(b'foreign user content')")
        docker('stop',name);docker('rm',name)
        create(IMAGE)
        health=api("print(json.dumps(api('/api/settings/storage-health')))")
        current=snap()
        if foreign:
            assert not health['ready'] and 'metadata_outcome_' in json.dumps(health),health
            assert current['ops']==failed['ops'] and not current['outcomes']
            assert current['tasks']==failed['tasks'] and current['source_sha']!=failed['source_sha']
            summary['foreign_bytes_preserved_and_blocked']=True
        else:
            assert health['ready'],health
            assert not current['ops'] and current['tasks']==failed['tasks']
            assert current['source_sha']==baseline['source_sha'] and current['source_inode']==baseline['source_inode']
            assert current['outcomes'][0]['reservation']==failed['ops'][0]
            summary['historic_same_reservation_preserved_in_receipt']=True
            summary['historic_error_row_unchanged']=True
            api("print(json.dumps(api('/api/libraries')))")
            if crash:
                docker('stop',name);docker('rm',name);create(IMAGE,kill=True)
                api("print(json.dumps(api('/api/settings/storage-health')))")
                result=api("print(json.dumps(api('/api/metadata-correction/correct',"+payload+",409)))",check=False)
                assert result.returncode!=0,'Expected SIGKILL at durable outcome boundary'
                docker('wait',name)
                killed=snap(stopped=True);assert killed['ops'] and len(killed['outcomes'])==2
                nonce=killed['ops'][0]['reservation_id']
                docker('rm',name);create(IMAGE)
                health=api("print(json.dumps(api('/api/settings/storage-health')))");assert health['ready'],health
                current=snap();assert not current['ops']
                assert any(o['reservation']['reservation_id']==nonce for o in current['outcomes'])
                summary['real_web_sigkill_recovered_same_nonce']=True
            else:
                api("print(json.dumps(api('/api/metadata-correction/correct',"+payload+",409)))")
                health=api("print(json.dumps(api('/api/settings/storage-health')))");assert health['ready'],health
                current=snap();assert not current['ops'] and len(current['tasks'])==2
                assert all(t['status']=='blocked' for t in current['tasks']) and current['tasks'][0]==failed['tasks'][0]
                docker('restart',name);assert api("print(json.dumps(api('/api/settings/storage-health')))")['ready']
                summary['future_refusal_and_restart_ready']=True
        assert current['archive']==baseline['archive']
        summary.update(status='PASS',archive_unchanged=True,authenticated_http=True)
        REPORT['cases'].append(summary)
    finally:
        log=docker('logs',name,check=False);(ROOT/(label+'.log')).write_text(log.stdout+log.stderr)
        (Path(os.environ['RUNNER_TEMP'])/'pre2-evidence.json').write_text(json.dumps(REPORT,indent=2))
        docker('rm','-f',name,check=False)


for label,options in [('historical',{}),('foreign',{'foreign':True}),('crash',{'crash':True})]:case(label,**options)
REPORT['status']='PASS';(Path(os.environ['RUNNER_TEMP'])/'pre2-evidence.json').write_text(json.dumps(REPORT,indent=2))
print(json.dumps(REPORT,indent=2))
