"""Reproduce the initial, deliberately non-final triage of all eight partitions.
Usage: python qa/pre5/classify_backend.py EXTRACTED_EVIDENCE OUTPUT_DIRECTORY
No application code executes, and no failing expectation is changed.
"""
import collections,hashlib,json,re,sys
from pathlib import Path
import xml.etree.ElementTree as ET

root,out=map(Path,sys.argv[1:]);out.mkdir(parents=True,exist_ok=True)
summary=json.loads((root/'summary.json').read_text())
assert summary['source']=='2908eacbf73e891ebd46078cb9ae4af43e0dd454'
assert summary['collected']==summary['selected_once']==2444 and summary['complete']
timeouts=set()
for p in root.glob('*/f14-qa/targets/results/execution-deadlines.json'):
    timeouts.update(json.loads(p.read_text())['timeouts'])

def classify(node,text,message):
    file=node.split('::')[0]
    if node in timeouts:return 'runtime_deadline','CONFIRMED_RUNTIME','Recorded SIGALRM deadline; SQLite callback may mask it as not authorized.'
    if 'not authorized' in text:
        if 'test_rc11_bootstrap.py' in file and '_ensure_registry_schema_table' in text:
            return 'rc11_snapshot_schema_order','CONFIRMED_FIXTURE','Fixture publishes orphan before preparing the database snapshot represented by it.'
        if 'ensure_schema_version_table' in text:
            return 'schema_read_requests_ddl','CONFIRMED_PRODUCT','Current-schema read executes CREATE IF NOT EXISTS, which requires SQLite write authorization.'
        if 'test_0561_recovery.py' in file or 'test_r1_restore_recovery.py' in file:
            return 'external_tamper_uses_guarded_connection','CONFIRMED_FIXTURE','Synthetic external corruption/edit is attempted through the protected production connection.'
        return 'domain_sql_authorization','REQUIRES_CAUSAL_REPRODUCTION','Inspect exact pending operation and SQL footprint; do not grant general write permission.'
    if file.endswith(('test_0554_config_brand.py','test_0414_patch_regressions.py')):
        return 'source_text_contract','OBSOLETE_ASSERTION_SHAPE','Source substring contract predates split startup/read-refresh code; replace with behavioral proof, not deletion.'
    if 'Regex pattern did not match' in message:
        return 'error_wording_contract','CONFIRMED_OBSOLETE_WORDING','The forbidden operation remains rejected; old German error regex no longer matches structured recovery error.'
    if 'catalog_unavailable:' in text and '/scratch/bootstrap/database/registry.sqlite3' in text:
        return 'ambient_registry_fixture_context','FIXTURE_CONTEXT_SUSPECT','Ad-hoc workspace uses unrelated global bootstrap registry; verify helper contract before changing setup.'
    if 'test_f14_o2_policy.py' in file:
        return 'f14_initial_state_contract','MIXED_REVIEW_REQUIRED','Known state.json now exists before operation; separately inspect SIGKILL receipts and root-change fences.'
    if 'test_0500_http_owner_auth.py' in file:
        return 'health_without_startup_contract','OBSOLETE_ASSUMPTION_TO_VERIFY','Auth-only client skips startup; health503 must still be public and all protected routes401.'
    if 'test_0500_backup_delete_recovery.py' in file:
        return 'backup_recovery_admission','PRODUCT_RECOVERY_REVIEW','Recovery lease conflicts with original backup intent before domain qualification.'
    if 'test_r1_restore_recovery.py' in file:
        return 'restore_recovery_and_scope','PRODUCT_OR_CONTRACT_REVIEW','Separate unreached rollback/commit/cleanup from obsolete global-start failure expectations; preserve unknown-byte fences.'
    if 'test_f11_trash_reservation.py' in file or 'test_0561_recovery.py' in file or 'test_0561_audit_regressions.py' in file:
        return 'trash_recovery_and_scope','PRODUCT_OR_FIXTURE_REVIEW','Original trash intent or missing technical anchor prevents qualified domain recovery; inspect receipts and retained bytes.'
    if 'test_0562_process_recovery.py' in file or 'test_0562_recovery_guards.py' in file or 'test_f14_runtime.py' in file:
        return 'startup_domain_recovery_not_reached','PRODUCT_OR_CONTRACT_REVIEW','Known crash recovery is not reached, job state/receipt remains pending, or negative test expects global process failure.'
    if 'test_rc4_sd_recheck.py' in file or 'test_rc5_practice_followup.py' in file and 'sigkill' in node or 'test_rc6_handoff.py' in file:
        return 'worker_resume_queued_or_verifying','PRODUCT_RECOVERY_REVIEW','Real restart does not complete original recheck/import; qualify original intent before worker resume.'
    if 'test_rc1_b01.py' in file:
        return 'read_view_and_contention_contract','REQUIRES_BEHAVIORAL_PROOF','GET no longer acquires mutating lease; prove safe reads and conflicting writes independently before changing200/409 assertions.'
    if 'test_rc4_acceptance_regressions.py' in file or 'test_rc1_sd_reimport.py' in file:
        return 'independent_operation_scope','PRODUCT_SCOPE_REVIEW','Old intent blocks separate selection/retry; narrow only after verifiable original effect qualification.'
    if 'test_metadata_consistency' in file or 'test_f14_continuation.py' in file:
        return 'historical_completion_and_retry','PRODUCT_RECOVERY_REVIEW','Original intent and domain completion/ownership receipt need exact retry qualification.'
    return 'storage_setup_anchor_and_reset','REQUIRES_CAUSAL_REPRODUCTION','Inspect configured required anchors, retained history, mount identity and repair contract; no automatic reset.'

