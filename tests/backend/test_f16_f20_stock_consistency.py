from pathlib import Path
import json,subprocess,sys
import pytest
from app.database import database_connection,initialize_database,create_job
from app import central_stock_reconcile as cs
from app.global_stock import migrate_main_free_stock_to_central
from app.workspace_layout import ensure_workspace_layout
from tests.backend.test_0311_global_stock import _insert_family_file
from tests.backend.legacy_storage_fixture import provision_legacy_storage
from tests.backend import test_0562_process_recovery as recovery
from tests.backend.test_0562_process_recovery import isolated_process_environment

@pytest.mark.parametrize('case',['f16','f16_public','f20'])
def test_unchanged_original(tmp_path,case):
    source=Path(__file__).resolve().parents[2];out=tmp_path/case
    r=subprocess.run([sys.executable,str(source/'qa/f16_f20/run_original.py'),str(source),str(out),case],timeout=80)
    assert r.returncode==0,(out/'stdout.log').read_text()[-5000:]


def seeded(tmp_path,monkeypatch):
    case=tmp_path/'case';case.mkdir();result=recovery.invoke(case,'seed','sort',tmp_path/'seed');assert result['returncode']==0,(result,(tmp_path/'seed/process.log').read_text())
    data=json.loads((case/'case.json').read_text());db=Path(data['db']);ws=Path(data['workspace'])
    for k,v in {'KAMERA_CONFIG':case/'settings.json','KAMERA_WORKSPACE':ws,'KAMERA_REGISTRY_DATABASE':case/'registry.sqlite3'}.items():monkeypatch.setenv(k,str(v))
    return case,data,db,ws

@pytest.mark.parametrize('state',['queued','verifying','moving','finalizing','rolling_back','interrupted'])
def test_pending_sort_preserves_catalogue_then_inventory_resumes(tmp_path,monkeypatch,state):
    case,data,db,ws=seeded(tmp_path,monkeypatch)
    with database_connection(db) as c:c.execute('UPDATE sort_runs SET status=?',(state,));before=[tuple(x) for x in c.execute('SELECT * FROM files')];families=[tuple(x) for x in c.execute('SELECT * FROM file_families')]
    for _ in range(2):
        result=cs.reconcile_central_free_stock(db,ws,library_id='main');assert result['postponed'] and result['deleted_file_count']==0
    with database_connection(db) as c:
        assert [tuple(x) for x in c.execute('SELECT * FROM files')]==before
        assert [tuple(x) for x in c.execute('SELECT * FROM file_families')]==families
        assert c.execute('SELECT COUNT(*) FROM central_missing_file_observations').fetchone()[0]==0
        c.execute("UPDATE sort_runs SET status='rolled_back'")
    result=cs.reconcile_central_free_stock(db,ws,library_id='main');assert not result.get('postponed') and result['deleted_file_count']==0
    snapshot=recovery.snapshot(case,tmp_path/'after.json');recovery.checks_sql(snapshot)


def test_new_durable_intent_during_enumeration_is_rechecked(tmp_path,monkeypatch):
    case,data,db,ws=seeded(tmp_path,monkeypatch)
    with database_connection(db) as c:
        run=dict(c.execute('SELECT * FROM sort_runs').fetchone());c.execute("UPDATE sort_runs SET status='rolled_back'")
    real=cs._actual_files
    def enumerate_then_intent(root):
        files=real(root);new={**run,'id':'LATE_SORT','status':'queued'}
        with database_connection(db) as c:c.execute('INSERT INTO sort_runs ('+','.join(new)+') VALUES ('+','.join('?' for _ in new)+')',tuple(new.values()))
        return files
    monkeypatch.setattr(cs,'_actual_files',enumerate_then_intent)
    result=cs.reconcile_central_free_stock(db,ws,library_id='main');assert result['postponed'] and 'LATE_SORT' in result['pending_sort_run_ids'] and result['deleted_file_count']==0
    with database_connection(db) as c:assert c.execute('SELECT COUNT(*) FROM files').fetchone()[0]==3 and c.execute('SELECT COUNT(*) FROM central_missing_file_observations').fetchone()[0]==0


def test_migration_skips_foreign_family_but_moves_real_main_stock(tmp_path):
    db=tmp_path/'main.sqlite3';ws=tmp_path/'workspace';ws.mkdir();provision_legacy_storage(ws);layout=ensure_workspace_layout(ws);initialize_database(db)
    create_job(db,job_id='J',kind='sd_import',trigger_type='approved_sd',source_path=str(tmp_path),working_path=layout['work_root'],operation='folder_import')
    excluded=_insert_family_file(db,job_id='J',family_key='foreign',relative_path='foreign.JPG',capture_time='2026-10-01T10:00:00',data=b'foreign-owned')
    _insert_family_file(db,job_id='J',family_key='free',relative_path='free.JPG',capture_time='2026-10-01T10:00:00',data=b'main-free')
    work=Path(layout['work_root']);central=Path(layout['backup_root']);(work/'foreign.JPG').write_bytes(b'unrelated-main-file');(central/'foreign.JPG').write_bytes(b'unrelated-central-file');(work/'free.JPG').write_bytes(b'main-free')
    for _ in range(3):migrate_main_free_stock_to_central(db,ws,excluded_family_ids={excluded})
    assert (work/'foreign.JPG').read_bytes()==b'unrelated-main-file' and (central/'foreign.JPG').read_bytes()==b'unrelated-central-file'
    assert not (work/'free.JPG').exists() and (central/'free.JPG').read_bytes()==b'main-free'
    with database_connection(db) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall() and c.execute('SELECT COUNT(*) FROM file_families').fetchone()[0]==2
