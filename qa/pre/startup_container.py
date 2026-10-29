"""Targeted RC14 -> hotfix startup with 4,000 files, real supervisor and RO binds.

All fixtures are created under RUNNER_TEMP. No production paths or host ACL edits.
Also runs the existing real RC14 fourteen-file correction/intent regression.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import subprocess
import time


def command(*args,check=True,timeout=180):
    result=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    if check:assert result.returncode==0,result.stdout+result.stderr
    return result.stdout if check else result


def docker(*args,**kwargs):return command('docker',*args,**kwargs)


source=Path(__file__).resolve().parents[2]
root=Path(os.environ['RUNNER_TEMP'])/'startup-stock';root.mkdir()
for folder in ('appdata','workspace','archive','business'):(root/folder).mkdir()
name='bibliothekar-startup-'+os.environ['GITHUB_RUN_ID']
image=os.environ['IMAGE'];old_image=os.environ['RC14_IMAGE']
report={'source':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN','count':4000,
        'baseline_image':old_image,'cases':[]}
mounts=[]
for host,target in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('business','/Businessarchiv:ro')]:
    mounts+=['-v',str(root/host)+':'+target]
env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace',
     'KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568',
     'KAMERA_SOURCE_HELPER_ENABLED':'false','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-startup-fixture-password'}
env_args=[value for key,val in env.items() for value in ('-e',key+'='+val)]
# Only our freshly created, empty fixture directories are assigned to web UID.
docker('run','--rm','--network','none','-v',str(root)+':/fixture','--entrypoint','python',image,'-c',
       "from pathlib import Path;import os; r=Path('/fixture'); assert not r.is_symlink(); os.chown(r,568,568); [(os.chown(p,568,568)) for p in r.iterdir() if p.is_dir() and not p.is_symlink()]")
for folder in ('archive','business'):
    # Runner still owns these outer fixtures through Docker's explicit test helper.
    docker('run','--rm','--network','none','--user','568:568','-v',str(root/folder)+':/archive','--entrypoint','python',image,'-c',
           "from pathlib import Path;Path('/archive/original.JPG').write_bytes(b'independent archive - never alter')")
API=r'''
import http.cookiejar,json,sys,time,urllib.request
host='http://127.0.0.1:8080';jar=http.cookiejar.CookieJar();browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
for attempt in range(240):
 try:
  with browser.open(host+'/login',timeout=2) as r:assert r.status==200
  break
 except OSError:
  if attempt==239:raise
  time.sleep(.25)
def api(path,payload=None,expect=200):
 h={'Origin':host}
 if payload is not None:
  h['Content-Type']='application/json'
  if path!='/auth/login':h['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
 q=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=h)
 with browser.open(q,timeout=30) as r:
  body=json.load(r);assert r.status==expect,(r.status,body);return body
api('/auth/login',{'password':'isolated-startup-fixture-password'})
'''
def api(code):return json.loads(docker('exec',name,'python','-c',API+'\n'+code,timeout=100))
def create(ref):
    docker('create','--name',name,'--network','none','--read-only','--tmpfs','/tmp:size=64m,mode=1777',*env_args,*mounts,ref)
    docker('start',name)
SNAPSHOT=r'''
import hashlib,json,sqlite3
from pathlib import Path
from contextlib import closing
from app.appdata import configure
configure()
from app.storage_config import storage_paths
ws=Path('/workspace');reg=Path('/appdata/database/bibliothekar-global.sqlite3')
with closing(sqlite3.connect(reg)) as c:
 rows=c.execute('SELECT library_id,database_path FROM libraries ORDER BY library_id').fetchall()
 origin={t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in ('source_families','source_media','source_family_members','canonical_families')}
files={}
for lid,db in rows:
 with closing(sqlite3.connect(db)) as c:
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert c.execute('PRAGMA foreign_key_check').fetchall()==[]
  files[lid]=c.execute('SELECT original_relative_path,current_relative_path,sha256_original,sha256_current,source_size_bytes,size_bytes,selected_capture_time,review_status,metadata_write_status FROM files ORDER BY id').fetchall()
central=storage_paths(ws)['backup_root'];corrected={str(p):[p.stat().st_ino,hashlib.sha256(p.read_bytes()).hexdigest()] for p in central.rglob('F000*.JPG') if int(p.stem[1:])<14}
archive={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for r in ('/main-library','/Businessarchiv') for p in Path(r).rglob('*') if p.is_file()}
print(json.dumps({'origin':origin,'files':files,'corrected':corrected,'archive':archive}))
'''
def snapshot():
    return json.loads(docker('exec','--user','568:568',name,'python','-c',SNAPSHOT))
try:
    create(old_image)
    api("print(json.dumps(api('/api/libraries',{'display_name':'Main','archive_root':'/main-library','work_root':''},201)))")
    api("print(json.dumps(api('/api/libraries',{'display_name':'Secondary','archive_root':'/Businessarchiv','work_root':''},201)))")
    docker('stop',name);docker('rm',name)
    # Populate only stopped synthetic catalogues, preserving the real bootstrap,
    # library identities, role bindings and generation evidence created by RC14.
    docker('run','--rm','--network','none','--user','568:568',*env_args,*mounts,'-v',str(source)+':/qa:ro',
           '--entrypoint','python',image,'-c',r'''
import sys,sqlite3,hashlib,subprocess,json
from pathlib import Path
from PIL import Image
sys.path.insert(0,'/qa')
from app.appdata import configure
configure()
from tests.backend.startup_inventory_fixture import seed
from app.storage_config import storage_paths
reg=Path('/appdata/database/bibliothekar-global.sqlite3')
with sqlite3.connect(reg) as c:rows=c.execute('SELECT library_id,database_path FROM libraries ORDER BY is_main DESC').fetchall()
seed(Path('/appdata/database'),4000,registry=reg,databases=[Path(r[1]) for r in rows],library_ids=[r[0] for r in rows],existing=True)
central=storage_paths(Path('/workspace'))['backup_root']
for i in range(4000):
 p=central/f'2026/2026-10-29/F{i:05}.JPG';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f'synthetic-{i}'.encode())
 if i<14:Image.new('RGB',(8,8),(i*17,i*13,i*7)).save(p)
corrected=[central/f'2026/2026-10-29/F{i:05}.JPG' for i in range(14)]
subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2025:12:07 15:04:37','-EXIF:OffsetTimeOriginal=+13:00',*map(str,corrected)],check=True,capture_output=True)
for _,db in rows:
 with sqlite3.connect(db) as c:
  for i,p in enumerate(corrected):
   c.execute("UPDATE files SET source_size_bytes=size_bytes,size_bytes=?,sha256_current=?,selected_capture_time='2025-12-07T15:04:37',review_status='corrected',metadata_write_status='written' WHERE family_id=?",(p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest(),i+1))
   c.execute("UPDATE file_families SET selected_capture_time='2025-12-07T15:04:37' WHERE id=?",(i+1,))
''',timeout=180)
    before=json.loads(docker('run','--rm','--network','none','--user','568:568',*env_args,*mounts,'--entrypoint','python',image,'-c',SNAPSHOT))
    for attempt in range(2):
        started=time.monotonic()
        if attempt==0:create(image)
        else:docker('restart',name)
        health=api("print(json.dumps(api('/api/settings/storage-health')))")
        elapsed=time.monotonic()-started
        assert elapsed<60,elapsed
        assert health['ready'],health
        current=snapshot();assert len(current['corrected'])==14
        assert all(len(rows)==4000 for rows in current['files'].values())
        assert current==before,'Startup changed source history, media, correction state or RO archive'
        report['cases'].append({'startup_seconds':elapsed,'ready':True,'authenticated_http':True,
                                'helper_disabled':True,'unchanged_second_restart':attempt==1})
    # Existing protected mutation must still work after the large start.
    # Recheck is authenticated and revalidates storage; no fixture reset.
    health=api("print(json.dumps(api('/api/settings/storage-recheck',{})))")
    assert health['ready'],health
    logs=docker('logs',name,check=False);log=logs.stdout+logs.stderr
    assert 'Source helper: disabled' in log
    assert 'Application startup complete' in log and '127.0.0.1:8090' not in log
    web_users=[line.split()[1] for line in docker('top',name,'-eo','pid,uid,args').splitlines()
               if 'uvicorn app.main:app ' in line]
    assert web_users==['568'],web_users
    report.update(status='PASS',corrected_files_preserved=14,origins_preserved=True,readonly_bytes_preserved=True,
                  recheck_passed=True,web_uid=568)

finally:
    logs=docker('logs',name,check=False)
    (Path(os.environ['RUNNER_TEMP'])/'startup-container.log').write_text(logs.stdout+logs.stderr)
    (Path(os.environ['RUNNER_TEMP'])/'startup-evidence.json').write_text(json.dumps(report,indent=2))
    docker('rm','-f',name,check=False)
print(json.dumps(report,indent=2))
