"""Reuse completed RC2 QA; never execute a backend suite."""
import hashlib,json,subprocess,xml.etree.ElementTree as ET,zipfile
from pathlib import Path
out=Path('release-assets');out.mkdir(exist_ok=True)
repo='heller-adrian/Bibliothekar'
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+path]))
full=api('/actions/runs/40108008839');smoke=api('/actions/runs/40111803032')
assert full['head_sha']=='40b97622ba8f89af5db771d2694ae9688cb6c448' and full['conclusion']=='failure'
assert smoke['head_sha']=='49bd136704fe273222f8169e8f4037897afd2543' and smoke['conclusion']=='success'
jobs=api('/actions/runs/40108008839/jobs');steps={s['name']:s['conclusion'] for j in jobs['jobs'] for s in j['steps']}
assert steps['One complete isolated Linux backend suite']==steps['Build the tested tree without pushing an image']=='success'
assert steps['Fresh isolated container health, authentication, database and UI smoke']=='failure'
for name,value in [('accepted-full-run',full),('accepted-full-jobs',jobs),('accepted-smoke-run',smoke)]:
 (out/(name+'.json')).write_text(json.dumps(value,indent=2))
for aid,name,expected in [(12565634718,'accepted-backend-evidence.zip','19bedf7e2d4f4079fd4b14267b23806da595f8173b63c05f1feaca1400b49870'),(12566464423,'accepted-smoke-evidence.zip','8b3f31e4608c64e16573d797ddc6fadad9cf7dd1595cade03ed6b33cb619b502')]:
 p=out/name
 with p.open('wb') as h:subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/{aid}/zip'],stdout=h,check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
 with zipfile.ZipFile(p) as z:
  assert z.testzip() is None
  if aid==12565634718:
   names=[n for n in z.namelist() if n.endswith('/result.xml')];assert len(names)==1
   xml=z.read(names[0]);(out/'accepted-backend.xml').write_bytes(xml)
   suite=ET.fromstring(xml).find('testsuite')
   assert {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}=={'tests':1743,'failures':0,'errors':0,'skipped':0}
  else:
   names=[n for n in z.namelist() if n.endswith('container-smoke.json')];assert len(names)==1
   result=json.loads(z.read(names[0]));assert result['onboarding']=='PASS' and result['delivered_ui']['pages']==6
(out/'QA-NACHWEISE.md').write_text('''# Abgeschlossene RC2-QA

Produkt: 40b97622ba8f89af5db771d2694ae9688cb6c448 / df54a038366684947bd2c9d001d4b17beb253818.

- https://github.com/heller-adrian/Bibliothekar/actions/runs/40108008839 : vollständige Linux-Suite 1743 PASS, 0 FAIL/ERROR/SKIP und Build erfolgreich. Gesamtstatus historisch failure, weil der alte Smoke die erste Bibliothek nicht per Onboarding anlegte.
- https://github.com/heller-adrian/Bibliothekar/actions/runs/40111803032 : korrigierter echter Container-Smoke einschließlich API-Onboarding, sechs Seiten/JS/CSS, UID/GID 568:568 und SQLite PASS. QA-Commit 49bd136704fe273222f8169e8f4037897afd2543 enthält nur Testinfrastruktur.
- Der Veröffentlichungsworkflow führt keine Backend-Gesamtsuite aus. Er baut das exakte Produkt, prüft sämtliche App-Dateihashes, veröffentlicht ausschließlich den RC2-Image-Tag, zieht das Image per Registry-Manifestdigest und prüft dieses mit dem freigegebenen Smoke erneut.

Die beiden ursprünglichen QA-Artefakte sind unverändert mit geprüften GitHub-SHA-256 beigefügt. Der alte rote Workflow wird nicht umdeklariert. TrueNAS-/ZFS-/SMB-/ACL-/Geräte-/Browserabnahme bleibt manuell erforderlich.
''')
print('Original 1743-test result and separate corrected smoke verified; no suite executed')
