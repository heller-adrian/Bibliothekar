"""RC14 lifecycle counterprobes use actual F14 bindings and WAL databases."""
import json
import sqlite3
from pathlib import Path
import pytest
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc14_import import staged_case


@pytest.mark.parametrize('published',[0,2,6])
def test_partial_publication_restart_is_same_import(fixture,published):
    from app.import_recovery import qualify,resume,finish_published_envelopes
    from app.database import update_import_file_paths,database_connection
    from app.import_publication import publish_import_file
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    for item in plan[:published]:
        publish_import_file(stage/'Original'/item['source_relative_path'],central/item['destination_relative_path'],item)
    assert qualify(db,reg,ws,logs,job)['published_file_count']==published
    resume(db,reg,ws,logs,job,path_callback=lambda p:update_import_file_paths(db,job,p,working_path=str(central)),history_callback=lambda p:None,progress_callback=lambda *a:None)
    # Crash after catalogue completion, before envelope retention.
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='completed' WHERE id=?",(job,))
    finish_published_envelopes(db,reg,ws,logs)
    finish_published_envelopes(db,reg,ws,logs)
    assert not stage.exists()
    assert qualify(db,reg,ws,logs,job)['published_file_count']==6


def test_sql_failure_after_moves_rolls_back_every_owned_inode(fixture):
    from app.import_recovery import resume,qualify
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    def busy(plan):raise sqlite3.OperationalError('database is locked')
    with pytest.raises(sqlite3.OperationalError):
        resume(db,reg,ws,logs,job,path_callback=busy,history_callback=lambda p:None,progress_callback=lambda *a:None)
    assert qualify(db,reg,ws,logs,job)['staged_file_count']==6
    assert all(not (central/i['destination_relative_path']).exists() for i in plan)


@pytest.mark.parametrize('condition',['confirmation','main','nonempty','writable_archive','open_job','success'])
def test_retirement_preserves_database_archive_and_bindings(fixture,monkeypatch,condition):
    from app import main,root_operations as ro
    from app.library_registry import get_library,unregister_library,LibraryRegistryError
    from app.database import create_job
    case,ws,reg,dbs,_=fixture
    lid='main' if condition=='main' else 'second'
    row=get_library(reg,lid,active_only=False);work=Path(row['work_root']);archive=Path(row['archive_root'])
    if condition!='nonempty':(work/'original.JPG').unlink()  # synthetic fixture only
    photo=archive/'original.JPG';photo.write_bytes(b'archive-original')
    before=(photo.stat().st_ino,photo.read_bytes(),ro.generation(ws,lid),ro._identity(work))
    monkeypatch.setattr(main,'_mount_read_only',lambda p:condition!='writable_archive')
    if condition=='open_job':create_job(dbs[1],job_id='pending',kind='sd_import',trigger_type='manual',operation='folder_import',source_path='/synthetic/source')
    confirmation='' if condition=='confirmation' else 'REMOVE LIBRARY'
    if condition=='success':
        result=unregister_library(reg,lid,confirmation=confirmation)
        assert not result['is_registered'] and result['settings']['retirement_receipt']['id']
        assert unregister_library(reg,lid,confirmation=confirmation)['settings']==result['settings']
    else:
        with pytest.raises((RuntimeError,OSError)):unregister_library(reg,lid,confirmation=confirmation)
        assert get_library(reg,lid,active_only=False)['is_registered']
    assert (photo.stat().st_ino,photo.read_bytes(),ro._identity(work))==(before[0],before[1],before[3])
    assert Path(row['database_path']).is_file()


@pytest.mark.parametrize('name,expected',[('Business','business'),('Fête été','fête-été'),('私の写真','私の写真')])
def test_readable_workspace_names(name,expected,tmp_path):
    from app.main import _new_workspace_name,_new_workspace_collision
    assert _new_workspace_name(name)==expected
    (tmp_path/expected.upper()).mkdir()
    assert _new_workspace_collision(tmp_path/expected)


@pytest.mark.parametrize('name',['../Business','A/B','A\\B','A\x00B','..'])
def test_workspace_name_traversal_rejected(name):
    from app.main import _new_workspace_name
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:_new_workspace_name(name)
    assert error.value.status_code==422


def test_failed_import_never_projects_as_free_inventory(fixture):
    from app.global_stock import project_import_job
    from app.inventory_availability import available_families
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    assert project_import_job(db,fixture[3][1],job)=={'jobs':0,'families':0,'files':0}
    assert not available_families(db,ws)


@pytest.mark.parametrize('after_generation',[False,True])
def test_retirement_registry_commit_crash_replays_own_receipt(fixture,monkeypatch,after_generation):
    from app import main,root_operations as ro
    from app.library_registry import get_library,unregister_library
    from app.library_retirement import recover
    case,ws,reg,dbs,_=fixture;row=get_library(reg,'second',active_only=False)
    (Path(row['work_root'])/'original.JPG').unlink()
    monkeypatch.setattr(main,'_mount_read_only',lambda p:True)
    before=ro.generation(ws,'second');actual=ro._write
    def crash(path,value):
        if path.name=='state.json' and value.get('libraries',{}).get('second',0)==before[1]+1:
            if after_generation:actual(path,value)
            raise SystemExit('isolated process death after registry commit')
        return actual(path,value)
    monkeypatch.setattr(ro,'_write',crash)
    with pytest.raises(SystemExit):unregister_library(reg,'second',confirmation='REMOVE LIBRARY')
    assert not get_library(reg,'second',active_only=False)['is_registered']
    monkeypatch.setattr(ro,'_write',actual)
    recover(ws);recover(ws)
    assert ro.generation(ws,'second')==(before[0],before[1]+1)
    assert not (ro._control_location(ws)/'mutation.json').exists()
    assert len(list(ro._control_location(ws).glob('library-retirement-*.json')))==1
