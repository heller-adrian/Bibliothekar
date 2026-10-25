"""SD history/status regressions; synthetic files and databases only."""
import hashlib,json
from pathlib import Path
import pytest
from PIL import Image
from app import main
from app.database import initialize_database,database_connection,create_job,store_imported_source_files
from app.folder_import import quick_source_signature,run_folder_import_job
from tests.backend.test_f14_root_operations import fixture


@pytest.fixture(autouse=True)
def direct_import_lifecycle(monkeypatch):
    # Synthetic source trees cannot be kernel-mounted RO on this host. Actual
    # read-only refusal is tested separately; no production bypass is added.
    from app import sd_recheck
    from threading import Event
    monkeypatch.setattr(sd_recheck,'read_only',lambda path:True)
    monkeypatch.setattr(main,'WORKER_STOP',Event())
    # These tests invoke the real claimed worker synchronously, without an
    # application lifespan. Do not inherit a stopped worker's startup state
    # from previous TestClient lifespans in the complete suite.
    for name in (
        'DATABASE_INITIALIZATION', 'WORKSPACE_LAYOUT_INITIALIZATION',
        'LIBRARY_REGISTRY_INITIALIZATION', 'WORKER_THREAD',
        'DATABASE_INITIALIZATION_ERROR', 'WORKSPACE_LAYOUT_ERROR',
        'LIBRARY_REGISTRY_ERROR',
    ):
        monkeypatch.setattr(main, name, None)


def test_initialized_runtime_without_worker_still_rejects_import(fixture, monkeypatch):
    from fastapi import HTTPException
    for name in ('DATABASE_INITIALIZATION', 'WORKSPACE_LAYOUT_INITIALIZATION',
                 'LIBRARY_REGISTRY_INITIALIZATION'):
        monkeypatch.setattr(main, name, {'ok': True})
    with pytest.raises(HTTPException) as error:
        main.api_run_folder_import({})
    assert error.value.status_code == 503
    assert 'Hintergrund-Worker nicht läuft' in error.value.detail
    with database_connection(fixture[3][0]) as connection:
        assert connection.execute('SELECT COUNT(*) FROM jobs').fetchone()[0] == 0


def old_job(db,card,device='CARD'):
    create_job(db,job_id='OLD',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path=str(card),source_device_id=device,source_signature=quick_source_signature(card))
    with database_connection(db) as c:c.execute("update jobs set state='completed',file_count=108 where id='OLD'")


def test_legacy_signature_does_not_report_every_file_new(tmp_path,monkeypatch):
    db=tmp_path/'db.sqlite3';initialize_database(db)
    card=tmp_path/'removable/CARD';card.mkdir(parents=True)
    (card/'A.JPG').write_bytes(b'photo');(card/'B.RAF').write_bytes(b'raw')
    old_job(db,card,device='OLD-DEVICE-ID')
    monkeypatch.setattr(main,'DATABASE_FILE',db)
    s=main.import_source_summary(card,'removable',card.parent)
    assert s['new_file_count']==0
    assert s['unknown_file_count']==2
    assert s['import_status']=='history_incomplete'


def test_summary_uses_importer_ignore_rules(tmp_path,monkeypatch):
    db=tmp_path/'db.sqlite3';initialize_database(db)
    card=tmp_path/'CARD';card.mkdir();(card/'A.JPG').write_bytes(b'photo');(card/'._A.JPG').write_bytes(b'appledouble')
    monkeypatch.setattr(main,'DATABASE_FILE',db)
    s=main.import_source_summary(card,'removable',card.parent)
    assert s['file_count']==2 and s['media_file_count']==1 and s['ignored_file_count']==1


