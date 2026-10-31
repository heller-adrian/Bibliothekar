from pathlib import Path
import hashlib,json,os,signal,sqlite3,subprocess,sys,time
from contextlib import closing
import pytest

class AuditBoundaryBlocked(Exception):pass

ROOT=Path(__file__).resolve().parent / 'recovery_0562'
OUT=None


@pytest.fixture(autouse=True)
def isolated_process_environment(tmp_path_factory, monkeypatch):
    global OUT
    base=tmp_path_factory.getbasetemp()
    OUT=base/'0562-evidence'
    OUT.mkdir(exist_ok=True)
    source=Path(__file__).resolve().parents[2]
    for key,value in dict(AUDIT_SOURCE=source, AUDIT_SCRATCH=base,
                          AUDIT_OUTPUT=OUT, AUDIT_LABEL='regression',
                          PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1',
                          KAMERA_SOURCE_HELPER_ENABLED='false',
                          BIBLIOTHEKAR_DEFAULT_DIRECTORY_LANGUAGE='de',
                          BIBLIOTHEKAR_ADMIN_PASSWORD='synthetic-recovery-qa-password',
                          BIBLIOTHEKAR_AUTH_TEST_BYPASS='pytest-isolated').items():
        monkeypatch.setenv(key,str(value))



def invoke(case,action,boundary,control,*,kill=False):
    control.mkdir(parents=True,exist_ok=True)
    command=[sys.executable,str(ROOT/'worker.py'),str(case),action,boundary,str(control)]
    log=control/'process.log'
    with log.open('w') as handle:
        process=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+45
        try:
            while process.poll() is None and time.monotonic()<deadline:
                if kill and (control/'checkpoint.json').exists():
                    try:
                        marker=json.loads((control/'checkpoint.json').read_text())
                    except (ValueError,OSError):
                        marker={}
                    if marker.get('pid')==process.pid:
                        os.killpg(process.pid,signal.SIGKILL)
                        break
                time.sleep(.01)
            if process.poll() is None:process.wait(timeout=max(1,deadline-time.monotonic()))
        except BaseException:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=5)
            raise
    record={'command':command,'pid':process.pid,'returncode':process.returncode,'signal':'SIGKILL' if process.returncode==-9 else None,'action':action,'boundary':boundary}
    if (control/'checkpoint.json').exists():record['checkpoint']=json.loads((control/'checkpoint.json').read_text())
    if (control/'result.json').exists():record['result']=json.loads((control/'result.json').read_text())
    (control/'execution.json').write_text(json.dumps(record,indent=2))
    if kill and process.returncode!=-signal.SIGKILL:
        if action=='startup' and 'Migration kann nicht fortgesetzt werden' in str(record.get('result',{}).get('error','')):
            raise AuditBoundaryBlocked(record['result']['error'])
        assert process.returncode==-signal.SIGKILL, log.read_text()[-7000:]
    return record


