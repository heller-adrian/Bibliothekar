"""R1: synthetic collision isolation, ownership receipts and real restarts."""
from contextlib import contextmanager
from pathlib import Path
import hashlib,json,os,threading
import pytest
from app import trash_restore as tr,trash_selective as ts,trash_import as ti,main
from app.trash import TrashError,empty_trash_filesystem
from app.database import database_connection,initialize_database,create_job
from app.library_context import resolve_library_context
from app.library_registry import register_library,ensure_library_identity
from tests.backend import test_0562_process_recovery as r
from tests.backend.test_0562_process_recovery import isolated_process_environment
from tests.backend.external_sql import external_edit


def seed(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();ev=tmp_path/'r1-evidence';ev.mkdir()
    for action,boundary in [('seed','trash'),('startup','none')]:assert r.invoke(case,action,boundary,ev/action)['returncode']==0
    data=json.loads((case/'case.json').read_text());data['dbs']=[Path(p) for p in data['databases']];ws=Path(data['workspace'])
    monkeypatch.setenv('KAMERA_CONFIG',str(case/'settings.json'))
    monkeypatch.setenv('KAMERA_WORKSPACE',str(ws))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(case/'registry.sqlite3'))
    context=resolve_library_context(case/'registry.sqlite3','main')
    for key,value in {'DATABASE_FILE':data['dbs'][0],'REGISTRY_DATABASE_FILE':case/'registry.sqlite3','WORKSPACE_PATH':ws,'MAIN_LIBRARY_CONTEXT':context,'LOG_PATH':case/'logs','DATABASE_INITIALIZATION_ERROR':None}.items():monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(main,'current_database_file',lambda:data['dbs'][0])
    r.snapshot(case,ev/'before.json');return case,ev,data,ws


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def journal(case):return next(case.rglob('.trash-restores/*.json'))

def starts(case,ev,blocked=False,label='restart'):
    states=[]
    for n in (1,2,3):
        record=r.invoke(case,'startup','none',ev/f'{label}{n}');assert (record['returncode']!=0)==blocked,record
        state=r.snapshot(case,ev/f'after-{label}{n}.json');r.checks_sql(state);states.append(state)
    assert r.business_rows(states[0])==r.business_rows(states[1])==r.business_rows(states[2])
    return states[-1]


def collision(data,ws,monkeypatch,kind='different',pause=None,operation_id=None):
    real=tr.os.link;seen=[]
    def link(src,dst,*args,**kw):
        if Path(src)==ws/'Papierkorb/A.JPG':
            dst=Path(dst);seen.append(dst)
            if kind=='same':dst.write_bytes(Path(src).read_bytes())
            elif kind=='hardlink':real(src,dst)
            elif kind=='symlink':dst.symlink_to(ws/'Papierkorb/A.JPG')
            elif kind=='directory':dst.mkdir();(dst/'foreign-member').write_bytes(b'foreign-member')
            else:dst.write_bytes(b'synthetic-foreign-target')
            if pause:pause()
        return real(src,dst,*args,**kw)
    monkeypatch.setattr(tr.os,'link',link)
    with pytest.raises(TrashError):tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG'],operation_id=operation_id)
    monkeypatch.setattr(tr.os,'link',real)
    assert seen;return seen[0]


def preserved(data,ws,target,kind='different'):
    assert digest(ws/'Papierkorb/A.JPG')==data['expected']['A.JPG']
    if kind=='symlink':assert target.is_symlink()
    elif kind=='directory':assert (target/'foreign-member').read_bytes()==b'foreign-member'
    else:assert target.read_bytes()==(b'synthetic-trash-A.JPG' if kind in {'same','hardlink'} else b'synthetic-foreign-target')
    for db in data['dbs']:
        with database_connection(db) as c:
            row=c.execute("SELECT * FROM files WHERE original_filename='A.JPG'").fetchone();assert row['current_root_kind']=='trash' and row['current_relative_path']=='A.JPG'
            assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='trash_file_restored' AND entity_id=?",(str(row['id']),)).fetchone()[0]==0