def test_confirmed_recheck_is_queued_without_erasing_history(fixture,monkeypatch):
    case,ws,reg,dbs,ev=fixture
    root=case/'removable';card=root/'CARD';card.mkdir(parents=True);(card/'A.JPG').write_bytes(b'photo')
    old_job(dbs[0],card)
    monkeypatch.setattr(main,'REMOVABLE_ROOT',root)
    monkeypatch.setattr(main,'preflight_folder_import',lambda *a,**kw:{})
    response=main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':True})
    assert response.status_code==202
    with database_connection(dbs[0]) as c:
        assert c.execute("select state from jobs where id='OLD'").fetchone()[0]=='completed'
        assert c.execute("select count(*) from jobs where state='queued'").fetchone()[0]==1


def test_exact_duplicates_are_successful_verified_noop(tmp_path):
    source=tmp_path/'source';source.mkdir();p=source/'A.JPG';Image.new('RGB',(8,8),'red').save(p)
    workspace=tmp_path/'workspace';workspace.mkdir();logs=tmp_path/'logs';logs.mkdir()
    seen=[];digest=hashlib.sha256(p.read_bytes()).hexdigest()
    result=run_folder_import_job(source=source,workspace=workspace,pool_probe_path=workspace,log_dir=logs,processing_buffer_percent=0,safety_reserve_gib=0,job_id='CHECK',central_stock=True,imported_sha256={digest},import_history_callback=lambda entries:seen.extend(entries))
    assert result['state']=='success' and result['organization']['file_count']==0
    assert result['source']['duplicate_file_count']==1 and len(seen)==1
    assert p.is_file()
    assert not (workspace/'SD Card Backups/.incoming/CHECK').exists()