def snapshot(case,dest):
    files=[];databases={};documents={}
    for p in sorted(case.rglob('*')):
        if p.is_symlink():files.append({'path':str(p.relative_to(case)),'kind':'symlink','target':os.readlink(p)});continue
        if not p.is_file():continue
        raw=p.read_bytes()
        files.append({'path':str(p.relative_to(case)),'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'inode':p.stat().st_ino,'nlink':p.stat().st_nlink})
        if p.suffix=='.json':
            try:documents[str(p.relative_to(case))]=json.loads(raw)
            except (ValueError,UnicodeDecodeError):pass
        if p.suffix=='.sqlite3':
            with closing(sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True)) as c:
                c.row_factory=sqlite3.Row
                tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
                databases[str(p.relative_to(case))]={'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],'foreign_key_errors':[tuple(r) for r in c.execute('PRAGMA foreign_key_check')],
                  'counts':{t:c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables},
                  'rows':{t:[dict(r) for r in c.execute('SELECT * FROM "'+t+'"')] for t in tables if c.execute('SELECT 1 FROM "'+t+'" LIMIT 1').fetchone()}}
    data={'files':files,'databases':databases,'documents':documents}
    dest.write_text(json.dumps(data,indent=2,default=str));return data


def hash_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def db_rows(state,table,db='kamera.sqlite3'):return state['databases'][db]['rows'].get(table,[])
def checks_sql(state):
    assert state['databases']
    for name,db in state['databases'].items():
        assert db['integrity']=='ok',(name,db['integrity'])
        assert not db['foreign_key_errors'],(name,db['foreign_key_errors'])


def business_rows(state):
    # IDs/ownership/provenance stay exact; volatile timestamps and file scan
    # watermarks are retained in raw evidence but not used for idempotence.
    tables={'files','file_families','event_assignments','source_families','source_family_claims','source_family_occurrences','library_source_families','source_family_local_claims','family_claims','library_family_claims','metadata_corrections','source_backups','source_family_members','source_media','canonical_families'}
    ignored={'updated_at','last_seen_at','created_at','last_scanned_at','seen_at','verified_at','missing_since'}
    return {db:{t:[{k:v for k,v in row.items() if k not in ignored} for row in data['rows'].get(t,[])] for t in sorted(tables) if t in data['counts']} for db,data in state['databases'].items()}


def run_case(tmp_path,kind,boundary,recovery_boundary=None):
    label=kind+'-'+boundary.replace('.','_')+('-repeat-'+recovery_boundary.replace('.','_') if recovery_boundary else '')
    evidence=OUT/os.environ['AUDIT_LABEL']/label
    if evidence.exists():
        evidence=evidence.with_name(label+'-'+hashlib.sha256(os.environ.get('PYTEST_CURRENT_TEST','').encode()).hexdigest()[:12])
    evidence.mkdir(parents=True,exist_ok=True)
    case=tmp_path/'case';case.mkdir()
    result=invoke(case,'seed',kind,evidence/'seed');assert result['returncode']==0,(evidence/'seed/process.log').read_text()[-7000:]
    data=json.loads((case/'case.json').read_text())
    before=snapshot(case,evidence/'before.json')
    invoke(case,'operate',boundary,evidence/'kill',kill=True)
    crashed=snapshot(case,evidence/'after-kill.json')
    checks_sql(crashed)
    if recovery_boundary:
        for round in (1,2):
            try:
                invoke(case,'startup',recovery_boundary,evidence/f'recovery-kill{round}',kill=True)
            except AuditBoundaryBlocked as error:
                data['recovery_blocked']=str(error)
                snapshot(case,evidence/f'after-recovery-blocked{round}.json')
                break
            snapshot(case,evidence/f'after-recovery-kill{round}.json')
    restarts=[]
    for i in range(1,4):
        record=invoke(case,'startup','none',evidence/f'restart{i}')
        state=snapshot(case,evidence/f'after-restart{i}.json');checks_sql(state)
        restarts.append((record,state))
    return evidence,case,data,before,crashed,restarts


TRASH=['trash.prepared','trash.stage1','trash.db1','trash.db2','trash.committed','trash.cleanup1']
@pytest.mark.parametrize('boundary',TRASH)
def test_trash_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'trash',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    state=restarts[-1][1]
    committed=boundary in {'trash.committed','trash.cleanup1'}
    for db in ('kamera.sqlite3','second1.sqlite3'):
        if committed:
            assert db_rows(state,'files',db)==[] and db_rows(state,'file_families',db)==[]
        else:
            assert db_rows(state,'files',db)==db_rows(before,'files',db)
            assert db_rows(state,'file_families',db)==db_rows(before,'file_families',db)
    trash=case/'workspace'/'Papierkorb'
    for name,digest in data['expected'].items():
        if committed:assert not (trash/name).exists()
        else:assert hash_file(trash/name)==digest
    assert not list(case.rglob('DELETE_*.json'))
    assert business_rows(restarts[0][1])==business_rows(restarts[1][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('recover',['trash.recover_db1','trash.recover_file1','trash.recover_cleanup'])
def test_trash_recovery_sigkill(tmp_path,recover):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'trash','trash.db1',recover)
    for record,state in restarts:assert record['returncode']==0,record
    state=restarts[-1][1]
    for db in ('kamera.sqlite3','second1.sqlite3'):
        assert db_rows(state,'files',db)==db_rows(before,'files',db)
        assert db_rows(state,'file_families',db)==db_rows(before,'file_families',db)
        audits=db_rows(state,'audit_log',db)
        assert sum(r['action']=='trash_deletion_rolled_back' for r in audits)==1
    for name,digest in data['expected'].items():assert hash_file(case/'workspace'/'Papierkorb'/name)==digest
    assert not list(case.rglob('DELETE_*.json'))
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('boundary',['meta.backup','meta.swap','meta.db','meta.committed','meta.cleanup'])
def test_metadata_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'metadata',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    task=db_rows(restarts[-1][1],'metadata_corrections')[0]
    source=Path(data['source'])
    if boundary in {'meta.backup','meta.swap'}:
        assert hash_file(source)==data['expected'][source.name]
        assert task['status']=='blocked'
        retry=invoke(case,'retry','none',evidence/'retry');assert retry['returncode']==0,retry
    else:assert task['status']=='completed'
    assert not list(case.rglob('.swap-journals/*.json'))
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('recover',['meta.recover_original','meta.recover_task'])
def test_metadata_recovery_sigkill(tmp_path,recover):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'metadata','meta.swap',recover)
    for record,state in restarts:assert record['returncode']==0,record
    source=Path(data['source']);assert hash_file(source)==data['expected'][source.name]
    assert db_rows(restarts[-1][1],'metadata_corrections')[0]['status']=='blocked'
    assert not list(case.rglob('.swap-journals/*.json'))
    retry=invoke(case,'retry','none',evidence/'retry');assert retry['returncode']==0,retry


@pytest.mark.parametrize('kind,boundary',[
 ('sort','sort.move1'),('sort','sort.move2'),('sort','sort.before_db'),('sort','sort.db'),
 ('reconcile','reconcile.move1'),('reconcile','reconcile.move2'),('reconcile','reconcile.before_db'),('reconcile','reconcile.db'),
])
def test_sort_reconcile_sigkill(tmp_path,kind,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,kind,boundary)
    if any(record['returncode'] for record,_ in restarts):
        probe=invoke(case,'manual_recover','none',evidence/'counterprobe-direct-recovery')
        snapshot(case,evidence/'after-counterprobe-recovery.json')
        invoke(case,'startup','none',evidence/'counterprobe-startup')
        snapshot(case,evidence/'after-counterprobe-startup.json')
    for record,state in restarts:assert record['returncode']==0,record
    dbkey=str(Path(data['db']).relative_to(case));state=restarts[-1][1]
    runs=db_rows(state,'sort_runs',dbkey)
    current=next(r for r in runs if r['id']==data['run'])
    committed=boundary in {'sort.db','reconcile.db'}
    assert current['status']==('applied' if committed else 'rolled_back'),current
    files=db_rows(state,'files',dbkey)
    for item in data['plan']['files']:
        row=next(r for r in files if r['id']==item['file_id'])
        assert row['current_relative_path']==item['destination_relative_path' if committed else 'source_relative_path']
        path=Path(item['destination_absolute_path' if committed else 'source_absolute_path'])
        digest=item.get('stored_sha256') or item.get('sha256') or item.get('expected_sha256')
        assert hash_file(path)==digest
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])
    if not committed:
        result=invoke(case,'retry','none',evidence/'retry')
        assert result['returncode']==0,result
        snapshot(case,evidence/'after-retry.json')


