"""Reuse the accepted RC4 evidence; never execute a backend suite."""
import hashlib,json,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path('release-assets');out.mkdir(exist_ok=True);repo='heller-adrian/Bibliothekar'
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+path]))
run=api('/actions/runs/40225974384');assert run['head_sha']=='7122afa8864258cba6d1d5500b78413ded7acae7' and run['conclusion']=='success'
jobs=api('/actions/runs/40225974384/jobs');steps={s['name']:s['conclusion'] for j in jobs['jobs'] for s in j['steps']}
assert all(steps[n]=='success' for n in ['One complete isolated Linux backend suite','Build the tested tree without pushing an image','Fresh isolated container health, authentication, database and UI smoke'])
(out/'accepted-run.json').write_text(json.dumps(run,indent=2));(out/'accepted-jobs.json').write_text(json.dumps(jobs,indent=2))
artifact=next(a for a in api('/actions/runs/40225974384/artifacts')['artifacts'] if a['id']==12612616595)
expected='7e154991a7e7367d300730e3af2941a79995e7e4ee8886dc87cd0b480c1260bb'
assert artifact['name']=='rc4-acceptance' and not artifact['expired'] and artifact['digest']=='sha256:'+expected
p=out/'accepted-rc4-evidence.zip'
with p.open('wb') as f:subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/12612616595/zip'],stdout=f,check=True)
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 def content(suffix):
  names=[n for n in z.namelist() if n.endswith(suffix)];assert len(names)==1,(suffix,names);return z.read(names[0])
 suite=ET.fromstring(content('/result.xml')).find('testsuite')
 assert {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}=={'tests':1849,'failures':0,'errors':0,'skipped':0}
 (out/'accepted-backend.xml').write_bytes(content('/result.xml'))
 smoke=json.loads(content('/container-smoke.json'));assert smoke['onboarding']=='PASS' and smoke['version']=='1.0.0-rc.4' and smoke['delivered_ui']['pages']==6
 assert content('/source.txt').decode().splitlines()==['7122afa8864258cba6d1d5500b78413ded7acae7','eb49870426748bc4b7722dadf531a841471ebb3d']
 identity=json.loads(content('/web-identity.json'));assert identity and all(r['uid']==568 and r['gid']==568 for r in identity)
 databases=json.loads(content('/database-smoke.json'));assert databases and all(r['integrity']==[['ok']] and not r['foreign_keys'] for r in databases)
 hashes=json.loads(content('/image-app-sha256.json'));assert len(hashes)==174
 current={str(p.relative_to('product')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product/app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 assert hashes==current
(out/'QA-NACHWEISE.md').write_text('# Abgeschlossene RC4-QA\n\nProduktcommit 7122afa8864258cba6d1d5500b78413ded7acae7; Tree eb49870426748bc4b7722dadf531a841471ebb3d.\nhttps://github.com/heller-adrian/Bibliothekar/actions/runs/40225974384\n\n1849 PASS,0 FAIL/ERROR/SKIP. Linux/amd64-Build und reales Onboarding mit sechs Seiten/JS/CSS,UID/GID568:568 und SQLite PASS. Alle174 App-Dateihashes stimmen überein. Originalartefakt mit festem GitHub-SHA-256 beigelegt.\nDer frühere Lauf40217245075 bleibt mit1822 PASS/12 FAIL historisch rot. Seine Fehler wurden gezielt korrigiert und am verbindlichen finalen Commit regulär bestanden. Lokale Adapter-Zwischenfehler und das1200s-Limit der gezielten Prozessauswahl sind im bestehenden RC4-Abnahmepaket dokumentiert; keine Umdeutung früherer Ergebnisse.\nDieser Veröffentlichungsworkflow führt keine Backend-Suite aus. Er verwendet den exakten Produktcheckout, veröffentlicht ausschließlichRC4 und prüft den tatsächlich veröffentlichten Registrydigest samtVersion,Quellcommit/Tree,174Apphashes und Onboarding erneut. Keine TrueNAS-Plattformfreigabe.\n')
print('Accepted RC4 evidence verified; no backend suite executed')
