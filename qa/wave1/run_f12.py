"""Preserve raw F12 originals and evaluate the separate native-barrier probe."""
from pathlib import Path
import json,os,subprocess,sys
source=Path(sys.argv[1]).resolve();mode=sys.argv[2]
root=Path(os.environ['RUNNER_TEMP'])/('wave1-f12-'+mode);root.mkdir();temporary=root/'temp';temporary.mkdir(mode=0o700)
launcher=Path(__file__).resolve().parents[1]/'f12/run_original.py'
env=dict(os.environ,F12_QA_ROOT=str(root),F12_QA_SOURCE_ROOT=str(source),TMPDIR=str(temporary))
# Explicitly complete historical installation prerequisites; original sources
# and assertions remain unchanged. Baseline needs no new fixture adapter.
if mode!='before':env['PYTEST_PLUGINS']='qa.f14.linux.complete_historical_fixture'
else:env.pop('PYTEST_PLUGINS',None)
argv=[sys.executable,str(launcher)]+(['--semantic'] if mode=='semantic' else [])
with (root/'raw.log').open('w') as log:result=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
(root/'execution.json').write_text(json.dumps({'argv':argv,'source':str(source),'returncode':result.returncode,'TMPDIR':str(temporary),'fixture_plugin':env.get('PYTEST_PLUGINS'),'raw_historical':mode!='semantic'},indent=2))
print((root/'raw.log').read_text()[-4000:])
if mode=='semantic':raise SystemExit(result.returncode)
assert result.returncode in {0,1} and (root/'results.xml').exists()