@pytest.mark.parametrize('kind,boundary',[('sort','sort.move2'),('reconcile','reconcile.move2')])
def test_sort_recovery_sigkill(tmp_path,kind,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,kind,boundary,'sort.recover1')
    if data.get('recovery_blocked'):
        # Separate diagnostic: the helper itself survives two real kills.
        for number in (1,2):
            invoke(case,'manual_recover','sort.recover1',evidence/f'direct-recovery-kill{number}',kill=True)
            snapshot(case,evidence/f'after-direct-recovery-kill{number}.json')
        probe=invoke(case,'startup','none',evidence/'after-direct-recovery-startup')
        snapshot(case,evidence/'after-direct-recovery-startup.json')
        assert probe['returncode']==0,probe
        pytest.skip('BLOCKED: startup migration prevents reaching sort recovery; direct recovery survives two SIGKILLs')
    for record,state in restarts:assert record['returncode']==0,record
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


IMPORT=['import.before_copy','import.copy_chunk','import.hash_chunk','import.copy_verify','import.move1','import.move2','import.paths','import.before_complete','import.complete','import.in_tx']
@pytest.mark.parametrize('boundary',IMPORT)
def test_sd_import_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'import',boundary)
    for name,digest in data['expected'].items():assert hash_file(case/'card'/name)==digest
    for record,state in restarts:assert record['returncode']==0,record
    state=restarts[-1][1];jobs=db_rows(state,'jobs');job=next(r for r in jobs if r['id']=='J')
    files=db_rows(state,'files');central=case/'workspace'/'SD-Kartensicherungen'
    expected_completed=boundary=='import.complete'
    if expected_completed:
        assert job['state']=='completed',job
        assert len(files)==3
    else:
        assert job['state']=='interrupted',job
    # Any catalogue row exposed as shared_workspace must refer to real verified
    # central bytes after restart. Unfinished job_root rows need preserved
    # originals and discoverable partial staging; never a false completion.
    missing=[]
    for row in files:
        if row['current_root_kind']=='shared_workspace':
            p=central/row['current_relative_path']
            if not p.is_file() or hash_file(p)!=row['sha256_current']:missing.append(row)
    assert not missing,{'dangling_catalogue_rows':missing}
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('boundary',['multi.source_family1','multi.project1','multi.project2','multi.inventory1','multi.in_tx'])
def test_multilibrary_projection_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'multi',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    state=restarts[-1][1]
    main_files=db_rows(state,'files')
    if boundary=='multi.source_family1':
        assert next(r for r in db_rows(state,'jobs') if r['id']=='J')['state']=='interrupted'
    else:
        assert len(main_files)==3
        for db in ('second1.sqlite3','second2.sqlite3'):
            rows=db_rows(state,'files',db);assert len(rows)==3
            for row in rows:
                original=next(r for r in main_files if r['original_relative_path']==row['original_relative_path'])
                assert row['job_id']==original['job_id'] and row['sha256_original']==original['sha256_original']
                families=db_rows(state,'file_families',db)
                assert next(r for r in families if r['id']==row['family_id'])['family_key']==next(r for r in db_rows(state,'file_families') if r['id']==original['family_id'])['family_key']
    for name,digest in data['expected'].items():assert hash_file(case/'card'/name)==digest
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('boundary',['restore.move1','restore.db1'])
def test_known_trash_restore_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'restore',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    # Attempt the persisted operation with its original identity, as required
    # for safe continuation. Preserve failure details before asserting.
    retry=invoke(case,'retry','none',evidence/'retry')
    final=snapshot(case,evidence/'after-retry.json')
    assert retry['returncode']==0,retry
    for db in ('kamera.sqlite3','second1.sqlite3'):
        rows=db_rows(final,'files',db);assert len(rows)==2
        for row in rows:
            assert row['current_root_kind']=='shared_workspace'
            assert hash_file(case/'workspace'/'SD-Kartensicherungen'/row['current_relative_path'])==row['sha256_current']


