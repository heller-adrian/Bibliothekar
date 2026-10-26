"""Runner orchestrator: real container startup, authenticated API, retained bytes."""
import http.cookiejar,json,os,subprocess,time,urllib.request,urllib.error
from pathlib import Path
out=Path(os.environ['RC6_EVIDENCE']);image=os.environ['IMAGE'];name='rc6-smoke';base='http://127.0.0.1:18080'
fixture=Path('qa/release/recovery_rc6_fixture.py').read_text()

def docker(*args,input=None):
    r=subprocess.run(['docker',*args],input=input,text=True,capture_output=True,timeout=90)
    if r.returncode:raise AssertionError(r.stdout+r.stderr)
    return r.stdout

def check(mode):
    env={'RC6_SYNTHETIC_QA':'1','KAMERA_CONFIG':'/config/settings.json','KAMERA_WORKSPACE':'/workspace',
         'KAMERA_DATABASE_DIR':'/database','KAMERA_REGISTRY_DATABASE':'/database/global.sqlite3'}
    args=['run','-i','--rm','--read-only','--network','none','--user','568:568','--volumes-from',name]
    for k,v in env.items():args+=['-e',k+'='+v]
    text=docker(*args,'--entrypoint','python',image,'-',mode,input=fixture)
    (out/('recovery-'+mode+'.json')).write_text(text)
    return json.loads(text)

def login():
    client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    for n in range(90):
        try:
            with client.open(base+'/healthz',timeout=5) as r:assert r.status==200
            break
        except (OSError,AssertionError):
            if n==89:raise
            time.sleep(1)
    with client.open(urllib.request.Request(base+'/auth/login',data=json.dumps({'password':'synthetic-rc-build-smoke-password'}).encode(),
                       headers={'Content-Type':'application/json','Origin':base}),timeout=10) as r:
        assert r.status==200 and json.load(r)['authenticated']
    return client

def empty(client,expected):
    jar=next(h.cookiejar for h in client.handlers if isinstance(h,urllib.request.HTTPCookieProcessor))
    csrf=next(c.value for c in jar if c.name=='bibliothekar_csrf')
    request=urllib.request.Request(base+'/api/trash/empty',data=json.dumps({'confirmation':'PAPIERKORB ENDGÜLTIG LEEREN'}).encode(),
        headers={'Content-Type':'application/json','Origin':base,'X-Bibliothekar-CSRF':csrf})
    try:r=client.open(request,timeout=30)
    except urllib.error.HTTPError as e:r=e
    with r:
        body=r.read().decode();assert r.code==expected,(r.code,body)
        (out/f'recovery-empty-{expected}.json').write_text(body)

for kind in ['good','bad']:
    docker('stop',name);check('seed-'+kind);docker('start',name)
    client=login()
    check('check-'+kind+'-before')
    empty(client,200 if kind=='good' else 409)
    check('check-'+kind+'-after')
    (out/('recovery-container-'+kind+'.log')).write_text(docker('logs',name))
(out/'recovery-smoke.json').write_text(json.dumps({'startup_finalization':'PASS','complete_empty_after_valid_receipt':'PASS',
    'mismatching_fingerprint_still_blocked':'PASS','failed_history_originals_stage_status_and_private_copies':'PASS',
    'platform':'Linux POSIX ACL container; not native TrueNAS/NFS4 qualification'},indent=2))
print('RC6 container recovery PASS')
