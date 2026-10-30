"""New storage/operation contract. All data belongs to pytest's temporary fixture."""
import json
from pathlib import Path
import pytest
from app import root_operations as ro, operation_health as operations
from app.storage_status import State, describe
from app.storage_config import storage_paths
from app.managed_directory_names import directory_name
from app.storage_anchors import pin
from app.managed_storage_health import inspect_storage
from tests.backend.test_f14_root_operations import fixture

@pytest.fixture
def ready(fixture):
    case,ws,reg,dbs,ev=fixture
    metadata=storage_paths(ws)['metadata_root']
    for kind in ('metadata_general','metadata_multiple'):
        (metadata/directory_name(metadata,kind)).mkdir(exist_ok=True)
    with ro.reserve(ws,library_id='main',database=dbs[0],paths=[ws,*[ws/n for n in __import__('app.storage_config',fromlist=['load_storage_settings']).load_storage_settings(workspace_root=ws).values()]]):pass
    pin(ws)
    operations.reset(ws)
    assert inspect_storage(ws,database=dbs[0])['ready']
    return fixture


def orphan(ws,db):
    try:
        with ro.reserve(ws,library_id='main',database=db,kind='unknown-test-operation',ids={'id':'synthetic'}):
            raise RuntimeError('synthetic interrupted operation')
    except RuntimeError:pass
    return list(ro._control_location(ws).glob('operation-*.json'))


def test_only_two_global_states():
    assert {s.value for s in State}=={'READY','UNAVAILABLE'}
    for ready in (True,False):
        for old in ('FRESH','DEGRADED','AMBIGUOUS','INITIALIZING'):
            assert describe({'ready':ready,'state':old})['state']==('READY' if ready else 'UNAVAILABLE')


def test_orphan_fences_writes_preserves_storage_and_evidence(ready):
    case,ws,reg,dbs,ev=ready
    records=orphan(ws,dbs[0]);before={p:p.read_bytes() for p in records}
    assert records and not operations.inspect(ws)['writes_allowed']
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    with pytest.raises(ro.RootOperationError,match='operation_recovery_required'):
        with ro.reserve(ws,library_id='main',database=dbs[0],kind='unrelated'):pytest.fail('unsafe admission')
    assert before=={p:p.read_bytes() for p in records}
    from app.operation_ui import catalogue
    assert catalogue(reg,'main')['read_only']


def test_live_operation_is_not_an_orphan(ready):
    _,ws,_,dbs,_=ready
    with ro.reserve(ws,library_id='main',database=dbs[0],kind='live'):
        assert operations.inspect(ws)['writes_allowed']
        assert inspect_storage(ws,database=dbs[0])['state']=='READY'


def test_dynamic_media_and_day_paths_do_not_change_storage(ready):
    _,ws,_,dbs,_=ready
    root=storage_paths(ws)['backup_root'];day=root/'synthetic-day';day.mkdir()
    f=day/'test.JPG';f.write_bytes(b'synthetic')
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    f.unlink();day.rmdir()
    work=storage_paths(ws)['workspaces_root']/'main'
    (work/'original.JPG').unlink()
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'


@pytest.mark.parametrize('kind',['metadata_general','metadata_multiple','trash_directory_name'])
def test_missing_required_anchor_is_global_and_not_recreated(ready,kind):
    _,ws,_,dbs,_=ready
    state=ro._read(ro._control_location(ws)/'state.json')
    anchor=Path(next(p for p,r in state['structural_anchors'].items() if r['role']==kind))
    anchor.rename(anchor.with_name(anchor.name+'-offline'))
    assert inspect_storage(ws,database=dbs[0])['state']=='UNAVAILABLE'
    assert not anchor.exists()


def test_replaced_required_anchor_is_global(ready):
    _,ws,_,dbs,_=ready
    anchor=storage_paths(ws)['trash_root'];anchor.rename(anchor.with_name(anchor.name+'-old'));anchor.mkdir()
    assert inspect_storage(ws,database=dbs[0])['state']=='UNAVAILABLE'