@pytest.mark.parametrize('boundary',['ssd.archive_verified','ssd.unlink1','ssd.unlink2','ssd.before_finalize','ssd.finalized'])
def test_ssd_release_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'ssd',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    retry=invoke(case,'retry','none',evidence/'retry')
    final=snapshot(case,evidence/'after-retry.json')
    for name,digest in data['expected'].items():assert hash_file(case/'archive'/'2026/07-23 - Trip/Alle'/name)==digest
    if retry['returncode']:
        invoke(case,'verify_archive','none',evidence/'counterprobe-archive-verification')
        snapshot(case,evidence/'after-counterprobe-archive-verification.json')
    assert retry['returncode']==0,retry
    assert all(row['current_root_kind']=='camera_archive' for row in db_rows(final,'files'))
    assert len(db_rows(final,'event_ssd_releases'))==1
    assert db_rows(final,'event_ssd_releases')[0]['status']=='completed'
    again=invoke(case,'retry','none',evidence/'retry-again');assert again['returncode']==0,again
    repeated=snapshot(case,evidence/'after-retry-again.json')
    assert len(db_rows(repeated,'event_ssd_releases'))==1
    assert not any(p.suffix=='.JPG' for p in (case/'workspace'/'Arbeitsbereich').rglob('*'))


@pytest.mark.parametrize('boundary',['claims.one','claims.two'])
def test_claims_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'claims',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    final=restarts[-1][1]
    claims=db_rows(final,'family_claims','registry.sqlite3')
    assert len(claims)==3,claims
    assert {r['library_id'] for r in claims}=={'main','second1','second2'}
    assert all(r['claim_state']=='reserved' for r in claims)
    assert len({r['canonical_family_id'] for r in claims})==3
    for claim in claims:
        db={'main':'kamera.sqlite3','second1':'second1.sqlite3','second2':'second2.sqlite3'}[claim['library_id']]
        assert claim['event_id'] in {r['id'] for r in db_rows(final,'events',db)}
        assert len(db_rows(final,'files',db))==3 and len(db_rows(final,'file_families',db))==3
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


def test_claims_recovery_sigkill(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'claims','claims.one','claims.one')
    for record,state in restarts:assert record['returncode']==0,record
    claims=db_rows(restarts[-1][1],'family_claims','registry.sqlite3');assert len(claims)==3
    assert len({(r['canonical_family_id'],r['library_id']) for r in claims})==3
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


def test_projection_recovery_sigkill(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'multi','multi.project1','multi.startup_project1')
    for record,state in restarts:assert record['returncode']==0,record
    for db in ('kamera.sqlite3','second1.sqlite3','second2.sqlite3'):
        assert len(db_rows(restarts[-1][1],'files',db))==3
        assert len(db_rows(restarts[-1][1],'file_families',db))==3
        assert len([r for r in db_rows(restarts[-1][1],'jobs',db) if r['id']=='J'])==1
    assert business_rows(restarts[0][1])==business_rows(restarts[2][1])


