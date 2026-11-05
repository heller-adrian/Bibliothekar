"""Fault counterprobes at newly introduced persistence boundaries."""
from pathlib import Path
import pytest
from app.database import database_connection, initialize_database


def test_restore_fsync_failure_keeps_last_original(tmp_path,monkeypatch):
    from tests.backend.test_0530_trash_restore import _fixture, _put
    from app.trash_restore import restore_trash_files
    from app.trash import TrashError
    import app.trash_selective as ts
    db,workspace,paths=_fixture(tmp_path,monkeypatch)
    _put(db,workspace,paths,'A.JPG',b'only-original-bytes')
    original=Path(paths['trash_root'])/'Gesichtet/A.JPG'
    actual=ts._sync_dir
    failed=False
    def fail_after_unlink(path):
        nonlocal failed
        if path==original.parent and not original.exists() and not failed:
            failed=True
            raise OSError('synthetic fsync after unlink failure')
        actual(path)
    monkeypatch.setattr(ts,'_sync_dir',fail_after_unlink)
    with pytest.raises(TrashError):restore_trash_files([db],workspace)
    assert failed and original.read_bytes()==b'only-original-bytes'
    with database_connection(db) as c:
        assert c.execute("SELECT current_root_kind FROM files").fetchone()[0]=='trash'


def test_metadata_propagation_missing_database_stays_pending(tmp_path,monkeypatch):
    from tests.backend.test_0500_metadata_swap_recovery import _seed_library
    from app.metadata_correction import apply_metadata_correction, replay_pending_metadata_propagations, get_metadata_correction
    from app.global_stock import GlobalStockError
    db,ws,src,fid,task=_seed_library(tmp_path)
    import app.metadata_correction as mc
    monkeypatch.setattr(mc,'write_metadata_datetime',lambda path,media,value: Path(path).write_bytes(Path(path).read_bytes()+b'|corrected'))
    monkeypatch.setattr(mc,'verify_metadata_datetime',lambda path,value: {'expected_datetime':value,'matching_tags':[{'tag':'synthetic','value':value}],'observed_tags':[]})
    apply_metadata_correction(db,task,workspace_root=ws,library_id='main')
    missing=tmp_path/'missing.sqlite3'
    with pytest.raises(GlobalStockError):replay_pending_metadata_propagations([db,missing])
    assert get_metadata_correction(db,task)['verification']['projection_pending'] is True
    assert src.is_file()


@pytest.mark.parametrize('registered',[True,False])
def test_startup_recovers_registered_databases_only(tmp_path,monkeypatch,registered):
    from types import SimpleNamespace
    from app import main
    from app.library_registry import register_library,unregister_library
    from tests.backend.test_0400_import_backup_controls import _foundation
    (tmp_path/'database').mkdir()
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(tmp_path/'database/bibliothekar-global.sqlite3'))
    monkeypatch.setenv('KAMERA_WORKSPACE',str(tmp_path/'workspace'))
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'))
    (tmp_path/'settings.json').write_text('{}')
    db,registry,workspace=_foundation(tmp_path)
    monkeypatch.setenv("KAMERA_REGISTRY_DATABASE",str(registry))
    monkeypatch.setenv("KAMERA_WORKSPACE",str(workspace))
    monkeypatch.setenv("KAMERA_CONFIG",str(tmp_path/"settings.json"))
    missing=tmp_path/'removed-library.sqlite3'
    register_library(registry,library_id='removed',display_name='Removed',database_path=missing,
                     workspace_root=workspace,work_root=workspace/'Arbeitsbereiche/Removed',archive_root=tmp_path/'other-archive',is_active=False)
    if not registered:
        # Historical pre-RC14 tombstone: removal cannot authorize missing DBs.
        import sqlite3
        with sqlite3.connect(registry) as c:
            c.execute("UPDATE libraries SET is_registered=0,is_active=0 WHERE library_id='removed'")
    for key,value in dict(DATABASE_FILE=db,REGISTRY_DATABASE_FILE=registry,WORKSPACE_PATH=workspace,
                          CONFIG_PATH=tmp_path/'settings.json',LOG_PATH=tmp_path/'logs',
                          WORKER_THREAD=None).items():
        monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(main,'Thread',lambda **kw:SimpleNamespace(start=lambda:None,is_alive=lambda:False,join=lambda timeout=None:None))
    monkeypatch.setattr(main,'start_cancel_worker',lambda:None)
    monkeypatch.setattr(main,'start_release_worker',lambda:None)
    main.startup_database()
    if registered:
        # The structural preflight must reject this *before* migrations or
        # recovery run. Assert exact role/path instead of obsolete wording.
        from app.managed_storage_health import inspect_storage
        health=inspect_storage(workspace,database=db)
        assert main.DATABASE_INITIALIZATION_ERROR is not None
        assert not health['ready'] and any(i['code']=='catalog_unavailable' and i['path']==str(missing) for i in health['issues']),health
    else:assert main.DATABASE_INITIALIZATION_ERROR is None,main.DATABASE_INITIALIZATION_ERROR
    assert not missing.exists()
