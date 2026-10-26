"""Reuse the accepted RC5 evidence; never execute a backend suite."""
import hashlib,json,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path('release-assets');out.mkdir(exist_ok=True);repo='heller-adrian/Bibliothekar'
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+path]))
run=api('/actions/runs/40291622012');assert run['head_sha']=='62db66fab6f066116b36ed67dc29e4eb7f4f9034' and run['conclusion']=='success'
jobs=api('/actions/runs/40291622012/jobs');steps={s['name']:s['conclusion'] for j in jobs['jobs'] for s in j['steps']}
assert all(steps[n]=='success' for n in ['One complete isolated Linux backend suite','Build the tested tree without pushing an image','Fresh isolated container health, authentication, database and UI smoke','Real startup recovery and full empty, then unsafe-case refusal'])
(out/'accepted-run.json').write_text(json.dumps(run,indent=2));(out/'accepted-jobs.json').write_text(json.dumps(jobs,indent=2))
artifact=next(a for a in api('/actions/runs/40291622012/artifacts')['artifacts'] if a['id']==12637793649)
expected='5cf04340a3a1620c8788e44eea1924067fe848394055aa5c9e2132bd2d3d9c21'
assert artifact['name']=='rc5-acceptance' and not artifact['expired'] and artifact['digest']=='sha256:'+expected
p=out/'accepted-rc5-evidence.zip'
with p.open('wb') as f:subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/12637793649/zip'],stdout=f,check=True)
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
with zipfile.ZipFile(p) as z:
 assert z.testzip() is None
 def content(suffix):
  names=[n for n in z.namelist() if n.endswith(suffix)];assert len(names)==1,(suffix,names);return z.read(names[0])
 suite=ET.fromstring(content('/result.xml')).find('testsuite')
 assert {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}=={'tests':1956,'failures':0,'errors':0,'skipped':0}
 (out/'accepted-backend.xml').write_bytes(content('/result.xml'))
 smoke=json.loads(content('/container-smoke.json'));assert smoke['onboarding']=='PASS' and smoke['version']=='1.0.0-rc.5' and smoke['delivered_ui']['pages']==6
 assert content('/source.txt').decode().splitlines()==['62db66fab6f066116b36ed67dc29e4eb7f4f9034','ab5b82ec43544cf8f9a92aecd63fb6a902c438bf']
 recovery=json.loads(content('/recovery-smoke.json'));assert all(recovery[k]=='PASS' for k in ['startup_finalization','complete_empty_after_valid_receipt','mismatching_fingerprint_still_blocked','failed_history_originals_stage_status_and_private_copies'])
 identity=json.loads(content('/web-identity.json'));assert identity and all(r['uid']==568 and r['gid']==568 for r in identity)
 databases=json.loads(content('/database-smoke.json'));assert databases and all(r['integrity']==[['ok']] and not r['foreign_keys'] for r in databases)
 hashes=json.loads(content('/image-app-sha256.json'));assert len(hashes)==176
 current={str(p.relative_to('product')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product/app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
 assert hashes==current
(out/'QA-NACHWEISE.md').write_text('# Abgeschlossene RC5-QA\n\nProduktcommit 62db66fab6f066116b36ed67dc29e4eb7f4f9034; Tree ab5b82ec43544cf8f9a92aecd63fb6a902c438bf.\nhttps://github.com/heller-adrian/Bibliothekar/actions/runs/40291622012\n\n1956 PASS, 0 FAIL/ERROR/SKIP. Linux/amd64-Build, frisches tatsächliches Onboarding, sechs Seiten samt JS/CSS, Authentifizierung/Zugriffsschutz, UID/GID568:568 und SQLite/Fremdschlüssel PASS. Alle176 App-Dateihashes stimmen überein. Echter Containerstartup finalisiert sicheren Failed-Restore und erlaubt danach vollständiges Leeren; Fingerprint-Mismatch bleibt gesperrt. Fehlstatus, Originalfehler, Originale und Rückfallbytes bleiben erhalten. Originalartefakt mit festem GitHub-SHA-256 beigefügt.\nDer frühere Lauf40269136661 bleibt mit1895 PASS/60 FAIL historisch rot, der spätere gezielte Lauf40273345586 mit88 PASS/1 FAIL ebenfalls. Fixture-Speicherreserve ausschließlich synthetisch korrigiert; einzelner Linux-Workertest40291335780 PASS. Keine Umdeutung früherer Ergebnisse.\nDie Veröffentlichung wiederholt keine Backend-Suite. Sie prüft den tatsächlich veröffentlichten Digest samtVersion,Quellcommit/Tree,176Apphashes, Onboarding und positiver/negativer Startup-Recovery erneut. Keine native TrueNAS-Plattformabnahme.\n')
print('Accepted RC5 evidence verified; no backend suite executed')
