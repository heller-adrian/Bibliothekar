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
    assert status['blocked_scopes']==['metadata/general/conflicted.JPG']
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


def test_independent_general_correction_still_runs_but_conflicted_file_cannot(ready):
    from PIL import Image
    from app import metadata_correction as mc
    _,ws,_,dbs,_=ready
    records=general_orphan(ws,dbs[0]);before={p:p.read_bytes() for p in records}
    root=mc.metadata_area_paths(area='general',workspace_root=ws,library_id='main')['root']
    source=root/'independent.JPG';Image.new('RGB',(12,12),'blue').save(source)
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        response=client.post('/api/metadata-correction/correct',json={'area':'general','relative_path':source.name,
            'proposed_datetime':'2026-07-21T12:00:00+02:00'})
        assert response.status_code==200,response.text
        assert response.json()['task']['status']=='completed'
        denied=client.post('/api/metadata-correction/correct',json={'area':'general','relative_path':'conflicted.JPG',
            'proposed_datetime':'2026-07-21T12:00:00+02:00'})
        assert denied.status_code==409,denied.text
    mc.verify_metadata_datetime(source,'2026-07-21T12:00:00+02:00')
    # An unrelated file may complete, retaining the exact unresolved original.
    assert before=={p:p.read_bytes() for p in records}


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


def test_mutable_task_row_alone_cannot_narrow_historical_apply(ready,monkeypatch):
    from tests.backend.test_pre3_metadata_transfer import completed
    from app.operation_scopes import resources
    _,ws,_,db,source,task=completed(ready,monkeypatch)
    candidate={'kind':'metadata','library':'main','database':str(db),'ids':{
        'function':'app.metadata_correction.apply_metadata_correction','correction_id':task['id']}}
    assert resources(candidate)=={'metadata','library:main','central_stock'}


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


def test_private_view_resolves_trash_to_original_workspace_and_keeps_f14_read_only(ready):
    from app.trash import trash_root
    from app.library_runtime import set_current_library,reset_current_library
    _,ws,reg,dbs,_=ready
    context=resolve_library_context(reg,'main')
    parent=ro._control_location(ws)
    before={p:p.read_bytes() for p in parent.glob('*.json')}
    token=set_current_library(context)
    try:
        with operations.read_session():
            view=main.compatibility_workspace_root(context)
            assert ro.canonical_workspace(view)==ws
            assert trash_root(view)==storage_paths(ws)['trash_root']
            assert not (view/storage_paths(ws)['trash_root'].name).exists()
    finally:reset_current_library(token)
    assert before=={p:p.read_bytes() for p in parent.glob('*.json')}


def test_database_diagnosis_never_creates_or_repairs_database(tmp_path):
    from app.database_diagnostics import inspect
    missing=tmp_path/'missing.sqlite3'
    report=inspect(missing)
    assert not report['connected'] and not missing.exists() and report['automatic_repair'] is False
    broken=tmp_path/'broken.sqlite3';broken.write_bytes(b'foreign bytes')
    report=inspect(broken)
    assert not report['connected'] and broken.read_bytes()==b'foreign bytes'


@pytest.mark.parametrize('damage',['missing_table','missing_column','wrong_versions','registry_table'])
def test_quick_check_alone_never_attests_a_complete_schema(ready,damage):
    from app.database_diagnostics import inspect
    _,ws,reg,dbs,_=ready
    db=reg if damage=='registry_table' else dbs[0]
    with closing(sqlite3.connect(db)) as connection:
        if damage=='missing_table':connection.execute('DROP TABLE metadata_corrections')
        elif damage=='missing_column':connection.execute('ALTER TABLE metadata_corrections DROP COLUMN proposed_datetime')
        elif damage=='wrong_versions':connection.execute('DELETE FROM schema_versions WHERE version=55')
        else:connection.execute('DROP TABLE source_family_members')
        connection.commit()
        assert connection.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    before=db.read_bytes()
    report=inspect(db,kind='registry' if damage=='registry_table' else 'catalogue')
    assert report['connected'] and report['consistent']
    assert not report['schema_current'] and report['schema_issues'],report
    assert not report['automatic_repair'] and db.read_bytes()==before


def test_schema_diagnosis_matches_both_shipped_schemas(ready):
    from app.database_diagnostics import inspect
    _,_,reg,dbs,_=ready
    assert inspect(dbs[0])['schema_current'],inspect(dbs[0])
    assert inspect(reg,kind='registry')['schema_current'],inspect(reg,kind='registry')


def test_incomplete_schema_does_not_start_workers_during_domain_recovery(ready,monkeypatch):
    _,ws,_,dbs,_=ready
    general_orphan(ws,dbs[0])
    with closing(sqlite3.connect(dbs[0])) as connection:
        connection.execute('DROP TABLE metadata_corrections');connection.commit()
    workers=[]
    monkeypatch.setattr(main,'_start_runtime_workers',lambda **kw:workers.append(kw))
    main._coordinate_startup(lambda:pytest.fail('ordinary startup past unresolved intent'))()
    assert not workers and 'database_schema_requires_qualification' in main.DATABASE_INITIALIZATION_ERROR
    assert main.DATABASE_INITIALIZATION['connected'] and main.DATABASE_INITIALIZATION['consistent']
    assert main.api_storage_health()['state']=='UNAVAILABLE'


