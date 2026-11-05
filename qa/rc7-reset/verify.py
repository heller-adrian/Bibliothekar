from pathlib import Path
import json,hashlib,subprocess
r=Path(__file__).resolve().parents[2];c=json.loads((r/'qa/rc7-reset/source.json').read_text())
subprocess.run(['git','merge-base','--is-ancestor',c['base'],'HEAD'],check=True)
names=subprocess.check_output(['git','ls-tree','-r','--name-only',c['base'],'app'],text=True).splitlines()
for n in names:
    actual=(r/n).read_bytes()
    if n in c['correction_sha256']:assert hashlib.sha256(actual).hexdigest()==c['correction_sha256'][n]
    else:assert actual==subprocess.check_output(['git','show',c['base']+':'+n])
assert len(names)==176
assert sorted(names)==sorted(str(p.relative_to(r)) for p in (r/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts)
print(json.dumps({'result':'PASS','base':c['base'],'app_sha256':{n:hashlib.sha256((r/n).read_bytes()).hexdigest() for n in names},'corrections':c['correction_sha256']}))
