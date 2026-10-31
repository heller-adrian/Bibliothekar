"""Real fresh General correction/admission, supervisor restart, fences and repairs.

Only newly created RUNNER_TEMP fixtures; real UID568 and RO archive mounts.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(os.environ['RUNNER_TEMP'])/'pre5-manual-changes';ROOT.mkdir()
IMAGE=os.environ['IMAGE'];NAME='bibliothekar-pre5-manual-'+os.environ['GITHUB_RUN_ID']
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
docker('create','--name',NAME,'--network',NETWORK,'--read-only','--tmpfs','/tmp:size=64m,mode=1777',*envargs,*mounts,os.environ['PRE4_IMAGE'])
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
files=[dict(row) for row in c.execute('SELECT * FROM files')];tasks=[dict(row) for row in c.execute('SELECT * FROM metadata_corrections')];jobs=[dict(row) for row in c.execute('SELECT * FROM jobs')];assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall();c.close()
central=storage_paths(ws)['backup_root']
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
applied={r[0] for r in c.execute("SELECT DISTINCT a.family_id FROM event_assignments a JOIN events e ON e.id=a.event_id JOIN events parent ON parent.id=COALESCE(e.parent_event_id,e.id) WHERE parent.status='applied'")};c.close()
c=sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True);work=Path(c.execute("SELECT work_root FROM libraries WHERE library_id='main'").fetchone()[0]);c.close()
for f in files:
 root=Path('/main-library') if f['current_root_kind']=='camera_archive' else work if f['family_id'] in applied else central
 p=root/f['current_relative_path'];f['actual_path']=str(p);f['actual_sha']=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
c=sqlite3.connect(registry.as_uri()+'?mode=ro',uri=True);assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall();origin={t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in ('source_media','source_family_members','source_families')};c.close()
from app.metadata_correction import metadata_area_paths
general=metadata_area_paths(area='general',workspace_root=ws,library_id='main',create=False)['root']
general_media={str(p.relative_to(general)):hashlib.sha256(p.read_bytes()).hexdigest() for p in general.rglob('*') if p.is_file()}
parent=r._control_location(ws)
print(json.dumps({'general_media':general_media,'files':files,'tasks':tasks,'jobs':jobs,'origins':origin,'operations':[r._read(p) for p in sorted(parent.glob('operation-*.json'))],'outcomes':[r._read(p) for p in sorted(parent.glob('metadata-outcome-*.json'))],'archives':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('/main-library','/second-library') for p in Path(root).rglob('*') if p.is_file()}}))
'''
def snapshot():return json.loads(script(SNAP))


def wait_idle():
    return api("\nfor _ in range(240):\n state=api('/api/operations/status')\n if not state['reservations']:break\n time.sleep(.1)\nassert not state['reservations'],state\nprint(json.dumps(state))")


def create_event(job,day,name):
    return api("rows="+script("import sqlite3,json;c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);print(json.dumps([r[0] for r in c.execute('SELECT DISTINCT family_id FROM files WHERE job_id=? AND substr(selected_capture_time,1,10)=?',("+repr(job)+","+repr(day)+"))]))").strip()+
        ";assert rows;print(json.dumps(api('/api/jobs/"+job+"/events',{'event_name':"+repr(name)+",'event_kind':'event','start_date':"+repr(day)+",'end_date':"+repr(day)+",'uses_time_range':False,'selected_family_ids':rows})))")['parent_event']['id']


def apply_event(job,event):
    result=api("from app.sort_apply import CONFIRMATION_PHRASE\nplan=api('/api/jobs/"+job+"/events/"+event+"/sort-plan')\nqueued=api('/api/jobs/"+job+"/events/"+event+"/apply-sort',{'plan_token':plan['plan_token'],'confirmation_phrase':CONFIRMATION_PHRASE},202)\nfor _ in range(240):\n run=api('/api/jobs/"+job+"/sort-runs/'+queued['run']['id'])\n if run.get('terminal'):break\n time.sleep(.25)\nassert run['status']=='applied' and run['error_message'] is None,run\nprint(json.dumps(run))")
    wait_idle()
    return result


try:
    # Actual import: 43 synthetic TIFF/JPEG pairs plus four single JPEGs.
    # The .RAF-labelled TIFF fixture is synthetic, not a native camera RAW test.
    docker('run','--rm','--network','none','--user','568:568',
        '-v',str(ROOT/'nas')+':/fixture','--entrypoint','python',IMAGE,'-c',r'''
from pathlib import Path
from PIL import Image
import subprocess
root=Path('/fixture/CARD');root.mkdir()
index=0
for day,count in zip(range(19,27),(8,8,6,5,5,5,5,5)):
 directory=root/str(day);directory.mkdir()
 for number in range(count):
  index+=1;stem=f'DSCF{index:04d}';paths=[];renames=[]
  for suffix in ('.JPG',) if day==26 and number>0 else ('.JPG','.RAF'):
   target=directory/(stem+suffix)
   if suffix=='.RAF':
    final=target;target=target.with_suffix('.tiff');renames.append((target,final))
   Image.new('RGB',(16,16),((index*41)%255,(index*61)%255,(index*79)%255)).save(target,format='JPEG' if suffix=='.JPG' else 'TIFF')
   paths.append(str(target))
  written=subprocess.run(['exiftool','-overwrite_original',f'-DateTimeOriginal=2026:07:{day} 12:{number:02d}:00',f'-CreateDate=2026:07:{day} 12:{number:02d}:00','-OffsetTimeOriginal=+02:00','-Model=Synthetic Camera','-Make=QA',*paths],text=True,capture_output=True)
  assert written.returncode==0,written.stdout+written.stderr
  for source,target in renames:source.rename(target)
assert index==47 and len(list(root.rglob('*.JPG')))+len(list(root.rglob('*.RAF')))==90
''')
    docker('start',NAME)
    api("print(json.dumps(api('/api/libraries',{'display_name':'Main','work_root':'','archive_root':'/main-library'},201)))")
    script("from pathlib import Path;import json;p=Path('/appdata/config/settings.json');d=json.loads(p.read_text());d.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(d))")
    job=api("task=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'CARD','source_mode':'folder'},202)\nfor _ in range(360):\n checked=api('/api/sd-rechecks/'+task['task_id'])\n if checked['state'] in ('completed','failed'):break\n time.sleep(.25)\nassert checked['state']=='completed',checked\njob=checked['result']['import_job_id']\nfor _ in range(360):\n imported=api('/api/jobs/'+job)\n if imported['state'] in ('completed','failed','interrupted'):break\n time.sleep(.25)\nassert imported['state']=='completed',imported\nprint(json.dumps(job))")
    wait_idle()
    initial=snapshot()
    assert len(initial['files'])==90 and len({f['family_id'] for f in initial['files']})==47
    summary=api("print(json.dumps(api('/api/workspace/summary?jobs="+job+"&physical_refresh=true')))")
    assert {k:summary['statistics'][k] for k in ('file_count','family_count','day_count')}=={'file_count':90,'family_count':47,'day_count':8},summary['statistics']
    applied=create_event(job,'2026-07-19','Test applied');apply_event(job,applied)
    archived=create_event(job,'2026-07-20','Test archiv');apply_event(job,archived)
    location=json.loads(script("import sqlite3,json;from pathlib import Path;from app.event_inventory import event_root_relative;c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row;e=dict(c.execute('SELECT * FROM events WHERE id=?',("+repr(archived)+",)).fetchone());r=sqlite3.connect('file:/appdata/database/bibliothekar-global.sqlite3?mode=ro',uri=True);work=r.execute(\"SELECT work_root FROM libraries WHERE library_id='main'\").fetchone()[0];rel=event_root_relative(e);print(json.dumps({'source':str(Path(work)/rel),'relative':str(rel)}))"))
    # Manual archival is an operator step on disposable fixtures. The app's
    # mount remains RO; verify the full copy before removing its workspace copy.
    docker('run','--rm','--network','none','--user','568:568','-v',str(ROOT)+':/fixture',
        '--entrypoint','python',IMAGE,'-c',"from pathlib import Path;import shutil,hashlib;source=Path('/fixture/workspace')/Path("+repr(location['source'])+").relative_to('/workspace');target=Path('/fixture/archive')/"+repr(location['relative'])+";assert source.is_dir() and not target.exists();target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(source,target);before={str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()};after={str(p.relative_to(target)):hashlib.sha256(p.read_bytes()).hexdigest() for p in target.rglob('*') if p.is_file()};assert before==after;shutil.rmtree(source)")
    api("print(json.dumps(api('/api/jobs/"+job+"/events/"+archived+"/archive-verify',{})))")
    wait_idle()
    prepared=snapshot()
    assert sum(f['current_root_kind']=='camera_archive' for f in prepared['files'])==16
    archive_before=prepared['archives']
    general=json.loads(script("import json;from pathlib import Path;from app.metadata_correction import metadata_area_paths;print(json.dumps(str(metadata_area_paths(area='general',workspace_root=Path('/workspace'),library_id='main',create=False)['root'])))"))
    selected=[]
    for day,label in [('2026-07-19','applied_move'),('2026-07-20','archive_copy'),('2026-07-21','day_move')]:
        rows=[f for f in prepared['files'] if str(f['selected_capture_time']).startswith(day) and f['extension'].lower()=='.jpg']
        assert rows,(day,prepared['files'])
        selected.append((label,rows[0]))
    REPORT['baseline_read_checks']=[]
    for label,row in selected:
        source=row['actual_path'];destination=str(Path(general)/Path(source).name)
        script("from pathlib import Path;import shutil;source=Path("+repr(source)+");target=Path("+repr(destination)+");assert source.is_file() and not target.exists();"+('shutil.copyfile(source,target)' if label=='archive_copy' else 'source.rename(target)'))
        # Record the original release's actual outcome without pretending the
        # previously unknown first NAS exception has already been established.
        result=api("request=urllib.request.Request(host+'/api/workspace/summary?jobs="+job+"&physical_refresh=true');\ntry:response=browser.open(request,timeout=60)\nexcept urllib.error.HTTPError as error:response=error\nwith response:print(json.dumps({'status':response.status,'body':response.read().decode()}))")
        REPORT['baseline_read_checks'].append({'action':label,**result})
    before_upgrade=snapshot()
    assert before_upgrade['archives']==archive_before
    REPORT['pre4']=before_upgrade
    docker('stop',NAME);docker('rm',NAME)
    docker('create','--name',NAME,'--network',NETWORK,'--read-only','--tmpfs','/tmp:size=64m,mode=1777',*envargs,*mounts,IMAGE)
    docker('start',NAME)
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
    assert api("print(json.dumps(api('/api/operations/status')))")['writes_allowed']
    for _ in range(2):api("print(json.dumps(api('/api/workspace/refresh',{})))")
    for label,row in selected:
        relative=Path(row['actual_path']).name
        task=api("print(json.dumps(api('/api/metadata-correction/correct',{'area':'general','relative_path':"+repr(relative)+",'proposed_datetime':"+repr(str(row['selected_capture_time'])[:10]+'T14:30:00+02:00')+"})))")['task']
        assert task['status']=='completed'
        # Variant A is not silently enabled by removing its origin checks.
        # The documented known-origin rejection must be a local, clean failure.
        # An unexpected 202 must be investigated through the real worker,
        # never treated as successful rejection or hidden by this assertion.
        before_transfer=snapshot()
        response=api("payload={'items':[{'relative_path':"+repr(relative)+"}]}\nrequest=urllib.request.Request(host+'/api/metadata-correction/general/reintegrate',data=json.dumps(payload).encode(),headers={'Origin':host,'Content-Type':'application/json','X-Bibliothekar-CSRF':next(c.value for c in jar if c.name=='bibliothekar_csrf')})\ntry:reply=browser.open(request,timeout=60)\nexcept urllib.error.HTTPError as error:reply=error\nwith reply:print(json.dumps({'status':reply.status,'body':json.loads(reply.read())}))")
        if response['status']==202:
            accepted=response['body']['job']['id']
            terminal=api("\nfor _ in range(360):\n value=api('/api/jobs/"+accepted+"')\n if value['state'] in ('completed','failed','interrupted','discarded'):break\n time.sleep(.25)\nprint(json.dumps(value))")
            REPORT['unexpected_general_admission']={'case':label,'correction':task,'response':response,
                'terminal_job':terminal,'before':before_transfer,'after':snapshot()}
            docker('restart',NAME)
            REPORT['unexpected_general_admission']['restart_health']=api("print(json.dumps(api('/api/settings/storage-health')))")
            REPORT['unexpected_general_admission']['after_restart']=snapshot()
        assert response['status']==409,{'case':label,'status':response['status'],
            'terminal_job':REPORT.get('unexpected_general_admission',{}).get('terminal_job')}
        refused=response['body']
        assert 'bekannten Kameraimport' in str(refused),refused
        assert api("print(json.dumps(api('/api/operations/status')))")['writes_allowed']
        REPORT['checks'][label+'_correction_local_rejection']='PASS'
    independent=create_event(job,'2026-07-22','Independent after all three changes');apply_event(job,independent)
    for _ in range(2):
        docker('restart',NAME)
        assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
        assert api("print(json.dumps(api('/api/operations/status')))")['writes_allowed']
        for path in ('/api/workspace/summary?jobs='+job,'/api/archive/summary?force_refresh=true','/api/trash','/api/health'):
            api('print(json.dumps(api('+repr(path)+')))')
    final=snapshot()
    assert final['archives']==archive_before and final['origins']==initial['origins']
    assert not final['operations']
    assert all(f['actual_sha']==f['sha256_current'] for f in final['files']),final['files']
    expected_general={t['source_relative_path']:t['output_sha256'] for t in final['tasks'] if t['area']=='general' and t['status']=='completed'}
    assert len(expected_general)==3 and final['general_media']==expected_general,(expected_general,final['general_media'])
    REPORT['checks']['catalogue_hashes_general_copies_and_both_sqlite_integrities']='PASS'
    REPORT.update(status='PASS',initial=initial,final=final,
        fixture={'files':90,'families':47,'days':8,'native_RAW':'NOT_RUN'},
        known_origin_variant_A='DEFERRED; local rejection tested')
finally:
    log=docker('logs',NAME,check=False)
    (Path(os.environ['RUNNER_TEMP'])/'pre5-manual-changes.log').write_text(log.stdout+log.stderr)
    (Path(os.environ['RUNNER_TEMP'])/'pre5-manual-changes.json').write_text(json.dumps(REPORT,indent=2))
    docker('rm','-f',NAME,check=False);docker('network','rm',NETWORK,check=False)
print(json.dumps({'status':REPORT.get('status'),'checks':REPORT['checks']}))
