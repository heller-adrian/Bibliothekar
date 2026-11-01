"""A dead read-only check cannot poison another check; writers remain fenced."""
import json
from pathlib import Path
import pytest
from app import root_operations as ro, observation_recovery as recovery
from app.database import create_job, database_connection
from app.sd_recheck import identity
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import setup_live_import


def orphan(fixture,monkeypatch,operation='sd_recheck',bad=None):
    case,ws,reg,dbs,photo,context=setup_live_import(fixture,monkeypatch)
    bound={'source_root':str(photo.parent.parent),'root_identity':identity(photo.parent.parent),
           'source_identity':identity(photo.parent)}
    if bad=='source_identity':bound['source_identity']=[0,0]
    create_job(dbs[0],job_id='OLD_CHECK',kind='sd_import',trigger_type='manual',
               operation=operation,source_path=str(photo.parent))
    with database_connection(dbs[0]) as c:
        c.execute("UPDATE jobs SET state='verifying',result_json=? WHERE id='OLD_CHECK'",(json.dumps(bound),))
    if bad=='child':
        create_job(dbs[0],job_id='FOLDER_IMPORT_OLD_CHECK',kind='sd_import',trigger_type='manual',operation='folder_import')
    roots=[ws,*storage_paths(ws).values(),context.work_root,context.archive_root]
    with pytest.raises(RuntimeError,match='controlled death'):
        with ro.reserve(ws,library_id='main',database=dbs[0],paths=roots,kind='import',shared=True,
                        ids={'function':'app.main.process_claimed_job','job_id':'OLD_CHECK'}):
            raise RuntimeError('controlled death after read-only source verification')
    path,=ro._control_location(ws).glob('operation-*.json')
    if bad=='generation':
        state=path.parent/'state.json';value=ro._read(state);value['generation']+=1;ro._write(state,value)
    return ws,dbs[0],photo,path


def test_sd_only_retirement_preserves_original_nonce_job_and_source(fixture,monkeypatch):
    ws,db,photo,path=orphan(fixture,monkeypatch)
    record=ro._read(path);source=photo.read_bytes()
    # Same shared locks are already held by another real check in the original
    # RC6 process test. Its continuation is separately exercised with SIGKILL.
    assert len(recovery.recover(ws,sd_checks_only=True))==1
    assert not path.exists() and photo.read_bytes()==source
    proof=ro._read(path.parent/('sd-check-interruption-'+record['reservation_id']+'.json'))
    assert proof['reservation']==record and proof['media_writes'] is False
    with database_connection(db) as c:
        assert c.execute("SELECT state FROM jobs WHERE id='OLD_CHECK'").fetchone()[0]=='verifying'
    assert recovery.recover(ws,sd_checks_only=True)==[]


@pytest.mark.parametrize('bad',['source_identity','generation','child','folder_import'])
def test_sd_only_retirement_rejects_unverified_or_writable_job(fixture,monkeypatch,bad):
    ws,db,photo,path=orphan(fixture,monkeypatch,
                           operation='folder_import' if bad=='folder_import' else 'sd_recheck',bad=bad)
    before=path.read_bytes();source=photo.read_bytes()
    if bad=='folder_import':assert recovery.recover(ws,sd_checks_only=True)==[]
    else:
        with pytest.raises(ro.RootOperationError):recovery.recover(ws,sd_checks_only=True)
    assert path.read_bytes()==before and photo.read_bytes()==source
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',database=db,paths=[ws],kind='probe-writer'):pass
    assert path.read_bytes()==before
