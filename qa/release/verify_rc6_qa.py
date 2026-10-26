"""Verify the explicitly accepted combined RC6 evidence; never run backend tests."""
import hashlib,json,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
out=Path('release-assets');out.mkdir(exist_ok=True);repo='heller-adrian/Bibliothekar'
product='d1caf00c9ce1f5a5ba4f026b957edb6a9a4c2234';tree='35d1436ac943e90de2f9e663f8c734f82f69ba5c';original='41dac4393de7ed76f0c2375148ef0bce79bf0cb1'
def api(path):return json.loads(subprocess.check_output(['gh','api','repos/'+repo+path]))
def read_artifact(run_id,commit,artifact_id,digest,label):
 run=api(f'/actions/runs/{run_id}');assert run['head_sha']==commit
 jobs=api(f'/actions/runs/{run_id}/jobs')
 (out/(label+'-run.json')).write_text(json.dumps(run,indent=2));(out/(label+'-jobs.json')).write_text(json.dumps(jobs,indent=2))
 item=next(a for a in api(f'/actions/runs/{run_id}/artifacts')['artifacts'] if a['id']==artifact_id)
 assert not item['expired'] and item['digest']=='sha256:'+digest
 p=out/(label+'-evidence.zip')
 with p.open('wb') as f:subprocess.run(['gh','api',f'repos/{repo}/actions/artifacts/{artifact_id}/zip'],stdout=f,check=True)
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
 z=zipfile.ZipFile(p);assert z.testzip() is None
 def content(suffix):
  names=[n for n in z.namelist() if n.endswith(suffix)];assert len(names)==1,(suffix,names)
  return z.read(names[0])
 return run,jobs,content
