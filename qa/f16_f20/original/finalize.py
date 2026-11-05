from pathlib import Path
import json,csv,shutil,subprocess,hashlib
O=Path('outputs/phase4').resolve();base=json.loads((O/'results-continuation2.json').read_text());rows=base['results']
selection={'eleventh':{0:'P401-live-restore-full',1:'P401-live-restore-selective',3:'P407-inventory-import-final',4:'P407-inventory-reconcile-final',5:'P407-inventory-ssd-final',6:'P408-duplicate-metadata-work',7:'P408-writing-metadata-rejected'},'twelfth':{0:'P404-metadata-batches-False',1:'P404-metadata-batches-True',4:'P401-restore-after-active-delete-verified'},'thirteenth':{0:'P404-reassign-new_event',1:'P404-reassign-new_no_event',2:'P404-cancel-after-reassignment'},'fourteenth':{1:'P403-rename-after-SSD-unlink-retry'},'fifteenth':{0:'P401-thread-restore-inventory-delete'},'sixteenth':{0:'P406-HTTP-secondary-ownership-deterministic',1:'P402-import-restore-identical-goal-verified'}}
for run,indexes in selection.items():
 tests=json.loads((O/(run+'-results.json')).read_text())['tests']
 for index,evidence in indexes.items():
  t=tests[index];rows.append({'test':t['nodeid'].split('::')[-1],'status':'PASS' if t['outcome']=='passed' else 'FAIL','evidence':evidence,'run':run})
assert len(rows)==45 and sum(r['status']=='PASS' for r in rows)==27,(len(rows),sum(r['status']=='PASS' for r in rows))
for r in rows:
 for f in ['before.json','interleaving.json','after-interleaving.json','after-restart1.json','after-restart2.json','after-restart3.json']:assert (O/r['evidence']/f).is_file(),(r,f)
 d=json.loads((O/r['evidence']/'after-restart3.json').read_text())
 assert all(x['integrity']=='ok' and not x['foreign_key_errors'] for x in d['databases'].values()),r
proof={'commit':base['commit'],'audit_status':'complete_with_findings_and_explicit_scope_limits','runtime_unique_cases':45,'PASS':27,'FAIL':18,'BLOCKED':0,'confirmed_groups':['F'+str(n) for n in range(11,21)],'availability_conflict_with_open_defect_classification':'R1','excluded_or_repeated_executions':13,'invalid_or_superseded_diagnostics':12,'valid_confirmation_repeats_not_counted_twice':1,'results':rows}
(O/'results-final.json').write_text(json.dumps(proof,indent=2))
with (O/'matrix-final.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['test','status','evidence','run']);w.writeheader();w.writerows({k:r.get(k,'earlier') for k in w.fieldnames} for r in rows)
lines=['# Phase 4 – vollständige konsolidierte Einzeltestmatrix','','45 eindeutige Laufzeitfälle: 27 PASS, 18 FAIL, 0 BLOCKED. Geltungsgrenzen und Fehlergruppen siehe Abschlussbericht. R1 ist FAIL der Verfügbarkeit bei erhaltener Dateisicherheit; Hardlink-PASS ist Charakterisierung.','','| Nr. | Fall | Status | Nachweis |','|---|---|---|---|']
for n,r in enumerate(rows,1):
 p=O/r['evidence'];links=' · '.join(f'[{label}]({p/file})' for label,file in [('Reihenfolge','interleaving.json'),('Vorher','before.json'),('Nachher','after-interleaving.json'),('Start 1','after-restart1.json'),('Start 2','after-restart2.json'),('Start 3','after-restart3.json')])
 lines.append(f"| {n} | `{r['test']}` / `{r['evidence']}` | {r['status']} | {links} |")
(O/'matrix-final.md').write_text('\n'.join(lines)+'\n')
T=O/'audit-tools-final';T.mkdir(exist_ok=True)
for name in ['launch.py','runner.py','guards.py','worker.py','worker_concurrent.py','test_process_crashes.py','test_interleavings.py','test_more.py','test_remaining.py','test_combinations.py','test_publication.py','test_completion.py','test_final_combinations.py','test_relational.py','test_mixed_queue.py','test_same_process_trash.py','finalize.py']:shutil.copyfile(Path('work/phase4')/name,T/name)
p=T/'launch.py';s=p.read_text();a=s.index('SOURCE=');b=s.index('for writable',a);p.write_text(s[:a]+"SOURCE=Path(os.environ['AUDIT_SOURCE_ROOT']).resolve()\nOUTPUT=Path(os.environ['AUDIT_RESULT_ROOT']).resolve()\nSCRATCH=Path(os.environ['AUDIT_SCRATCH_ROOT']).resolve()\n"+s[b:])
source=Path('work/patch-0562');assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==base['commit'];assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True)
(O/'source-verification-final.json').write_text(json.dumps({'commit':base['commit'],'git_status_porcelain':'','app_file_sha256':{str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source/'app').glob('*.py')}},indent=2))
# Compact new state summary without replacing any earlier evidence.
summary={}
for r in rows[28:]:
 d=json.loads((O/r['evidence']/'after-restart3.json').read_text())
 summary[r['evidence']]={'media':[v for v in d['files'] if v['path'].endswith(('.JPG','.XMP'))],'database_counts':{k:{t:v for t,v in db['counts'].items() if t in ['files','file_families','family_claims','event_assignments','sort_runs','event_ssd_releases','metadata_corrections','event_mutations']} for k,db in d['databases'].items()},'journals':{k:v for k,v in d['documents'].items() if 'journal' in k or 'trash-deletions' in k or 'trash-restores' in k}}