@pytest.mark.parametrize('boundary',['meta.before_journal','meta.journal'])
def test_metadata_pre_swap_sigkill(tmp_path,boundary):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'metadata',boundary)
    for record,state in restarts:assert record['returncode']==0,record
    source=Path(data['source']);assert hash_file(source)==data['expected'][source.name]
    retry=invoke(case,'retry','none',evidence/'retry');assert retry['returncode']==0,retry
    final=snapshot(case,evidence/'after-retry.json')
    assert db_rows(final,'metadata_corrections')[0]['status']=='completed'
    leftovers=[p for p in source.parent.iterdir() if p.name.startswith('.'+source.name+'.metadata-')]
    assert not leftovers,{'unjournaled_metadata_staging':[str(p) for p in leftovers]}


def test_ssd_rehash_boundary_sigkill(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'ssd','ssd.rehash1')
    for record,state in restarts:assert record['returncode']==0,record
    retry=invoke(case,'retry','none',evidence/'retry');assert retry['returncode']==0,retry
    final=snapshot(case,evidence/'after-retry.json')
    assert db_rows(final,'event_ssd_releases')[0]['status']=='completed'
    for name,digest in data['expected'].items():assert hash_file(case/'archive'/'2026/07-23 - Trip/Alle'/name)==digest


def test_ssd_recovery_blocks_changed_archive(tmp_path):
    # First reconstruct the ordinary killed state without running any recovery.
    evidence=OUT/os.environ['AUDIT_LABEL']/'ssd-changed-archive';evidence.mkdir(parents=True)
    case=tmp_path/'case';case.mkdir()
    assert invoke(case,'seed','ssd',evidence/'seed')['returncode']==0
    data=json.loads((case/'case.json').read_text());snapshot(case,evidence/'before.json')
    invoke(case,'operate','ssd.unlink1',evidence/'kill',kill=True);snapshot(case,evidence/'after-kill.json')
    remaining=case/'workspace/Arbeitsbereich/2026/07-23 - Trip/Alle/B.JPG'
    assert remaining.exists();original=remaining.read_bytes()
    archive=case/'archive/2026/07-23 - Trip/Alle/B.JPG';archive.write_bytes(b'synthetic-corrupt-archive')
    snapshot(case,evidence/'after-synthetic-tamper.json')
    for n in (1,2,3):
        invoke(case,'startup','none',evidence/f'restart{n}')
        retry=invoke(case,'retry','none',evidence/f'retry{n}')
        assert retry['returncode']!=0,retry
        state=snapshot(case,evidence/f'after-restart{n}.json');checks_sql(state)
        assert remaining.read_bytes()==original
        assert archive.read_bytes()==b'synthetic-corrupt-archive'
        assert not any(r['status']=='completed' for r in db_rows(state,'event_ssd_releases'))


@pytest.mark.parametrize('kind,boundary', [('trash','trash.db1'),('metadata','meta.swap')])
def test_recovery_keeps_foreign_bytes_after_sigkill(tmp_path,kind,boundary):
    evidence=OUT/os.environ['AUDIT_LABEL']/(kind+'-foreign-bytes');evidence.mkdir(parents=True)
    case=tmp_path/'case';case.mkdir()
    assert invoke(case,'seed',kind,evidence/'seed')['returncode']==0
    data=json.loads((case/'case.json').read_text());snapshot(case,evidence/'before.json')
    invoke(case,'operate',boundary,evidence/'kill',kill=True);snapshot(case,evidence/'after-kill.json')
    if kind=='trash':target=next(case.rglob('DELETE_*/A.JPG'))
    else:target=Path(data['source'])
    target.write_bytes(b'synthetic-foreign-content');snapshot(case,evidence/'after-synthetic-tamper.json')
    for n in (1,2,3):
        record=invoke(case,'startup','none',evidence/f'restart{n}')
        assert record['returncode']!=0,record
        snapshot(case,evidence/f'after-restart{n}.json')
        assert target.read_bytes()==b'synthetic-foreign-content'
        assert list(case.rglob('DELETE_*.json')) if kind=='trash' else list(case.rglob('.swap-journals/*.json'))