def test_unknown_operation_never_runs_normal_startup_recovery(ready):
    _,ws,reg,dbs,_=ready
    records=orphan(ws,dbs[0]);before=[p.read_bytes() for p in records]
    with pytest.raises(operations.DomainStartupError,match='unresolved_operation_scope'):
        with operations.recovery_session():operations.recover_known_before_startup(ws,reg,None)
    assert before==[p.read_bytes() for p in records]
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'


def test_refused_dng_write_preserves_verified_rollback(ready,monkeypatch):
    from tests.backend.test_pre2_metadata_abort import test_refused_write_finishes_only_verified_rollback
    test_refused_write_finishes_only_verified_rollback(ready,monkeypatch)
    _,ws,_,dbs,_=ready
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    assert operations.inspect(ws)['writes_allowed']


def test_corrected_jpeg_actual_transfer_and_repeated_startup(ready,monkeypatch):
    from tests.backend.test_pre3_metadata_transfer import test_new_success_receipt_then_transfer_and_two_restarts
    test_new_success_receipt_then_transfer_and_two_restarts(ready,monkeypatch)
    _,ws,_,dbs,_=ready
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    assert operations.inspect(ws)['writes_allowed']


def test_unknown_recovery_keeps_normal_ui_and_read_apis(ready,monkeypatch):
    from app import main
    from fastapi.testclient import TestClient
    _,ws,_,dbs,_=ready
    records=orphan(ws,dbs[0]);before={p:p.read_bytes() for p in records}
    calls=[]
    main._coordinate_startup(lambda:calls.append('ordinary startup mutation'))()
    assert calls==[] and main.DATABASE_INITIALIZATION_ERROR is None
    from contextlib import closing
    with closing(TestClient(main.app)) as client:
        for path in ('/','/trash','/api/jobs','/api/metadata-correction/areas','/api/metadata-correction/scan?area=general','/api/operations/status'):
            response=client.get(path)
            assert response.status_code==200,(path,response.status_code,response.text[:600])
            if path=='/':
                assert 'Storage unavailable' not in response.text
                assert 'bibliothekar-operation-notice' in response.text
        denied=client.post('/api/metadata-correction/correct',json={'area':'general','relative_path':'unknown.JPG'})
        assert denied.status_code==409 and denied.json()['storage_state']=='READY'
    assert {p:p.read_bytes() for p in records}==before


def test_read_session_and_direct_db_write_barrier(ready):
    from app.database import database_connection
    import sqlite3
    _,ws,_,dbs,_=ready
    orphan(ws,dbs[0])
    with operations.read_session(), database_connection(dbs[0]) as c:
        assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==0
        with pytest.raises(sqlite3.DatabaseError):c.execute("INSERT INTO settings(key,value) VALUES ('unsafe','value')")
    with pytest.raises(sqlite3.DatabaseError):
        with database_connection(dbs[0]) as c:c.execute("DELETE FROM files")


@pytest.mark.parametrize('failure',['missing_database','corrupt_database','missing_state','missing_workspace','symlink_general','binding_contradiction'])
def test_technical_failures_still_unavailable(ready,failure):
    _,ws,_,dbs,_=ready
    parent=ro._control_location(ws)
    if failure=='missing_database':dbs[0].unlink()
    elif failure=='corrupt_database':
        # Remove WAL checkpoint ambiguity in this isolated fixture, not a repair.
        import sqlite3
        c=sqlite3.connect(dbs[0]);c.execute('PRAGMA wal_checkpoint(TRUNCATE)');c.close()
        dbs[0].write_bytes(b'not a SQLite database')
    elif failure=='missing_state':(parent/'state.json').rename(parent/'state-lost-synthetic.json')
    elif failure=='missing_workspace':ws.rename(ws.with_name('workspace-offline'))
    elif failure=='symlink_general':
        root=storage_paths(ws)['metadata_root'];general=root/directory_name(root,'metadata_general');saved=general.with_name('original-general');general.rename(saved);general.symlink_to(saved,target_is_directory=True)
    else:
        record=orphan(ws,dbs[0])[0];data=ro._read(record);data['bindings'][str(ws)]=[1,2];ro._write(record,data)
    assert inspect_storage(ws,database=dbs[0])['state']=='UNAVAILABLE'


