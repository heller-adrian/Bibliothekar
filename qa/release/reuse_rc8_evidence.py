"""Bind accepted targeted Linux evidence to RC8's exact version-only source contract."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path(os.environ['RUNNER_TEMP'])/'rc8-prior'
product=Path(os.environ.get('PRODUCT_CHECKOUT','product'))
out=Path('release-assets');out.mkdir(exist_ok=True)
base='00b40f68f9d515b0d2b8ab4a84a26781986be307';tree='1303bceeea4d9c59b93a99db264978eb0ef7894c'
run=json.loads((out/'accepted-run.json').read_text());assert run['conclusion']=='success' and run['head_sha']==base and run['id']==40392556689
assert next(root.rglob('source.txt')).read_text().splitlines()==[base,tree]
app=json.loads(next(root.rglob('image-app-sha256.json')).read_text())
assert len(app)==176
for name,sha in app.items():
    assert sha==hashlib.sha256(subprocess.check_output(['git','-C',str(product),'show',base+':'+name])).hexdigest(),name
prior=json.loads(next(root.rglob('prior-results.json')).read_text())
current=json.loads(next(root.rglob('targets-results.json')).read_text());assert current['exitstatus']==0
merged={r['nodeid']:r for r in prior['tests']};merged.update({r['nodeid']:r for r in current['tests']})
assert len(merged)==175 and all(r['outcome']=='passed' for r in merged.values())
for case in ['A-roots','A-technical','B-missing','A-header','B-header']:
    d=json.loads(next(p for p in root.rglob('reset-container.json') if p.parent.name==case).read_text())
    assert d['csrf']=='PASS' and d['actual_onboarding']['library']['is_registered'] and not d['damaged_used_state_blocked']['ready']
assert json.loads(next(root.rglob('container-smoke.json')).read_text())['onboarding']=='PASS'
(out/'accepted-evidence-summary.json').write_text(json.dumps({'source':base,'tree':tree,'linux_distinct_pass':175,'app_hashes_verified':176,'persistent_container_cases':5,'original_169_pass_6_fixture_fail_preserved':True,'scope':'Targeted combined evidence; no full RC8 backend suite','workflow':run['html_url']},indent=2))
print('Accepted 175-case/5-container evidence and 176 base app hashes verified.')
