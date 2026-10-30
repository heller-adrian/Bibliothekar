"""Real fresh General correction/admission, supervisor restart, fences and repairs.

Only newly created RUNNER_TEMP fixtures; real UID568 and RO archive mounts.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(os.environ['RUNNER_TEMP'])/'pre4-live';ROOT.mkdir()
IMAGE=os.environ['IMAGE'];NAME='bibliothekar-pre4-'+os.environ['GITHUB_RUN_ID']
REPORT={'source':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN','real_DNG_1_7':'NOT_RUN','checks':{}}
for name in ('appdata','workspace','archive','second'):(ROOT/name).mkdir()
def run(*args,check=True,timeout=150):
    result=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check:assert result.returncode==0,result.stdout+result.stderr
    return result.stdout if check else result

def docker(*args,**kwargs):return run('docker',*args,**kwargs)
mounts=[]
for host,target in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('second','/second-library:ro')]:mounts+=['-v',str(ROOT/host)+':'+target]
env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-pre4-test-password'}
envargs=[v for k,x in env.items() for v in ('-e',k+'='+x)]
docker('run','--rm','--network','none','-v',str(ROOT)+':/fixture','--entrypoint','python',IMAGE,'-c',"from pathlib import Path;import os;r=Path('/fixture');os.chown(r,568,568);[os.chown(p,568,568) for p in r.iterdir()];(r/'archive/untouched.JPG').write_bytes(b'archive-one');(r/'second/untouched.JPG').write_bytes(b'archive-two');[(os.chmod(p,0o644)) for p in r.rglob('untouched.JPG')]")
# A dedicated internal bridge has no external connectivity; Chromium uses loopback only.
NETWORK=NAME+'-internal'
docker('network','create','--internal',NETWORK)
docker('create','--name',NAME,'--network',NETWORK,'--read-only','--tmpfs','/tmp:size=64m,mode=1777',*envargs,*mounts,IMAGE)
API=r'''
import http.cookiejar,json,time,urllib.request,urllib.error
host='http://127.0.0.1:8080';jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
for attempt in range(240):
 try:
  with browser.open(host+'/login',timeout=2) as r:assert r.status==200
  break
 except OSError:
  if attempt==239:raise
  time.sleep(.25)
def api(path,payload=None,expect=200):
 headers={'Origin':host}
 if payload is not None:
  headers['Content-Type']='application/json'
  if path!='/auth/login':headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
 request=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
 try:response=browser.open(request,timeout=60)
 except urllib.error.HTTPError as e:response=e
 with response:
  text=response.read().decode();assert response.status==expect,(path,response.status,text)
  return json.loads(text) if response.headers.get('content-type','').startswith('application/json') else text
api('/auth/login',{'password':'isolated-pre4-test-password'})
'''
def api(code):return json.loads(docker('exec',NAME,'python','-c',API+'\n'+code,timeout=150))
def script(code):return docker('exec','--user','568:568',NAME,'python','-c',code)
SNAP=r'''
import hashlib,json,sqlite3
from pathlib import Path
from app import root_operations as r
from app.storage_config import storage_paths
ws=Path('/workspace');db=Path('/appdata/database/kamera.sqlite3');registry=db.parent/'bibliothekar-global.sqlite3'
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
files=[dict(row) for row in c.execute('SELECT * FROM files')];tasks=[dict(row) for row in c.execute('SELECT * FROM metadata_corrections')];jobs=[dict(row) for row in c.execute('SELECT * FROM jobs')];assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok';c.close()
central=storage_paths(ws)['backup_root']
for f in files:
 p=central/f['current_relative_path'];f['actual_sha']=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
c=sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True);origin={t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in ('source_media','source_family_members','source_families')};c.close()
parent=r._control_location(ws)
print(json.dumps({'files':files,'tasks':tasks,'jobs':jobs,'origins':origin,'operations':[r._read(p) for p in sorted(parent.glob('operation-*.json'))],'outcomes':[r._read(p) for p in sorted(parent.glob('metadata-outcome-*.json'))],'archives':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('/main-library','/second-library') for p in Path(root).rglob('*') if p.is_file()}}))
'''
def snapshot():return json.loads(script(SNAP))
try:
    docker('start',NAME)
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    assert api("print(json.dumps(api('/healthz')))")['status']=='ok'
    onboarding=api("print(json.dumps(api('/')))");assert 'id="create"' in onboarding
    api("print(json.dumps(api('/api/libraries',{'display_name':'Main','work_root':'','archive_root':'/main-library'},201)))")
    api("print(json.dumps(api('/api/libraries',{'display_name':'Second','work_root':'','archive_root':'/second-library'},201)))")
    script("from pathlib import Path;import json;p=Path('/appdata/config/settings.json');d=json.loads(p.read_text());d.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(d))")
    assert api("print(json.dumps(api('/healthz')))")['status']=='ok'
    before=snapshot()
    script("from pathlib import Path;from PIL import Image;from app.metadata_correction import metadata_area_paths;p=metadata_area_paths(area='general',workspace_root=Path('/workspace'),library_id='main')['root']/'20260719_175150_Fuji-X-E5.JPG';Image.new('RGB',(32,32),'blue').save(p)")
    # Real ExifTool and real HTTP API, no injected jobs/manifests/origin rows.
    task=api("print(json.dumps(api('/api/metadata-correction/correct',{'area':'general','relative_path':'20260719_175150_Fuji-X-E5.JPG','proposed_datetime':'2026-07-19T17:51:50+02:00'})))")['task']
    assert task['status']=='completed'
    job=api("print(json.dumps(api('/api/metadata-correction/general/reintegrate',{'items':[{'relative_path':'20260719_175150_Fuji-X-E5.JPG'}]},202)))")['job']['id']
    for _ in range(240):
        result=api("print(json.dumps(api('/api/jobs/"+job+"')))")
        if result['state'] in ('completed','failed','interrupted'):break
        time.sleep(.25)
    assert result['state']=='completed',result
    imported=snapshot();assert len(imported['files'])==1 and not imported['operations']
    file=imported['files'][0];assert file['actual_sha']==task['output_sha256']==file['sha256_current']
    assert '2026-07-19' in file['current_relative_path'],file
    assert imported['origins']['source_families'] and imported['origins']['source_family_members']
    assert result['result']['organization']['imported_source_files'][0]['sha256']==task['output_sha256']
    # Native supervisor exits when web exits. Restart that same retained container.
    script("import os,signal;from pathlib import Path;found=[]\nfor p in Path('/proc').iterdir():\n if p.name.isdigit():\n  try:\n   cmd=(p/'cmdline').read_bytes().split(b'\\0')\n   if b'uvicorn' in cmd and b'app.main:app' in cmd and p.stat().st_uid==568:found.append(int(p.name))\n  except OSError:pass\nassert len(found)==1,found\nos.kill(found[0],signal.SIGTERM)")
    web_exit=int(docker('wait',NAME).strip())
    # Supervisor returns the web child's status; Unix SIGTERM can surface as
    # -15 translated to 241 by Python, or as conventional shell status 143.
    assert web_exit in (0,143,241),web_exit
    shutdown_result=docker('logs',NAME,check=False)
    assert shutdown_result.returncode==0,shutdown_result.stderr
    shutdown=shutdown_result.stdout+shutdown_result.stderr
    assert 'Application shutdown complete' in shutdown and 'Traceback (most recent call last)' not in shutdown,shutdown[-5000:]
    REPORT['web_sigterm_exit_status']=web_exit
    docker('start',NAME)
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    docker('restart',NAME)
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    assert api("print(json.dumps(api('/healthz')))")['status']=='ok'
    after=snapshot();assert after['origins']==imported['origins'] and after['files']==imported['files']
    REPORT['checks']['real_general_api_and_two_restarts']='PASS'
    # A missing media member alone remains a domain issue; no fabricated new location.
    script("from pathlib import Path;import sqlite3;from app.storage_config import storage_paths;c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);rel=c.execute('SELECT current_relative_path FROM files').fetchone()[0];c.close();p=storage_paths(Path('/workspace'))['backup_root']/rel;p.rename(p.with_name('synthetic-held-'+p.name))")
    docker('restart',NAME);assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    # Explicitly create a synthetic failed domain lease, never remove it afterwards.
    script("from pathlib import Path;from app import root_operations as r\ntry:\n with r.reserve(Path('/workspace'),library_id='main',database=Path('/appdata/database/kamera.sqlite3'),kind='unknown-test-domain',ids={'id':'controlled-failure'}):raise RuntimeError('synthetic process failure')\nexcept RuntimeError:pass")
    frozen=snapshot();docker('restart',NAME)
    health=api("print(json.dumps(api('/api/settings/storage-health')))")
    assert health['state']=='READY' and not health['operation_health']['writes_allowed'],health
    assert api("print(json.dumps(api('/healthz')))")['status']=='ok'
    for path in ('/','/trash','/api/trash','/api/libraries','/api/jobs','/api/metadata-correction/tasks','/api/metadata-correction/scan?area=general'):
        response=api("print(json.dumps(api("+repr(path)+")))")
        if path=='/':assert 'Storage unavailable' not in response and 'bibliothekar-operation-notice' in response
    api("print(json.dumps(api('/api/metadata-correction/correct',{'area':'general','relative_path':'unknown.JPG'},409)))")
    api("print(json.dumps(api('/api/settings/storage-recheck',{},409)))")
    final=snapshot();assert final['operations']==frozen['operations'] and final['files']==frozen['files'] and final['origins']==frozen['origins']
    assert final['archives']==before['archives']
    # The operation diagnostics and catalogue remain protected by real login.
    script("import urllib.request,urllib.error\ntry:urllib.request.urlopen('http://127.0.0.1:8080/api/operations/status');raise AssertionError('anonymous diagnostics')\nexcept urllib.error.HTTPError as e:assert e.code==401")
    REPORT['checks']['missing_media_and_unknown_operation_readable_write_fenced']='PASS'
    REPORT['checks']['archives_unchanged']='PASS'
    from browser_tunnel import chromium_loopback_tunnel
    with chromium_loopback_tunnel(docker,NAME,ROOT/'workspace') as port:
        browser=run('node',str(Path(__file__).with_name('browser.cjs')),'http://127.0.0.1:'+str(port),str(Path(os.environ['RUNNER_TEMP'])/'pre4-browser'),timeout=180)
    REPORT['checks']['chromium_normal_pages_fenced_reads_de_en_mobile_desktop']='PASS'
    REPORT.update(status='PASS',before=before,imported=imported,final=final)
finally:
    log=docker('logs',NAME,check=False)
    (Path(os.environ['RUNNER_TEMP'])/'pre4-live.log').write_text(log.stdout+log.stderr)
    (Path(os.environ['RUNNER_TEMP'])/'pre4-live.json').write_text(json.dumps(REPORT,indent=2))
    docker('rm','-f',NAME,check=False)
    docker('network','rm',NETWORK,check=False)
print(json.dumps({'status':REPORT.get('status'),'checks':REPORT['checks']}))