def test_malformed_domain_intent_fences_without_replacing_normal_storage(ready):
    _,ws,_,dbs,_=ready
    parent=ro._control_location(ws);path=parent/'operation-unknown.json';path.write_bytes(b'{"unknown":"preserve"}')
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    assert not operations.inspect(ws)['writes_allowed']
    assert path.read_bytes()==b'{"unknown":"preserve"}'


@pytest.mark.parametrize('key',['trash_directory_name','metadata_general','metadata_multiple','metadata_directory_name','workspaces_directory_name'])
def test_loss_confirmed_replacement_retains_anchors(ready,key):
    from app.storage_replacement import replace_managed_directory,CONFIRMATION
    _,ws,reg,dbs,_=ready
    state=ro._read(ro._control_location(ws)/'state.json')
    target=Path(next(p for p,r in state['structural_anchors'].items() if r['role']==key))
    retained=target.with_name(target.name+'-offline');target.rename(retained)
    assert inspect_storage(ws,database=dbs[0])['state']=='UNAVAILABLE'
    try:
        result=replace_managed_directory(ws,dbs[0],reg,key,CONFIRMATION)
    except ro.RootOperationError as error:
        raise AssertionError(str(error)+' '+json.dumps(inspect_storage(ws,database=dbs[0]))) from error
    assert result['loss_recorded'] and retained.is_dir()
    assert inspect_storage(ws,database=dbs[0])['state']=='READY',inspect_storage(ws,database=dbs[0])


@pytest.mark.parametrize('kind',['missing_media','hash_conflict','transfer_proof','failed_job'])
def test_domain_startup_errors_never_become_storage_failure_or_new_startup_intent(ready,monkeypatch,kind):
    from app import main
    _,ws,_,dbs,_=ready
    def domain():
        if kind=='missing_media':raise FileNotFoundError('single synthetic medium missing')
        if kind=='hash_conflict':raise ro.RootOperationError('individual media hash mismatch')
        if kind=='transfer_proof':raise operations.DomainStartupError('metadata_transfer_admission_missing_or_ambiguous')
        raise ValueError('single import result conflict')
    monkeypatch.setattr(main,'_start_runtime_workers',lambda:pytest.fail('unqualified worker release'))
    main._coordinate_startup(domain)()
    assert main.DATABASE_INITIALIZATION_ERROR is None
    assert main.api_storage_health()['state']=='READY'
    assert not operations.inspect(ws)['writes_allowed']
    assert not list(ro._control_location(ws).glob('operation-*.json'))


def test_existing_connection_cannot_reuse_old_write_authorization(ready):
    import sqlite3
    from app.database import database_connection
    _,ws,_,dbs,_=ready
    with database_connection(dbs[0]) as c:
        c.execute('DELETE FROM files');c.commit()
        orphan(ws,dbs[0])
        with pytest.raises(sqlite3.DatabaseError):c.execute('DELETE FROM files')


def test_recovering_live_lease_cannot_release_other_request_writes(ready):
    import threading
    _,ws,_,dbs,_=ready
    observations=[]
    @operations.startup_session(lambda:ws)
    def recovery():
        with ro.reserve(ws,library_id='main',database=dbs[0],kind='metadata',ids={'id':'synthetic-recovery'}):
            def other_request():
                status=operations.inspect(ws)
                assert not status['writes_allowed']
                assert any(i['phase']=='recovery_in_progress' for i in status['issues'])
                with pytest.raises(ro.RootOperationError):operations.require_write(ws)
                observations.append(inspect_storage(ws,database=dbs[0])['state'])
            thread=threading.Thread(target=other_request);thread.start();thread.join(5)
            assert not thread.is_alive()
    recovery()
    assert observations==['READY'] and operations.inspect(ws)['writes_allowed']


def test_technical_sqlite_startup_failure_keeps_authenticated_recovery_server(ready,monkeypatch):
    import sqlite3
    from app import main
    _,ws,_,_,_=ready
    def fail():raise sqlite3.DatabaseError('synthetic SQLite structural failure')
    monkeypatch.setattr(main,'_prepare_technical_storage',fail)
    main._coordinate_startup(lambda:pytest.fail('domain work past failed schema'))()
    assert main.DATABASE_INITIALIZATION_ERROR
    assert main.api_storage_health()['state']=='UNAVAILABLE'
    assert list(ro._control_location(ws).glob('operation-*.json'))


