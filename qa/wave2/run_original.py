"""Run unchanged F11/R1 audit tools in fresh synthetic roots; retain raw FAILs."""
from pathlib import Path
import json,os,subprocess,sys
source=Path(sys.argv[1]).resolve();kind=sys.argv[2];stage=sys.argv[3]
assert kind in {'f11','r1'} and stage in {'before','after'}
root=Path(os.environ['RUNNER_TEMP'])/('wave2-'+kind+'-'+stage);root.mkdir()
temporary=root/'temp';temporary.mkdir(mode=0o700)
launcher=Path(__file__).resolve().parents[1]/kind/'run_original.py'
env=dict(os.environ,TMPDIR=str(temporary))
env[kind.upper()+'_QA_ROOT']=str(root);env[kind.upper()+'_QA_SOURCE_ROOT']=str(source)
if stage=='after':env['PYTEST_PLUGINS']='qa.f14.linux.complete_historical_fixture'
else:env.pop('PYTEST_PLUGINS',None)
argv=[sys.executable,str(launcher)]
with (root/'raw.log').open('w') as log:
 result=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
(root/'execution.json').write_text(json.dumps({'argv':argv,'source':str(source),'returncode':result.returncode,'TMPDIR':str(temporary),'fixture_plugin':env.get('PYTEST_PLUGINS'),'raw_historical':True},indent=2))
print((root/'raw.log').read_text()[-4000:])
assert result.returncode in {0,1} and (root/'results.xml').exists()
