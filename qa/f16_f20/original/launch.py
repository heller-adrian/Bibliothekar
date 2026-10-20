"""Run only selected, reviewed tests with an isolated environment and controlled child processes and startup."""
from pathlib import Path
import json, os, subprocess, sys

ROOT=Path(__file__).resolve().parent
SOURCE=Path(os.environ['AUDIT_SOURCE_ROOT']).resolve()
OUTPUT=Path(os.environ['AUDIT_RESULT_ROOT']).resolve()
SCRATCH=Path(os.environ['AUDIT_SCRATCH_ROOT']).resolve()
for writable in (ROOT,OUTPUT,SCRATCH):
    assert not SOURCE.is_relative_to(writable) and not writable.is_relative_to(SOURCE), 'source must be separate from writable audit directories'
SCRATCH.mkdir(exist_ok=True)
OUTPUT.mkdir(exist_ok=True)
env=dict(os.environ)
for key in list(env):
    if key.startswith(('KAMERA_','BIBLIOTHEKAR_','PYTEST_','PYTHONPATH')):
        env.pop(key)
paths={
 'KAMERA_CONFIG':SCRATCH/'bootstrap/settings.json',
 'KAMERA_WORKSPACE':SCRATCH/'bootstrap/workspace',
 'KAMERA_DATABASE_DIR':SCRATCH/'bootstrap/database',
 'KAMERA_REGISTRY_DATABASE':SCRATCH/'bootstrap/database/registry.sqlite3',
 'KAMERA_LOG_DIR':SCRATCH/'bootstrap/logs',
 'KAMERA_POOL_PROBE':SCRATCH/'bootstrap/workspace',
 'KAMERA_ARCHIVE_ROOT':SCRATCH/'bootstrap/archive',
 'KAMERA_IMPORT_ROOT':SCRATCH/'bootstrap/import',
 'KAMERA_REMOVABLE_ROOT':SCRATCH/'bootstrap/removable',
 'KAMERA_NAS_SOURCE_ROOT':SCRATCH/'bootstrap/nas',
 'KAMERA_REMOVABLE_MOUNT_ROOT':SCRATCH/'bootstrap/removable',
 'KAMERA_DEVICE_NODE_ROOT':SCRATCH/'bootstrap/devices',
}
for key,p in paths.items():
    (p.parent if key.endswith(('CONFIG','DATABASE')) else p).mkdir(parents=True,exist_ok=True)
env.update({k:str(v) for k,v in paths.items()})
env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
           BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',
           BIBLIOTHEKAR_AUTH_TEST_BYPASS='pytest-isolated',
           BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-audit-password-2026',
           KAMERA_SOURCE_HELPER_ENABLED='false',KAMERA_SOURCE_HELPER_URL='http://127.0.0.1:1',
           PYTHONPATH=str(SOURCE)+os.pathsep+str(ROOT),
           TMPDIR=str(SCRATCH/'tmp'),AUDIT_OUTPUT=str(OUTPUT),AUDIT_SOURCE=str(SOURCE),
           AUDIT_SCRATCH=str(SCRATCH))
Path(env['TMPDIR']).mkdir(exist_ok=True)
profile=ROOT/'isolation.sb'
profile.write_text('(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'
                   '(allow file-write* (literal "/dev/null"))\n'
                   f'(allow file-write* (subpath "{ROOT}") (subpath "{OUTPUT}") (subpath "{SCRATCH}"))\n')
if sys.argv[1:]==['smoke']:
    script=ROOT/'smoke.py'
    script.write_text('''from pathlib import Path
import os,socket,json
allowed=Path(os.environ['AUDIT_SCRATCH'])/'sandbox-allowed'
allowed.write_text('synthetic')
denied=Path(os.environ['AUDIT_SCRATCH']).parents[2]/'phase2-denied-sentinel'
checks={}
try: denied.write_text('synthetic'); checks['outside_write_blocked']=False
except PermissionError: checks['outside_write_blocked']=True
try:
 s=socket.socket(); s.bind(('127.0.0.1',0)); checks['network_bind_blocked']=False; s.close()
except PermissionError: checks['network_bind_blocked']=True
checks['allowed_write_worked']=allowed.read_text()=='synthetic'
print(json.dumps(checks)); assert all(checks.values())
''')
    cmd=[sys.executable,str(script)]
    label='sandbox-smoke'
else:
    label=sys.argv[1]
    selections=sys.argv[2:]
    if len(selections)==1 and selections[0].startswith('@'):
        selections=json.loads(Path(selections[0][1:]).read_text())
    selections=[str(SOURCE/s) if s.startswith('tests/') else s for s in selections]
    cmd=[sys.executable,str(ROOT/'runner.py'),'-q','-p','no:cacheprovider','--import-mode=importlib',
         '--basetemp',str(SCRATCH/(label+'-tmp')),'--junitxml',str(OUTPUT/(label+'.xml')),
         *selections]
env['AUDIT_LABEL']=label
env['PATH']='/Users/adi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:'+env.get('PATH','')
(OUTPUT/(label+'-command.json')).write_text(json.dumps({'argv':cmd,'cwd':str(SOURCE),'paths':{k:str(v) for k,v in paths.items()},'network':'denied','repository_writes':'denied','timeout_seconds':1200},indent=2))
try:
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(profile),*cmd],env=env,cwd=SOURCE,
                          stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1200)
except subprocess.TimeoutExpired as e:
    (OUTPUT/(label+'.log')).write_text(str(e.stdout));print('TIMEOUT');raise
(OUTPUT/(label+'.log')).write_text(result.stdout)
print(result.stdout)
raise SystemExit(result.returncode)
