"""Unpublished imports may update history, never media ownership or admission."""
import json
from pathlib import Path
import pytest
from app import root_operations as ro,operation_health as health
from app.database import create_job,database_connection
from app.import_recovery import pending_reservations,qualify
from app.pipeline import PipelineError
from app.storage_config import storage_paths
from tests.backend.test_f14_root_operations import fixture
from tests.backend.test_rc1_sd_reimport import setup_live_import


def seed(fixture,monkeypatch,operation='folder_import',state='copying'):
    case,ws,reg,dbs,source,context=setup_live_import(fixture,monkeypatch)
    create_job(dbs[0],job_id='EARLY',kind='sd_import',trigger_type='manual',operation=operation,source_path=str(source.parent))
    with database_connection(dbs[0]) as c:c.execute("UPDATE jobs SET state=? WHERE id='EARLY'",(state,))
    stage=storage_paths(ws)['backup_root']/'.incoming/EARLY/Original';stage.mkdir(parents=True)
    foreign=stage/'not-owned.partial';foreign.write_bytes(b'unverified partial copy retained verbatim')
    with pytest.raises(RuntimeError,match='controlled death'):
        with ro.reserve(ws,library_id='main',database=dbs[0],kind='import',shared=True,
                        ids={'function':'app.main.process_claimed_job','job_id':'EARLY'},
                        paths=[ws,*storage_paths(ws).values(),context.work_root,context.archive_root]):
            raise RuntimeError('controlled death before publication proof')
    path,=ro._control_location(ws).glob('operation-*.json')
    return ws,reg,dbs[0],case/'logs',source,foreign,path


def test_unpublished_status_is_idempotent_without_releasing_media_fence(fixture,monkeypatch):
    ws,reg,db,logs,source,foreign,path=seed(fixture,monkeypatch)
    record=ro._read(path);before=path.read_bytes();original=source.read_bytes();unknown=foreign.read_bytes()
    for _ in range(3):
        with health.recovery_session():assert pending_reservations(db,reg,ws,logs)==set()
    assert path.read_bytes()==before and source.read_bytes()==original and foreign.read_bytes()==unknown
    marker=ro._read(path.parent/('import-interruption-status-'+record['reservation_id']+'.json'))
    assert marker['reservation']==record and marker['media_completion_verified'] is False
    with health.read_session(),database_connection(db) as c:
        assert c.execute("SELECT state,stage FROM jobs WHERE id='EARLY'").fetchone()[:]==('interrupted','interrupted_after_restart')
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='import_interrupted_unverified'").fetchone()[0]==1
    with pytest.raises(PipelineError,match='journal_missing'):qualify(db,reg,ws,logs,'EARLY')
    with pytest.raises(ro.RootOperationError):
        with ro.reserve(ws,library_id='main',database=db,paths=[ws],kind='unrelated-unsafe-import'):pass
    assert path.read_bytes()==before


@pytest.mark.parametrize('fault',['not_recovery','wrong_operation','terminal','generation'])
def test_unpublished_status_rejects_unqualified_original(fixture,monkeypatch,fault):
    ws,reg,db,logs,source,foreign,path=seed(fixture,monkeypatch,
        operation='legacy_simulation' if fault=='wrong_operation' else 'folder_import',
        state='completed' if fault=='terminal' else 'copying')
    if fault=='generation':
        state=path.parent/'state.json';value=ro._read(state);value['generation']+=1;ro._write(state,value)
    before=path.read_bytes();original=source.read_bytes();unknown=foreign.read_bytes()
    from contextlib import nullcontext
    with pytest.raises(PipelineError):
        with nullcontext() if fault=='not_recovery' else health.recovery_session():
            pending_reservations(db,reg,ws,logs)
    assert path.read_bytes()==before and source.read_bytes()==original and foreign.read_bytes()==unknown
    with health.read_session(),database_connection(db) as c:
        assert c.execute("SELECT state FROM jobs WHERE id='EARLY'").fetchone()[0]==('completed' if fault=='terminal' else 'copying')
        assert not c.execute("SELECT 1 FROM audit_log WHERE action='import_interrupted_unverified'").fetchall()