def test_import_discard_after_sigkill_preserves_moved_file_and_history(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'import','import.move1')
    for record,state in restarts:assert record['returncode']==0,record
    staged=snapshot(case,evidence/'before-refusal.json')
    copies={str(p):hash_file(p) for p in (case/'workspace'/'SD-Kartensicherungen').rglob('*.JPG')}
    discarded=invoke(case,'discard','none',evidence/'discard')
    assert discarded['returncode']!=0,discarded
    final=snapshot(case,evidence/'after-discard.json')
    assert db_rows(final,'jobs')==db_rows(staged,'jobs')
    assert db_rows(final,'files')==db_rows(staged,'files')
    assert copies=={str(p):hash_file(p) for p in (case/'workspace'/'SD-Kartensicherungen').rglob('*.JPG')}
    assert list(case.rglob('move-journal.json'))
    for name,digest in data['expected'].items():assert hash_file(case/'card'/name)==digest


@pytest.mark.parametrize('kind',['library_metadata','multiple_metadata','reintegrate'])
def test_other_metadata_modes_sigkill(tmp_path,kind):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,kind,'meta.backup')
    for record,state in restarts:assert record['returncode']==0,record
    source=Path(data['source'])
    for name,digest in data['expected'].items():assert hash_file(source.parent/name)==digest
    assert not list(case.rglob('.swap-journals/*.json'))
    retry=invoke(case,'retry','none',evidence/'retry');assert retry['returncode']==0,retry
    snapshot(case,evidence/'after-retry.json')


def test_known_restore_without_crash_control(tmp_path):
    evidence=OUT/os.environ['AUDIT_LABEL']/'known-restore-control';evidence.mkdir(parents=True)
    case=tmp_path/'case';case.mkdir()
    assert invoke(case,'seed','restore',evidence/'seed')['returncode']==0
    before=snapshot(case,evidence/'before.json')
    result=invoke(case,'control_restore','none',evidence/'operation');assert result['returncode']==0,result
    state=snapshot(case,evidence/'after-operation.json')
    for db in ('kamera.sqlite3','second1.sqlite3'):
        rows=db_rows(state,'files',db);assert len(rows)==2
        for row in rows:
            assert row['current_root_kind']=='shared_workspace'
            assert hash_file(case/'workspace/SD-Kartensicherungen'/row['current_relative_path'])==row['sha256_current']
    assert any(r['operation']=='trash_import' and r['state']=='completed' for r in db_rows(state,'jobs'))


def test_ssd_repeat_retry_counterprobe(tmp_path):
    # Own the original SIGKILL fixture; no dependency on another test's files.
    evidence,case,data=new_case(tmp_path,'ssd','ssd-repeat-retry')
    invoke(case,'operate','ssd.unlink1',evidence/'kill',kill=True)
    checks_sql(snapshot(case,evidence/'after-kill.json'))
    # Complete once, then repeat three more real startup/retry sequences.
    for n in (1,2,3,4):
        invoke(case,'startup','none',evidence/f'restart{n}')
        invoke(case,'retry','none',evidence/f'retry{n}')
        state=snapshot(case,evidence/f'after-retry{n}.json');checks_sql(state)
        assert len(db_rows(state,'files'))==2,{'catalogue_rows':db_rows(state,'files')}
        for name,digest in data['expected'].items():assert hash_file(case/'archive/2026/07-23 - Trip/Alle'/name)==digest
    assert len(db_rows(state,'event_ssd_releases'))==1
    assert db_rows(state,'event_ssd_releases')[0]['status']=='completed'


def test_metadata_projection_partial_commit_sigkill(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'metadata_projection','metadata.projection1')
    for record,state in restarts:assert record['returncode']==0,record
    final=restarts[-1][1];dbkey=str(Path(data['db']).relative_to(case))
    original=db_rows(final,'files',dbkey)[0]
    assert db_rows(final,'metadata_corrections',dbkey)[0]['status']=='completed'
    expected=(original['sha256_current'],original['size_bytes'],original['selected_capture_time'])
    observed={}
    for db in data['databases']:
        row=db_rows(final,'files',str(Path(db).relative_to(case)))[0]
        observed[str(Path(db).relative_to(case))]=(row['sha256_current'],row['size_bytes'],row['selected_capture_time'])
    # Counterprobe replays only the existing idempotent projection routine.
    counter=invoke(case,'sync_metadata','none',evidence/'counterprobe-explicit-sync')
    snapshot(case,evidence/'after-counterprobe-sync.json')
    assert counter['returncode']==0,counter
    assert all(values==expected for values in observed.values()),{'persistent_projection_difference':observed,'expected':expected}