@pytest.mark.parametrize('kind',['different','same','hardlink','symlink','directory'])
def test_r1_collision_and_three_full_starts(tmp_path,monkeypatch,kind):
    case,ev,data,ws=seed(tmp_path,monkeypatch);source=ws/'Papierkorb/A.JPG';ident=tr._identity(source)
    target=collision(data,ws,monkeypatch,kind);before=tr._identity(target);record=journal(case);raw=record.read_bytes()
    assert json.loads(raw)['state']=='conflict';r.snapshot(case,ev/'after-conflict.json')
    starts(case,ev);preserved(data,ws,target,kind)
    assert tr._identity(source)==ident and tr._identity(target)==before and record.read_bytes()==raw
    conflicts=main.api_trash_inventory()['restore_conflicts'];assert len(conflicts)==1 and conflicts[0]['operation_id']==record.stem
    assert 'Ungeklärte Wiederherstellung; Details prüfen.' in main.TRASH_HTML
    assert 'Unresolved restore; review details.' in main.TRASH_HTML and 'status.textContent+=' in main.TRASH_HTML


@pytest.mark.parametrize('operation',['restore','queue','selective','full'])
def test_r1_conflict_reserves_source(tmp_path,monkeypatch,operation):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch);raw=journal(case).read_bytes()
    with pytest.raises(TrashError):
        if operation=='restore':tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG'])
        elif operation=='queue':ti.queue_trash_restore(data['dbs'][0],ws,['A.JPG'])
        elif operation=='selective':ts.delete_selected_trash_files(data['dbs'],ws,['A.JPG'])
        else:empty_trash_filesystem(ws)
    starts(case,ev);preserved(data,ws,target);assert journal(case).read_bytes()==raw


@pytest.mark.parametrize('operation',['restore','delete'])
def test_r1_independent_file_remains_usable(tmp_path,monkeypatch,operation):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch)
    if operation=='restore':assert tr.restore_trash_files(data['dbs'],ws,relative_paths=['B.JPG'])['restored_file_count']==1
    else:assert ts.delete_selected_trash_files(data['dbs'],ws,['B.JPG'])['deleted_file_count']==1
    state=starts(case,ev);preserved(data,ws,target)
    for db in ('kamera.sqlite3','second1.sqlite3'):
        b=[row for row in r.db_rows(state,'files',db) if row['original_filename']=='B.JPG']
        assert (len(b)==1 and b[0]['current_root_kind']=='shared_workspace') if operation=='restore' else b==[]
    assert len(main.api_trash_inventory()['restore_conflicts'])==1


@pytest.mark.parametrize('second',['restore_A','restore_B','selective_A','full'])
def test_r1_parallel_operation_boundary(tmp_path,monkeypatch,second):
    case,ev,data,ws=seed(tmp_path,monkeypatch);reached=threading.Event();release=threading.Event();attempt=threading.Event();results=[];other=[]
    real_link=tr.os.link;real_lock=ts._operation_lock;targets=[]
    def link(src,dst,*a,**kw):
        if Path(src)==ws/'Papierkorb/A.JPG':
            dst=Path(dst);dst.write_bytes(b'synthetic-foreign-target');targets.append(dst);reached.set();assert release.wait(15)
        return real_link(src,dst,*a,**kw)
    @contextmanager
    def lock(*a,**kw):
        if threading.current_thread().name=='second':attempt.set()
        with real_lock(*a,**kw):yield
    monkeypatch.setattr(tr.os,'link',link);monkeypatch.setattr(ts,'_operation_lock',lock)
    def first():
        try:results.append(tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG']))
        except Exception as e:results.append(e)
    def run():
        try:
            if second.startswith('restore'):other.append(tr.restore_trash_files(data['dbs'],ws,relative_paths=[second[-1]+'.JPG'],operation_id='R1_SECOND'))
            elif second=='selective_A':other.append(ts.delete_selected_trash_files(data['dbs'],ws,['A.JPG']))
            else:other.append(empty_trash_filesystem(ws))
        except Exception as e:other.append(e)
    a=threading.Thread(target=first);a.start();assert reached.wait(15)
    b=threading.Thread(target=run,name='second');b.start();assert attempt.wait(15);assert other==[]
    r.snapshot(case,ev/'second-waits-before-conflict.json');release.set();a.join(20);b.join(20);assert not a.is_alive() and not b.is_alive()
    assert isinstance(results[0],TrashError)
    assert isinstance(other[0],dict) if second=='restore_B' else isinstance(other[0],TrashError)
    monkeypatch.setattr(tr.os,'link',real_link);starts(case,ev);preserved(data,ws,targets[0])


@pytest.mark.parametrize('boundary',['r1.prepared','r1.rolling_back','r1.before_conflict','r1.after_conflict'])
def test_r1_collision_sigkill(tmp_path,monkeypatch,boundary):
    case,ev,data,ws=seed(tmp_path,monkeypatch);r.invoke(case,'r1_conflict',boundary,ev/'kill',kill=True);r.snapshot(case,ev/'after-kill.json')
    starts(case,ev)
    if boundary=='r1.prepared':
        assert not (ws/'Papierkorb/A.JPG').exists();assert not list(case.rglob('.trash-restores/*.json'))
        assert any(digest(p)==data['expected']['A.JPG'] for p in (ws/'SD-Kartensicherungen').rglob('A.JPG'))
    else:
        target=next((ws/'SD-Kartensicherungen').rglob('A.JPG'));preserved(data,ws,target);assert json.loads(journal(case).read_text())['state']=='conflict'


@pytest.mark.parametrize('boundary',['r1.before_conflict','r1.conflict_rechecked'])
def test_r1_recovery_sigkill_twice(tmp_path,monkeypatch,boundary):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch)
    if boundary=='r1.before_conflict':
        path=journal(case);record=json.loads(path.read_text());record['state']='rolling_back';record.pop('conflict_sources');path.write_text(json.dumps(record))
    for n in (1,2):r.invoke(case,'startup',boundary,ev/f'recovery-kill{n}',kill=True);r.snapshot(case,ev/f'after-recovery-kill{n}.json')
    starts(case,ev);preserved(data,ws,target)


