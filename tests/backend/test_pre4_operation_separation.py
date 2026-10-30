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