@pytest.mark.parametrize('extension',['JPG','RAF','MOV'])
def test_new_media_with_complete_history_remains_available(tmp_path,monkeypatch,extension):
    db=tmp_path/'db.sqlite3';initialize_database(db);card=tmp_path/'CARD';card.mkdir();p=card/'A.JPG';p.write_bytes(b'old')
    old_job(db,card)
    st=p.stat();store_imported_source_files(db,source_device_id='CARD',job_id='OLD',entries=[dict(relative_path=p.name,size_bytes=st.st_size,modified_at_ns=st.st_mtime_ns,sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
    with database_connection(db) as c:c.execute("update jobs set result_json=? where id='OLD'",(json.dumps({'source':{'file_history_complete':True}}),))
    (card/('B.'+extension)).write_bytes(b'added')
    monkeypatch.setattr(main,'DATABASE_FILE',db)
    s=main.import_source_summary(card,'removable',card.parent)
    assert s['new_file_count']==1 and s['already_imported_file_count']==1
    assert s['unknown_file_count']==0 and s['import_status']=='available'


def test_identical_card_and_remount_keep_consistent_counts(tmp_path,monkeypatch):
    db=tmp_path/'db.sqlite3';initialize_database(db);root=tmp_path/'removable';card=root/'CARD';card.mkdir(parents=True);p=card/'A.JPG';p.write_bytes(b'old')
    old_job(db,card);st=p.stat()
    store_imported_source_files(db,source_device_id='CARD',job_id='OLD',entries=[dict(relative_path=p.name,size_bytes=st.st_size,modified_at_ns=st.st_mtime_ns,sha256=hashlib.sha256(p.read_bytes()).hexdigest())])
    monkeypatch.setattr(main,'DATABASE_FILE',db)
    for _ in range(2):
        s=main.import_source_summary(card,'removable',root)
        assert s['import_status']=='already_imported' and s['already_imported_file_count']==1 and s['new_file_count']==0
    moved=card.rename(root/'OTHER-HELPER-ID')
    s=main.import_source_summary(moved,'removable',root)
    assert s['unknown_file_count']==1 and s['new_file_count']==0
    assert s['source_device_id']=='OTHER-HELPER-ID'


def setup_live_import(fixture,monkeypatch):
    import subprocess
    from app.library_context import resolve_library_context
    case,ws,reg,dbs,ev=fixture
    (case/'settings.json').write_text(json.dumps({'storage':{'safety_reserve_gib':0,'processing_buffer_percent':0}}))
    root=case/'removable';card=root/'CARD';card.mkdir(parents=True);p=card/'A.JPG';Image.new('RGB',(8,8),'green').save(p)
    subprocess.run(['exiftool','-overwrite_original','-DateTimeOriginal=2026:07:22 10:14:04',str(p)],check=True,capture_output=True)
    monkeypatch.setattr(main,'REMOVABLE_ROOT',root);monkeypatch.setattr(main,'LOG_PATH',case/'logs')
    return case,ws,reg,dbs,p,resolve_library_context(reg,'main')


def queue_and_run(db,context,confirmed=False):
    from app.database import claim_next_job,get_job
    response=main.api_run_folder_import({'source_root_key':'removable','source_relative_path':'CARD','source_mode':'sd_card','confirm_reimport':confirmed})
    assert response.status_code==202
    job=claim_next_job(db);assert job
    main.process_claimed_job(job,library_context=context)
    final=get_job(db,job['id']);assert final['state']=='completed',final
    if final['operation']=='sd_recheck' and final['result'].get('import_job_id'):
        job=claim_next_job(db);assert job and job['id']==final['result']['import_job_id']
        main.process_claimed_job(job,library_context=context)
        final=get_job(db,job['id']);assert final['state']=='completed',final
    return final


@pytest.mark.parametrize('where',['workspace','archive','missing'])
def test_confirmed_reimport_uses_real_worker_and_preserves_source(fixture,monkeypatch,where):
    from app.storage_config import storage_paths
    case,ws,reg,dbs,p,context=setup_live_import(fixture,monkeypatch)
    source=p.read_bytes();first=queue_and_run(dbs[0],context)
    with database_connection(dbs[0]) as c:
        old=c.execute('select * from files where job_id=?',(first['id'],)).fetchone()
        relative=old['current_relative_path'];expected=old['sha256_current']
    original=storage_paths(ws)['backup_root']/relative
    assert original.read_bytes()==source
    if where=='archive':
        archive=context.archive_root/relative;archive.parent.mkdir(parents=True,exist_ok=True);original.rename(archive)
        for db in dbs:
            with database_connection(db) as c:c.execute("update files set current_root_kind='camera_archive' where job_id=?",(first['id'],))
    elif where=='missing':original.unlink()  # synthetic external loss, source preserved
    if where=='missing':
        second=queue_and_run(dbs[0],context,confirmed=True)
        assert second['duplicate_of_job_id']==first['id']
        assert second['result']['organization']['file_count']==1
    else:
        check=queue_and_run(dbs[0],context,confirmed=True)
        assert check['operation']=='sd_recheck' and check['result']['integrity_verified'] is True
        with database_connection(dbs[0]) as c: assert c.execute("SELECT COUNT(*) FROM jobs WHERE operation='folder_import'").fetchone()[0]==1
    if where=='missing':assert original.read_bytes()==source
    if where=='archive':assert archive.read_bytes()==source and not original.exists()
    assert p.read_bytes()==source
    from app.global_library_inventory import backfill_library_inventory
    for _ in range(3):
        for index,db in enumerate(dbs):
            initialize_database(db)
            backfill_library_inventory(reg,database_path=db,library_id='main' if index==0 else 'second',claim_all_owned=False)
    for db in dbs:
        with database_connection(db) as c:
            assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
            assert not c.execute('pragma foreign_key_check').fetchall()
            assert c.execute('select state from jobs where id=?',(first['id'],)).fetchone()[0]=='completed'


@pytest.mark.parametrize('conflict',['corrupt','symlink','unavailable-root'])
def test_reimport_uncertainty_preserves_everything(fixture,monkeypatch,conflict):
    from app.source_reimport import retained_origins
    from app.storage_config import storage_paths
    from app.database import list_imported_media_origins
    from app.pipeline import PipelineError
    case,ws,reg,dbs,p,context=setup_live_import(fixture,monkeypatch);first=queue_and_run(dbs[0],context)
    origins=list_imported_media_origins(dbs[0]);original=storage_paths(ws)['backup_root']/origins[0]['current_relative_path']
    source=p.read_bytes()
    if conflict=='corrupt':original.write_bytes(b'externally damaged')
    elif conflict=='symlink':
        saved=original.rename(original.with_suffix('.saved'));original.symlink_to(saved)
    else:
        work=context.work_root;work.rename(work.with_name('unavailable'))
    with pytest.raises(PipelineError):retained_origins(reg,origins)
    assert p.read_bytes()==source


def test_active_job_wins_over_old_completed_signature(tmp_path):
    from app.database import find_folder_import_by_identity
    db=tmp_path/'db.sqlite3';initialize_database(db);card=tmp_path/'CARD';card.mkdir();(card/'A.JPG').write_bytes(b'photo')
    old_job(db,card)
    create_job(db,job_id='ACTIVE',kind='sd_import',trigger_type='manual',operation='folder_import',source_signature=quick_source_signature(card))
    assert find_folder_import_by_identity(db,source_signature=quick_source_signature(card))['id']=='ACTIVE'


def test_actual_hash_change_with_same_fast_signature_is_imported(fixture,monkeypatch):
    from app.storage_config import storage_paths
    import os
    case,ws,reg,dbs,p,context=setup_live_import(fixture,monkeypatch)
    first=queue_and_run(dbs[0],context);original_source=p.read_bytes();info=p.stat()
    with database_connection(dbs[0]) as c:relative=c.execute('select current_relative_path from files where job_id=?',(first['id'],)).fetchone()[0]
    original=storage_paths(ws)['backup_root']/relative
    # Harmless same-size metadata/comment byte change defeats a stat-only scan.
    changed=original_source.replace(b'JFIF',b'JFIZ',1);assert changed!=original_source
    p.write_bytes(changed);os.utime(p,ns=(info.st_atime_ns,info.st_mtime_ns))
    assert quick_source_signature(p.parent)==first['source_signature']
    second=queue_and_run(dbs[0],context,confirmed=True)
    assert second['result']['organization']['file_count']==1
    assert original.read_bytes()==original_source and p.read_bytes()==changed


def test_cancelled_import_can_retry_without_source_loss(tmp_path):
    from app.folder_import import ImportCancelled
    source=tmp_path/'source';source.mkdir();p=source/'A.JPG';Image.new('RGB',(8,8),'blue').save(p)
    workspace=tmp_path/'workspace';workspace.mkdir();logs=tmp_path/'logs';logs.mkdir()
    before=p.read_bytes();cancelled=False
    def after_metadata(*a):
        nonlocal cancelled
        cancelled=True
    with pytest.raises(ImportCancelled):
        run_folder_import_job(source=source,workspace=workspace,pool_probe_path=workspace,log_dir=logs,processing_buffer_percent=0,safety_reserve_gib=0,job_id='CANCELLED',central_stock=True,metadata_callback=after_metadata,cancellation_callback=lambda:cancelled)
    assert p.read_bytes()==before
    result=run_folder_import_job(source=source,workspace=workspace,pool_probe_path=workspace,log_dir=logs,processing_buffer_percent=0,safety_reserve_gib=0,job_id='RETRY',central_stock=True)
    assert result['state']=='success' and result['organization']['file_count']==1
    assert p.read_bytes()==before


def test_frontend_recheck_contract_and_javascript_syntax():
    import re,subprocess
    html=main.index()
    assert 'source.unknown_file_count' in html
    assert 'confirm_reimport: confirmReimport' in html
    assert 'sdSourceSummary?.has_import_history' in html
    # Compile actual rendered inline JS where the HTML constant is available.
    for script in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',html,re.S):
        result=subprocess.run(['node','--check'],input=script,text=True,capture_output=True)
        assert result.returncode==0,result.stderr
