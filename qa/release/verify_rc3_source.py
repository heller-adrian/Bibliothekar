"""RC3: preserve the accepted application exactly, with version substitutions only."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[2]
contract=json.loads((ROOT/'qa/release/rc3.json').read_text())
base=contract['accepted_base']
for commit in [base,*contract['accepted_packages']]:
    subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
names=subprocess.check_output(['git','ls-tree','-r','--name-only',base,'app'],cwd=ROOT,text=True).splitlines()
for name in names:
    expected=subprocess.check_output(['git','show',base+':'+name],cwd=ROOT)
    if name in {'app/__init__.py','app/main.py','app/ui_shell.py'}:
        expected=expected.replace(b'1.0.0-rc.2',contract['version'].encode())
    assert (ROOT/name).read_bytes()==expected,name
actual=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
assert actual==sorted(names)
print(json.dumps({'contract':contract,'application_files':len(names),
    'source_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names},
    'result':'Accepted RC2/RC3 app bytes retained; release version substitutions only'}))
