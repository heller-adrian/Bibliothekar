"""RC6 isolated container practice: reset, damaged state and duplicate sources."""
import http.cookiejar,json,os,subprocess,time,urllib.request,urllib.error
from pathlib import Path
out=Path(os.environ['RC6_EVIDENCE']);image=os.environ['IMAGE'];fixture=Path('qa/release/practice_rc6_fixture.py').read_text()

def docker(*args,input=None):
    r=subprocess.run(['docker',*args],input=input,text=True,capture_output=True,timeout=90)
    assert r.returncode==0,r.stdout+r.stderr
    return r.stdout

def seed(name,mode):
    args=['run','-i','--rm','--read-only','--network','none','--user','568:568','--volumes-from',name]
    for key,value in {'RC6_SYNTHETIC_QA':'1','KAMERA_CONFIG':'/config/settings.json','KAMERA_WORKSPACE':'/workspace','KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3','KAMERA_ARCHIVE_ROOT':'/main-library'}.items():args+=['-e',key+'='+value]
    text=docker(*args,'--entrypoint','python',image,'-',mode,input=fixture)
    (out/('practice-'+mode+'.json')).write_text(text)

def connect(port):
    base='http://127.0.0.1:'+str(port);jar=http.cookiejar.CookieJar();client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for n in range(90):
        try:
            with client.open(base+'/healthz',timeout=5) as r:assert r.status==200
            break
        except (OSError,AssertionError):
            if n==89:raise
            time.sleep(1)
    def api(path,payload=None,status=200,csrf=True):
        headers={'Origin':base}
        if payload is not None:
            headers['Content-Type']='application/json'
            if csrf:headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        request=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:r=client.open(request,timeout=25)
        except urllib.error.HTTPError as e:r=e
        with r:
            raw=r.read().decode();assert r.code==status,(path,r.code,raw)
            return json.loads(raw)
    api('/auth/login',{'password':'synthetic-rc-build-smoke-password'},csrf=False)
    return api

# The primary container has undergone the regular six-page onboarding smoke.
# Source bytes are tiny real EXIF JPEGs on a runner-only read-only NAS binding.
docker('stop','rc6-smoke');seed('rc6-smoke','prepare-import');docker('start','rc6-smoke');api=connect(18080)
initial=api('/api/import-history')['total'];assert initial==0
checks=[]
for folder in ['CARD','OTHER']:
    checks.append(api('/api/jobs/folder-import',{'source_root_key':'nas','source_relative_path':folder,'source_mode':'folder'},202)['task_id'])
until=time.monotonic()+120
while True:
    parents=[api('/api/sd-rechecks/'+jid) for jid in checks]
    # The public endpoint returns the persistent technical job.
    jobs=parents
    assert all(j['state']!='failed' for j in jobs),jobs
    if all(j['state']=='completed' for j in jobs):break
    assert time.monotonic()<until,parents
    time.sleep(.5)
history=api('/api/import-history');assert history['total']==1,history
until=time.monotonic()+120
while True:
    history=api('/api/import-history');job=api('/api/jobs/'+next(j['result']['import_job_id'] for j in jobs if j['result'].get('import_job_id')))
    assert job['state']!='failed',job
    if job['state']=='completed':break
    assert time.monotonic()<until,job
    time.sleep(.5)
seed('rc6-smoke','check-import')
(out/'duplicate-container.json').write_text(json.dumps({'checks':parents,'history':history,'import':job},indent=2))
# Restore probes have already run on this container. Preserve their failed
# history and retained originals; never delete test catalogue records to reset it.

name='rc6-setup-smoke';scratch=Path(os.environ['RUNNER_TEMP'])/'rc6-reset-smoke'
for path in ['config','database','logs','workspace','archive']:(scratch/path).mkdir(parents=True)
subprocess.run(['sudo','chown','-R','568:568',str(scratch)],check=True)
args=['create','--name',name,'--read-only','--tmpfs','/tmp:size=64m,mode=1777','-p','127.0.0.1:18081:8080']
for k,v in {'KAMERA_SOURCE_HELPER_ENABLED':'false','BIBLIOTHEKAR_ADMIN_PASSWORD':'synthetic-rc-build-smoke-password','KAMERA_CONFIG':'/config/settings.json','KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3','KAMERA_LOG_DIR':'/logs','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library'}.items():args+=['-e',k+'='+v]
for d,target in [('config','/config'),('database','/database'),('logs','/logs'),('workspace','/workspace'),('archive','/main-library:ro')]:args+=['-v',str(scratch/d)+':'+target]
docker(*args,image)
try:
    seed(name,'seed-reset');docker('start',name);reset=connect(18081)
    health=reset('/api/settings/storage-health');assert not health['ready'] and health['can_setup_again'],health
    reset('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':health['setup_token']},403,csrf=False)
    assert reset('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':health['setup_token']})['ready']
    seed(name,'check-reset')
    check=reset('/api/libraries/check',{'display_name':'RC6 Reset','work_root':'','archive_root':'/main-library'});assert check['valid'],check
    created=reset('/api/libraries',{'display_name':'RC6 Reset','work_root':'','archive_root':'/main-library'},201)
    docker('stop',name);seed(name,'seed-damage');docker('start',name);damaged=connect(18081)
    bad=damaged('/api/settings/storage-health');assert not bad['ready'] and not bad.get('can_setup_again'),bad
    damaged('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':'0'*64},409)
    seed(name,'check-damage')
    (out/'reset-container.json').write_text(json.dumps({'confirmed_empty_reset':'PASS','csrf':'PASS','actual_onboarding':created,'damaged_used_state_blocked':bad},indent=2))
finally:
    (out/'reset-container.log').write_text(docker('logs',name));docker('rm','-f',name)
print('RC6 reset/damage/duplicate container PASS')