seen=set();allnodes=None;rows=[];totals=collections.Counter();partitions=[]
for index in range(8):
    manifest=json.loads((root/str(index)/'rc13-partition.json').read_text());nodes=manifest['all_nodes'];selected=manifest['selected_nodes']
    if allnodes is None:allnodes=nodes
    assert nodes==allnodes and not seen.intersection(selected);seen.update(selected)
    cases=list(ET.parse(root/str(index)/'f14-qa/targets/results/result.xml').iter('testcase'))
    assert len(cases)==len(selected)
    counts=collections.Counter()
    for case in cases:
        assert case.find('error') is None and case.find('skipped') is None
        failure=case.find('failure');counts['FAIL' if failure is not None else 'PASS']+=1
        if failure is None:continue
        matches=[n for n in selected if n.endswith('::'+case.get('name')) and case.get('classname','').startswith(n.split('.py::')[0].replace('/','.'))]
        assert len(matches)==1
        node=matches[0];text=failure.text or '';message=failure.get('message','')
        group,assessment,reason=classify(node,text,message)
        rows.append({'nodeid':node,'partition':index,'seconds':float(case.get('time',0)),
            'group':group,'assessment':assessment,'reason':reason,'message':message[:500],
            'trace_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'trace_source':f'{index}/f14-qa/targets/results/result.xml'})
    partitions.append({'partition':index,**counts});totals.update(counts)
assert seen==set(allnodes) and totals=={'PASS':2204,'FAIL':240} and len(rows)==240
counts=collections.Counter(row['group'] for row in rows)
result={'source':summary['source'],'run':41194643144,'artifact':13044081687,
    'artifact_sha256':'7838e1590c892d24deb7a071276353ec35447e985c98b42da050806eacf6b996',
    'status':'FULL_FAILURE_INVENTORY_INITIAL_CAUSAL_TRIAGE_NOT_ACCEPTANCE','counts':dict(totals),
    'partitions':partitions,'deadline_nodes':sorted(timeouts),'groups':dict(sorted(counts.items())),
    'failures':sorted(rows,key=lambda r:r['nodeid'])}
(out/'BACKEND-FAILURES.json').write_text(json.dumps(result,indent=2)+'\n')
report=['# Backend 41194643144 – vollständiges Fehlerinventar, erste Ursachenklassifikation','',
 'Alle acht Partitionen und alle2444 JUnit-Fälle geprüft:2204 PASS,240 FAIL,0 ERROR/SKIP.',
 'Jeder rote Node besitzt unten Gruppe, Prüfstatus und SHA256 seines vollständigen Originaltrace.',
 'Die Zuordnung ist eine erste Triage. REQUIRES/MIXED/SUSPECT sind ausdrücklich noch keine nachgewiesene Ursache oder veraltete Erwartung. Keine roten Tests gelten damit als erledigt.','',
 '| Gruppe | Fälle |','|---|---:|']
report += [f'| {group} | {count} |' for group,count in sorted(counts.items())]
report += ['', '## Nachgewiesene gemeinsame Ursachen', '',
 '1. Zwölf Fälle: schema_versions wird auch bei aktuellem Schema per CREATE TABLE IF NOT EXISTS angefragt. SQLite verlangt dafür DDL-Autorisierung. Bestehende Versionsdaten müssen rein lesend geprüft werden; echte Migrationen bleiben schreibgeschützt.',
 '2. Neunzehn RC11-Fixtures erstellen eine Registry erst nach Veröffentlichung ihres simulierten Orphans. Der Snapshot muss das schon vorher vorbereitete Schema enthalten; kein Laufzeit-Bypass.',
 '3. Sechs negative Fixtures versuchen externe Beschädigung über geschützte App-Verbindungen. Für einen echten negativen Recoverytest muss diese Beschädigung explizit nur in synthetischen Testdaten aufgebaut werden; die App-Barriere bleibt erhalten.',
 '4. Zwei Deadlines sind belegt. Beim3892-Dateien-Fall wird SIGALRM im SQLite-Authorizer verschluckt und als not authorized gemeldet (374,859s bei300s). Keine pauschale Autorisierungsfreigabe und keine pauschale Deadline-Erhöhung.',
 '5. Backup-/Trash-/Restore-/Import-Recovery erreicht teilweise ihre Qualifikation nicht, weil die neue allgemeine Eintrittssperre schon davor greift. Sichere Lösung benötigt exakte ursprüngliche Reservationsidentität und geprüften Wirkungsbereich; keine globale Recovery-Freigabe.',
 '', '## Nachweise und Grenzen','',
 'Das vollständig heruntergeladene ZIP hat248983932 Bytes und seinen GitHub-SHA256 erfüllt. Es enthält51527 Einträge mit rund16,46GB unkomprimierten Daten. JUnit, alle vollständigen stdout-Protokolle, Deadlines, Node-Manifeste und Ergebnis-JSONs wurden gezielt extrahiert; sämtliche weiteren Snapshots bleiben unverändert im ZIP verfügbar.',
 'Veröffentlichung gesperrt. Der vorbereitete Publisher muss dieses große Archiv später ebenfalls begrenzt nach Pflichtnachweisen entpacken; seine bisherige300MB-Gesamtgrenze darf nicht blind aufgehoben werden.',
 '', '## Alle240 fehlgeschlagenen Nodes','']
for row in result['failures']:
    report += [f"- `{row['nodeid']}` — P{row['partition']}; **{row['group']}**; {row['assessment']}; Trace `{row['trace_sha256']}`."]
(out/'BACKEND-FAILURES.md').write_text('\n'.join(report)+'\n')
print(json.dumps({'counts':result['counts'],'groups':result['groups'],'deadline_nodes':result['deadline_nodes']},indent=2))
