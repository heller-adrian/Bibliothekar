"""Exact replay of recovery leases, never blanket admission of old file jobs."""
from contextlib import closing
import json,sqlite3,threading
import pytest
from app import root_operations as ro,operation_health as health,domain_recovery
from app.storage_config import load_storage_settings,storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_pre4_operation_separation import ready

FUNCTIONS=['app.trash_selective.recover_trash_deletions','app.trash_restore.recover_trash_restores']


def interrupted(ready,function):
    _,ws,_,_,_=ready
    domain_recovery.handlers()
    with pytest.raises(RuntimeError):
        with ro.reserve(ws,library_id='shared',database=None,kind='recovery',
                ids={'function':function},paths=[ws,*(ws/n for n in load_storage_settings(workspace_root=ws).values())]):
            raise RuntimeError('synthetic death inside audited recovery')
    record=next(p for p in ro._control_location(ws).glob('operation-*.json'))
    return record,ro._read(record)


@pytest.mark.parametrize('function',FUNCTIONS)
def test_empty_historical_recovery_reuses_original_nonce_and_keeps_receipt(ready,function):
    _,ws,reg,dbs,_=ready
    path,original=interrupted(ready,function)
    assert domain_recovery.replay(ws,reg,database=dbs[0])
    proof=ro._read(path.parent/('domain-recovery-'+original['reservation_id']+'.json'))
    assert proof['reservation']==original and not path.exists()
    assert proof['disposition']=='audited_recovery_returned_no_pending_journal'
    assert health.inspect(ws)['writes_allowed']
    assert not domain_recovery.replay(ws,reg,database=dbs[0])
    assert ro._read(path.parent/('domain-recovery-'+original['reservation_id']+'.json'))==proof


@pytest.mark.parametrize('damage',['generation','binding','unknown_field','extra_operation'])
def test_recovery_cannot_certify_changed_or_unrelated_evidence(ready,damage):
    _,ws,reg,dbs,_=ready
    path,original=interrupted(ready,FUNCTIONS[0])
    if damage=='generation':original['generation'][0]+=1
    elif damage=='binding':original['bindings'][str(ws)]=[0,999]
    elif damage=='unknown_field':original['unknown_effect']='unqualified'
    else:
        # An already present historical/untrusted intent, not a newly admitted
        # production writer: the latter must be refused by the existing fence.
        from app.storage_bootstrap import key_for
        other={**original,'reservation_id':'f'*32,'ids':{'function':'unrecognized.domain.writer'}}
        ro._write(path.parent/('operation-'+key_for(other)+'.json'),other)
    if damage!='extra_operation':ro._write(path,original)
    before={p:p.read_bytes() for p in path.parent.glob('operation-*.json')}
    if damage=='extra_operation':
        assert not domain_recovery.replay(ws,reg,database=dbs[0])
    else:
        with pytest.raises((health.DomainStartupError,ro.RootOperationError)):
            domain_recovery.replay(ws,reg,database=dbs[0])
    assert before=={p:p.read_bytes() for p in path.parent.glob('operation-*.json')}
    assert not list(path.parent.glob('domain-recovery-*.json'))


@pytest.mark.parametrize('function',FUNCTIONS)
def test_unknown_journal_bytes_are_not_a_successful_recovery(ready,function):
    _,ws,reg,dbs,_=ready
    path,original=interrupted(ready,function)
    directory=storage_paths(ws)['metadata_root']/('.trash-deletions' if function==FUNCTIONS[0] else '.trash-restores')
    directory.mkdir(exist_ok=True)
    journal=directory/(('DELETE_'+'A'*32+'.json') if function==FUNCTIONS[0] else 'unknown.json')
    journal.write_bytes(b'unknown journal bytes must survive')
    with pytest.raises((ValueError,ro.RootOperationError,RuntimeError)):
        domain_recovery.replay(ws,reg,database=dbs[0])
    assert ro._read(path)==original and journal.read_bytes()==b'unknown journal bytes must survive'
    assert not (path.parent/('domain-recovery-'+original['reservation_id']+'.json')).exists()
    intent=ro._read(path.parent/('domain-recovery-intent-'+original['reservation_id']+'.json'))
    assert intent=={'format':1,'reservation':original,'phase':'qualified_recovery_not_finished'}


