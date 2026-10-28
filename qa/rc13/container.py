"""Real RC12 import/deletion/block -> RC13 upgrade, HTTP and crash recovery.

All data is synthetic, below RUNNER_TEMP; archives and sources are real RO binds.
No production connection or test bypass is used by the web process.
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

source=Path(__file__).resolve().parents[2]
base=Path(os.environ['RUNNER_TEMP'])/'rc13-container';base.mkdir()
logs=Path(os.environ['RUNNER_TEMP'])/'rc13-container-logs';logs.mkdir()
report={'source':os.environ['GITHUB_SHA'],'native_truenas':'NOT_RUN','cases':[]}

def command(*args,check=True):
    result=subprocess.run(args,capture_output=True,text=True,timeout=180)
    if check:assert result.returncode==0,result.stdout+result.stderr
    return result.stdout if check else result

def docker(*args,**kw):return command('docker',*args,**kw)

def client():
    host='http://127.0.0.1:18319';jar=http.cookiejar.CookieJar()
    browser=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for attempt in range(160):
        try:
            with browser.open(host+'/login',timeout=3) as r:assert r.status==200
            break
        except OSError:
            if attempt==159:raise
            time.sleep(.25)
    def api(path,payload=None,expect=200):
        headers={'Origin':host}
        if payload is not None:
            headers['Content-Type']='application/json'
            if path!='/auth/login':headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        request=urllib.request.Request(host+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:response=browser.open(request,timeout=60)
        except urllib.error.HTTPError as error:response=error
        with response:
            body=response.read().decode();assert response.status==expect,(path,response.status,body)
            return json.loads(body)
    api('/auth/login',{'password':'isolated-rc13-upgrade-password'})
    return api

SNAPSHOT=r'''
from pathlib import Path
import sqlite3,json,hashlib
from contextlib import closing
result={}
for key,name in [('origin','bibliothekar-global.sqlite3'),('local','kamera.sqlite3')]:
 with closing(sqlite3.connect('file:/appdata/database/'+name+'?mode=ro',uri=True)) as c:
  c.row_factory=sqlite3.Row
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert not c.execute('PRAGMA foreign_key_check').fetchall()
  if key=='origin':
   result[key]={t:[dict(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY 1,2')] for t in ('source_families','canonical_families','source_family_members','source_media')}
  else:
   result['files']=[dict(r) for r in c.execute('SELECT * FROM files ORDER BY id')]
   result['counts']={t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('jobs','file_families','files','audit_log')}
   result['loss']=[dict(r) for r in c.execute("SELECT * FROM audit_log WHERE action='central_file_deletion_confirmed'")]
paths=list(Path('/workspace/SD Card Backups').rglob('*.RAF'))
result['raw']=[{'path':str(p),'identity':[p.stat().st_dev,p.stat().st_ino],'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]
result['readonly']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for root in ('/main-library','/Businessarchiv','/sources/nas') for p in Path(root).rglob('*') if p.is_file()}
print(json.dumps(result))
'''

def run_case(label,crash=False):
    root=base/label;root.mkdir()
    for name in ('appdata','workspace','archive','business','nas','evidence'):(root/name).mkdir()
    command('sudo','chown','-R','568:568',str(root))
    # Fixture generation uses the image's actual tools, before RO source binding.
    docker('run','--rm','--user','568:568','-v',str(root)+':/fixture','--entrypoint','python',os.environ['RC12_IMAGE'],'-c',r'''
from pathlib import Path
from PIL import Image
import subprocess
p=Path('/fixture/nas/CARD');p.mkdir()
for name,color in [('A.JPG','red'),('A.RAF','blue')]:
 Image.new('RGB',(8,8),color).save(p/name,format='JPEG')
subprocess.run(['exiftool','-overwrite_original','-EXIF:DateTimeOriginal=2026:10:27 12:00:00','-EXIF:Make=FUJIFILM','-EXIF:Model=X-E5',*map(str,p.iterdir())],check=True,capture_output=True)
Path('/fixture/archive/original.JPG').write_bytes(b'Independent existing archive')
Path('/fixture/business/original.JPG').write_bytes(b'Independent business archive')
Path('/fixture/workspace/.DS_Store').write_bytes(b'Finder')
''')
    name='bibliothekar-rc13-'+label
    def create(image):
        args=['--read-only','--tmpfs','/tmp:size=64m,mode=1777','-p','127.0.0.1:18319:8080']
        env={'KAMERA_APPDATA':'/appdata','KAMERA_WORKSPACE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library','KAMERA_POOL_PROBE':'/workspace','KAMERA_NAS_SOURCE_ROOT':'/sources/nas','KAMERA_SOURCE_HELPER_ENABLED':'false','KAMERA_WEB_UID':'568','KAMERA_WEB_GID':'568','BIBLIOTHEKAR_ADMIN_PASSWORD':'isolated-rc13-upgrade-password'}
        if crash and image==os.environ['IMAGE']:env.update(PYTHONPATH='/qa-code:/opt/kamera',RC13_QA_BOUNDARY='origin-qualified')
        for key,value in env.items():args+=['-e',key+'='+value]
        for src,dst in [('appdata','/appdata'),('workspace','/workspace'),('archive','/main-library:ro'),('business','/Businessarchiv:ro'),('nas','/sources/nas:ro'),('evidence','/qa-evidence')]:args+=['-v',str(root/src)+':'+dst]
        args+=['-v',str(source/'qa/rc13')+':/qa-code:ro']
        docker('create','--name',name,*args,image);docker('start',name)
    def read():return json.loads(docker('exec','--user','568:568',name,'python','-c',SNAPSHOT))
    def capture(suffix):
        r=docker('logs',name,check=False);(logs/(label+'-'+suffix+'.log')).write_text(r.stdout+r.stderr)
    try:
        create(os.environ['RC12_IMAGE']);api=client();assert api('/api/settings/storage-health')['ready']
        api('/api/libraries',{'display_name':'Main Library','work_root':'','archive_root':'/main-library'},expect=201)
        # Only space reserves for this tiny synthetic acceptance fixture are zero.
        docker('exec','--user','568:568',name,'python','-c',"import json;from pathlib import Path;p=Path('/appdata/config/settings.json');v=json.loads(p.read_text());v.setdefault('storage',{}).update(safety_reserve_gib=0,processing_buffer_percent=0);p.write_text(json.dumps(v))")
        admitted=api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':'CARD','source_mode':'folder'},expect=202)
        task=admitted['task_id']
        for _ in range(160):
            checked=api('/api/sd-rechecks/'+task)
            if checked['state'] in ('completed','failed'):break
            time.sleep(.25)
        assert checked['state']=='completed',checked
        imported=checked['result']['import_job_id']
        for _ in range(240):
            job=api('/api/jobs/'+imported)
            if job['state'] in ('completed','failed'):break
            time.sleep(.25)
        assert job['state']=='completed',job
        before=read();assert len(before['files'])==2 and len(before['origin']['source_family_members'])==2,before
        assert len(before['origin']['source_families'])==1,before
        api('/api/workspace/summary')
        jpeg=next(f for f in before['files'] if f['media_type']=='jpeg')
        docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;p=Path('/workspace/SD Card Backups')/"+repr(jpeg['current_relative_path'])+";p.unlink()")
        api('/api/workspace/summary');api('/api/workspace/summary')
        lost=read();assert len(lost['files'])==1 and len(lost['loss'])==1,lost
        assert lost['origin']==before['origin'] and lost['raw']==before['raw']
        docker('restart',name);api=client();health=api('/api/settings/storage-health')
        assert not health['ready'],health
        capture('rc12-confirmed-block')
        old=read();assert old['origin']==before['origin']
        docker('stop','-t','15',name);docker('rm',name)
        create(os.environ['IMAGE'])
        checkpoint=None
        if crash:
            for _ in range(240):
                if (root/'evidence/rc13-checkpoint.json').exists() and docker('inspect','-f','{{.State.Running}}',name).strip()=='false':break
                time.sleep(.25)
            assert (root/'evidence/rc13-checkpoint.json').exists(),docker('logs',name)
            checkpoint=json.loads((root/'evidence/rc13-checkpoint.json').read_text())
            docker('start',name)
        api=client();health=api('/api/settings/storage-health');assert health['ready'],health
        after=read();assert after['origin']==before['origin'] and after['raw']==before['raw'],after
        assert after['readonly']==before['readonly']
        api('/api/libraries',{'display_name':'Business Library','work_root':'','archive_root':'/Businessarchiv'},expect=201)
        libraries=api('/api/libraries')['libraries'];assert len(libraries)==2,libraries
        docker('exec','--user','568:568',name,'python','-c',"from pathlib import Path;Path('/workspace/Trash/unknown.JPG').write_bytes(b'Unknown original')")
        prior=read();api('/api/trash/restore',{'relative_paths':['unknown.JPG']},expect=409)
        assert read()['counts']==prior['counts']
        api('/api/trash/empty',{'confirmation':'PAPIERKORB ENDGÜLTIG LEEREN'})
        for _ in range(2):
            docker('restart',name);api=client();assert api('/api/settings/storage-health')['ready']
            assert len(api('/api/libraries')['libraries'])==2
        final=read();assert final['readonly']==before['readonly'] and final['raw']==before['raw']
        # Each projection retains the same canonical family, including the lost JPG.
        origins=final['origin']['source_families'];assert len(origins)==2
        assert len({o['canonical_family_id'] for o in origins})==1,origins
        report['cases'].append({'label':label,'status':'PASS','rc12_block_reproduced':True,'real_http_import':True,'source_members_preserved':True,'second_library_created':True,'unknown_restore_no_mutation':True,'protected_mutation_after_restart':True,'raw_identity_preserved':True,'readonly_bytes_preserved':True,'crash':checkpoint})
        capture('rc13-completed')
    finally:
        capture('final');docker('rm','-f',name,check=False)
        (Path(os.environ['RUNNER_TEMP'])/'rc13-evidence.json').write_text(json.dumps(report,indent=2))

run_case('rc12-upgrade')
run_case('rc12-upgrade-sigkill',crash=True)