def test_r1_owned_receipt_sigkill(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path,monkeypatch);r.invoke(case,'r1_owned','r1.receipt',ev/'kill',kill=True)
    record=json.loads(journal(case).read_text());assert record['plans'][0]['target_identity']==tr._identity(ws/'Papierkorb/A.JPG')
    r.snapshot(case,ev/'after-receipt-kill.json');state=starts(case,ev)
    for db in ('kamera.sqlite3','second1.sqlite3'):
        a=[row for row in r.db_rows(state,'files',db) if row['original_filename']=='A.JPG'];assert len(a)==1 and a[0]['current_root_kind']=='shared_workspace'
    assert not list(case.rglob('.trash-restores/*.json'))


@pytest.mark.parametrize('tamper',['source_bytes','source_inode','database_inode','catalogue','family','missing_original','empty_plan_rows','new_library_origin'])
def test_r1_unsafe_invariant_blocks_global_start(tmp_path,monkeypatch,tamper):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch);source=ws/'Papierkorb/A.JPG'
    if tamper=='source_bytes':source.write_bytes(b'changed-source')
    elif tamper=='source_inode':p=source.with_suffix('.new');p.write_bytes(source.read_bytes());os.replace(p,source)
    elif tamper=='database_inode':p=data['dbs'][1].with_suffix('.new');p.write_bytes(data['dbs'][1].read_bytes());os.replace(p,data['dbs'][1])
    elif tamper=='missing_original':source.rename(case/'explicit-test-moved-original.JPG')
    elif tamper=='empty_plan_rows':
        path=journal(case);record=json.loads(path.read_text());record['plans'][0]['rows']=[];path.write_text(json.dumps(record))
    elif tamper=='new_library_origin':
        from tests.backend.test_0440_trash import _file
        db=case/'new-library.sqlite3';initialize_database(db);ensure_library_identity(db,'new')
        for job in ('J','K'):create_job(db,job_id=job,kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(case/'other-card'))
        _file(db,'A.JPG',b'synthetic-trash-A.JPG')
        with database_connection(db) as c:
            c.execute("UPDATE files SET current_root_kind='trash',job_id='K'");c.execute("UPDATE file_families SET job_id='K'");c.execute("DELETE FROM jobs WHERE id='J'");c.execute("UPDATE jobs SET state='completed',stage='organized_verified'")
        work=ws/'Arbeitsbereiche/new';work.mkdir(parents=True);archive=case/'new-archive';archive.mkdir()
        register_library(case/'registry.sqlite3',library_id='new',display_name='New',database_path=db,workspace_root=ws,work_root=work,archive_root=archive)

    else:
        with external_edit(data['dbs'][1],fixture_root=case) as c:
            if tamper=='catalogue':c.execute("UPDATE files SET current_root_kind='shared_workspace' WHERE original_filename='A.JPG'")
            else:c.execute("UPDATE file_families SET family_key=family_key||'-external' WHERE id=(SELECT family_id FROM files WHERE original_filename='A.JPG')")
    # Family identity is stronger than physical bytes: changing the natural
    # family key must not silently rebind the original restore.
    r.snapshot(case,ev/'before-unsafe-start.json');raw=journal(case).read_bytes();starts(case,ev,True)
    assert target.read_bytes()==b'synthetic-foreign-target' and journal(case).read_bytes()==raw