@pytest.mark.parametrize('damage',['none','foreign_copy','missing_copy'])
def test_failed_restore_replay_requires_complete_retained_bytes(fixture,monkeypatch,damage):
    from tests.backend.test_rc4_practice import protocol_failure
    from app import trash_failure as tf,trash_import as ti
    from app.database import get_job
    db,ws,jid,journal,data,incoming,status=protocol_failure(fixture)
    before=get_job(db,jid)
    def die(point):
        if point=='journal_prepared':raise RuntimeError('synthetic finalizer interruption')
    monkeypatch.setattr(tf,'checkpoint',die)
    with pytest.raises(RuntimeError,match='synthetic finalizer interruption'):
        tf.finalize_failure(db,ws,jid)
    monkeypatch.setattr(tf,'checkpoint',lambda point:None)
    parent=ro._control_location(ws)
    path=next(parent.glob('operation-*.json'));original=ro._read(path)
    copy=ti.stage_parent(ws)/jid/data['files'][0]['relative_path']
    if damage=='foreign_copy':copy.write_bytes(b'foreign retained bytes')
    if damage=='missing_copy':copy.unlink()
    remaining={p:p.read_bytes() for p in (ti.stage_parent(ws)/jid).rglob('*') if p.is_file()}
    if damage=='none':
        assert domain_recovery.replay(ws,fixture[2],database=db)
        assert not path.exists() and tf.validate_finalized(db,ws,jid)
        receipt=ro._read(parent/('domain-recovery-'+original['reservation_id']+'.json'))
        assert receipt['reservation']==original
        assert receipt['disposition']=='verified_failed_restore_finalized_error_preserved'
    else:
        with pytest.raises((RuntimeError,ValueError)):
            domain_recovery.replay(ws,fixture[2],database=db)
        assert ro._read(path)==original
        assert not (parent/('domain-recovery-'+original['reservation_id']+'.json')).exists()
        assert not health.inspect(ws)['writes_allowed']
    after=get_job(db,jid)
    assert all(after[k]==before[k] for k in ('state','stage','error_message'))
    assert remaining=={p:p.read_bytes() for p in (ti.stage_parent(ws)/jid).rglob('*') if p.is_file()}


def test_live_recovery_fences_cached_sql_and_root_changes_but_keeps_safe_reads(ready,monkeypatch):
    from contextlib import contextmanager
    from app.database import connect
    from app import trash_selective
    from app.managed_storage_health import inspect_storage
    _,ws,reg,dbs,_=ready
    path,original=interrupted(ready,FUNCTIONS[0])
    entered=threading.Event();release=threading.Event();errors=[]
    real=trash_selective._operation_lock
    @contextmanager
    def hold(*args,**kwargs):
        with real(*args,**kwargs):
            entered.set();assert release.wait(10)
            yield
    monkeypatch.setattr(trash_selective,'_operation_lock',hold)
    # The connection's dynamic authorizer must also protect cached/open handles.
    connection=connect(dbs[0])
    def worker():
        try:domain_recovery.replay(ws,reg,database=dbs[0])
        except BaseException as error:errors.append(error)
    thread=threading.Thread(target=worker);thread.start()
    try:
        assert entered.wait(10)
        assert inspect_storage(ws,database=dbs[0])['state']=='READY'
        assert connection.execute('SELECT count(*) FROM jobs').fetchone()[0]>=0
        with pytest.raises(sqlite3.DatabaseError,match='not authorized'):
            connection.execute("UPDATE files SET updated_at='unsafe'")
        with pytest.raises(ro.RootOperationError):
            with ro.mutate(ws,databases=dbs):pytest.fail('root change during domain recovery')
    finally:release.set();thread.join(10);connection.close()
    assert not thread.is_alive() and not errors,errors
    assert not path.exists() and health.inspect(ws)['writes_allowed']