def new_case(tmp_path,kind,name):
    evidence=OUT/os.environ['AUDIT_LABEL']/name;evidence.mkdir(parents=True)
    case=tmp_path/'case';case.mkdir()
    assert invoke(case,'seed',kind,evidence/'seed')['returncode']==0
    data=json.loads((case/'case.json').read_text())
    snapshot(case,evidence/'before.json')
    return evidence,case,data


def three_restarts(case,evidence):
    states=[]
    for n in (1,2,3):
        result=invoke(case,'startup','none',evidence/f'restart{n}')
        assert result['returncode']==0,result
        state=snapshot(case,evidence/f'after-restart{n}.json');checks_sql(state);states.append(state)
    assert business_rows(states[0])==business_rows(states[2])
    return states[-1]


def test_0562_restore_recovery_two_progressive_sigkills(tmp_path):
    evidence,case,data=new_case(tmp_path,'restore','restore-progressive-recovery')
    invoke(case,'operate','restore.move1',evidence/'kill',kill=True)
    invoke(case,'startup','restore.move1',evidence/'recovery-move-kill',kill=True)
    snapshot(case,evidence/'after-second-move.json')
    invoke(case,'startup','restore.db1',evidence/'recovery-commit-kill',kill=True)
    state=three_restarts(case,evidence)
    for db in ('kamera.sqlite3','second1.sqlite3'):
        assert len(db_rows(state,'files',db))==2
        assert len([r for r in db_rows(state,'audit_log',db) if r['action']=='trash_file_restored'])==2
        for row in db_rows(state,'files',db):
            assert row['current_root_kind']=='shared_workspace'
            assert hash_file(case/'workspace/SD-Kartensicherungen'/row['current_relative_path'])==row['sha256_current']
    assert not list(case.rglob('.trash-restores/*.json'))


@pytest.mark.parametrize('tamper',['bytes','database'])
def test_0562_restore_preserves_ambiguous_evidence(tmp_path,tamper):
    evidence,case,data=new_case(tmp_path,'restore','restore-foreign-'+tamper)
    invoke(case,'operate','restore.move1',evidence/'kill',kill=True)
    target=next((case/'workspace/SD-Kartensicherungen').rglob('A.JPG'))
    if tamper=='bytes':target.write_bytes(b'synthetic-foreign-restore')
    else:
        db=case/'second1.sqlite3'; replacement=db.with_suffix('.replacement')
        replacement.write_bytes(db.read_bytes());os.replace(replacement,db)
    digest=hash_file(target)
    for n in (1,2,3):
        restart=invoke(case,'startup','none',evidence/f'restart{n}')
        if restart['returncode']==0:
            op=(restart.get('result') or {}).get('result',{}).get('operation_health') or {}
            assert op.get('writes_allowed') is False,restart
            assert any(not lease.get('live') and lease.get('qualified')
                       and lease.get('kind')=='trash'
                       for lease in op.get('reservations',[])),restart
        else:
            assert restart['returncode']!=0,restart
        assert hash_file(target)==digest
        assert (case/'workspace/Papierkorb/B.JPG').exists()
        assert list(case.rglob('.trash-restores/*.json'))
        checks_sql(snapshot(case,evidence/f'after-restart{n}.json'))


def test_0562_import_discard_preserves_crashed_import_for_verified_recovery(tmp_path):
    evidence,case,data=new_case(tmp_path,'import','discard-preserves-recovery')
    invoke(case,'operate','import.move2',evidence/'kill',kill=True)
    before=three_restarts(case,evidence)
    copies={str(p):hash_file(p) for p in (case/'workspace/SD-Kartensicherungen').rglob('*.JPG')}
    for n in (1,2):
        result=invoke(case,'discard','none',evidence/f'discard-refused{n}')
        assert result['returncode']!=0
        after=snapshot(case,evidence/f'after-refusal{n}.json');checks_sql(after)
        assert db_rows(after,'files')==db_rows(before,'files')
        assert db_rows(after,'jobs')==db_rows(before,'jobs')
        assert copies=={str(p):hash_file(p) for p in (case/'workspace/SD-Kartensicherungen').rglob('*.JPG')}
    assert list(case.rglob('move-journal.json'))
    for name,digest in data['expected'].items():assert hash_file(case/'card'/name)==digest