(O/'state-summary-final.json').write_text(json.dumps(summary,indent=2))
print('45 Fälle konsolidiert: 27 PASS / 18 FAIL. Quellbaum sauber.')
# Per-case classification and precise component references supplement the raw logs.
references={
 'P401':'app/main.py api_restore_trash:4972, api_empty_trash_selection:5024, api_empty_trash:5054; app/trash_selective.py _operation_lock:29; app/trash_restore.py restore_trash_files:281',
 'P402':'app/folder_import.py move_import_into_workspace:506; app/trash_restore.py _move_checked:60; app/main.py worker_loop:1993',
 'P403':'app/main.py api_set_storage_paths:2865; app/sort_apply.py execute_sort_run:1382; app/workspace_reconcile.py execute_workspace_reconcile_run:464; app/ssd_release.py release_event_ssd:837',
 'P404':'app/event_reapply.py prepare_reapply_sort_run:66; app/workspace_reconcile.py prepare_workspace_reconcile_run:415; app/event_mutation.py cancel_mutation:307; app/event_reassignment.py assign_event_reassignments:573; app/metadata_correction.py apply_multiple_metadata_correction:813; app/operation_batches.py execute_apply_batch:174',
 'P405':'app/ssd_release.py release_event_ssd:837; app/archive_staging.py _stage_verified_source:150',
 'P406':'app/library_registry.py claim_source_family:1577; app/global_stock.py propagate_corrected_family:204, migrate_main_free_stock_to_central:312; app/main.py api_create_event:6810, _sort_run_thread_target:7784',
 'P407':'app/main.py reconcile_global_central_stock_state:1006; app/central_stock_reconcile.py reconcile_central_free_stock:325; app/event_inventory.py scan_event_inventory:438',
 'P408':'app/database.py claim_next_job:734; app/main.py library_context_middleware:895, api_current_library:4020, api_restore_trash:4972; app/metadata_correction.py apply_metadata_correction:2213'
}
findings={'P401-full-empty-race':'F11','P402-target-True':'F12','P405-archive-unlink-race':'F13','P406-delayed-metadata':'F15','P407-inventory-sort':'F16','P407-public-inventory-sort-verified':'F16','P408-duplicate-metadata-work':'F17','P404-metadata-batches-False':'F18','P401-restore-after-active-delete-verified':'F19','P401-thread-restore-inventory-delete':'F19','P406-HTTP-secondary-ownership-deterministic':'F20','P402-restore-publication-collision':'R1'}
for r in rows:
 r['code_references']=references[r['evidence'][:4]]
 r['finding']='F14' if r['status']=='FAIL' and r['evidence'].startswith('P403') else findings.get(r['evidence'],'')
 r['classification']='reproduced_runtime_error_and_static_cause' if r['finding'].startswith('F') else ('observed_startup_block_defect_assessment_open' if r['finding']=='R1' else ('filesystem_property_only' if 'hardlink' in r['evidence'] else 'bounded_runtime_counterexample_pass'))
(O/'results-final.json').write_text(json.dumps(proof,indent=2))
with (O/'matrix-final.csv').open('w') as f:
 fields=['test','status','finding','classification','code_references','evidence','run'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r.get(k,'earlier') for k in fields} for r in rows)
lines=['# Phase 4 – konsolidierte Einzeltestmatrix','','45 eindeutige Laufzeitfälle: 27 PASS, 18 FAIL, 0 BLOCKED. Die Fehlerbewertung von R1 bleibt offen; Hardlink-PASS ist Eigenschaftsnachweis. Ein PASS gilt nur für das dokumentierte Interleaving.','','| Nr. | Fall | Status / Befund | Fundstellen und Nachweise |','|---|---|---|---|']
for n,r in enumerate(rows,1):
 links=' · '.join(f'[{label}]({r["evidence"]}/{file})' for label,file in [('Reihenfolge','interleaving.json'),('Vorher','before.json'),('Nachher','after-interleaving.json'),('Start 1','after-restart1.json'),('Start 2','after-restart2.json'),('Start 3','after-restart3.json')])
 lines.append(f"| {n} | `{r['test']}` / `{r['evidence']}` | {r['status']} {r['finding']} / `{r['classification']}` | {r['code_references']}; {links} |")
(O/'matrix-final.md').write_text('\n'.join(lines)+'\n')
shutil.copyfile(Path('work/phase4/finalize.py'),T/'finalize.py')
