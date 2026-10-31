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
    assert not list(path.parent.glob('domain-recovery-*.json'))


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
