"""Full authenticated HTTP/container scenario: applied No Event -> 16 pending families -> explicit reconcile.

Runs exclusively inside throwaway CI volumes; real JPEG, synthetic TIFF-in-RAF, and XMP sidecar.
Never touches NAS data, other jobs, production archives or immutable QA files.
"""
"""Real fresh General correction/admission, supervisor restart, fences and repairs.

Only newly created RUNNER_TEMP fixtures; real UID568 and RO archive mounts.
"""
import hashlib,json,os,subprocess,time
from pathlib import Path
ROOT=Path(os.environ['RUNNER_TEMP'])/'pre6-no-event-http';ROOT.mkdir()
IMAGE=os.environ['IMAGE'];NAME='bibliothekar-pre6-noevent-'+os.environ['GITHUB_RUN_ID']
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
    api("print(json.dumps(api('/api/libraries',{'display_name':'Main','work_root':'','archive_root':'/main-library'},201)))")
    script("from pathlib import Path;import json;p=Path('/appdata/config/settings.json');d=json.loads(p.read_text());d.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(d))")
    assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'

    # The host fixture is a disjoint directory, never a production path.
    # Valid JPEG with actual EXIFTool metadata, TIFF-formatted synthetic RAF,
    # and a sidecar XMP. This does NOT claim native camera RAF write support.
    docker('run','--rm','--network','none','--user','568:568',
        '-v',str(ROOT/'nas')+':/fixture','--entrypoint','python',IMAGE,'-c',r'''
from pathlib import Path
from PIL import Image
import subprocess
root=Path('/fixture')
for name,count,day in [('OLD',8,'2026:07:22'),('NEW',16,'2026:07:24')]:
 folder=root/name;folder.mkdir(parents=True)
 for i in range(count):
  stem=f'202607{22 if name=="OLD" else 24}_120000_{name}{i:02d}'
  path=folder/(stem+'.JPG')
  Image.new('RGB',(20,20),(i*13%255,i*17%255,i*19%255)).save(path)
  subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal='+day+' 12:00:00',
   '-CreateDate='+day+' 12:00:00','-OffsetTimeOriginal=+02:00',
   '-OffsetTimeDigitized=+02:00',str(path)],check=True,capture_output=True)
  if name=='NEW' and i==15:
   raf=folder/(stem+'.RAF')
   Image.new('RGB',(12,12),(10,30,50)).save(raf,format='TIFF')
   (folder/(stem+'.XMP')).write_text(
    '<x:xmpmeta xmlns:x="adobe:ns:meta/" xmlns:exif="http://ns.adobe.com/exif/1.0/" '
    'xmlns:xmp="http://ns.adobe.com/xap/1.0/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
    '<rdf:Description exif:DateTimeOriginal="2026-07-24T12:00:00+02:00" '
    'xmp:CreateDate="2026-07-24T12:00:00+02:00"/>'
    '</rdf:RDF></x:xmpmeta>',encoding='utf8')
''')

    def import_job(folder):
        code=r'''
task=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':''' + repr(folder) + r''','source_mode':'folder'},202)
for _ in range(320):
 checked=api('/api/sd-rechecks/'+task['task_id'])
 if checked['state'] in ('completed','failed'):break
 time.sleep(.25)
assert checked['state']=='completed',checked
job=checked['result']['import_job_id']
for _ in range(320):
 state=api('/api/jobs/'+job)
 if state['state'] in ('completed','failed','interrupted'):break
 time.sleep(.25)
assert state['state']=='completed',state
print(json.dumps(job))
'''
        return api(code)

    def inventory(job_id):
        code=r'''
import json,sqlite3,hashlib
from pathlib import Path
from app.storage_config import storage_paths
db=Path('/appdata/database/kamera.sqlite3')
c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
rows=[dict(x) for x in c.execute("""SELECT f.id AS file_id,f.family_id,
 f.job_id,f.original_filename,f.current_relative_path,f.sha256_current,
 f.size_bytes,ff.selected_capture_time FROM files f
 JOIN file_families ff ON ff.id=f.family_id WHERE f.job_id=?
 ORDER BY f.id""",(''' + repr(job_id) + r''',))]
central=storage_paths(Path('/workspace'))['backup_root']
for item in rows:
 p=central/item['current_relative_path']
 item['source_exists']=p.is_file()
 item['source_sha']=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
c.close()
print(json.dumps(rows))
'''
        return json.loads(script(code))

    first=import_job('OLD')
    old=inventory(first)
    assert len(old)==8 and len({r['family_id'] for r in old})==8,old
    assert all(r['source_exists'] and r['source_sha']==r['sha256_current'] for r in old),old
    created=api("print(json.dumps(api('/api/jobs/"+first+"/events',"+repr({
        'event_name':'No Event July Test','event_kind':'no_event',
        'no_event_segments':[{'day_key':'2026-07-22','start_time':'00:00','end_time':'23:59'}],
        'selected_family_ids':sorted({r['family_id'] for r in old})})+")))")
    event=str(created['parent_event']['id'])
    confirmation=json.loads(script("import json;from app.sort_apply import CONFIRMATION_PHRASE;print(json.dumps(CONFIRMATION_PHRASE))"))
    api("p=api('/api/events/"+event+"/sort-plan');assert p['summary']['ready'],p['blockers'];r=api('/api/events/"+event+"/apply',{'plan_token':p['plan_token'],'confirmation_phrase':"+repr(confirmation)+"},202)\nfor _ in range(320):\n state=api('/api/jobs/"+first+"/sort-runs/'+r['run']['id'])\n if state.get('terminal'):break\n time.sleep(.25)\nassert state['status']=='applied',state\nprint(json.dumps(state['status']))")
    REPORT['checks']['old_no_event_applied_via_authenticated_http']='PASS'

    second=import_job('NEW')
    incoming=inventory(second)
    families=sorted({r['family_id'] for r in incoming})
    assert len(families)==16 and len(incoming)==18,(families,incoming)
    assert all(r['source_exists'] and r['source_sha']==r['sha256_current'] for r in incoming),incoming
    assert {Path(r['original_filename']).suffix.lower() for r in incoming}=={'.jpg','.raf','.xmp'}
    source_before={r['file_id']:(r['current_relative_path'],r['sha256_current'],r['source_sha']) for r in incoming}
    assigned=api("print(json.dumps(api('/api/jobs/"+second+"/no-event/assign-existing',"+repr({
        'target_event_id':event,'segments':[{'day_key':'2026-07-24','start_time':'00:00','end_time':'23:59'}],
        'family_ids':families,'confirm_cross_backup_membership':True})+")))")
    assert assigned.get('resort_required') and str(assigned.get('event_id'))==event,assigned
    assert set(assigned['family_ids'])==set(families),assigned
    REPORT['checks']['save_is_plan_not_physical_move']='PASS'

    for iteration in range(2):
        status=api("print(json.dumps(api('/api/workspace/summary?physical_refresh=true')))")
        after=inventory(second)
        assert {r['file_id']:(r['current_relative_path'],r['sha256_current'],r['source_sha']) for r in after}==source_before
        assert all(r['source_exists'] for r in after)
        issues=json.loads(script("import sqlite3,json;c=sqlite3.connect('file:/appdata/database/kamera.sqlite3?mode=ro',uri=True);print(json.dumps(c.execute(\"SELECT count(*) FROM external_change_notices WHERE status='open' AND kind='placement_conflict'\").fetchone()[0]));c.close()"))
        assert issues==0,('false external moves after pending NoEvent assignment',issues)
    REPORT['checks']['two_physical_inventories_no_false_external_moves']='PASS'

    plan=api("print(json.dumps(api('/api/events/"+event+"/reconcile-plan?verify_sha256=true')))")
    assert plan['summary']['ready'] and not plan['blockers'],plan
    start=api("print(json.dumps(api('/api/events/"+event+"/reconcile',{'plan_token':"+repr(plan['plan_token'])+",'confirmation_phrase':"+repr(confirmation)+"},202)))")
    run_id=start['run']['id']
    api("for _ in range(320):\n state=api('/api/jobs/"+first+"/sort-runs/"+run_id+"')\n if state.get('terminal'):break\n time.sleep(.25)\nassert state['status']=='applied' and state['verified_file_count']==state['file_count'],state\nprint(json.dumps(state['status']))")
    for iteration in range(2):
        docker('restart',NAME)
        assert api("print(json.dumps(api('/api/settings/storage-health')))")['state']=='READY'
        api("print(json.dumps(api('/api/workspace/summary?physical_refresh=true')))")
    checked=inventory(second)
    assert all(not r['source_exists'] for r in checked),checked
    check=json.loads(script(r'''
import sqlite3,json,hashlib
from pathlib import Path
db=Path('/appdata/database/kamera.sqlite3');c=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)
c.row_factory=sqlite3.Row
with sqlite3.connect('file:/appdata/database/bibliothekar-global.sqlite3?mode=ro',uri=True) as g:
 row=g.execute("SELECT work_root FROM libraries WHERE library_id='main'").fetchone()
 assert row is not None
 root=Path(row[0])
rows=[dict(x) for x in c.execute("SELECT id,current_relative_path,sha256_current FROM files WHERE job_id=?",('''+repr(second)+r''',))]
for item in rows:
 path=root/item['current_relative_path']
 assert path.is_file(),path
 assert hashlib.sha256(path.read_bytes()).hexdigest()==item['sha256_current']
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert c.execute("SELECT status FROM event_mutations ORDER BY created_at DESC LIMIT 1").fetchone()[0]=='completed'
print(json.dumps({'verified':len(rows),'bytes':sum((root/x['current_relative_path']).stat().st_size for x in rows)}))
'''))
    assert check['verified']==18,check
    assert (ROOT/'archive/untouched.JPG').read_bytes()==b'archive-one'
    assert (ROOT/'second/untouched.JPG').read_bytes()==b'archive-two'
    REPORT['checks']['apply_18_files_16_families_two_restarts_hashes_archive_ro']='PASS'
    REPORT.update(status='PASS',new_job=second,old_job=first,event_id=event,media_kinds=['jpeg','synthetic_tiff_raf','xmp'])
finally:
    log=docker('logs',NAME,check=False)
    (Path(os.environ['RUNNER_TEMP'])/'pre6-no-event-http.log').write_text(log.stdout+log.stderr)
    (Path(os.environ['RUNNER_TEMP'])/'pre6-no-event-http.json').write_text(json.dumps(REPORT,indent=2))
    docker('rm','-f',NAME,check=False)
    docker('network','rm',NETWORK,check=False)
print(json.dumps({'status':REPORT.get('status'),'checks':REPORT['checks']}))