def test_r1_legacy_collision_and_unowned_identical_target(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch,'same');path=journal(case);record=json.loads(path.read_text());record['format']=1;record['state']='rolling_back';record.pop('conflict_sources')
    for plan in record['plans']:plan.pop('source_identity',None);plan.pop('target_identity',None)
    path.write_text(json.dumps(record));starts(case,ev);preserved(data,ws,target,'same')
    assert json.loads(path.read_text())['state']=='conflict'


def test_r1_queue_manifest_cannot_erase_conflict(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch);path=journal(case);raw=path.read_bytes()
    with pytest.raises(TrashError):ti._finish_known_restore(ws,path.stem)
    assert path.read_bytes()==raw;starts(case,ev);preserved(data,ws,target)


def test_r1_independent_library_and_provenance(tmp_path,monkeypatch):
    from tests.backend.test_0440_trash import _file
    case,ev,data,ws=seed(tmp_path,monkeypatch)
    db=case/'independent.sqlite3';initialize_database(db);ensure_library_identity(db,'independent')
    create_job(db,job_id='J',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(case/'independent-card'))
    _file(db,'C.JPG',b'synthetic-independent-C')
    create_job(db,job_id='K',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(case/'independent-card'))
    with database_connection(db) as c:
        c.execute("UPDATE files SET job_id='K'");c.execute("UPDATE file_families SET job_id='K'");c.execute("DELETE FROM jobs WHERE id='J'");c.execute("UPDATE jobs SET state='completed',stage='organized_verified'")
    (ws/'Papierkorb/C.JPG').write_bytes(b'synthetic-independent-C')
    work=ws/'Arbeitsbereiche/independent';work.mkdir(parents=True);archive=case/'independent-archive';archive.mkdir()
    register_library(case/'registry.sqlite3',library_id='independent',display_name='Independent',database_path=db,workspace_root=ws,work_root=work,archive_root=archive)
    from app.trash import reconcile_trash_inventory
    reconcile_trash_inventory(db,ws)
    data['dbs'].append(db);data['databases'].append(str(db));(case/'case.json').write_text(json.dumps({k:v for k,v in data.items() if k!='dbs'}))
    target=collision(data,ws,monkeypatch);record=json.loads(journal(case).read_text())
    assert all(str(db)!=str(path) for path,row in record['plans'][0]['rows'])
    with database_connection(db) as c:before=dict(c.execute("SELECT * FROM files WHERE original_filename='C.JPG'").fetchone())
    result=tr.restore_trash_files(data['dbs'],ws,relative_paths=['C.JPG']);assert result['restored_file_count']==1
    state=starts(case,ev)
    with database_connection(db) as c:
        after=dict(c.execute("SELECT * FROM files WHERE original_filename='C.JPG'").fetchone());assert after['current_root_kind']=='shared_workspace'
        for key in ('id','job_id','family_id','original_relative_path','sha256_original','sha256_current'):assert after[key]==before[key]
    assert digest(ws/'SD-Kartensicherungen'/after['current_relative_path'])==hashlib.sha256(b'synthetic-independent-C').hexdigest()
    assert target.read_bytes()==b'synthetic-foreign-target' and digest(ws/'Papierkorb/A.JPG')==data['expected']['A.JPG']
    assert json.loads(journal(case).read_text())['state']=='conflict'


def test_r1_identical_foreign_target_excluded_from_reconcile(tmp_path,monkeypatch):
    from app.central_stock_reconcile import reconcile_central_free_stock
    case,ev,data,ws=seed(tmp_path,monkeypatch);target=collision(data,ws,monkeypatch,'same');ident=tr._identity(target)
    before=r.snapshot(case,ev/'before-reconcile.json')
    for db,lid in zip(data['dbs'],('main','second1')):
        for n in (1,2,3):
            result=reconcile_central_free_stock(db,ws,library_id=lid);assert result['ready']
    state=starts(case,ev);preserved(data,ws,target,'same');assert tr._identity(target)==ident
    assert r.business_rows(before)==r.business_rows(state)


