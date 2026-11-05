"""Real synthetic startup/configuration and retained-restore counterprobes."""
from pathlib import Path
import json
import threading
import pytest

from app import main,root_operations as ro,operation_health as health
from app.central_stock_reconcile import reconcile_central_free_stock
from app.managed_storage_health import inspect_storage
from tests.backend.test_f14_fixed_storage import home,stable,child
from tests.backend.test_0562_process_recovery import isolated_process_environment
from tests.backend import test_r1_restore_recovery as restore


@pytest.mark.parametrize('fault',['missing','malformed','symlink','wrong_config_path'])
def test_established_configuration_failure_is_not_recreated(home,monkeypatch,fault):
    case,ws,reg,db,context=home;config=case/'settings.json'
    if fault=='missing':config.unlink()
    elif fault=='malformed':config.write_text('{"storage":')
    elif fault=='symlink':
        saved=case/'saved-settings.json';config.rename(saved);config.symlink_to(saved)
    else:
        config=case/'wrong-settings.json'
        monkeypatch.setenv('KAMERA_CONFIG',str(config));monkeypatch.setattr(main,'CONFIG_PATH',config)
    before=stable(case)
    observed=inspect_storage(ws,database=db)
    assert not observed['ready'] and not observed['can_initialize'],observed
    assert any(i['path']==str(config) for i in observed['issues']),observed
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is not None
    assert stable(case)==before,'Startup rewrote an unavailable established configuration or its evidence'
    if fault in {'missing','wrong_config_path'}:assert not config.exists()


@pytest.mark.parametrize('fault',['workspace_replaced','general_missing'])
def test_empty_folder_bootstrap_does_not_waive_future_anchor_identity(tmp_path,monkeypatch,fault):
    from app.storage_config import ENGLISH_STORAGE_DEFAULTS
    case=tmp_path/'case';case.mkdir();ws=case/'workspace';ws.mkdir()
    private=case/'database';private.mkdir();(case/'archive').mkdir()
    for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
    for name,value in {'KAMERA_CONFIG':case/'settings.json','KAMERA_WORKSPACE':ws,
                       'KAMERA_REGISTRY_DATABASE':private/'registry.sqlite3',
                       'KAMERA_ARCHIVE_ROOT':case/'archive'}.items():monkeypatch.setenv(name,str(value))
    assert child(case,tmp_path/'initial-boot')['error'] is None
    if fault=='workspace_replaced':
        ws.rename(case/'retained-original-workspace');ws.mkdir()
        for name in ENGLISH_STORAGE_DEFAULTS.values():(ws/name).mkdir()
        (ws/'Metadata Correction/General').mkdir();(ws/'Metadata Correction/Batch Correction').mkdir()
    else:(ws/'Metadata Correction/General').rename(case/'retained-original-general')
    before=stable(case);status=inspect_storage(ws,database=private/'main.sqlite3')
    assert not status['ready'] and not status['can_initialize'],status
    assert any(i['code'] in {'workspace_identity_changed','identity_changed','missing'} for i in status['issues']),status
    assert child(case,tmp_path/'refused-restart')['error'] is not None
    assert stable(case)==before,'Replacement administrative anchor was silently adopted'


@pytest.mark.parametrize('kind',['different','same','hardlink','symlink','directory'])
def test_reconcile_qualifies_restore_but_never_adopts_foreign_target(tmp_path,monkeypatch,kind):
    case,ev,data,ws=restore.seed(tmp_path,monkeypatch)
    target=restore.collision(data,ws,monkeypatch,kind);identity=restore.tr._identity(target)
    parent=ro._control_location(ws);operation,=parent.glob('operation-*.json')
    original=ro._read(operation);journal=restore.journal(case);saved=journal.read_bytes()
    for database,library in zip(data['dbs'],('main','second1')):
        for _ in range(2):assert reconcile_central_free_stock(database,ws,library_id=library)['ready']
    assert not operation.exists()
    receipt=ro._read(parent/('domain-recovery-'+original['reservation_id']+'.json'))
    assert receipt['reservation']==original
    assert receipt['disposition']=='verified_restore_conflict_isolated_paths_remain_reserved'
    assert journal.read_bytes()==saved and restore.tr._identity(target)==identity
    restore.preserved(data,ws,target,kind)
    with pytest.raises(restore.TrashError):restore.tr.assert_restore_paths_available(ws,['A.JPG'])
    restore.tr.assert_restore_paths_available(ws,['B.JPG'])
    restore.starts(case,ev);restore.preserved(data,ws,target,kind)


@pytest.mark.parametrize('fault',['source_bytes','source_inode','catalogue'])
def test_reconcile_cannot_finish_unqualified_restore_or_create_a_new_intent(tmp_path,monkeypatch,fault):
    from tests.backend.external_sql import external_edit
    case,ev,data,ws=restore.seed(tmp_path,monkeypatch)
    target=restore.collision(data,ws,monkeypatch,'same');source=ws/'Papierkorb/A.JPG'
    if fault=='source_bytes':source.write_bytes(b'unknown-original-variant')
    elif fault=='source_inode':
        replacement=source.with_suffix('.new');replacement.write_bytes(source.read_bytes());replacement.replace(source)
    else:
        with external_edit(data['dbs'][1],fixture_root=case) as connection:
            connection.execute("UPDATE files SET current_root_kind='shared_workspace' WHERE original_filename='A.JPG'")
    parent=ro._control_location(ws);before={p.name:p.read_bytes() for p in parent.glob('operation-*.json')}
    original_bytes=source.read_bytes();foreign_bytes=target.read_bytes()
    with pytest.raises(RuntimeError):reconcile_central_free_stock(data['dbs'][0],ws,library_id='main')
    assert {p.name:p.read_bytes() for p in parent.glob('operation-*.json')}==before
    assert not health.inspect(ws)['writes_allowed']
    assert source.read_bytes()==original_bytes and target.read_bytes()==foreign_bytes


def test_read_snapshot_does_not_wait_for_or_replay_a_physical_trash_writer(tmp_path,monkeypatch):
    case,ev,data,ws=restore.seed(tmp_path,monkeypatch);outcomes=[]
    def read():
        try:
            with health.read_session():outcomes.append(reconcile_central_free_stock(data['dbs'][0],ws,library_id='main'))
        except BaseException as error:outcomes.append(error)
    parent=ro._control_location(ws);before={p.name:p.read_bytes() for p in parent.glob('*.json')}
    with restore.ts._operation_lock(ws):
        thread=threading.Thread(target=read);thread.start();thread.join(3)
        assert not thread.is_alive(),'A protected READ waited for the writer lock'
        assert len(outcomes)==1 and isinstance(outcomes[0],dict) and outcomes[0]['read_only'],outcomes
    assert {p.name:p.read_bytes() for p in parent.glob('*.json')}==before
