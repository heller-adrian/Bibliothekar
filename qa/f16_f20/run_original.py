from pathlib import Path
import hashlib,json,os,subprocess,sys
source=Path(sys.argv[1]).resolve();root=Path(sys.argv[2]).resolve();case=sys.argv[3]
original=Path(__file__).parent/'original';manifest=json.loads((original.parent/'original-integrity.json').read_text())
assert all(hashlib.sha256((original/n).read_bytes()).hexdigest()==h for n,h in manifest.items())
root.mkdir(parents=True,exist_ok=True);temp=root/'temp';temp.mkdir(mode=0o700)
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH=os.pathsep.join(map(str,[source,original,Path(__file__).resolve().parents[2],source/'qa/f14/linux'])),AUDIT_SOURCE=str(source),AUDIT_SCRATCH=str(root),AUDIT_OUTPUT=str(root),AUDIT_LABEL=case,TMPDIR=str(temp),KAMERA_SOURCE_HELPER_ENABLED='false',BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-f1620-password',PYTEST_PLUGINS='qa.f16_f20.fixtures')
for key,value in {'KAMERA_WORKSPACE':'workspace','KAMERA_CONFIG':'settings.json','KAMERA_DATABASE_DIR':'database','KAMERA_REGISTRY_DATABASE':'registry.sqlite3','KAMERA_LOG_DIR':'logs','KAMERA_ARCHIVE_ROOT':'archive'}.items():
 p=root/value;(p.parent if key.endswith(('CONFIG','DATABASE')) else p).mkdir(parents=True,exist_ok=True);env[key]=str(p)
choices={'f16':'test_remaining.py::test_inventory_during_sort','f16_public':'test_combinations.py::test_public_inventory_during_sort','f20':'test_final_combinations.py::test_parallel_library_plans_and_promotion'}
args=[sys.executable,str(original/'runner.py'),'-q','-p','no:cacheprovider','--import-mode=importlib','--basetemp',str(root/'pytest'),'--junitxml',str(root/'result.xml'),str(original/choices[case])]
with (root/'stdout.log').open('w') as log:r=subprocess.run(args,env=env,cwd=source,stdout=log,stderr=subprocess.STDOUT,timeout=180)
(root/'execution.json').write_text(json.dumps({'argv':args,'returncode':r.returncode,'source':str(source),'historical_auth_bypass':True,'TMPDIR':str(temp)},indent=2))
raise SystemExit(r.returncode)