def test_r1_conflict_job_is_not_automatically_requeued(tmp_path,monkeypatch):
    from app.database import get_job
    case,ev,data,ws=seed(tmp_path,monkeypatch);queued=ti.queue_trash_restore(data['dbs'][0],ws,['A.JPG']);jid=queued['job_id']
    target_holder=[];actual=tr.os.link
    def fail(src,dst,*a,**kw):
        if Path(src)==ws/'Papierkorb/A.JPG':Path(dst).write_bytes(b'synthetic-foreign-target');target_holder.append(Path(dst))
        return actual(src,dst,*a,**kw)
    monkeypatch.setattr(tr.os,'link',fail)
    with pytest.raises(TrashError):ti.prepare_queued_trash_restore(data['dbs'][0],data['dbs'],ws,jid)
    monkeypatch.setattr(tr.os,'link',actual)
    # Build a historical interrupted SQL state independently of the application
    # writer, whose existing unresolved-operation guard must remain effective.
    with external_edit(data['dbs'][0],fixture_root=case) as c:c.execute("UPDATE jobs SET state='interrupted',stage='interrupted' WHERE id=?",(jid,))
    assert ti.resume_safe_queued_trash_restores(data['dbs'][0],ws)==0
    starts(case,ev);preserved(data,ws,target_holder[0]);assert get_job(data['dbs'][0],jid)['state']=='interrupted'
    assert json.loads(journal(case).read_text())['state']=='conflict'


@pytest.mark.parametrize('operation',['legacy_stage','legacy_cleanup'])
def test_r1_legacy_import_cannot_remove_reserved_original(tmp_path,monkeypatch,operation):
    case,ev,data,ws=seed(tmp_path,monkeypatch)
    if operation=='legacy_cleanup':staged=ti.stage_trash_import(data['dbs'][0],ws,['A.JPG'])
    target=collision(data,ws,monkeypatch,operation_id=staged['job_id'] if operation=='legacy_cleanup' else None)
    with pytest.raises(TrashError):
        if operation=='legacy_stage':ti.stage_trash_import(data['dbs'][0],ws,['A.JPG'])
        else:ti.cleanup_successful_trash_import(ws,staged['job_id'],[{'relative_path':'A.JPG','sha256':data['expected']['A.JPG']}])
    starts(case,ev);preserved(data,ws,target)


@pytest.mark.parametrize('same',[False,True])
def test_r1_replaced_target_after_receipt_is_not_claimed(tmp_path,monkeypatch,same):
    case,ev,data,ws=seed(tmp_path,monkeypatch);r.invoke(case,'r1_owned','r1.receipt',ev/'kill',kill=True)
    record=json.loads(journal(case).read_text());target=ws/'SD-Kartensicherungen'/record['plans'][0]['target_relative']
    replacement=target.with_suffix('.foreign');replacement.write_bytes(b'synthetic-trash-A.JPG' if same else b'synthetic-foreign-target');os.replace(replacement,target);ident=tr._identity(target)
    r.snapshot(case,ev/'foreign-replaced-own-target.json');starts(case,ev);preserved(data,ws,target,'same' if same else 'different')
    assert tr._identity(target)==ident and json.loads(journal(case).read_text())['state']=='conflict'


@pytest.mark.parametrize('boundary',['restore.db1','r1.completed'])
def test_r1_direct_restore_commits_resume_once(tmp_path,monkeypatch,boundary):
    case,ev,data,ws=seed(tmp_path,monkeypatch);r.invoke(case,'r1_owned',boundary,ev/'kill',kill=True);r.snapshot(case,ev/'after-commit-kill.json');state=starts(case,ev)
    for db in ('kamera.sqlite3','second1.sqlite3'):
        a=[row for row in r.db_rows(state,'files',db) if row['original_filename']=='A.JPG'];assert len(a)==1 and a[0]['current_root_kind']=='shared_workspace'
        logs=[row for row in r.db_rows(state,'audit_log',db) if row['action']=='trash_file_restored'];assert len(logs)==1
    assert not list(case.rglob('.trash-restores/*.json'))


