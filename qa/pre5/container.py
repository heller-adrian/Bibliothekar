"""Real fresh General correction/admission, supervisor restart, fences and repairs.

Only newly created RUNNER_TEMP fixtures; real UID568 and RO archive mounts.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(os.environ['RUNNER_TEMP'])/'pre5-live';ROOT.mkdir()
IMAGE=os.environ['IMAGE'];NAME='bibliothekar-pre5-'+os.environ['GITHUB_RUN_ID']
REPORT={'source':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN','real_DNG_1_7':'NOT_RUN','checks':{}}
for name in ('appdata','workspace','archive','second','nas'):(ROOT/name).mkdir()
def run(*args,check=True,timeout=150):
    result=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check:assert result.returncode==0,result.stdout+result.stderr
    return result.stdout if check else result

def docker(*args,**kwargs):return run('docker',*args,**kwargs)
mounts=[]
for host,target in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('second','/second-library:ro'),('nas','/sources/nas:ro')]:mounts+=['-v',str(ROOT/host)+':'+target]
env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_NAS_SOURCE_ROOT':'/sources/nas','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-pre5-test-password'}
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
api('/auth/login',{'password':'isolated-pre5-test-password'})
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
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
applied={r[0] for r in c.execute("SELECT DISTINCT a.family_id FROM event_assignments a JOIN events e ON e.id=a.event_id JOIN events parent ON parent.id=COALESCE(e.parent_event_id,e.id) WHERE parent.status='applied'")};c.close()
c=sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True);work=Path(c.execute("SELECT work_root FROM libraries WHERE library_id='main'").fetchone()[0]);c.close()
for f in files:
 root=work if f['family_id'] in applied else central
 p=root/f['current_relative_path'];f['actual_path']=str(p);f['actual_sha']=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
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
    # The worker commits the job before exiting its F14 write reservation.
    # Do not mistake this short, legitimate commit-to-lease-release interval
    # for a failed import. Require BOTH durable catalogue and no pending lease.
    for _ in range(120):
        imported=snapshot()
        if len(imported['files'])==1 and not imported['operations']:
            break
        time.sleep(.1)
    assert len(imported['files'])==1 and not imported['operations'], {
        'files':[(f['id'],f['job_id'],f['current_relative_path'],f['actual_sha']) for f in imported['files']],
        'operations':[(o.get('kind'),o.get('reservation_id'),o.get('ids')) for o in imported['operations']],
        'jobs':[(j['id'],j['state']) for j in imported['jobs']]
    }
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
    # Reproduce the actual old code's permanent scan lease, with the app
    # stopped: no synthetic JSON reservation or manual SQL edit is used.
    docker('stop',NAME)
    historical=json.loads(docker('run','--rm','--network','none','--user','568:568',
        *envargs,*mounts,'--entrypoint','python',os.environ['PRE4_IMAGE'],'-c',r'''
import json
from pathlib import Path
from app import central_stock_reconcile as stock,root_operations as ro
from app.storage_config import storage_paths
ws=Path('/workspace');db=Path('/appdata/database/kamera.sqlite3')
source=storage_paths(ws)['backup_root']/'unknown-scan.JPG';source.write_bytes(b'synthetic unreadable during scan')
def changed(path):raise PermissionError('synthetic permission changed during old inventory')
stock._sha256_file=changed
try:stock.reconcile_central_free_stock(db,ws,library_id='main')
except PermissionError:pass
else:raise AssertionError('original failure was not reached')
records=[ro._read(p) for p in ro._control_location(ws).glob('operation-*.json')]
assert len(records)==1 and records[0]['kind']=='inventory',records
print(json.dumps(records[0]))
'''))
    docker('start',NAME)
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    recovered=snapshot();assert not recovered['operations'],recovered['operations']
    receipt=json.loads(script("from pathlib import Path;import json;from app import root_operations as r;p=r._control_location(Path('/workspace'))/"+
        repr('inventory-interruption-'+historical['reservation_id']+'.json')+";print(p.read_text())"))
    assert receipt['reservation']==historical and receipt['media_writes'] is False
    REPORT['checks']['real_pre4_inventory_failure_upgrade_original_reservation']='PASS'

    # An actual completed correction whose output is later externally removed
    # retains its exact history. It may not prevent an independent SD import
    # and event sort. The failed acknowledgement is injected before F14 release.
    docker('stop',NAME)
    orphan=json.loads(docker('run','--rm','--network','none','--user','568:568',
        *envargs,*mounts,'--entrypoint','python',IMAGE,'-c',r'''
import json
from pathlib import Path
from PIL import Image
from app import metadata_correction as mc,root_operations as ro
ws=Path('/workspace');db=Path('/appdata/database/kamera.sqlite3')
source=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']/'conflicted.JPG'
Image.new('RGB',(16,16),'yellow').save(source)
real=ro._write
def interrupted(path,value):
 if path.name.startswith('finished-') and value.get('reservation',{}).get('kind')=='metadata':
  raise OSError('synthetic interrupted F14 acknowledgement')
 return real(path,value)
ro._write=interrupted
try:mc.execute_metadata_correction(db,area='general',relative_path=source.name,
 proposed_datetime='2026-07-22T12:00:00+02:00',workspace_root=ws,library_id='main')
except OSError:pass
else:raise AssertionError('acknowledgement fault not reached')
ro._write=real
tasks=mc.list_metadata_corrections(db,include_completed=True)
assert any(t['status']=='completed' and t['source_filename']==source.name for t in tasks),tasks
records=[ro._read(p) for p in ro._control_location(ws).glob('operation-*.json')]
assert len(records)==1 and records[0]['kind']=='metadata',records
source.unlink()  # Controlled external removal of this synthetic work copy.
print(json.dumps(records[0]))
'''))
    # Prepare one independent, real JPEG on the isolated read-only NAS source.
    docker('run','--rm','--network','none','--user','568:568',
        '-v',str(ROOT/'nas')+':/fixture','--entrypoint','python',IMAGE,'-c',r'''
from pathlib import Path
from PIL import Image
import subprocess
p=Path('/fixture/CARD');p.mkdir()
f=p/'20260723_120000_Test.JPG';Image.new('RGB',(16,16),'red').save(f)
subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:07:23 12:00:00','-OffsetTimeOriginal=+02:00',str(f)],check=True,capture_output=True)
''')
    docker('start',NAME)
    state=api("print(json.dumps(api('/api/settings/storage-health')))")
    assert state['state']=='READY' and state['operation_health']['workspace_writes_allowed'],state
    assert not state['operation_health']['writes_allowed'],state
    assert api("print(json.dumps(api('/api/health')))")['database']['initialized']
    imported_job=api(r'''
task=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'CARD','source_mode':'folder'},202)
for _ in range(240):
 checked=api('/api/sd-rechecks/'+task['task_id'])
 if checked['state'] in ('completed','failed'):break
 time.sleep(.25)
assert checked['state']=='completed',checked
job=checked['result']['import_job_id']
for _ in range(240):
 result=api('/api/jobs/'+job)
 if result['state'] in ('completed','failed','interrupted'):break
 time.sleep(.25)
assert result['state']=='completed',result
print(json.dumps(job))
''')
    stock=snapshot();assert len(stock['files'])==2,stock['files']
    independent=[f for f in stock['files'] if f['job_id']==imported_job]
    assert len(independent)==1 and independent[0]['actual_sha']==independent[0]['sha256_current']
    created=api("print(json.dumps(api('/api/jobs/"+imported_job+"/events',"+repr({
        'event_name':'Independent after metadata failure','event_kind':'event',
        'start_date':'2026-07-23','end_date':'2026-07-23','uses_time_range':False,
        'selected_family_ids':[independent[0]['family_id']]})+")))")
    event=created['parent_event']['id']
    confirmation=json.loads(script("import json;from app.sort_apply import CONFIRMATION_PHRASE;print(json.dumps(CONFIRMATION_PHRASE))"))
    api("plan=api('/api/jobs/"+imported_job+"/events/"+event+"/sort-plan');result=api('/api/jobs/"+imported_job+"/events/"+event+"/apply-sort',{'plan_token':plan['plan_token'],'confirmation_phrase':"+repr(confirmation)+"},202)\nfor _ in range(240):\n run=api('/api/jobs/"+imported_job+"/sort-runs/'+result['run']['id'])\n if run['status'] in ('completed','blocked','failed','rollback_failed'):break\n time.sleep(.25)\nassert run['status']=='completed',run\nprint(json.dumps(run['status']))")
    for _ in range(2):
        docker('restart',NAME)
        assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
        assert api("print(json.dumps(api('/api/health')))")['database']['initialized']
        api("print(json.dumps(api('/api/workspace/summary?physical_refresh=true')))")
        api("print(json.dumps(api('/api/archive/summary?force_refresh=true')))")
    retained=snapshot();assert retained['operations']==[orphan],retained['operations']
    assert all(f['actual_sha']==f['sha256_current'] for f in retained['files']),retained['files']
    assert retained['archives']==before['archives']
    for table,rows in imported['origins'].items():
        assert all(row in retained['origins'][table] for row in rows),(table,rows,retained['origins'][table])
    REPORT['checks']['scoped_conflict_real_import_event_sort_two_restarts']='PASS'
    REPORT['scoped_original_reservation']=orphan
    script("import urllib.request,urllib.error\ntry:urllib.request.urlopen('http://127.0.0.1:8080/api/operations/status');raise AssertionError('anonymous diagnostics')\nexcept urllib.error.HTTPError as e:assert e.code==401")
    REPORT['checks']['authenticated_scoped_diagnostics']='PASS'
    REPORT['checks']['archives_unchanged']='PASS'
    final=snapshot()
    # The self-hosted runner intentionally does not have system Chromium
    # libraries (libatk et al.). Use the version-matched official browser QA
    # image in the already isolated app network namespace. No host packages,
    # external network exposure or Docker -p publication are necessary.
    output=Path(os.environ['RUNNER_TEMP'])/'pre5-browser'
    output.mkdir()
    browser=docker('run','--rm','--network','container:'+NAME,
        '--read-only','--tmpfs','/tmp:rw,size=256m,mode=1777',
        '-v',str(Path(__file__).with_name('browser.cjs').absolute())+':/qa/browser.cjs:ro',
        '-v',str(Path(os.environ['RUNNER_TEMP'])/'browser-tools/node_modules')+':/qa/node_modules:ro',
        '-v',str(output)+':/qa/output',
        '-e','NODE_PATH=/qa/node_modules',
        '-e','PLAYWRIGHT_BROWSERS_PATH=/ms-playwright',
        'mcr.microsoft.com/playwright:v1.62.1-noble',
        'node','/qa/browser.cjs','http://127.0.0.1:8080','/qa/output',
        timeout=240)
    REPORT['checks']['chromium_normal_pages_fenced_reads_de_en_mobile_desktop']='PASS'
    REPORT.update(status='PASS',before=before,imported=imported,final=final)
finally:
    log=docker('logs',NAME,check=False)
    (Path(os.environ['RUNNER_TEMP'])/'pre5-live.log').write_text(log.stdout+log.stderr)
    (Path(os.environ['RUNNER_TEMP'])/'pre5-live.json').write_text(json.dumps(REPORT,indent=2))
    docker('rm','-f',NAME,check=False)
    docker('network','rm',NETWORK,check=False)
print(json.dumps({'status':REPORT.get('status'),'checks':REPORT['checks']}))
