"""A durable F14 finish can be retired; SQL status/absence never suffice."""
import json
from pathlib import Path
import pytest
from app import root_operations as ro
from app.database import create_job,database_connection
from tests.backend.test_f14_root_operations import fixture


class Crash(BaseException):pass


def completed_but_not_unlinked(fixture,monkeypatch,kind='verified-synthetic-finish'):
    case,ws,reg,dbs,ev=fixture;actual=ro._write
    with monkeypatch.context() as fault:
        def persist_then_crash(path,value):
            actual(path,value)
            if path.name.startswith('finished-'):raise Crash()
        fault.setattr(ro,'_write',persist_then_crash)
        with pytest.raises(Crash):
            with ro.reserve(ws,library_id='main',database=dbs[0],paths=[ws],kind=kind):
                pass
    operation,=ro._control_location(ws).glob('operation-*.json');record=ro._read(operation)
    proof=operation.parent/('finished-'+record['reservation_id']+'.json')
    assert ro._receipt_completed(record)
    (ev/'f14-proof.json').write_text(json.dumps({'original':record,'finished':ro._read(proof)},indent=2))
    return operation,record,proof


def test_durable_finish_retirement_is_idempotent_and_preserves_original(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture
    operation,record,proof=completed_but_not_unlinked(fixture,monkeypatch);raw=proof.read_bytes()
    for _ in range(3):ro.retire_finished_operations(ws)
    assert not operation.exists() and proof.read_bytes()==raw
    receipts=list(operation.parent.glob('completed-*.json'));assert len(receipts)==1
    saved=ro._read(receipts[0]);assert saved['reservation']==record and saved['finished_receipt']==json.loads(raw)
    with ro.reserve(ws,library_id='main',database=dbs[0],paths=[ws],kind='independent-after-finish'):pass
    assert not list(operation.parent.glob('operation-*.json'))
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'


@pytest.mark.parametrize('fault',['missing','wrong_nonce','wrong_type','changed_generation','missing_root_binding'])
def test_invalid_finished_evidence_never_retires_original(fixture,monkeypatch,fault):
    case,ws,reg,dbs,ev=fixture
    operation,record,proof=completed_but_not_unlinked(fixture,monkeypatch)
    if fault=='missing':proof.rename(case/'retained-original-finish.json')
    elif fault=='changed_generation':
        state=operation.parent/'state.json';value=ro._read(state);value['generation']+=1;ro._write(state,value)
    else:
        value=ro._read(proof)
        if fault=='wrong_nonce':value['reservation']['reservation_id']='0'*32
        elif fault=='wrong_type':value['receipt']='SQL_status_only'
        else:
            record['bindings'].pop(str(ws));ro._write(operation,record);value['reservation']=record
        ro._write(proof,value)
    before=operation.read_bytes()
    with pytest.raises(ro.RootOperationError):
        with ro.mutate(ws,databases=dbs):pytest.fail('Invalid completion authorized a root mutation')
    assert operation.read_bytes()==before
    assert (ws/'Arbeitsbereiche/main/original.JPG').read_bytes()==b'synthetic-main'


def test_terminal_sql_status_without_finished_receipt_remains_fenced(fixture):
    case,ws,reg,dbs,ev=fixture
    create_job(dbs[0],job_id='TERMINAL',kind='sd_import',trigger_type='manual',operation='folder_import')
    with database_connection(dbs[0]) as connection:
        connection.execute("UPDATE jobs SET state='completed' WHERE id='TERMINAL'")
    with pytest.raises(RuntimeError):
        with ro.reserve(ws,library_id='main',database=dbs[0],paths=[ws],kind='import',ids={'job_id':'TERMINAL'}):
            raise RuntimeError('Unverified media outcome despite terminal SQL')
    operation,=ro._control_location(ws).glob('operation-*.json');record=ro._read(operation);raw=operation.read_bytes()
    assert ro._completed(record) and not ro._receipt_completed(record)
    with pytest.raises(ro.RootOperationError):
        with ro.mutate(ws,databases=dbs):pytest.fail('SQL status alone released original media fence')
    assert operation.read_bytes()==raw


def test_backup_receipt_with_pending_journal_is_left_for_domain_replay(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture
    operation,record,proof=completed_but_not_unlinked(fixture,monkeypatch,kind='backup')
    directory=case/'pending-backup-journals';directory.mkdir()
    journal=directory/'original.json';journal.write_text('{"phase":"pending_cleanup"}')
    ro._write(proof,{'receipt':'backup_domain_finished','reservation':record,'disposition':'rolled_back',
                    'journal':str(journal),'journal_parent_identity':ro._identity(directory)})
    before=operation.read_bytes();saved=journal.read_bytes()
    assert not ro._receipt_completed(record)
    ro.retire_finished_operations(ws)
    assert operation.read_bytes()==before and journal.read_bytes()==saved
    with pytest.raises(ro.RootOperationError):
        with ro.mutate(ws,databases=dbs):pytest.fail('Pending backup cleanup was ignored')