@pytest.mark.parametrize('conflict',['none','general','unknown'])
def test_real_read_endpoints_never_mutate_catalogues_or_f14(ready,conflict):
    from tests.backend.test_pre4_operation_separation import orphan
    _,ws,reg,dbs,_=ready
    db=dbs[0];context=resolve_library_context(reg,'main')
    create_job(db,job_id='J',kind='sd_import',trigger_type='approved_sd',
        source_path='/synthetic/card',working_path=str(ws),operation='folder_import')
    event,_,_=_event(db,context.work_root,name='read-event',day='2026-07-19',
        items=[('read.JPG',b'synthetic media','Alle')],status='applied')
    if conflict=='general':general_orphan(ws,db)
    elif conflict=='unknown':orphan(ws,db)
    def dump(path):
        with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as c:
            return '\n'.join(c.iterdump())
    before={p:dump(p) for p in (*dbs,reg)}
    control=ro._control_location(ws)
    evidence={p:p.read_bytes() for p in control.glob('*.json')}
    routes=['/api/workspace/summary?jobs=J&physical_refresh=true','/api/jobs/J/workspace-summary',
        '/api/jobs','/api/jobs/J/events','/api/events/search?physical_refresh=true','/api/trash',
        '/api/metadata-correction/areas','/api/metadata-correction/scan?area=general',
        '/api/settings/event-folder-layout','/api/settings/recovery-diagnostics',
        f'/api/events/{event}/folder-layout',f'/api/jobs/J/events/{event}/structure',
        f'/api/jobs/J/events/{event}/edit',f'/api/jobs/J/events/{event}/reconcile-plan']
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        for route in routes:
            response=client.get(route)
            expected=409 if route.endswith('/reconcile-plan') else 200
            assert response.status_code==expected,(route,response.status_code,response.text[:1000])
            if expected==409:
                assert 'keine gemeinsame Nachsortierung' in response.json()['detail']
    assert before=={p:dump(p) for p in before}
    assert evidence=={p:p.read_bytes() for p in control.glob('*.json')}


def test_transient_scan_never_recreates_lost_registered_control_state(ready):
    _,ws,_,dbs,_=ready
    state=ro._control_location(ws)/'state.json'
    state.rename(state.with_name('original-retained.json'))
    with pytest.raises((RuntimeError,ro.RootOperationError)):
        reconcile_central_free_stock(dbs[0],ws,library_id='main')
    assert not state.exists()


def test_empty_but_identity_pinned_stock_is_not_a_missing_mount(ready):
    _,ws,_,dbs,_=ready
    db=dbs[0];root=storage_paths(ws)['backup_root']
    _,file_id,relative=_seed_free_file(db,family_key='moved',filename='moved.JPG',
        day='2026-07-21',data=b'known bytes')
    # All media may have left the pinned directory before its first scan.
    result=reconcile_central_free_stock(db,ws,library_id='main')
    assert result['ready'] and result['pending_missing_count']==1
    assert not (root/'.bibliothekar-central-stock-v1').exists()
    assert operations.inspect(ws)['writes_allowed']


def test_legacy_sentinel_never_writes_outside_inventory_root(ready):
    case,ws,_,dbs,_=ready
    foreign=case/'foreign-retained.txt';foreign.write_bytes(b'untouched')
    sentinel=storage_paths(ws)['backup_root']/'.bibliothekar-central-stock-v1'
    sentinel.symlink_to(foreign)
    assert reconcile_central_free_stock(dbs[0],ws,library_id='main')['ready']
    assert foreign.read_bytes()==b'untouched' and sentinel.is_symlink()


def test_real_trash_restore_and_confirmed_delete_work_beside_general_conflict(ready,monkeypatch):
    from tests.backend.test_rc1_sd_reimport import setup_live_import,queue_and_run
    from tests.backend.test_rc13_provenance import origin
    from app.trash import reconcile_trash_inventory
    from app.trash_restore import restore_trash_files
    from app.trash_selective import delete_selected_trash_files
    case,ws,reg,dbs,source,context=setup_live_import(ready,monkeypatch)
    queue_and_run(dbs[0],context)
    before=origin(reg)
    records=general_orphan(ws,dbs[0]);evidence={p:p.read_bytes() for p in records}
    with database_connection(dbs[0]) as c:row=dict(c.execute('SELECT * FROM files').fetchone())
    paths=storage_paths(ws);published=paths['backup_root']/row['current_relative_path']
    data=published.read_bytes();trash=paths['trash_root']/published.name
    published.rename(trash);reconcile_trash_inventory(dbs[0],ws)
    with closing(TestClient(main.app,raise_server_exceptions=False)) as client:
        shown=client.get('/api/trash')
        assert shown.status_code==200,shown.text
        assert shown.json()['tracked_file_count']==1,shown.json()
        assert not shown.json()['deletion_blocked'],shown.json()
    restored=restore_trash_files(dbs,ws,relative_paths=[trash.name])
    assert restored['restored_file_count']==1 and published.read_bytes()==data
    published.rename(trash);reconcile_trash_inventory(dbs[0],ws)
    deleted=delete_selected_trash_files(dbs,ws,[trash.name])
    assert deleted['deleted_file_count']==1 and not trash.exists()
    assert source.read_bytes()==data
    assert before==origin(reg)
    assert evidence=={p:p.read_bytes() for p in records}
