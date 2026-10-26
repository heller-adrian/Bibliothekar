"""Retain actual prior outcomes; recheck only affected fixtures on identical app bytes."""
from pathlib import Path
import json,os,shutil
root=Path(os.environ['RUNNER_TEMP'])/'reset-prior';out=Path(os.environ['RC7_EVIDENCE'])
old=json.loads(next(root.rglob('source-contract.json')).read_text());new=json.loads((out/'source-contract.json').read_text())
assert old['app_sha256']==new['app_sha256'] and old['corrections']==new['corrections']
run=json.loads((out/'prior-run.json').read_text());assert run['head_sha']=='f8ea430eac4778baf872af4925f5e5a7e27f3913' and run['conclusion']=='failure'
p=next(root.rglob('targets-results.json'));data=json.loads(p.read_text());assert len(data['tests'])==175 and sum(r['outcome']=='failed' for r in data['tests'])==6
shutil.copyfile(p,out/'prior-results.json')
print('169 prior PASS reused on identical app; six fixture FAIL retained raw')
