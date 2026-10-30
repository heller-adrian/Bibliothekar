"""pre.5: reproductions use only pytest's synthetic, registered workspaces."""
from contextlib import closing
from itertools import combinations
import sqlite3
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import shutil

import pytest
from fastapi.testclient import TestClient

from app import main, root_operations as ro, operation_health as operations
from app.central_stock_reconcile import reconcile_central_free_stock
from app.database import create_job, database_connection
from app.library_context import resolve_library_context
from app.storage_config import storage_paths
from tests.backend.test_pre4_operation_separation import ready
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_0412_consistency_semantics import _seed_free_file
from tests.backend.test_0501_external_event_deletion import _event


def inventory_orphan(ws, db):
    with pytest.raises(RuntimeError, match='synthetic interrupted scan'):
        with ro.reserve(ws, library_id='main', database=db, kind='inventory', ids={
            'function': 'app.central_stock_reconcile.reconcile_central_free_stock',
        }):
            raise RuntimeError('synthetic interrupted scan')
    return tuple(ro._control_location(ws).glob('operation-*.json'))


@pytest.mark.parametrize('refresh', ['false', 'true'])
def test_workspace_get_after_interrupted_inventory(ready, refresh):
    _, ws, _, dbs, _ = ready
    records = inventory_orphan(ws, dbs[0])
    before = {p: p.read_bytes() for p in records}
    # No lifespan: this specifically exercises the original request failure.
    with closing(TestClient(main.app, raise_server_exceptions=False)) as client:
        response = client.get('/api/workspace/summary?physical_refresh=' + refresh)
        assert response.status_code == 200, response.text[:1000]
    assert before == {p: p.read_bytes() for p in records}


@pytest.mark.parametrize('actions', [c for n in (1, 2, 3) for c in combinations(('applied', 'archived', 'day'), n)])
def test_three_reported_file_changes_before_metadata(ready, actions):
    _, ws, reg, dbs, _ = ready
    db = dbs[0]
    context = resolve_library_context(reg, 'main')
    paths = storage_paths(ws)
    general = paths['metadata_root'] / 'Allgemein'
    general.mkdir(exist_ok=True)
    # These production fixture helpers create actual files, catalogue rows,
    # assignments and scan results, not a hypothetical recovery receipt.
    events = {}
    create_job(db, job_id='J', kind='sd_import', trigger_type='approved_sd',
        source_path='/synthetic/card', working_path=str(paths['backup_root']), operation='folder_import')
    for status, day in [('applied', '2026-07-19'), ('archived', '2026-07-20')]:
        root = context.archive_root if status == 'archived' else context.work_root
        events[status] = _event(db, root, name=status, day=day,
            items=[(status + '.JPG', b'synthetic-' + status.encode(), 'Alle')], status=status)[1]
    _, _, rel = _seed_free_file(db, family_key='day', filename='day.JPG',
        day='2026-07-21', data=b'synthetic-day')
    day_file = paths['backup_root'] / rel
    day_file.parent.mkdir(parents=True, exist_ok=True)
    day_file.write_bytes(b'synthetic-day')
    assert reconcile_central_free_stock(db, ws, library_id='main')['ready']
    for action in actions:
        source = day_file if action == 'day' else events[action] / 'Alle' / (action + '.JPG')
        if action == 'archived':
            shutil.copyfile(source, general / source.name)
        else:
            source.rename(general / source.name)
    for _ in range(3):
        result = reconcile_central_free_stock(db, ws, library_id='main')
        assert result['ready'], result
    assert operations.inspect(ws)['writes_allowed'], operations.inspect(ws)
    with database_connection(db) as c:
        assert c.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    assert (events['archived'] / 'Alle/archived.JPG').read_bytes() == b'synthetic-archived'


def test_inventory_exception_then_retry_does_not_poison_other_library(ready):
    _, ws, reg, dbs, _ = ready
    inventory_orphan(ws, dbs[0])
    from app.observation_recovery import recover
    recovered = recover(ws)
    assert len(recovered) == 1
    context = resolve_library_context(reg, 'second')
    # A read/SQLite-only inventory interruption cannot claim unknown writes
    # throughout another library. All root and generation checks still apply.
    with ro.reserve(ws, library_id='second', database=dbs[1], paths=[context.work_root], kind='plan'):
        with database_connection(dbs[1]) as c:
            c.execute("INSERT INTO app_settings(setting_key,value_json,updated_at) VALUES ('pre5-independent','\"written\"','2026-10-30')")