full,full_jobs,f=read_artifact(40326767389,original,12656516285,'a33368e7dbe05cb3406ccf15d0082dcfe8ba23b843521311d4aa6922746b37b1','original-full')
follow,follow_jobs,t=read_artifact(40335487988,'04ef307bdca0949b1c08a5130fe3e160a003d209',12655753916,'e820c7de5410a30f61973d28dd6a210a14ebabcdaed715bc58a1f072d55a24b2','linux-fixture')
final,final_jobs,s=read_artifact(40337033762,product,12656559887,'39ff765105c430208919932dd795b95e432adba2d1b3cdd3c6693a5dccbcf7eb','accepted-container')
assert full['conclusion']=='failure' and follow['conclusion']=='failure' and final['conclusion']=='success'
steps=lambda jobs:{x['name']:x['conclusion'] for j in jobs['jobs'] for x in j['steps']}
assert steps(follow_jobs)['Only fixture-affected Linux regressions (no full suite)']=='success'
assert all(steps(final_jobs)[n]=='success' for n in ['Build the tested tree without pushing an image','Fresh isolated container health, authentication, database and UI smoke','Real startup recovery and full empty, then unsafe-case refusal','Confirmed reset, damaged installation refusal and duplicate folder smoke'])
def cases(content,label,counts):
 raw=content('/result.xml');(out/(label+'-backend.xml')).write_bytes(raw);root=ET.fromstring(raw);suite=root.find('testsuite')
 assert {k:int(suite.attrib[k]) for k in ('tests','failures','errors','skipped')}==counts
 return {(c.attrib['classname'],c.attrib['name']):('FAIL' if c.find('failure') is not None else 'ERROR' if c.find('error') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS') for c in root.iter('testcase')}
rows=cases(f,'original-full',dict(tests=2010,failures=17,errors=0,skipped=0))
rerun=cases(t,'linux-fixture',dict(tests=56,failures=0,errors=0,skipped=0))
failed={k for k,v in rows.items() if v!='PASS'};assert len(failed)==17 and all(k[0]=='tests.backend.test_rc5_practice_followup' and rerun.get(k)=='PASS' for k in failed)
assert sum(k[0]=='tests.backend.test_rc5_practice_followup' for k in rerun)==48
assert any('cross_filesystem_refuses_without_copy_fallback' in k[1] and v=='PASS' for k,v in rerun.items())
rows.update(rerun);assert len(rows)==2010 and set(rows.values())=={'PASS'}
(out/'combined-linux-matrix.json').write_text(json.dumps([{'test':c+'::'+n,'outcome':v} for (c,n),v in rows.items()],indent=2))
allowed={'.github/workflows/qa-rc6-closeout.yml','qa/release/container_practice_rc6.py','qa/release/practice_rc6_fixture.py','qa/release/rc6-closeout-targets.json','tests/backend/test_rc5_practice_followup.py'}
changed=set(subprocess.check_output(['git','-C','product','diff','--name-only',original,product],text=True).splitlines());assert changed==allowed
old=subprocess.check_output(['git','-C','product','show',original+':tests/backend/test_rc5_practice_followup.py'])
new=Path('product/tests/backend/test_rc5_practice_followup.py').read_bytes()
assert new==old.replace(b'import setup_live_import,queue_and_run\n',b'import setup_live_import,queue_and_run,direct_import_lifecycle\n')
(out/'source-identity.json').write_text(json.dumps({'original':original,'accepted':product,'qa_only_changes':sorted(changed),'all_other_tracked_bytes_identical':True},indent=2))
assert s('/source.txt').decode().splitlines()==[product,tree]
expected={str(p.relative_to('product')):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('product/app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
assert len(expected)==176 and json.loads(s('/image-app-sha256.json'))==expected
assert json.loads(f('/source-contract.json'))['source_sha256']==expected
for name in ['container-smoke','recovery-smoke','practice-check-reset','practice-check-damage','practice-check-import','reset-container','web-identity','database-smoke']:
 data=json.loads(s('/'+name+'.json'));(out/('accepted-'+name+'.json')).write_text(json.dumps(data,indent=2))
 if name=='container-smoke':assert data['onboarding']=='PASS' and data['version']=='1.0.0-rc.6' and data['delivered_ui']['pages']==6
 elif name=='recovery-smoke':assert all(data[k]=='PASS' for k in ['startup_finalization','complete_empty_after_valid_receipt','mismatching_fingerprint_still_blocked','failed_history_originals_stage_status_and_private_copies'])
 elif name=='web-identity':assert data and all(r['uid']==568 and r['gid']==568 for r in data)
 elif name=='database-smoke':assert data and all(r['integrity']==[['ok']] and not r['foreign_keys'] for r in data)
(out/'QA-NACHWEISE.md').write_text('''# Akzeptierte kombinierte RC6-Abnahme

Produkt d1caf00c9ce1f5a5ba4f026b957edb6a9a4c2234, Tree35d1436ac943e90de2f9e663f8c734f82f69ba5c.

- Originalgesamtlauf40326767389:1993 PASS /17 FAIL /0 ERROR/SKIP,2010 gesammelt.
- Alle17 Fixturefehler anschließend gezielt behoben; Linux-Nachlauf40335487988:56 PASS /0 FAIL/ERROR/SKIP, darunter sämtliche48 Fälle des betroffenen Moduls. Dieser Workflow blieb wegen eines nachfolgenden Container-Testadapters insgesamt rot.
- Insgesamt2010 unterschiedliche Backendfälle mit tatsächlichem Linux-PASS nachgewiesen.
- Containerabschluss40337033762:SUCCESS; Build,176Apphashes,Version,Onboarding,Auth,sechsSeiten,JS/CSS,UID/GID,SQLite,privateRecovery,Reset,geschützteBestandsinstallation undDuplikatordner PASS.
- Kein einzelner vollständig grüner Gesamtlauf. Kein roter Lauf wird umetikettiert. Der Auftraggeber hat diesen kombinierten Nachweis zur Veröffentlichung ausdrücklich akzeptiert.

Zwischen Original und Abschluss ändern sich ausschließlich fünf dokumentierte QA-/Testpfade. Anwendung, Dockerfile und sämtliche übrigen Verpackungsbytes bleiben identisch. Originalartefakte sind mit festen GitHub-SHA256 verifiziert und beigefügt. Veröffentlichung führt keine Backend-Suite aus; das publizierte Image wird per Digest mit176Apphashes und isoliertem Onboarding-/Recovery-Smoke erneut geprüft.
Native TrueNAS-/ZFS-/NFSv4-/SMB-/Geräteabnahme bleibt offen. F13/F24-Risikoakzeptanz unverändert.
''')
print('Combined RC6 evidence verified honestly; no backend suite executed')
