"""Run F14 QA only in a disposable Linux runner with synthetic paths."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
source=Path(sys.argv[1]).resolve();mode=sys.argv[2]
base=Path(os.environ['RUNNER_TEMP'])/'f14-qa';base.mkdir(exist_ok=True)
tools=Path(__file__).resolve().parent
original=tools.parent/'original'
manifest=json.loads((tools.parent/'original-integrity.json').read_text())
assert all(hashlib.sha256((original/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
selections=['test_more.py::test_rename_with_live_worker','test_more.py::test_rename_same_web_process','test_remaining.py::test_rename_remaining_workers','test_final_combinations.py::test_rename_after_ssd_unlink']
label=mode;root=base/label;root.mkdir();scratch=root/'scratch';scratch.mkdir();output=root/'results';output.mkdir()
temporary=scratch/'tmp';temporary.mkdir(mode=0o700)
env=dict(os.environ)
env['TMPDIR']=str(temporary)
for k in list(env):
 if k.startswith(('KAMERA_','BIBLIOTHEKAR_','PYTEST_','PYTHONPATH')):env.pop(k)
paths={'KAMERA_CONFIG':'settings.json','KAMERA_WORKSPACE':'workspace','KAMERA_DATABASE_DIR':'database','KAMERA_REGISTRY_DATABASE':'database/registry.sqlite3','KAMERA_LOG_DIR':'logs','KAMERA_POOL_PROBE':'workspace','KAMERA_ARCHIVE_ROOT':'archive','KAMERA_IMPORT_ROOT':'import','KAMERA_REMOVABLE_ROOT':'removable','KAMERA_NAS_SOURCE_ROOT':'nas','KAMERA_REMOVABLE_MOUNT_ROOT':'removable','KAMERA_DEVICE_NODE_ROOT':'devices'}
for k,v in paths.items():
 p=scratch/'bootstrap'/v;(p.parent if k.endswith(('CONFIG','DATABASE')) else p).mkdir(parents=True,exist_ok=True);env[k]=str(p)
env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH=os.pathsep.join(map(str,[source,tools,original])),AUDIT_SOURCE=str(source),AUDIT_OUTPUT=str(output),AUDIT_SCRATCH=str(scratch),AUDIT_LABEL=label,KAMERA_SOURCE_HELPER_ENABLED='false',KAMERA_SOURCE_HELPER_URL='http://127.0.0.1:1',BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-f14-ci-password',BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de')
with (output/'bootstrap.log').open('w') as log:
 result=subprocess.run([sys.executable,str(tools/'bootstrap.py')],cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=60)
if result.returncode:
 print((output/'bootstrap.log').read_text());raise SystemExit(result.returncode)
args=[sys.executable,str(tools/'runner.py'),'-q','-p','no:cacheprovider','--import-mode=importlib','-o','addopts=','--basetemp',str(scratch/'pytest'),'--junitxml',str(output/'result.xml'),'-p','finite_execution']
if env.get('AUDIT_PROFILE_MATCH'):args+=['-p','profile_execution']
if mode=='targets' and 'RC13_PARTITION' in env:args+=['-p','qa.rc13.partition']
if mode=='backend':args+=[str(source/'tests/backend')]
elif mode=='targets':
 chosen=json.loads(Path(sys.argv[3]).read_text());assert chosen and all(n.startswith('tests/backend/') and '..' not in n.split('::')[0].split('/') for n in chosen)
 args+=[str(source/n) for n in chosen]
else:args+=['-p','complete_historical_fixture']+[str(original/n) for n in selections]
(output/'command.json').write_text(json.dumps({'argv':args,'source':str(source),'paths':{k:env[k] for k in paths},'original_sha256':manifest,'TMPDIR':env['TMPDIR'],'AUDIT_SCRATCH':env['AUDIT_SCRATCH']},indent=2))
with (output/'stdout.log').open('w') as log:
 # The full Pre.5 historical gate reached 116/147 nodes in 2400s,
 # then the wrapper killed pytest without a final JUnit. Only this exact
 # 147-case manifest gets a longer deadline; every per-test watchdog is intact.
 pre5_historical_gate=(mode=='targets' and len(sys.argv)>3
                        and Path(sys.argv[3]).name=='backend_unretested.json')
 limit=5400 if pre5_historical_gate else (3600 if mode=='backend' else 2400)
 try:
  result=subprocess.run(args,cwd=source,env=env,stdout=log,
                        stderr=subprocess.STDOUT,timeout=limit)
 except subprocess.TimeoutExpired:
  # Partial output can be diagnostic evidence, never a passing test result.
  (output/'exit.json').write_text(json.dumps({
   'returncode':None,'mode':mode,'timed_out':True,
   'timeout_seconds':limit,'result_complete':False}))
  raise
print((output/'stdout.log').read_text()[-5000:])
(output/'exit.json').write_text(json.dumps({'returncode':result.returncode,'mode':mode,'historical_raw_result':mode not in {'backend','targets'}}))
if mode in {'backend','targets'}:raise SystemExit(result.returncode)
# Preserve red historical contracts. Infrastructure/collection errors still fail QA.
assert result.returncode in {0,1} and (output/'result.xml').is_file()
