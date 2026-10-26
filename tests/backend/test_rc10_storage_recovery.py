"""RC10 regression: Finder metadata is not library history; lost roots stay gated."""
from pathlib import Path

import pytest

from app.managed_storage_health import inspect_storage
from app.storage_warning_ui import storage_warning_html
from app.storage_replacement import replacement_candidates
from app.database import initialize_database, create_job


@pytest.fixture
def fresh_case(tmp_path,monkeypatch):
    root=tmp_path/'workspace';root.mkdir()
    database_dir=tmp_path/'database';database_dir.mkdir()
    db=database_dir/'kamera.sqlite3'
    reg=database_dir/'bibliothekar-global.sqlite3'
    archive=tmp_path/'archive';archive.mkdir()
    config=tmp_path/'config';config.mkdir()
    monkeypatch.setenv('KAMERA_DATABASE_DIR',str(database_dir))
    monkeypatch.setenv('KAMERA_REGISTRY_DATABASE',str(reg))
    monkeypatch.setenv('KAMERA_ARCHIVE_ROOT',str(archive))
    monkeypatch.setenv('KAMERA_CONFIG',str(config/'settings.json'))
    return root,db,reg,archive


def test_ds_store_does_not_block_automatic_first_install(fresh_case):
    root,db,reg,archive=fresh_case
    source=b'untouched independent archive bytes'
    (archive/'original.JPG').write_bytes(source)
    (root/'.DS_Store').write_bytes(b'Finder metadata')
    health=inspect_storage(root,database=db)
    assert health['can_initialize'] and not health['ready'],health
    assert not health['existing_installation'],health
    assert (archive/'original.JPG').read_bytes()==source
    assert not db.exists() and not reg.exists()


def test_finder_metadata_in_existing_empty_roots_is_technical(fresh_case):
    root,db,_,_=fresh_case
    (root/'.DS_Store').write_bytes(b'x')
    for name in ('SD Card Backups','Library Workspaces','Metadata Correction','Trash'):
        (root/name).mkdir()
    (root/'Library Workspaces'/'.DS_Store').write_bytes(b'y')
    status=inspect_storage(root,database=db)
    assert status['can_initialize'] or status['ready'],status


def test_real_media_and_old_job_prohibit_first_install(fresh_case):
    root,db,_,_=fresh_case
    (root/'.DS_Store').write_bytes(b'x')
    (root/'old-file.JPG').write_bytes(b'protected')
    assert not inspect_storage(root,database=db)['can_initialize']
    (root/'old-file.JPG').unlink()
    initialize_database(db)
    create_job(db,job_id='PRESERVE',source_path=str(root),working_path=str(root),
               kind='sd_import',trigger_type='manual',operation='folder_import')
    status=inspect_storage(root,database=db)
    assert not status['can_initialize'],status


def test_explicit_replacement_offer_requires_historical_identity(fresh_case):
    root,_,_,_=fresh_case
    rows=[{'key':'trash_directory_name','status':'missing',
           'path':str(root/'Trash'),'expected_identity':[8,99]}]
    status={'ready':False,'can_initialize':False,'can_setup_again':False,
            'workspace':str(root),'folders':rows,
            'issues':[{'code':'missing','path':str(root/'Trash')}]}
    assert len(replacement_candidates(status))==1
    html=storage_warning_html(status)
    assert 'data-key="trash_directory_name"' in html
    assert 'class="storage-replace"' in html
    assert 'id="storage-retry"' in html
    assert 'id="storage-initialize"' not in html
    rows[0]['expected_identity']=None
    assert not replacement_candidates(status)


def test_unknown_or_symlink_named_dsstore_never_qualifies(fresh_case):
    root,db,_,_=fresh_case
    (root/'.DS_Store').symlink_to(root.parent/'archive',target_is_directory=True)
    assert not inspect_storage(root,database=db)['can_initialize']