def test_technical_only_startup_retries_original_nonce(ready,monkeypatch):
    from app import main
    _,ws,_,_,_=ready
    prepare=main._prepare_technical_storage
    def fail():
        prepare()
        raise OSError('synthetic interruption after schema preparation')
    monkeypatch.setattr(main,'_prepare_technical_storage',fail)
    monkeypatch.setattr(main,'_start_runtime_workers',lambda:None)
    main._coordinate_startup(lambda:None)()
    path=next(ro._control_location(ws).glob('operation-*.json'))
    original=ro._read(path)
    assert original['ids']==operations._TECHNICAL_STARTUP_IDS
    monkeypatch.setattr(main,'_prepare_technical_storage',prepare)
    main._coordinate_startup(lambda:None)()
    assert main.DATABASE_INITIALIZATION_ERROR is None and not path.exists()
    proof=ro._read(path.parent/('technical-startup-'+original['reservation_id']+'.json'))
    assert proof['reservation']==original
    assert main.api_storage_health()['state']=='READY' and operations.inspect(ws)['writes_allowed']


def test_trash_inventory_restore_and_confirmed_delete_preserve_global_ready(ready,monkeypatch):
    from app.database import database_connection
    from app.trash import reconcile_trash_inventory
    from app.trash_restore import restore_trash_files
    from app.trash_selective import delete_selected_trash_files
    from tests.backend.test_rc1_sd_reimport import setup_live_import,queue_and_run
    from tests.backend.test_rc13_provenance import origin
    case,ws,reg,dbs,source,context=setup_live_import(ready,monkeypatch)
    queue_and_run(dbs[0],context)
    historical=origin(reg)
    with database_connection(dbs[0]) as c:row=dict(c.execute('SELECT * FROM files').fetchone())
    paths=storage_paths(ws);published=paths['backup_root']/row['current_relative_path']
    original=published.read_bytes();trash=paths['trash_root']/'Reviewed'/published.name
    trash.parent.mkdir();published.rename(trash)
    # The supported Finder intake is reconciled by the actual trash module.
    reconcile_trash_inventory(dbs[0],ws)
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    result=restore_trash_files(dbs,ws,relative_paths=['Reviewed/'+trash.name])
    assert result['restored_file_count']==1 and published.read_bytes()==original
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    published.rename(trash);reconcile_trash_inventory(dbs[0],ws)
    deleted=delete_selected_trash_files(dbs,ws,['Reviewed/'+trash.name])
    assert deleted['deleted_file_count']==1 and not trash.exists()
    assert source.read_bytes()==original
    current=origin(reg)
    for table in ('source_families','source_media','source_family_members'):assert current[table]==historical[table]
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'


def test_sd_write_mount_refusal_keeps_global_ready_and_original_source(ready,monkeypatch):
    from app import main
    from tests.backend.test_rc1_sd_reimport import setup_live_import,queue_and_run
    data=setup_live_import(ready,monkeypatch)
    case,ws,reg,dbs,source,context=data
    before=source.read_bytes()
    queue_and_run(dbs[0],context)
    # This pytest source really is RW. Do not manufacture a RO success.
    with pytest.raises(main.HTTPException) as error:
        main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':True,'request_id':'isolated-read-write-card'})
    assert error.value.status_code==409 and 'lesend' in str(error.value.detail)
    assert source.read_bytes()==before
    assert inspect_storage(ws,database=dbs[0])['state']=='READY'
    assert operations.inspect(ws)['writes_allowed']


def test_required_subanchor_is_checked_during_active_operation(ready):
    _,ws,_,dbs,_=ready
    root=storage_paths(ws)['metadata_root'];general=root/directory_name(root,'metadata_general')
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',database=dbs[0],kind='metadata'):
            general.rename(general.with_name('preserved-general'));general.mkdir()
            ro.validate_active_roots()
    assert inspect_storage(ws,database=dbs[0])['state']=='UNAVAILABLE'
    assert list(ro._control_location(ws).glob('operation-*.json'))
