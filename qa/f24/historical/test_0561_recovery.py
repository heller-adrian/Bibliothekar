"""Focused fault injection for the four audited 0.56.2 corrections."""
from pathlib import Path
import json
import sqlite3
import threading

import pytest
from fastapi import HTTPException

from app import main, metadata_correction as mc, metadata_swap_recovery as ms, trash_selective as ts
from app.database import database_connection, initialize_database
from app.library_registry import initialize_library_registry
from app.storage_config import load_storage_settings, storage_paths
from app.trash import TrashError
from tests.backend.test_0561_audit_regressions import trash_case, sha


class Interrupted(BaseException):
    """Process-stop boundary: bypass application exception recovery."""


def journal_for(workspace):
    return next((storage_paths(workspace)['metadata_root']/'.trash-deletions').glob('DELETE_*.json'))


def catalogue(db):
    with database_connection(db) as c:
        return {t: [dict(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY id')]
                for t in ('files', 'file_families')}


@pytest.mark.parametrize('boundary', ['stage', 'first_db', 'last_db', 'committed', 'cleanup'])
def test_trash_restart_at_each_durable_boundary(tmp_path, monkeypatch, boundary):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    before = [catalogue(p) for p in (db, other)]
    with monkeypatch.context() as m:
        if boundary == 'stage':
            real = ts._move_checked
            def stop(*args, **kwargs):
                real(*args, **kwargs)
                raise Interrupted()
            m.setattr(ts, '_move_checked', stop)
        elif boundary in ('first_db', 'last_db'):
            real = ts._purge_selected
            target = db if boundary == 'first_db' else other
            def stop(path, selection):
                real(path, selection)
                if path == target:
                    raise Interrupted()
            m.setattr(ts, '_purge_selected', stop)
        elif boundary == 'committed':
            real = ts._atomic_json
            def stop(path, value):
                real(path, value)
                if value['state'] == 'committed':
                    raise Interrupted()
            m.setattr(ts, '_atomic_json', stop)
        else:
            m.setattr(ts, '_remove_empty_staging', lambda *_: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted):
            ts.delete_selected_trash_files([db, other], workspace, ['A.JPG'])
    assert journal_for(workspace).is_file()
    for _ in range(2):
        ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    source = Path(paths['trash_root'])/'A.JPG'
    if boundary in ('committed', 'cleanup'):
        assert not source.exists()
        assert all(catalogue(p)['files'] == [] for p in (db, other))
    else:
        assert source.read_bytes() == payload
        assert [catalogue(p) for p in (db, other)] == before
    assert not list(journal_for_parent(workspace).glob('DELETE_*'))


def journal_for_parent(workspace):
    return storage_paths(workspace)['metadata_root']/'.trash-deletions'


def interrupt_after_first_db(db, other, workspace, monkeypatch):
    real = ts._purge_selected
    with monkeypatch.context() as m:
        def stop(path, selection):
            if path == other:
                raise Interrupted()
            real(path, selection)
        m.setattr(ts, '_purge_selected', stop)
        with pytest.raises(Interrupted):
            ts.delete_selected_trash_files([db, other], workspace, ['A.JPG'])


@pytest.mark.parametrize('boundary', ['catalogue', 'file_return', 'journal_removal'])
def test_trash_recovery_can_itself_be_interrupted(tmp_path, monkeypatch, boundary):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    before = [catalogue(p) for p in (db, other)]
    interrupt_after_first_db(db, other, workspace, monkeypatch)
    with monkeypatch.context() as m:
        name = {'catalogue':'_restore_catalogue', 'file_return':'_return_checked',
                'journal_removal':'_remove_empty_staging'}[boundary]
        real = getattr(ts, name)
        def stop(*a, **kw):
            real(*a, **kw)
            raise Interrupted()
        m.setattr(ts, name, stop)
        with pytest.raises(Interrupted):
            ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert journal_for(workspace).exists()
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert [catalogue(p) for p in (db, other)] == before
    assert (Path(paths['trash_root'])/'A.JPG').read_bytes() == payload
    with database_connection(db) as c:
        assert c.execute("SELECT count(*) FROM audit_log WHERE action='trash_deletion_rolled_back'").fetchone()[0] == 1


def test_partial_commit_restores_cascade_and_set_null_preserves_other_edits(tmp_path, monkeypatch):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    with database_connection(db) as c:
        fid = c.execute('SELECT id FROM files').fetchone()[0]
        c.execute('CREATE TABLE qa_cascade(id INTEGER PRIMARY KEY, file_id INTEGER REFERENCES files(id) ON DELETE CASCADE, note TEXT)')
        c.execute('CREATE TABLE qa_nullable(id INTEGER PRIMARY KEY, file_id INTEGER REFERENCES files(id) ON DELETE SET NULL, note TEXT)')
        c.execute("INSERT INTO qa_cascade VALUES(1,?,'provenance')", (fid,))
        c.execute("INSERT INTO qa_nullable VALUES(1,?,'before')", (fid,))
    interrupt_after_first_db(db, other, workspace, monkeypatch)
    with database_connection(db) as c:
        assert c.execute('SELECT count(*) FROM qa_cascade').fetchone()[0] == 0
        assert c.execute('SELECT file_id FROM qa_nullable').fetchone()[0] is None
        c.execute("UPDATE qa_nullable SET note='independent edit'")
        c.execute("INSERT INTO qa_cascade VALUES(2,NULL,'unrelated row')")
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    with database_connection(db) as c:
        assert tuple(c.execute('SELECT * FROM qa_cascade WHERE id=1').fetchone()) == (1, fid, 'provenance')
        assert c.execute('SELECT note FROM qa_cascade WHERE id=2').fetchone()[0] == 'unrelated row'
        assert tuple(c.execute('SELECT * FROM qa_nullable').fetchone()) == (1, fid, 'independent edit')
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert (Path(paths['trash_root'])/'A.JPG').read_bytes() == payload


@pytest.mark.parametrize('tamper', ['bytes', 'unexpected_file', 'symlink', 'unregistered_db', 'schema', 'row_conflict', 'legacy'])
def test_trash_recovery_refuses_ambiguous_state_and_keeps_evidence(tmp_path, monkeypatch, tamper):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    interrupt_after_first_db(db, other, workspace, monkeypatch)
    journal = journal_for(workspace)
    data = json.loads(journal.read_text())
    staged = journal.with_suffix('')/'A.JPG'
    if tamper == 'bytes': staged.write_bytes(b'changed synthetic bytes')
    elif tamper == 'unexpected_file': (staged.parent/'foreign.JPG').write_bytes(b'foreign')
    elif tamper == 'symlink':
        staged.unlink()
        staged.symlink_to(tmp_path/'outside')
    elif tamper == 'unregistered_db': data['databases'][0]['path'] = str(tmp_path/'unregistered.sqlite3')
    elif tamper == 'schema':
        with database_connection(db) as c: c.execute('CREATE TABLE qa_new(id INTEGER PRIMARY KEY)')
    elif tamper == 'row_conflict':
        with database_connection(db) as c:
            row = dict(next(e['row'] for e in data['databases'][0]['snapshot']['deleted'] if e['table']=='file_families'))
            row['original_stem'] = 'foreign conflict'
            c.execute('INSERT INTO file_families ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')', tuple(row.values()))
    elif tamper == 'legacy': data.pop('format')
    journal.write_text(json.dumps(data))
    with pytest.raises(TrashError):
        ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert journal.exists()
    assert staged.exists() or staged.is_symlink()
    assert not (Path(paths['trash_root'])/'A.JPG').exists()


def test_journal_replace_failure_retains_previous_durable_record(tmp_path, monkeypatch):
    path = tmp_path/'journal.json'
    ts._atomic_json(path, {'state':'prepared'})
    with monkeypatch.context() as m:
        m.setattr(ts.os, 'replace', lambda *_: (_ for _ in ()).throw(OSError('injected replace')))
        with pytest.raises(OSError): ts._atomic_json(path, {'state':'committed'})
    assert json.loads(path.read_text()) == {'state':'prepared'}
    assert list(tmp_path.iterdir()) == [path]


def test_recovery_waits_for_live_deletion(tmp_path, monkeypatch):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    entered = threading.Event(); release = threading.Event(); recovered = threading.Event()
    errors = []
    real = ts._purge_selected
    def pause(path, selection):
        if path == db:
            entered.set()
            assert release.wait(5)
        real(path, selection)
    monkeypatch.setattr(ts, '_purge_selected', pause)
    def deleting():
        try: ts.delete_selected_trash_files([db, other], workspace, ['A.JPG'])
        except BaseException as e: errors.append(e)
    def recovery():
        try: ts.recover_trash_deletions(workspace, allowed_databases={db, other})
        except BaseException as e: errors.append(e)
        finally: recovered.set()
    a = threading.Thread(target=deleting); a.start()
    assert entered.wait(5)
    b = threading.Thread(target=recovery); b.start()
    try: assert not recovered.wait(.1)
    finally: release.set(); a.join(5); b.join(5)
    assert not a.is_alive() and not b.is_alive() and not errors
    assert not (Path(paths['trash_root'])/'A.JPG').exists()


def general_case(tmp_path, monkeypatch):
    from PIL import Image
    workspace = tmp_path/'workspace'; workspace.mkdir()
    monkeypatch.setenv('KAMERA_CONFIG', str(tmp_path/'settings.json'))
    db = tmp_path/'catalogue.sqlite3'; initialize_database(db)
    root = mc.metadata_area_paths(area='general', workspace_root=workspace, library_id='main')['root']
    source = root/'synthetic.JPG'; Image.new('RGB', (16,16), (51,102,153)).save(source)
    original = source.read_bytes()
    task = mc.create_metadata_correction(db, area='general', relative_path=source.name,
        proposed_datetime='2026-10-01T12:34:56', workspace_root=workspace, library_id='main',
        _prevalidated_row={'relative_path':source.name,'filename':source.name,'media_type':'jpeg'}, _prevalidated_source=source)
    return db, workspace, source, original, task


@pytest.mark.parametrize('boundary', ['backup', 'swap', 'db_commit', 'journal_commit', 'cleanup'])
def test_general_metadata_restart_boundaries(tmp_path, monkeypatch, boundary):
    db, workspace, source, original, task = general_case(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        if boundary in ('backup', 'swap'):
            real = mc.os.replace
            def stop(src, dst):
                real(src, dst)
                if (boundary == 'backup' and Path(src) == source) or (boundary == 'swap' and Path(dst) == source):
                    raise Interrupted()
            m.setattr(mc.os, 'replace', stop)
        elif boundary == 'db_commit':
            real = mc._complete_task
            def stop(*a, **kw):
                real(*a, **kw)
                raise Interrupted()
            m.setattr(mc, '_complete_task', stop)
        elif boundary == 'journal_commit':
            real = ms.mark_swap_committed
            def stop(*a, **kw):
                real(*a, **kw)
                raise Interrupted()
            m.setattr(ms, 'mark_swap_committed', stop)
        else:
            real = ms._finish
            def stop(*a, **kw):
                real(*a, **kw)
                raise Interrupted()
            m.setattr(ms, '_finish', stop)
        with pytest.raises(Interrupted):
            mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    metadata = storage_paths(workspace)['metadata_root']
    result = ms.recover_metadata_swaps(metadata, allowed_databases={db})
    assert result['blocked'] == 0
    assert ms.recover_metadata_swaps(metadata, allowed_databases={db})['blocked'] == 0
    current = mc.get_metadata_correction(db, task['id'])
    if boundary in ('backup', 'swap'):
        assert source.read_bytes() == original and current['status'] == 'blocked'
        mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    assert mc.get_metadata_correction(db, task['id'])['status'] == 'completed'
    assert mc.verify_metadata_datetime(source, '2026-10-01T12:34:56')['matching_tags']


def test_general_metadata_recovery_interrupted_after_original_return(tmp_path, monkeypatch):
    db, workspace, source, original, task = general_case(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(mc, '_complete_task', lambda *a, **k: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted): mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    metadata = storage_paths(workspace)['metadata_root']
    with monkeypatch.context() as m:
        real = ms._rollback
        def stop(*a):
            real(*a)
            raise Interrupted()
        m.setattr(ms, '_rollback', stop)
        with pytest.raises(Interrupted): ms.recover_metadata_swaps(metadata, allowed_databases={db})
    assert source.read_bytes() == original
    assert ms.recover_metadata_swaps(metadata, allowed_databases={db})['rolled_back'] == 1
    mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    assert mc.get_metadata_correction(db, task['id'])['status'] == 'completed'


def rename_case(tmp_path, monkeypatch):
    monkeypatch.setenv('KAMERA_CONFIG', str(tmp_path/'settings.json'))
    workspace = tmp_path/'workspace'; workspace.mkdir()
    db = tmp_path/'main.sqlite3'; reg = tmp_path/'registry.sqlite3'
    initialize_database(db); initialize_library_registry(reg)
    for key, value in {'WORKSPACE_PATH':workspace, 'DATABASE_FILE':db, 'REGISTRY_DATABASE_FILE':reg,
                       'DATABASE_DIRECTORY':tmp_path}.items(): monkeypatch.setattr(main,key,value)
    monkeypatch.setattr(main,'_storage_settings_state',lambda:{'synthetic_response':True})
    return workspace


@pytest.mark.parametrize('target', ['existing', 'new', 'workspace', 'parent', 'dangling'])
def test_root_rename_rejects_raw_symlink_components(tmp_path, monkeypatch, target):
    workspace = rename_case(tmp_path, monkeypatch)
    outside = tmp_path/'outside'; outside.mkdir(); (outside/'sentinel').write_bytes(b'synthetic')
    name = load_storage_settings()['trash_directory_name']
    if target in ('existing', 'dangling'):
        (workspace/name).symlink_to(outside if target == 'existing' else tmp_path/'absent', target_is_directory=True)
    elif target == 'new': (workspace/'RenamedTrash').symlink_to(outside, target_is_directory=True)
    elif target == 'workspace':
        link = tmp_path/'alias'; link.symlink_to(workspace, target_is_directory=True)
        monkeypatch.setattr(main,'WORKSPACE_PATH',link)
    else:
        link = tmp_path/'parent'; link.symlink_to(tmp_path, target_is_directory=True)
        monkeypatch.setattr(main,'WORKSPACE_PATH',link/'workspace')
    with pytest.raises(HTTPException) as error: main.api_set_storage_paths({'trash_directory_name':'RenamedTrash'})
    assert error.value.status_code == 422
    assert (outside/'sentinel').read_bytes() == b'synthetic'
    assert load_storage_settings()['trash_directory_name'] == name


def test_root_rename_normal_directory_preserves_bytes(tmp_path, monkeypatch):
    workspace = rename_case(tmp_path, monkeypatch)
    old = workspace/load_storage_settings()['trash_directory_name']; old.mkdir()
    (old/'synthetic.JPG').write_bytes(b'synthetic')
    main.api_set_storage_paths({'trash_directory_name':'RenamedTrash'})
    assert not old.exists()
    assert (workspace/'RenamedTrash'/'synthetic.JPG').read_bytes() == b'synthetic'
    assert load_storage_settings()['trash_directory_name'] == 'RenamedTrash'


@pytest.mark.parametrize('tamper', ['unregistered_db', 'changed_source', 'changed_backup'])
def test_general_metadata_recovery_keeps_ambiguous_originals(tmp_path, monkeypatch, tamper):
    db, workspace, source, original, task = general_case(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(mc, '_complete_task', lambda *a, **k: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted): mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    metadata = storage_paths(workspace)['metadata_root']
    journal = next((metadata/'.swap-journals').glob('*.json'))
    record = json.loads(journal.read_text())
    backup = Path(record['files'][0]['backup'])
    approved = {db}
    if tamper == 'unregistered_db': approved = {tmp_path/'unregistered.sqlite3'}
    elif tamper == 'changed_source': source.write_bytes(b'changed synthetic file')
    else: backup.write_bytes(b'changed synthetic backup')
    result = ms.recover_metadata_swaps(metadata, allowed_databases=approved)
    assert result['blocked'] == 1 and journal.exists() and backup.exists()
    assert mc.get_metadata_correction(db, task['id'])['status'] == 'writing'
    if tamper != 'changed_backup': assert backup.read_bytes() == original


@pytest.mark.parametrize('boundary', ['link', 'source_unlink'])
def test_trash_recovery_handles_dual_copy_stage_boundary(tmp_path, monkeypatch, boundary):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    before = [catalogue(p) for p in (db, other)]
    source = Path(paths['trash_root'])/'A.JPG'
    with monkeypatch.context() as m:
        if boundary == 'link':
            real = ts.os.link
            def stop(*a, **kw):
                real(*a, **kw)
                raise Interrupted()
            m.setattr(ts.os, 'link', stop)
        else:
            real = Path.unlink
            def stop(path, *a, **kw):
                real(path, *a, **kw)
                if path == source: raise Interrupted()
            m.setattr(Path, 'unlink', stop)
        with pytest.raises(Interrupted): ts.delete_selected_trash_files([db, other], workspace, ['A.JPG'])
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert source.read_bytes() == payload
    assert [catalogue(p) for p in (db, other)] == before


def test_partial_commit_restores_real_family_and_file_assignments(tmp_path, monkeypatch):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    with database_connection(db) as c:
        file_id, family_id = tuple(c.execute('SELECT id,family_id FROM files').fetchone())
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,folder_name,created_at,updated_at)
                     VALUES('E','J','parent','Synthetic','2026-10-01','2026-10-31','Synthetic','now','now')""")
        c.execute("INSERT INTO event_assignments(event_id,family_id,assignment_source,created_at) VALUES('E',?,'manual','now')", (family_id,))
        c.execute("INSERT INTO event_assignments(event_id,file_id,assignment_source,created_at) VALUES('E',?,'manual','now')", (file_id,))
        before = [tuple(r) for r in c.execute('SELECT * FROM event_assignments ORDER BY id')]
    interrupt_after_first_db(db, other, workspace, monkeypatch)
    with database_connection(db) as c: assert c.execute('SELECT count(*) FROM event_assignments').fetchone()[0] == 0
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    with database_connection(db) as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM event_assignments ORDER BY id')] == before
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
    assert (Path(paths['trash_root'])/'A.JPG').read_bytes() == payload


def test_trash_stage_and_return_cross_mount_fallback(tmp_path, monkeypatch):
    import errno
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    before = [catalogue(p) for p in (db, other)]
    monkeypatch.setattr(ts.os, 'link', lambda *a, **k: (_ for _ in ()).throw(OSError(errno.EXDEV, 'synthetic bind-mount boundary')))
    interrupt_after_first_db(db, other, workspace, monkeypatch)
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert (Path(paths['trash_root'])/'A.JPG').read_bytes() == payload
    assert [catalogue(p) for p in (db, other)] == before


def test_startup_recovers_general_swap_before_onboarding_worker(tmp_path, monkeypatch):
    from types import SimpleNamespace
    db, workspace, source, original, task = general_case(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(mc, '_complete_task', lambda *a, **k: (_ for _ in ()).throw(Interrupted()))
        with pytest.raises(Interrupted): mc.apply_metadata_correction(db, task['id'], workspace_root=workspace, library_id='main')
    reg = tmp_path/'registry.sqlite3'; initialize_library_registry(reg)
    for key,value in {'WORKSPACE_PATH':workspace, 'DATABASE_FILE':db, 'REGISTRY_DATABASE_FILE':reg,
        'CONFIG_PATH':tmp_path/'settings.json', 'WORKER_THREAD':SimpleNamespace(is_alive=lambda:True)}.items():
        monkeypatch.setattr(main,key,value)
    checks = []
    def worker_start():
        checks.append(source.read_bytes() == original and mc.get_metadata_correction(db, task['id'])['status'] == 'blocked')
    monkeypatch.setattr(main,'start_cancel_worker',worker_start)
    monkeypatch.setattr(main,'start_release_worker',lambda:None)
    main.startup_database()
    assert main.DATABASE_INITIALIZATION_ERROR is None
    assert checks == [True]
    assert not list((storage_paths(workspace)['metadata_root']/'.swap-journals').glob('*.json'))


def test_committed_journal_sync_failure_retains_original_until_retry(tmp_path, monkeypatch):
    db, other, workspace, paths, payload = trash_case(tmp_path, monkeypatch, two=True)
    real_write = ts._atomic_json
    armed = False
    with monkeypatch.context() as m:
        def arm_after_replace(path, value):
            nonlocal armed
            real_write(path, value)
            if value['state'] == 'committed': armed = True
        real_sync = ts._sync_dir
        def fail_sync(path):
            if armed: raise OSError('synthetic directory fsync failure')
            real_sync(path)
        m.setattr(ts, '_atomic_json', arm_after_replace)
        m.setattr(ts, '_sync_dir', fail_sync)
        with pytest.raises(TrashError): ts.delete_selected_trash_files([db, other], workspace, ['A.JPG'])
    journal = journal_for(workspace)
    assert json.loads(journal.read_text())['state'] == 'committed'
    assert (journal.with_suffix('')/'A.JPG').read_bytes() == payload
    ts.recover_trash_deletions(workspace, allowed_databases={db, other})
    assert not journal.exists() and not (Path(paths['trash_root'])/'A.JPG').exists()
    assert all(catalogue(p)['files'] == [] for p in (db, other))
