"""RC4: preserve the accepted application exactly, with exact approved hashes and version substitutions."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
contract=json.loads((ROOT/'qa/release/rc4.json').read_text())
base=contract['accepted_base']
for commit in [base,*contract['accepted_packages']]:
    subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
names=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'app'],cwd=ROOT,text=True).splitlines()
fixes=contract['approved_product_sha256']
assert set(fixes)=={'app/main.py','app/trash_selective.py','app/trash_ui.py'}
assert all(len(h)==64 and all(c in '0123456789abcdef' for c in h) for h in fixes.values())
for name in names:
    if name in fixes:
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==fixes[name],name
        continue
    expected=subprocess.check_output(['git','show',base+':'+name],cwd=ROOT)
    if name in {'app/__init__.py','app/main.py','app/ui_shell.py'}:
        expected=expected.replace(contract['previous_version'].encode(),contract['version'].encode())
    assert (ROOT/name).read_bytes()==expected,name
actual=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
assert actual==sorted(names)
print(json.dumps({'contract':contract,'application_files':len(names),
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
    'result':'Accepted RC4 app bytes retained except exact approved product hashes and release version substitutions'}))