def test_interrupted_hash_scan_preserves_media_and_has_no_durable_intent(ready, monkeypatch):
    from app import central_stock_reconcile as stock
    _, ws, _, dbs, _ = ready
    root = storage_paths(ws)['backup_root']
    source = root/'external.JPG'
    source.write_bytes(b'synthetic external bytes')
    before = source.read_bytes()
    def denied(path):
        raise PermissionError('synthetic SMB permission changed during scan')
    monkeypatch.setattr(stock, '_sha256_file', denied)
    with pytest.raises(PermissionError, match='synthetic SMB'):
        stock.reconcile_central_free_stock(dbs[0], ws, library_id='main')
    assert source.read_bytes() == before
    assert not operations.inspect(ws)['reservations']
    assert operations.inspect(ws)['writes_allowed']


@pytest.mark.parametrize('damage', ['generation', 'database', 'record', 'receipt', 'unknown_function'])
def test_historical_inventory_never_waives_contradictory_evidence(ready, damage):
    from app.observation_recovery import recover
    _, ws, _, dbs, _ = ready
    path = inventory_orphan(ws, dbs[0])[0]
    record = ro._read(path)
    if damage == 'generation':
        state_path = path.parent/'state.json'
        state = ro._read(state_path);state['generation'] += 1;ro._write(state_path, state)
    elif damage == 'database':
        dbs[0].rename(dbs[0].with_suffix('.retained'))
    elif damage == 'record':
        record['bindings'][str(ws)] = [1,2];ro._write(path, record)
    elif damage == 'receipt':
        ro._write(path.parent/('inventory-interruption-'+record['reservation_id']+'.json'), {'unknown': 'preserve'})
    else:
        record['ids']['function'] = 'unknown.media_writer'
        from app.storage_bootstrap import key_for
        path.unlink();path = path.parent/('operation-'+key_for(record)+'.json');ro._write(path, record)
    before = path.read_bytes()
    if damage == 'unknown_function':
        assert recover(ws) == []
    else:
        with pytest.raises((ro.RootOperationError, OSError, RuntimeError)):
            recover(ws)
    assert path.read_bytes() == before
    assert not operations.inspect(ws)['writes_allowed']


def general_orphan(ws, db):
    with pytest.raises(RuntimeError, match='synthetic unresolved metadata'):
        with ro.reserve(ws, library_id='main', database=db, kind='metadata', ids={
            'function':'app.metadata_correction.execute_metadata_correction',
            'area':'general', 'relative_path':'conflicted.JPG',
        }):
            raise RuntimeError('synthetic unresolved metadata')
    return tuple(ro._control_location(ws).glob('operation-*.json'))


def test_known_general_conflict_allows_real_independent_catalogue_writes(ready):
    _, ws, _, dbs, _ = ready
    records=general_orphan(ws, dbs[0]);before={p:p.read_bytes() for p in records}
    status=operations.inspect(ws)
    assert not status['writes_allowed'] and status['workspace_writes_allowed']
    assert status['blocked_scopes']==['metadata']
    # Genuine queued jobs/claims in each database, including the affected main
    # library. No fake completion or fabricated transfer proof is inserted.
    from app.database import create_job, claim_next_job
    for db in dbs:
        create_job(db,job_id='INDEPENDENT',kind='sd_import',trigger_type='manual',
            source_path='/synthetic/unrelated-card',working_path=str(storage_paths(ws)['backup_root']),operation='folder_import')
        claimed=claim_next_job(db,operation='folder_import')
        assert claimed and claimed['id']=='INDEPENDENT'
    with pytest.raises(sqlite3.DatabaseError):
        with database_connection(dbs[0]) as c:
            c.execute("UPDATE metadata_corrections SET status='completed'")
    assert before=={p:p.read_bytes() for p in records}


def test_conflicted_job_is_not_claimed(ready):
    from app.database import create_job, claim_next_job, get_job
    _, ws, _, dbs, _=ready
    general_orphan(ws,dbs[0])
    create_job(dbs[0],job_id='CONFLICTED',kind='sd_import',trigger_type='manual',
        source_path='/synthetic/general',working_path=str(ws),operation='metadata_general_import')
    assert claim_next_job(dbs[0],operation='metadata_general_import') is None
    assert get_job(dbs[0],'CONFLICTED')['state']=='queued'


