"""RC8 accepts exactly the approved legacy-initialization app plus version substitutions."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
contract=json.loads((ROOT/'qa/release/rc8.json').read_text())
base=contract['accepted_base']
assert subprocess.check_output(['git','rev-parse',base+'^{tree}'],cwd=ROOT,text=True).strip()==contract['accepted_tree']
for commit in [base,*contract['accepted_packages']]:
    subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
names=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'app'],cwd=ROOT,text=True).splitlines()
for name in names:
    expected=subprocess.check_output(['git','show',base+':'+name],cwd=ROOT)
    if name in contract['version_files']:
        assert contract['previous_version'].encode() in expected
        expected=expected.replace(contract['previous_version'].encode(),contract['version'].encode())
    assert (ROOT/name).read_bytes()==expected,name
actual=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
assert actual==sorted(names)
assert len(names)==176
for name in ['Dockerfile','requirements.txt','requirements-rc.constraints.txt']:
    assert (ROOT/name).read_bytes()==subprocess.check_output(['git','show',base+':'+name],cwd=ROOT),name
assert (ROOT/'compose.example.yaml').read_bytes()==subprocess.check_output(['git','show',base+':compose.example.yaml'],cwd=ROOT).replace(contract['previous_version'].encode(),contract['version'].encode())
assert contract['version'] in (ROOT/'compose.example.yaml').read_text()
assert contract['version'] in (ROOT/'docs/rc8/compose.truenas.yaml').read_text()
print(json.dumps({'contract':contract,'application_files':len(names),
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
    'result':'PASS: accepted application, explicit version substitutions'}))
