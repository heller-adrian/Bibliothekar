"""RC7 isolated container practice: reset, damaged state and duplicate sources."""
import http.cookiejar,json,os,subprocess,time,urllib.request,urllib.error
from pathlib import Path
scenario=os.environ['RC7_RESET_CASE']
assert scenario in {'A-roots','A-technical','B-missing'}
out=Path(os.environ['RC7_EVIDENCE'])/scenario;out.mkdir()
image=os.environ['IMAGE'];fixture=Path('qa/rc7-reset/fixture.py').read_text()

def docker(*args,input=None):
    r=subprocess.run(['docker',*args],input=input,text=True,capture_output=True,timeout=90)
    assert r.returncode==0,r.stdout+r.stderr
    return r.stdout

def seed(name,mode):
    args=['run','-i','--rm','--read-only','--network','none','--user','568:568','--volumes-from',name]
    for key,value in {'RC7_SYNTHETIC_QA':'1','RC7_RESET_CASE':scenario,'KAMERA_CONFIG':'/config/settings.json','KAMERA_WORKSPACE':'/workspace','KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3','KAMERA_ARCHIVE_ROOT':'/main-library'}.items():args+=['-e',key+'='+value]
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
    def api(path,payload=None,status=200,csrf=True,text=False):
        headers={'Origin':base}
        if payload is not None:
            headers['Content-Type']='application/json'
            if csrf:headers['X-Bibliothekar-CSRF']=next(c.value for c in jar if c.name=='bibliothekar_csrf')
        request=urllib.request.Request(base+path,data=None if payload is None else json.dumps(payload).encode(),headers=headers)
        try:r=client.open(request,timeout=25)
        except urllib.error.HTTPError as e:r=e
        with r:
            raw=r.read().decode();assert r.code==status,(path,r.code,raw)
            return raw if text else json.loads(raw)
    api('/auth/login',{'password':'synthetic-rc-build-smoke-password'},csrf=False)
    return api

name='rc7-setup-smoke';scratch=Path(os.environ['RUNNER_TEMP'])/('rc7-reset-'+scenario)
for path in ['config','database','logs','workspace','archive']:(scratch/path).mkdir(parents=True)
subprocess.run(['sudo','chown','-R','568:568',str(scratch)],check=True)
args=['create','--name',name,'--read-only','--tmpfs','/tmp:size=64m,mode=1777','-p','127.0.0.1:18081:8080']
for k,v in {'KAMERA_SOURCE_HELPER_ENABLED':'false','BIBLIOTHEKAR_ADMIN_PASSWORD':'synthetic-rc-build-smoke-password','KAMERA_CONFIG':'/config/settings.json','KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3','KAMERA_LOG_DIR':'/logs','KAMERA_WORKSPACE':'/workspace','KAMERA_POOL_PROBE':'/workspace','KAMERA_ARCHIVE_ROOT':'/main-library'}.items():args+=['-e',k+'='+v]
for d,target in [('config','/config'),('database','/database'),('logs','/logs'),('workspace','/workspace'),('archive','/main-library:ro')]:args+=['-v',str(scratch/d)+':'+target]
docker(*args,image)
try:
    seed(name,'seed-reset');docker('start',name);reset=connect(18081)
    health=reset('/api/settings/storage-health');assert not health['ready'] and health['can_setup_again'] and not health['can_initialize'],health
    assert health['setup_evidence']=={'A-roots':'complete_legacy_root_bindings','A-technical':'technical_control_only','B-missing':'empty_without_control_evidence'}[scenario],health
    assert 'id="storage-initialize"' in reset('/',text=True)
    assert all(f['status']=='missing' for f in health['folders']),health
    if scenario=='A-roots':assert len([i for i in health['issues'] if i['code']=='catalog_unavailable'])==1,health
    reset('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':health['setup_token']},403,csrf=False)
    assert reset('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':health['setup_token']})['ready']
    seed(name,'check-reset')
    check=reset('/api/libraries/check',{'display_name':'RC7 Reset','work_root':'','archive_root':'/main-library','default_library_id':'rc7-reset'});assert check['valid'],check
    created=reset('/api/libraries',{'display_name':'RC7 Reset','work_root':'','archive_root':'/main-library'},201)
    docker('restart',name);reset=connect(18081)
    assert reset('/api/settings/storage-health')['ready']
    assert reset('/api/libraries')['libraries'][0]['display_name']=='RC7 Reset'
    docker('stop',name);seed(name,'seed-damage');docker('start',name);damaged=connect(18081)
    bad=damaged('/api/settings/storage-health');assert not bad['ready'] and not bad.get('can_setup_again'),bad
    warning=damaged('/',text=True);assert 'id="storage-initialize"' not in warning and 'id="storage-recovery-help"' in warning
    damaged('/api/settings/storage-initialize',{'confirmation':'SET UP AGAIN','token':'0'*64},409)
    seed(name,'check-damage')
    (out/'reset-container.json').write_text(json.dumps({'confirmed_empty_reset':'PASS','csrf':'PASS','actual_onboarding':created,'damaged_used_state_blocked':bad},indent=2))
finally:
    (out/'reset-container.log').write_text(docker('logs',name));docker('rm','-f',name)
print('RC7 historical missing intent/reset/onboarding/restart/damage container PASS')
