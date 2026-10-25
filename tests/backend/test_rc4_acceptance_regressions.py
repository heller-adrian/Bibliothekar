"""Bounded RC4 acceptance: reservation selection and registered runtime context."""
import hashlib,json
from pathlib import Path
import pytest
from app import main,trash_import as ti,trash_selective as ts
from app.database import database_connection
from app.trash import TrashError,empty_trash_filesystem
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc4_nas_legacy import failed_restore


def integrity(dbs):
    for db in dbs:
        with database_connection(db) as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            assert not c.execute('PRAGMA foreign_key_check').fetchall()


@pytest.mark.parametrize('state',['failed','interrupted','missing-job'])
@pytest.mark.parametrize('entry',['direct','http'])
def test_inactive_reservation_only_blocks_its_own_selection(fixture,state,entry):
    db,ws,jid,journal,data=failed_restore(fixture)
    with database_connection(db) as c:
        if state=='missing-job':c.execute('DELETE FROM jobs WHERE id=?',(jid,))
        else:c.execute('UPDATE jobs SET state=? WHERE id=?',(state,jid))
    root=storage_paths(ws)['trash_root'];other=root/'B.JPG';other.write_bytes(b'independent-original')
    before=journal.read_bytes();identities={p:(root/p).stat().st_ino for p in data['relative_paths']}
    with pytest.raises(TrashError):ts.delete_selected_trash_files(fixture[3],ws,[data['relative_paths'][0],other.name])
    assert other.read_bytes()==b'independent-original'
    if entry=='http':result=main.api_empty_trash_selection({'relative_paths':[other.name]})
    else:result=ts.delete_selected_trash_files(fixture[3],ws,[other.name])
    assert result['deleted_file_count']==1 and not other.exists()
    with pytest.raises(TrashError):empty_trash_filesystem(ws)
    assert journal.read_bytes()==before
    for item in data['files']:
        p=root/item['relative_path'];assert p.stat().st_ino==identities[item['relative_path']]
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
        assert hashlib.sha256((ti.stage_parent(ws)/jid/item['relative_path']).read_bytes()).hexdigest()==item['sha256']
    integrity(fixture[3])


@pytest.mark.parametrize('state',['queued','copying','verifying','backup_verified','analyzing_metadata','organizing'])
def test_active_restore_rejects_independent_http_and_physical_deletion(fixture,state):
    db,ws,jid,journal,data=failed_restore(fixture)
    with database_connection(db) as c:c.execute('UPDATE jobs SET state=? WHERE id=?',(state,jid))
    other=storage_paths(ws)['trash_root']/'B.JPG';other.write_bytes(b'independent')
    with pytest.raises(main.HTTPException):main.api_empty_trash_selection({'relative_paths':[other.name]})
    with pytest.raises(TrashError):ts.delete_selected_trash_files(fixture[3],ws,[other.name])
    assert other.read_bytes()==b'independent'
    integrity(fixture[3])


def test_reservation_is_rechecked_after_delete_journal_before_staging(fixture,monkeypatch):
    db,ws,jid,journal,data=failed_restore(fixture)
    other=storage_paths(ws)['trash_root']/'B.JPG';other.write_bytes(b'independent')
    real=ts._atomic_json;injected=[]
    def publish(path,record):
        real(path,record)
        if record.get('state')=='prepared' and path.name.startswith('DELETE_') and not injected:
            data['relative_paths'].append(other.name)
            data['files'].append({'relative_path':other.name,'size_bytes':other.stat().st_size,
                                  'sha256':hashlib.sha256(other.read_bytes()).hexdigest()})
            journal.write_text(json.dumps(data));injected.append(journal.read_bytes())
    monkeypatch.setattr(ts,'_atomic_json',publish)
    with pytest.raises(TrashError):ts.delete_selected_trash_files(fixture[3],ws,[other.name])
    assert injected and other.read_bytes()==b'independent'
    assert journal.read_bytes()==injected[0]
    assert other.name in ti.protected_trash_paths(None,ws)
    integrity(fixture[3])


@pytest.mark.parametrize('read_only',[False,True])
def test_onboarding_mount_contract_and_registered_trash_guard(tmp_path,monkeypatch,read_only):
    from app.database import initialize_database
    from app.library_registry import initialize_library_registry,list_libraries
    from app.workspace_layout import ensure_workspace_layout
    from app.trash_failure import assert_no_active_restore
    workspace=tmp_path/'workspace';workspace.mkdir()
    archive=tmp_path/'archive';archive.mkdir()
    directory=tmp_path/'database';directory.mkdir()
    db=directory/'kamera.sqlite3';registry=directory/'registry.sqlite3';config=tmp_path/'settings.json'
    config.write_text('{}')
    for name,value in {'KAMERA_WORKSPACE':workspace,'KAMERA_CONFIG':config,
                       'KAMERA_REGISTRY_DATABASE':registry,'KAMERA_DATABASE_DIR':directory}.items():
        monkeypatch.setenv(name,str(value))
    initialize_database(db);initialize_library_registry(registry)
    ensure_workspace_layout(workspace,create_default_main=False)
    for name,value in {'WORKSPACE_PATH':workspace,'DATABASE_FILE':db,'DATABASE_DIRECTORY':directory,
                       'REGISTRY_DATABASE_FILE':registry,'CONFIG_PATH':config}.items():
        monkeypatch.setattr(main,name,value)
    monkeypatch.setattr(main,'MAIN_LIBRARY_CONTEXT',main.build_main_library_context())
    monkeypatch.setattr(main,'current_database_file',lambda:db)
    assert not list_libraries(registry)
    # Isolate the registry/onboarding contract using explicit kernel-probe
    # responses. This is not a real read-only mount qualification: the later
    # container smoke uses an actual read-only bind and unmodified findmnt.
    probes=[]
    def mount_probe(path):
        assert Path(path)==archive
        probes.append(path)
        return read_only
    monkeypatch.setattr(main,'_mount_read_only',mount_probe)
    payload={'display_name':'RC4 Onboarding','work_root':'','archive_root':str(archive)}
    checked=main.api_check_library({**payload,'default_library_id':'rc4-onboarding'})
    assert probes and checked['archive_read_only'] is read_only
    if not read_only:
        assert not checked['valid'] and any('read-only' in error for error in checked['errors'])
        with pytest.raises(main.HTTPException):main.api_create_library(payload)
        assert not list_libraries(registry)
        assert_no_active_restore(workspace)
        integrity([db,registry])
        return
    assert checked['valid'],json.dumps(checked,indent=2)
    created=main.api_create_library(payload)['library']
    assert created['is_registered'] and created['library_id']=='main'
    registered=list_libraries(registry)
    assert len(registered)==1 and Path(registered[0]['database_path'])==db
    assert Path(created['archive_root'])==archive
    assert_no_active_restore(workspace)
    root=storage_paths(workspace)['trash_root'];(root/'unknown.txt').write_bytes(b'synthetic')
    empty_trash_filesystem(workspace)
    assert not list(root.iterdir())
    integrity([db,registry])
