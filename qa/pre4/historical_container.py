"""Released pre.2 completed correction -> actual General import -> candidate.
Synthetic real JPEGs, real ExifTool, supervisor, UID568, RO archives, no network.
"""
import json,os,subprocess,time
from pathlib import Path
ROOT=Path(os.environ['RUNNER_TEMP'])/'pre4-historical';ROOT.mkdir()
IMAGE=os.environ['IMAGE'];BASE=os.environ['PRE2_IMAGE']
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
import json,sqlite3,hashlib
from pathlib import Path
from app import root_operations as ro
from app.storage_config import storage_paths
from app.managed_directory_names import directory_name
ws=Path('/workspace');metadata=storage_paths(ws)['metadata_root'];general=metadata/directory_name(metadata,'metadata_general')
c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row
rows=[dict(r) for r in c.execute('SELECT * FROM metadata_corrections ORDER BY created_at,id')]
files=[dict(r) for r in c.execute('SELECT job_id,original_relative_path,current_relative_path,sha256_original,sha256_current,size_bytes FROM files ORDER BY id')];jobs=[dict(r) for r in c.execute('SELECT id,operation,state,stage FROM jobs ORDER BY created_at')];c.close()
for row in files:
 p=storage_paths(ws)['backup_root']/row['current_relative_path'];row['actual_sha']=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
parent=ro._control_location(ws)
read=lambda pattern:[json.loads(p.read_text()) for p in sorted(parent.glob(pattern))]
print(json.dumps({'tasks':rows,'files':files,'jobs':jobs,'ops':read('operation-*.json'),'outcomes':read('metadata-outcome-*.json'),
 'locations':read('metadata-location-*.json'),'general_files':[p.name for p in general.iterdir() if p.is_file()],
 'archive':hashlib.sha256(Path('/main-library/untouched.JPG').read_bytes()).hexdigest()}))
'''
HOOK=r'''
import os,sys
if os.getuid()==568 and 'uvicorn' in sys.orig_argv:
 from app import root_operations as ro
 import signal
 real=ro._write
 def write(path,data):
  if os.environ.get('PRE3_OLD_FINISH_FAILURE')=='1' and path.name.startswith('finished-') and data.get('reservation',{}).get('ids',{}).get('function')=='app.metadata_correction.execute_metadata_correction':
   raise OSError('injected historical F14 completion failure AFTER completed SQL')
  real(path,data)
  if os.environ.get('PRE3_KILL_IMPORT')=='1' and data.get('kind')=='import' and data.get('ids',{}).get('function')=='app.main.process_claimed_job':
   from app import main
   original_complete=main.complete_job
   def complete(database,job_id,**kwargs):
    job=main.get_job(database,job_id)
    if job and job.get('operation')=='metadata_general_import':os.kill(os.getpid(),signal.SIGKILL)
    return original_complete(database,job_id,**kwargs)
   main.complete_job=complete
  if os.environ.get('PRE3_KILL_COMPLETED')=='1' and path.name.startswith('metadata-outcome-') and data.get('disposition')=='completed':os.kill(os.getpid(),signal.SIGKILL)
 ro._write=write
