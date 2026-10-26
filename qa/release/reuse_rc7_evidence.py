"""Reuse only authenticated evidence for this exact immutable RC7 product."""
from pathlib import Path
import json,os,shutil,hashlib,subprocess
r=Path(os.environ['RUNNER_TEMP'])/'rc7-prior';out=Path('release-assets')
old=next(p for p in r.rglob('source-contract.json') if p.parent.name=='release-assets')
expected=json.loads((out/'source-contract.json').read_text());assert json.loads(old.read_text())==expected
source=old.parent/'source.txt';assert source.read_text().splitlines()==[os.environ['PRODUCT_COMMIT'],os.environ['PRODUCT_TREE']]
run=json.loads((out/'initial-run.json').read_text());assert run['id']==40381064662 and run['head_sha']=='bed8f5846f735b2c1cd4e42b19d426b9a2fcf548' and run['conclusion']=='failure'
data=json.loads((old.parent/'targeted-linux/targets-results.json').read_text());assert data['exitstatus']==0 and len(data['tests'])==246 and all(t['outcome']=='passed' for t in data['tests'])
browser=json.loads((old.parent/'warning-browser/results.json').read_text());assert len(browser)==8 and all(t['result']=='PASS' for t in browser)
shutil.copytree(old.parent/'targeted-linux',out/'targeted-linux');shutil.copytree(old.parent/'warning-browser',out/'warning-browser')
(out/'QA-SCOPE.txt').write_text('RC7:246 targeted Linux PASS,8 browser PASS on identical product. Original run40381064662 remains failure: obsolete RC6 Smoke fixture label. Container-only correction normalizes RC6 QA labels to RC7; assertions retained. No backend rerun; no full RC7 suite. RC6 combined prior evidence retained in its release. Native TrueNAS/NFSv4 remains OPEN.\n')
# Exact historical QA normalization; no relaxed assertions.
for new,original in [('container_recovery_rc7.py','container_recovery_rc6.py'),('recovery_rc7_fixture.py','recovery_rc6_fixture.py')]:
 assert Path('qa/release',new).read_text().replace('RC7','RC6').replace('rc7','rc6')==Path('product/qa/release',original).read_text()
for rel in expected['source_sha256']:
 assert hashlib.sha256(Path('product',rel).read_bytes()).hexdigest()==expected['source_sha256'][rel]
print('Reused exact-source Linux246/browser8 PASS; historical failure preserved')
