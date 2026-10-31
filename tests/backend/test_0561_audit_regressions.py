"""Unchanged Phase-2 F1–F4 test bodies and assertions; optional evidence output."""
from pathlib import Path
import hashlib, json, os, sqlite3
import pytest

from app import main
from app.database import initialize_database, database_connection, create_job, store_metadata_analysis, update_import_file_paths, update_job_progress
from app.library_registry import initialize_library_registry
from app.storage_config import storage_paths, load_storage_settings
from app import trash_selective as ts
from app import metadata_correction as mc
from app.folder_import import run_folder_import_job, partition_import_entries
from app.safe_transfer import move_verified_no_overwrite, SafeTransferError
from tests.backend.test_0440_trash import _file, _fixture

OUT=Path(os.environ['AUDIT_OUTPUT']) if os.environ.get('AUDIT_OUTPUT') else None
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def capture(label,root,**extra):
    if OUT is None:
        return
    files=[]; dbs={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():files.append({'path':str(p.relative_to(root)),'type':'symlink','target':os.readlink(p)});continue
        if p.is_file():
            files.append({'path':str(p.relative_to(root)),'size':p.stat().st_size,'sha256':sha(p),'inode':p.stat().st_ino,'nlink':p.stat().st_nlink})
            if p.suffix in {'.sqlite3','.db'}:
                with sqlite3.connect('file:'+str(p)+'?mode=ro',uri=True) as c:
                    tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
                    dbs[str(p.relative_to(root))]={'integrity':c.execute('PRAGMA integrity_check').fetchone()[0],
                       'foreign_key_errors':c.execute('PRAGMA foreign_key_check').fetchall(),
                       'table_counts':{t:c.execute('SELECT count(*) FROM "'+t+'"').fetchone()[0] for t in tables},
                       'rows':{t:[dict(zip([r[1] for r in c.execute('PRAGMA table_info("'+t+'")')],row)) for row in c.execute('SELECT * FROM "'+t+'"')] for t in ['files','file_families','event_assignments','metadata_corrections'] if t in tables}}
    (OUT/(label+'.json')).write_text(json.dumps({'files':files,'databases':dbs,**extra},indent=2,default=str))

def test_P201_F4_symlink_rename_must_preserve_outside_directory(tmp_path,monkeypatch):
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'))
    workspace=tmp_path/'workspace';workspace.mkdir()
    outside=tmp_path/'outside-workspace';outside.mkdir()
    (outside/'sentinel.JPG').write_bytes(b'synthetic-outside-file')
    names=load_storage_settings()
    (workspace/names['trash_directory_name']).symlink_to(outside,target_is_directory=True)
    db=tmp_path/'main.sqlite3';reg=tmp_path/'registry.sqlite3'
    initialize_database(db);initialize_library_registry(reg)
    for key,value in {'WORKSPACE_PATH':workspace,'DATABASE_FILE':db,'REGISTRY_DATABASE_FILE':reg,'DATABASE_DIRECTORY':tmp_path}.items():
        monkeypatch.setattr(main,key,value)
    # Only response rendering is stubbed; real validation, rename, config and registry paths execute.
    monkeypatch.setattr(main,'_storage_settings_state',lambda:{'synthetic_response':True})
    capture('P201-before',tmp_path)
    error=None
    try:main.api_set_storage_paths({'trash_directory_name':'RenamedTrash'})
    except Exception as e:error=repr(e)
    capture('P201-after',tmp_path,error=error,outside_exists=outside.exists(),renamed_exists=(workspace/'RenamedTrash').exists())
    assert outside.is_dir(), 'F4: directory outside workspace was renamed into workspace'
    assert not (workspace/'RenamedTrash').exists()

def trash_case(tmp_path,monkeypatch,two=False):
    db,workspace,paths=_fixture(tmp_path,monkeypatch)
    other=tmp_path/'second.sqlite3'
    if two:
        initialize_database(other)
        create_job(other,job_id='J',kind='sd_import',trigger_type='approved_sd',operation='folder_import',source_path='synthetic-only')
        # A second catalogue participating in shared recovery is a registered
        # library, not an unexplained database discovered by directory scan.
        from app.library_registry import register_library,ensure_library_identity
        ensure_library_identity(other,'second')
        work=Path(paths['workspaces_root'])/'second';work.mkdir()
        archive=tmp_path/'archive-second';archive.mkdir()
        register_library(tmp_path/'registry.sqlite3',library_id='second',display_name='Second',
            database_path=other,workspace_root=workspace,work_root=work,archive_root=archive)
    payload=b'synthetic-retain-provenance'
    _file(db,'A.JPG',payload)
    if two:_file(other,'A.JPG',payload)
    (Path(paths['trash_root'])/'A.JPG').write_bytes(payload)
    from app.trash import reconcile_trash_inventory
    for p in ([db,other] if two else [db]):reconcile_trash_inventory(p,workspace)
    return db,other,workspace,paths,payload

def test_P202_F2_partial_database_commit_must_restore_catalogue(tmp_path,monkeypatch):
    db,other,workspace,paths,payload=trash_case(tmp_path,monkeypatch,two=True)
    real=ts._purge_selected
    def fail_second(path,selection):
        if path==other:raise sqlite3.OperationalError('AUDIT injected failure before database B commit')
        return real(path,selection)
    monkeypatch.setattr(ts,'_purge_selected',fail_second)
    capture('P202-before',tmp_path)
    with pytest.raises(sqlite3.OperationalError):ts.delete_selected_trash_files([db,other],workspace,['A.JPG'])
    capture('P202-after',tmp_path)
    assert (Path(paths['trash_root'])/'A.JPG').read_bytes()==payload
    counts=[]
    for p in [db,other]:
        with database_connection(p) as c:counts.append(c.execute('SELECT count(*) FROM files').fetchone()[0])
    assert counts==[1,1], f'F2: physical file restored but catalogue counts are {counts}'

def test_P202b_F1_journal_write_error_must_leave_recovery_evidence(tmp_path,monkeypatch):
    db,_,workspace,paths,payload=trash_case(tmp_path,monkeypatch)
    real=ts._atomic_json
    def fail_committed(path,value):
        if value.get('state')=='committed':raise OSError('AUDIT injected journal rewrite error')
        return real(path,value)
    monkeypatch.setattr(ts,'_atomic_json',fail_committed)
    capture('P202b-before',tmp_path)
    with pytest.raises(OSError):ts.delete_selected_trash_files([db],workspace,['A.JPG'])
    recovery=ts.recover_trash_deletions(workspace)
    capture('P202b-after',tmp_path,recovery=recovery)
    parent=storage_paths(workspace)['metadata_root']/'.trash-deletions'
    assert (Path(paths['trash_root'])/'A.JPG').exists() or list(parent.glob('DELETE_*.json')), 'F1: neither restored source nor discoverable journal; staged original orphaned'

def test_P203_F3_after_swap_db_error_must_leave_retryable_task(tmp_path,monkeypatch):
    from PIL import Image
    workspace=tmp_path/'workspace';workspace.mkdir()
    monkeypatch.setenv('KAMERA_CONFIG',str(tmp_path/'settings.json'))
    db=tmp_path/'catalogue.sqlite3';initialize_database(db)
    root=mc.metadata_area_paths(area='general',workspace_root=workspace,library_id='main')['root']
    source=root/'synthetic.JPG';Image.new('RGB',(16,16),(51,102,153)).save(source)
    original=sha(source)
    task=mc.create_metadata_correction(db,area='general',relative_path='synthetic.JPG',proposed_datetime='2026-10-01T12:34:56',workspace_root=workspace,library_id='main',
        _prevalidated_row={'relative_path':'synthetic.JPG','filename':'synthetic.JPG','media_type':'jpeg'},_prevalidated_source=source)
    capture('P203-before',tmp_path,original_sha256=original)
    def fail_complete(*a,**k):raise sqlite3.OperationalError('AUDIT injected error after file swap before completion')
    retry=None
    with monkeypatch.context() as m:
        m.setattr(mc,'_complete_task',fail_complete)
        with pytest.raises(mc.MetadataCorrectionError):mc.apply_metadata_correction(db,task['id'],workspace_root=workspace,library_id='main')
    try:mc.apply_metadata_correction(db,task['id'],workspace_root=workspace,library_id='main')
    except Exception as e:retry=str(e)
    verification=mc.verify_metadata_datetime(source,'2026-10-01T12:34:56')
    current=mc.get_metadata_correction(db,task['id'])
    capture('P203-after',tmp_path,original_sha256=original,current_sha256=sha(source),retry_error=retry,metadata_verification=verification,task_status=current['status'])
    assert sha(source)==original or (current['status']=='completed' and retry is None), 'F3: corrected file with blocked task and retry rejected on old size/hash'