'''
NAME='20260719_175150_Fuji-X-E5.JPG'
PAYLOAD="{'area':'general','relative_path':'"+NAME+"','proposed_datetime':'2026-07-19T17:51:50+02:00'}"

def case(label,*,foreign=False,unknown=False,kill=False,import_kill=False,rc14=False):
 root=ROOT/label;root.mkdir()
 for n in ('appdata','workspace','archive','hooks'):(root/n).mkdir()
 (root/'hooks/sitecustomize.py').write_text(HOOK)
 name='bibliothekar-pre3-'+os.environ['GITHUB_RUN_ID']+'-'+label
 mounts=[]
 for h,t in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('hooks','/qa-hooks:ro')]:mounts+=['-v',str(root/h)+':'+t]
 env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-pre2-metadata-test-password'}
 envargs=[v for k,x in env.items() for v in ('-e',k+'='+x)]
 docker('run','--rm','--network','none','-v',str(root)+':/fixture','--entrypoint','python',IMAGE,'-c',"from pathlib import Path;import os;r=Path('/fixture');os.chown(r,568,568);[os.chown(r/n,568,568) for n in ('appdata','workspace','archive')];(r/'archive/untouched.JPG').write_bytes(b'RO independent archive');os.chmod(r/'archive/untouched.JPG',0o644)")
 def create(image,hook=None):
  extra=['-e','PYTHONPATH=/qa-hooks:/opt/kamera','-e',hook+'=1'] if hook else []
  docker('create','--name',name,'--network','none','--read-only','--tmpfs','/tmp:size=64m,mode=1777',*envargs,*extra,*mounts,image);docker('start',name)
 def api(code,check=True):
  r=docker('exec',name,'python','-c',API+'\n'+code,check=check,timeout=100)
  return json.loads(r) if check else r
 def snap(stopped=False):
  args=['run','--rm','--network','none','--user','568:568',*envargs,*mounts,'--entrypoint','python',IMAGE] if stopped else ['exec','--user','568:568',name,'python']
  return json.loads(docker(*args,'-c',SNAPSHOT))
 def photo(color):
  docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;from PIL import Image;from app.metadata_correction import metadata_area_paths;p=metadata_area_paths(area='general',workspace_root=Path('/workspace'),library_id='main')['root']/'"+NAME+"';Image.new('RGB',(16,16),'"+color+"').save(p)")
 def correct(expect=200,check=True):return api("print(json.dumps(api('/api/metadata-correction/correct',"+PAYLOAD+","+str(expect)+")))",check=check)
 def transfer():
  job=api("print(json.dumps(api('/api/metadata-correction/general/reintegrate',{'items':[{'relative_path':'"+NAME+"'}]},202)))")['job']['id']
  for _ in range(240):
   value=api("print(json.dumps(api('/api/jobs/"+job+"')))")
   # /api/jobs/{id} is the native general-import polling endpoint.
   if value.get('state') in ('completed','failed','interrupted'):
    assert value['state']=='completed',value;return job
   time.sleep(.25)
  raise AssertionError('General import timeout: '+job)
 summary={'label':label}
 try:
  create(os.environ['RC14_IMAGE'] if rc14 else BASE,'PRE3_OLD_FINISH_FAILURE')
  api("print(json.dumps(api('/api/libraries',{'display_name':'Main','work_root':'','archive_root':'/main-library'},201)))")
  docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;import json;p=Path('/appdata/config/settings.json');v=json.loads(p.read_text());v.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(v))")
  photo('blue');correct(expect=409)
  corrected=snap();assert len(corrected['ops'])==1 and corrected['tasks'][0]['status']=='completed' and not corrected['outcomes']
  job=transfer();before=snap();assert NAME not in before['general_files'] and before['files'][0]['actual_sha']==before['tasks'][0]['output_sha256']
  docker('restart',name);health=api("print(json.dumps(api('/api/settings/storage-health')))")
  assert not health['ready'] and ('unresolved_reservation' if rc14 else 'metadata_outcome_unverified') in json.dumps(health),health
  summary['released_rc14_pending_intent_reproduced' if rc14 else 'released_pre2_exact_missing_path_block_reproduced']=True
  if foreign:
   docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;import sqlite3;from app.storage_config import storage_paths;c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);rel=c.execute('SELECT current_relative_path FROM files').fetchone()[0];c.close();(storage_paths(Path('/workspace'))['backup_root']/rel).write_bytes(b'foreign user bytes')")
  if unknown:
   docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;from app import root_operations as r\nfor k in ('trash','import'):\n try:\n  with r.reserve(Path('/workspace'),library_id='main',database=Path('/appdata/database/kamera.sqlite3'),kind=k,ids={'function':'unknown_domain','job_id':k}):raise RuntimeError('isolated unresolved domain')\n except RuntimeError:pass")
   before=snap();assert len(before['ops'])==3
  docker('stop',name);docker('rm',name);create(IMAGE)
  health=api("print(json.dumps(api('/api/settings/storage-health')))");after=snap()
  # Authentication remains mandatory even in recovery.
  unauth=docker('exec',name,'python','-c',"import urllib.request,urllib.error\ntry:urllib.request.urlopen('http://127.0.0.1:8080/api/settings/recovery-diagnostics');raise AssertionError('anonymous recovery')\nexcept urllib.error.HTTPError as e:assert e.code==401")
  if foreign or unknown:
   assert health['state']=='READY' and not health['operation_health']['writes_allowed'],health
   diagnostic=api("print(json.dumps(api('/api/settings/recovery-diagnostics')))")
   assert diagnostic['mode']=='authenticated_read_only' and diagnostic['operations_allowed'] is False
   assert diagnostic['libraries'] and len(diagnostic['operations'])==len(after['ops']), (label,diagnostic,after['ops'])
   assert all(x['authorized_to_finish'] is False for x in diagnostic['operations'])
   api("print(json.dumps(api('/api/metadata-correction/correct',"+PAYLOAD+",409)))")
   assert snap()['tasks']==before['tasks']
   if foreign:
    assert all(op in after['ops'] for op in before['ops']) and not after['outcomes']
    extra=[op for op in after['ops'] if op not in before['ops']]
    # An earlier central-stock fingerprint refusal may preserve one additional
    # startup F14 lease before General metadata recovery runs. That lease is
    # evidence of the refusal, not authority to release the old metadata lease.
    assert len(extra)<=1 and all(op['kind']=='startup' for op in extra), (label,extra)
   else:assert [r for r in after['ops'] if r['kind']!='metadata']==[r for r in before['ops'] if r['kind']!='metadata']
   summary['read_only_recovery_and_write_fence']=True
  else:
   assert health['ready'],health
   assert after['tasks']==before['tasks'] and not after['ops']
   proof=after['outcomes'][0];assert proof['reservation']==before['ops'][0] and proof['source']['transfer']['job']['id']==job
   assert after['files']==before['files']
   summary['same_reservation_proven_transfer']=True
   if kill or import_kill:
    docker('stop',name);docker('rm',name);create(IMAGE,'PRE3_KILL_IMPORT' if import_kill else 'PRE3_KILL_COMPLETED');api("print(json.dumps(api('/api/settings/storage-health')))")
   photo('green')
   if kill:
    result=correct(check=False);assert result.returncode!=0;docker('wait',name)
    dead=snap(stopped=True);pending=next(r for r in dead['ops'] if r['kind']=='metadata')
    assert dead['tasks'][-1]['status']=='completed'
    docker('rm',name);create(IMAGE);assert api("print(json.dumps(api('/api/settings/storage-health')))")['ready']
    assert any(r['reservation']['reservation_id']==pending['reservation_id'] for r in snap()['outcomes'])
    summary['completed_outcome_real_sigkill_recovered']=True
   else:
    correct();assert not snap()['ops']
   if import_kill:
    result=api("print(json.dumps(api('/api/metadata-correction/general/reintegrate',{'items':[{'relative_path':'"+NAME+"'}]},202)))",check=False)
    docker('wait',name)
    dead=snap(stopped=True);assert any(r['kind']=='import' for r in dead['ops']) and not any(r['kind']=='metadata' for r in dead['ops'])
    assert dead['tasks'][-1]['status']=='completed' and all(f['actual_sha']==f['sha256_current'] for f in dead['files'])
    docker('rm',name);create(IMAGE)
    health=api("print(json.dumps(api('/api/settings/storage-health')))");assert health['state']=='READY' and not health['operation_health']['writes_allowed']
    diagnostic=api("print(json.dumps(api('/api/settings/recovery-diagnostics')))");assert any(r['kind']=='import' for r in diagnostic['operations'])
    assert snap()['files']==dead['files'] and snap()['ops']==dead['ops']
    summary.update(status='PASS',archive_unchanged=snap()['archive']==before['archive'],import_commit_sigkill_retained_and_fenced=True)
    REPORT['cases'].append(summary);return
   transfer();assert NAME not in snap()['general_files']
   for _ in range(2):
    docker('restart',name);assert api("print(json.dumps(api('/api/settings/storage-health')))")['ready']
    api("print(json.dumps(api('/api/libraries')))")
   summary['new_success_transfer_two_restarts']=True
  assert snap()['archive']==before['archive'];summary.update(status='PASS',archive_unchanged=True)
  REPORT['cases'].append(summary)
 finally:
  log=docker('logs',name,check=False);(ROOT/(label+'.log')).write_text(log.stdout+log.stderr)
  (Path(os.environ['RUNNER_TEMP'])/'pre3-evidence.json').write_text(json.dumps(REPORT,indent=2))
  docker('rm','-f',name,check=False)

for label,options in [('historical',{}),('rc14',{'rc14':True}),('foreign',{'foreign':True}),('three',{'unknown':True}),('sigkill',{'kill':True}),('import-sigkill',{'import_kill':True})]:case(label,**options)
REPORT['status']='PASS';(Path(os.environ['RUNNER_TEMP'])/'pre3-evidence.json').write_text(json.dumps(REPORT,indent=2));print(json.dumps(REPORT,indent=2))