@pytest.mark.parametrize('boundary',['stage','first_db','committed'])
def test_original_delete_is_recovered_under_original_identity(tmp_path,monkeypatch,boundary):
    from tests.backend.test_0561_audit_regressions import trash_case
    from app import trash_selective as ts
    db,other,ws,paths,payload=trash_case(tmp_path,monkeypatch,two=True)
    class Cut(BaseException):pass
    name={'stage':'_move_checked','first_db':'_purge_selected','committed':'_atomic_json'}[boundary]
    real=getattr(ts,name)
    def cut(*args,**kwargs):
        value=real(*args,**kwargs)
        if boundary!='committed' or args[1].get('state')=='committed':raise Cut()
        return value
    with monkeypatch.context() as patch:
        patch.setattr(ts,name,cut)
        with pytest.raises(Cut):ts.delete_selected_trash_files([db,other],ws,['A.JPG'])
    path=next(ro._control_location(ws).glob('operation-*.json'));original=ro._read(path)
    ts.recover_trash_deletions(ws,allowed_databases={db,other})
    assert not path.exists()
    assert ro._read(path.parent/('domain-recovery-'+original['reservation_id']+'.json'))['reservation']==original
    assert health.inspect(ws)['writes_allowed']
    from pathlib import Path
    media=Path(paths['trash_root'])/'A.JPG'
    if boundary=='committed':assert not media.exists()
    else:assert media.read_bytes()==payload
    from app.database import database_connection
    for target in (db,other):
        with database_connection(target) as c:
            assert c.execute('PRAGMA integrity_check').fetchall()[0][0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()
            assert c.execute('SELECT count(*) FROM files').fetchone()[0]==(0 if boundary=='committed' else 1)


def test_get_cannot_start_domain_recovery_or_write_a_recovery_intent(ready):
    from app import trash_selective as ts
    _,ws,_,dbs,_=ready
    path,original=interrupted(ready,FUNCTIONS[0]);before={p.name:p.read_bytes() for p in path.parent.glob('*.json')}
    with health.read_session(),pytest.raises(RuntimeError):
        ts.recover_trash_deletions(ws,allowed_databases=set(dbs))
    assert before=={p.name:p.read_bytes() for p in path.parent.glob('*.json')}


def test_original_delete_without_journal_is_not_inferred_complete(ready):
    _,ws,reg,dbs,_=ready
    domain_recovery.handlers()
    with pytest.raises(RuntimeError):
        with ro.reserve(ws,library_id='shared',kind='trash',ids={
                'function':'app.trash_selective.delete_selected_trash_files','relative_paths':'["A.JPG"]'},
                paths=[ws,*(ws/n for n in load_storage_settings(workspace_root=ws).values())]):
            raise RuntimeError('unproved original deletion')
    path=next(ro._control_location(ws).glob('operation-*.json'));original=ro._read(path)
    with pytest.raises(health.DomainStartupError,match='missing_delete_journal_or_receipt'):
        domain_recovery.replay(ws,reg,database=dbs[0])
    assert ro._read(path)==original and not health.inspect(ws)['writes_allowed']
    assert not (path.parent/('domain-recovery-'+original['reservation_id']+'.json')).exists()


def test_shared_recovery_does_not_reopen_a_retired_catalogue(ready):
    import hashlib
    from app.library_registry import _connect
    _,ws,reg,dbs,_=ready
    with closing(_connect(reg)) as connection:
        connection.execute("UPDATE libraries SET is_registered=0,unregistered_at='synthetic-retired' WHERE library_id='second'")
        connection.commit()
    retained=dbs[1].with_suffix('.retired');dbs[1].rename(retained)
    original_hash=hashlib.sha256(retained.read_bytes()).hexdigest()
    path,original=interrupted(ready,FUNCTIONS[0])
    assert domain_recovery.replay(ws,reg,database=dbs[0])
    assert not dbs[1].exists() and hashlib.sha256(retained.read_bytes()).hexdigest()==original_hash
    assert ro._read(path.parent/('domain-recovery-'+original['reservation_id']+'.json'))['reservation']==original