def test_scoped_startup_reports_connected_database_and_releases_only_admitted_workers(ready,monkeypatch):
    _,ws,_,dbs,_=ready
    records=general_orphan(ws,dbs[0]);before={p:p.read_bytes() for p in records}
    workers=[];domain=[]
    monkeypatch.setattr(main,'_start_runtime_workers',lambda **kw:workers.append(kw))
    main._coordinate_startup(lambda:domain.append('unqualified replay'))()
    assert domain==[] and workers==[{'recover_domain':False}]
    assert main.DATABASE_INITIALIZATION_ERROR is None
    assert main.DATABASE_INITIALIZATION['connected'] and main.DATABASE_INITIALIZATION['consistent']
    assert main.DATABASE_INITIALIZATION['applied_versions']==list(range(1,56))
    assert operations.inspect(ws)['workspace_writes_allowed']
    assert before=={p:p.read_bytes() for p in records}


def test_unknown_effects_still_fence_every_write(ready):
    from tests.backend.test_pre4_operation_separation import orphan
    _,ws,_,dbs,_=ready
    orphan(ws,dbs[0])
    assert not operations.inspect(ws)['workspace_writes_allowed']
    from app.database import create_job
    with pytest.raises(sqlite3.DatabaseError):
        create_job(dbs[1],job_id='UNSAFE',kind='sd_import',trigger_type='manual',
            source_path='/synthetic/card',working_path=str(ws),operation='folder_import')


def test_domain_constraint_failure_is_not_database_corruption():
    assert not operations.technical_failure(sqlite3.IntegrityError('UNIQUE constraint failed: media'))


def test_real_pre4_failed_scan_is_retained_then_qualified(ready):
    from app.observation_recovery import recover
    case,ws,_,dbs,_=ready
    old=case/'published-pre4';old.mkdir()
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive','v1.0.0-pre.4','app']))) as archive:
        archive.extractall(old,filter='data')
    source=storage_paths(ws)['backup_root']/'scan-race.JPG'
    source.write_bytes(b'synthetic original scan bytes')
    code='''
from pathlib import Path
import sys
from app import central_stock_reconcile as scan
def permission_changed(path):raise PermissionError('synthetic concurrent SMB ACL change')
scan._sha256_file=permission_changed
try:scan.reconcile_central_free_stock(Path(sys.argv[1]),Path(sys.argv[2]),library_id='main')
except PermissionError as error:print(str(error))
else:raise AssertionError('fault injection was not reached')
'''
    process=subprocess.run([sys.executable,'-c',code,str(dbs[0]),str(ws)],
        cwd=old,env=dict(os.environ,PYTHONPATH=str(old),PYTHONDONTWRITEBYTECODE='1'),
        text=True,capture_output=True,timeout=30)
    assert process.returncode==0,process.stdout+process.stderr
    assert 'concurrent SMB ACL change' in process.stdout
    path=next(ro._control_location(ws).glob('operation-*.json'))
    original=ro._read(path)
    assert original['kind']=='inventory'
    assert not operations.inspect(ws)['writes_allowed']
    assert len(recover(ws))==1
    proof=ro._read(path.parent/('inventory-interruption-'+original['reservation_id']+'.json'))
    assert proof['reservation']==original and proof['media_writes'] is False
    assert source.read_bytes()==b'synthetic original scan bytes'
    assert operations.inspect(ws)['writes_allowed']


def test_transient_observer_cannot_nest_durable_media_writes(ready):
    _,ws,_,dbs,_=ready
    with ro.reserve(ws,library_id='main',database=dbs[0],kind='inventory',
                    ids={'function':'app.central_stock_reconcile.reconcile_central_free_stock'},durable=False):
        with pytest.raises(ro.RootOperationError,match='observational scan'):
            with ro.reserve(ws,library_id='main',database=dbs[0],kind='import'):
                pytest.fail('unsafe media mutation')


def test_database_diagnosis_never_creates_or_repairs_database(tmp_path):
    from app.database_diagnostics import inspect
    missing=tmp_path/'missing.sqlite3'
    report=inspect(missing)
    assert not report['connected'] and not missing.exists() and report['automatic_repair'] is False
    broken=tmp_path/'broken.sqlite3';broken.write_bytes(b'foreign bytes')
    report=inspect(broken)
    assert not report['connected'] and broken.read_bytes()==b'foreign bytes'