def test_r1_partial_commit_foreign_target_requires_global_block(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path,monkeypatch);r.invoke(case,'r1_owned','restore.db1',ev/'kill',kill=True)
    record=json.loads(journal(case).read_text());target=ws/'SD-Kartensicherungen'/record['plans'][0]['target_relative'];other=target.with_suffix('.foreign');other.write_bytes(target.read_bytes());os.replace(other,target);ident=tr._identity(target)
    before=r.snapshot(case,ev/'before-ambiguous-recovery.json');raw=journal(case).read_bytes();state=starts(case,ev,True)
    assert r.business_rows(before)==r.business_rows(state) and journal(case).read_bytes()==raw
    assert tr._identity(target)==ident and digest(target)==data['expected']['A.JPG']


def test_r1_batch_collision_after_first_move_stays_blocked(tmp_path,monkeypatch):
    case,ev,data,ws=seed(tmp_path,monkeypatch);real=tr.os.link;targets=[]
    def clash(src,dst,*a,**kw):
        if Path(src)==ws/'Papierkorb/B.JPG':Path(dst).write_bytes(b'foreign-b');targets.append(Path(dst))
        return real(src,dst,*a,**kw)
    monkeypatch.setattr(tr.os,'link',clash)
    with pytest.raises(TrashError):tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG','B.JPG'])
    monkeypatch.setattr(tr.os,'link',real);before=r.snapshot(case,ev/'partial-physical-before-start.json')
    # RC14 may keep the process available for protected read views even when
    # the abandoned original F14 lease blocks all further trash mutations.
    # A process exit code is not proof that the dangerous partial move was
    # safely reconciled; require the actual durable write fence and byte state.
    state=starts(case,ev)
    from app.operation_health import inspect as operation_status
    held=operation_status(ws)
    assert not held['writes_allowed'] and any(
        not item['live'] and item.get('kind')=='trash' for item in held['reservations']
    ),held
    with pytest.raises(TrashError):
        tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG','B.JPG'])
    assert r.business_rows(before)==r.business_rows(state) and targets[0].read_bytes()==b'foreign-b'
    assert digest(ws/'Papierkorb/B.JPG')==data['expected']['B.JPG']
    assert any(digest(p)==data['expected']['A.JPG'] for p in (ws/'SD-Kartensicherungen').rglob('A.JPG'))
    assert json.loads(journal(case).read_text())['state']=='rolling_back'


def test_r1_two_restore_processes_after_owner_sigkill(tmp_path,monkeypatch):
    import subprocess,sys,signal,time
    case,ev,data,ws=seed(tmp_path,monkeypatch);worker=Path(r.ROOT)/'worker.py';processes=[];streams=[]
    def spawn(label,boundary):
        control=ev/label;control.mkdir();handle=(control/'process.log').open('w');streams.append(handle)
        process=subprocess.Popen([sys.executable,str(worker),str(case),'r1_owned',boundary,str(control)],stdout=handle,stderr=subprocess.STDOUT,start_new_session=True);processes.append(process)
        return process,control
    def ready(process,path):
        end= time.monotonic()+20
        while process.poll() is None and not path.exists() and time.monotonic()<end:time.sleep(.01)
        assert path.exists(),process.returncode
    try:
        owner,control=spawn('owner','r1.receipt');ready(owner,control/'checkpoint.json')
        second,second_control=spawn('second','r1.wait_lock');ready(second,second_control/'attempt.json');assert second.poll() is None
        r.snapshot(case,ev/'second-process-waits.json');os.killpg(owner.pid,signal.SIGKILL);owner.wait(timeout=5);assert owner.returncode==-signal.SIGKILL
        second.wait(timeout=10);assert second.returncode!=0
        (ev/'process-results.json').write_text(json.dumps({'owner_pid':owner.pid,'owner_returncode':owner.returncode,'second_pid':second.pid,'second_returncode':second.returncode,'different_processes':owner.pid!=second.pid}))
        assert digest(ws/'Papierkorb/A.JPG')==data['expected']['A.JPG'];state=starts(case,ev)
        for db in ('kamera.sqlite3','second1.sqlite3'):
            assert len([x for x in r.db_rows(state,'audit_log',db) if x['action']=='trash_file_restored'])==1
    finally:
        for p in processes:
            if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=5)
        for stream in streams:stream.close()