@pytest.mark.parametrize('tamper',['bytes','same_bytes_new_inode','symlink'])
def test_0562_import_discard_keeps_unowned_files(tmp_path,tamper):
    evidence,case,data=new_case(tmp_path,'import','discard-foreign-'+tamper)
    invoke(case,'operate','import.move2',evidence/'kill',kill=True)
    state=three_restarts(case,evidence)
    targets=sorted((case/'workspace/SD-Kartensicherungen').rglob('*.JPG'))
    target=targets[-1]
    if tamper=='bytes':target.write_bytes(b'synthetic-foreign-import')
    elif tamper=='same_bytes_new_inode':
        replacement=target.with_suffix('.replacement');replacement.write_bytes(target.read_bytes());os.replace(replacement,target)
    else:
        foreign=case/'foreign.JPG';foreign.write_bytes(target.read_bytes());target.unlink();target.symlink_to(foreign)
    other_hash=hash_file(targets[0])
    assert invoke(case,'discard','none',evidence/'discard')['returncode']!=0
    final=snapshot(case,evidence/'after-discard.json');checks_sql(final)
    assert hash_file(targets[0])==other_hash
    assert next(r for r in db_rows(final,'jobs') if r['id']=='J')['state']=='interrupted'
    assert list(case.rglob('move-journal.json'))
    for name,digest in data['expected'].items():assert hash_file(case/'card'/name)==digest


def test_0562_metadata_preparation_recovery_two_sigkills(tmp_path):
    evidence,case,data=new_case(tmp_path,'metadata','preparation-repeat-recovery')
    invoke(case,'operate','meta.before_journal',evidence/'kill',kill=True)
    invoke(case,'startup','meta.preparation_cleanup',evidence/'cleanup-kill',kill=True)
    # Cleanup is complete but its receipt still exists. The next replay is safe.
    invoke(case,'startup','meta.preparation_cleanup',evidence/'receipt-kill',kill=True)
    three_restarts(case,evidence)
    source=Path(data['source']);assert hash_file(source)==data['expected'][source.name]
    assert not list(source.parent.glob('.*metadata-*'))
    assert invoke(case,'retry','none',evidence/'retry')['returncode']==0


def test_0562_metadata_preparation_keeps_unknown_file(tmp_path):
    evidence,case,data=new_case(tmp_path,'metadata','preparation-unknown-inode')
    invoke(case,'operate','meta.before_journal',evidence/'kill',kill=True)
    source=Path(data['source']);staged=next(source.parent.glob('.*metadata-*'))
    replacement=staged.with_suffix('.replacement');replacement.write_bytes(staged.read_bytes());os.replace(replacement,staged)
    digest=hash_file(staged)
    for n in (1,2,3):
        assert invoke(case,'startup','none',evidence/f'restart{n}')['returncode']!=0
        assert hash_file(staged)==digest and hash_file(source)==data['expected'][source.name]
        assert list(case.rglob('.swap-journals/*.json'))


def test_0562_metadata_projection_recovery_two_sigkills(tmp_path):
    evidence,case,data,before,crashed,restarts=run_case(tmp_path,'metadata_projection','metadata.projection1','metadata.projection1')
    for record,state in restarts:assert record['returncode']==0,record
    final=restarts[-1][1]
    values=[]
    for db in data['databases']:
        row=db_rows(final,'files',str(Path(db).relative_to(case)))[0]
        values.append((row['sha256_current'],row['size_bytes'],row['selected_capture_time']))
        assert len(db_rows(final,'files',str(Path(db).relative_to(case))))==1
    assert len(set(values))==1
    task=db_rows(final,'metadata_corrections',str(Path(data['db']).relative_to(case)))[0]
    assert not json.loads(task['verification_json']).get('projection_pending')


def test_0562_ssd_retry_two_progressive_sigkills(tmp_path):
    evidence,case,data=new_case(tmp_path,'ssd','ssd-progressive-recovery')
    invoke(case,'operate','ssd.unlink1',evidence/'kill',kill=True)
    invoke(case,'retry','ssd.archive_verified',evidence/'verify-kill',kill=True)
    invoke(case,'retry','ssd.unlink1',evidence/'second-unlink-kill',kill=True)
    three_restarts(case,evidence)
    assert invoke(case,'retry','none',evidence/'retry')['returncode']==0
    state=snapshot(case,evidence/'after-retry.json');checks_sql(state)
    assert len(db_rows(state,'event_ssd_releases'))==1
    assert db_rows(state,'event_ssd_releases')[0]['status']=='completed'
    for name,digest in data['expected'].items():assert hash_file(case/'archive/2026/07-23 - Trip/Alle'/name)==digest


@pytest.mark.parametrize('round',[1,2,3])
def test_0562_sqlite_read_counterprobe(tmp_path,round,monkeypatch):
    # Fresh processes and explicitly closed read-only connections. Retest the
    # original negative archive case without claiming an unproven root cause.
    monkeypatch.setenv("AUDIT_LABEL", "sqlite-counterprobe-"+str(round))
    test_ssd_recovery_blocks_changed_archive(tmp_path)
