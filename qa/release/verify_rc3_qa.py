"""Reuse the accepted RC3 evidence; never execute a backend suite."""
import hashlib,json,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path('release-assets');out.mkdir(exist_ok=True);repo='heller-adrian/Bibliothekar'
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+path]))
run=api('/actions/runs/40146864570');assert run['head_sha']=='d7610205f2c7bc8708e36a130bab896d3ef568d1' and run['conclusion']=='success'
jobs=api('/actions/runs/40146864570/jobs');steps={s['name']:s['conclusion'] for j in jobs['jobs'] for s in j['steps']}
assert all(steps[n]=='success' for n in ['One complete isolated Linux backend suite','Build the tested tree without pushing an image','Fresh isolated container health, authentication, database and UI smoke'])
(out/'accepted-run.json').write_text(json.dumps(run,indent=2));(out/'accepted-jobs.json').write_text(json.dumps(jobs,indent=2))
artifact=next(a for a in api('/actions/runs/40146864570/artifacts')['artifacts'] if a['id']==12581488701)
expected='1bd910cc9fd03d39a8f52217c0697440afb07128ba0c229482376b93d24d3a04'
assert artifact['name']=='rc3-acceptance' and not artifact['expired'] and artifact['digest']=='sha256:'+expected
p=out/'accepted-rc3-evidence.zip'
with p.open('wb') as f:subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/12581488701/zip'],stdout=f,check=True)
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 def content(suffix):
  names=[n for n in z.namelist() if n.endswith(suffix)];assert len(names)==1,(suffix,names);return z.read(names[0])
 suite=ET.fromstring(content('/result.xml')).find('testsuite')
 assert {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}=={'tests':1751,'failures':0,'errors':0,'skipped':0}
 (out/'accepted-backend.xml').write_bytes(content('/result.xml'))
 smoke=json.loads(content('/container-smoke.json'));assert smoke['onboarding']=='PASS' and smoke['version']=='1.0.0-rc.3' and smoke['delivered_ui']['pages']==6
 assert content('/source.txt').decode().splitlines()==['d7610205f2c7bc8708e36a130bab896d3ef568d1','4e722f8bd78365ad437bb918589ffaf6fb3ab7b4']
 identity=json.loads(content('/web-identity.json'));assert identity and all(r['uid']==568 and r['gid']==568 for r in identity)
 databases=json.loads(content('/database-smoke.json'));assert databases and all(r['integrity']==[['ok']] and not r['foreign_keys'] for r in databases)
 hashes=json.loads(content('/image-app-sha256.json'));assert len(hashes)==172
 current={str(p.relative_to('product')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product/app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 assert hashes==current
(out/'QA-NACHWEISE.md').write_text('''# Abgeschlossene RC3-QA

Produktcommit d7610205f2c7bc8708e36a130bab896d3ef568d1; Tree 4e722f8bd78365ad437bb918589ffaf6fb3ab7b4.
https://github.com/heller-adrian/Bibliothekar/actions/runs/40146864570

1751 Backendtests PASS,0 FAIL/ERROR/SKIP. Linux/amd64-Build und frischer Onboarding-Smoke einschließlich sechs Seiten/JS/CSS,UID/GID568:568 und SQLite PASS. Alle172 App-Dateihashes stimmen mit dem Produktcheckout überein. Originalartefakt unverändert mit geprüftem GitHub-SHA-256 beigelegt.
Der frühere Lauf40144407333 blieb mit1748 PASS/3 FAIL historisch rot (README-Version und alter SD-Fallback-Test); diese Nachweise werden nicht umdeklariert. Der endgültige Lauf am korrigierten Commit oben ist vollständig grün.
Der Veröffentlichungsworkflow führt keine Backend-Gesamtsuite aus. Er baut ausschließlich den Produktcommit, prüft die App-Dateien, veröffentlicht nur den RC3-Image-Tag, zieht denselben Registrydigest und prüft Version/App-Dateien/Onboarding erneut. Keine TrueNAS-Plattformabnahme daraus ableiten.
''')
print('Accepted RC3 run,1751 tests,172 hashes,onboarding,UID and SQLite verified; no suite executed')