@pytest.mark.parametrize('target_only',[False,True])
def test_r1_legacy_without_ownership_receipt(tmp_path,monkeypatch,target_only):
    case,ev,data,ws=seed(tmp_path,monkeypatch)
    r.invoke(case,'r1_owned','r1.receipt' if target_only else 'r1.prepared',ev/'kill',kill=True)
    path=journal(case);record=json.loads(path.read_text());record['format']=1
    for plan in record['plans']:plan.pop('source_identity',None);plan.pop('target_identity',None);[row.pop('family_key',None) for db,row in plan['rows']]
    path.write_text(json.dumps(record))
    if target_only:(ws/'Papierkorb/A.JPG').rename(case/'externally-moved-original.JPG')
    r.snapshot(case,ev/'legacy-input.json');starts(case,ev,blocked=target_only)
    if target_only:assert path.exists() and digest(case/'externally-moved-original.JPG')==data['expected']['A.JPG']
    else:assert not list(case.rglob('.trash-restores/*.json')) and any(digest(p)==data['expected']['A.JPG'] for p in (ws/'SD-Kartensicherungen').rglob('A.JPG'))


@pytest.mark.parametrize('interrupted',[False,True])
def test_r1_exdev_receipt_and_partial_copy(tmp_path,monkeypatch,interrupted):
    import errno
    case,ev,data,ws=seed(tmp_path,monkeypatch);actual_link=tr.os.link;published=tr._published
    def exdev(src,dst,*a,**kw):
        if Path(src)==ws/'Papierkorb/A.JPG':raise OSError(errno.EXDEV,'synthetic cross-filesystem link')
        return actual_link(src,dst,*a,**kw)
    class SyntheticInterruption(BaseException):pass
    def receipt(*a):
        published(*a)
        if interrupted:raise SyntheticInterruption('after exclusive target receipt, before copy')
    monkeypatch.setattr(tr.os,'link',exdev);monkeypatch.setattr(tr,'_published',receipt)
    if interrupted:
        with pytest.raises(SyntheticInterruption):tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG'])
    else:assert tr.restore_trash_files(data['dbs'],ws,relative_paths=['A.JPG'])['restored_file_count']==1
    monkeypatch.setattr(tr.os,'link',actual_link);monkeypatch.setattr(tr,'_published',published)
    r.snapshot(case,ev/'exdev-after-operation.json');starts(case,ev)
    if interrupted:
        assert digest(ws/'Papierkorb/A.JPG')==data['expected']['A.JPG'];record=json.loads(journal(case).read_text());assert record['state']=='conflict'
        target=ws/'SD-Kartensicherungen'/record['plans'][0]['target_relative'];assert target.read_bytes()==b'' and tr._identity(target)==record['plans'][0]['target_identity']
    else:assert not list(case.rglob('.trash-restores/*.json')) and any(digest(p)==data['expected']['A.JPG'] for p in (ws/'SD-Kartensicherungen').rglob('A.JPG'))


def test_r1_sqlite_writers_wait_for_durable_conflict(tmp_path,monkeypatch):
    import sqlite3
    case,ev,data,ws=seed(tmp_path,monkeypatch);reached=threading.Event();release=threading.Event();attempt=threading.Event();acquired=threading.Event();results=[];writer_results=[];write=ts._atomic_json
    def durable(path,value):
        if path.parent.name=='.trash-restores' and value.get('state')=='conflict':reached.set();assert release.wait(20)
        return write(path,value)
    monkeypatch.setattr(ts,'_atomic_json',durable)
    def restore():
        try:results.append(collision(data,ws,monkeypatch))
        except Exception as e:results.append(e)
    first=threading.Thread(target=restore);first.start();assert reached.wait(20)
    with sqlite3.connect(data['dbs'][1],timeout=0) as probe:
        with pytest.raises(sqlite3.OperationalError,match='locked'):probe.execute('BEGIN IMMEDIATE')
    def writer():
        try:
            with sqlite3.connect(data['dbs'][1],timeout=20) as c:
                c.set_trace_callback(lambda statement:attempt.set() if statement=='BEGIN IMMEDIATE' else None)
                c.execute('BEGIN IMMEDIATE');acquired.set();writer_results.append(json.loads(journal(case).read_text())['state'])
        except Exception as e:writer_results.append(e)
    second=threading.Thread(target=writer);second.start();assert attempt.wait(20);assert not acquired.is_set()
    r.snapshot(case,ev/'writer-waits-for-durable-conflict.json');release.set();first.join(20);second.join(20);assert not first.is_alive() and not second.is_alive()
    assert len(results)==1 and isinstance(results[0],Path),results
    assert writer_results==['conflict'],writer_results
    monkeypatch.setattr(ts,'_atomic_json',write);starts(case,ev);preserved(data,ws,results[0])
