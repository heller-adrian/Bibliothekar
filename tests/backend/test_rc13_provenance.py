"""RC13: current inventory must never redefine immutable camera origin."""
from pathlib import Path
import hashlib
import json
import sqlite3
import subprocess
import sys

import pytest

from app.central_stock_reconcile import reconcile_central_free_stock
from app.database import database_connection, initialize_database
from app.global_library_inventory import backfill_library_inventory
from app.library_registry import initialize_library_registry, LibraryRegistryError
from app.workspace_layout import ensure_workspace_layout
from tests.backend.test_0411_physical_truth import _seed_free_file, NOW


def seed(tmp_path):
    db, reg, ws = tmp_path/'db.sqlite3', tmp_path/'registry.sqlite3', tmp_path/'workspace'
    ws.mkdir()
    initialize_database(db)
    initialize_library_registry(reg)
    root = Path(ensure_workspace_layout(ws)['backup_root'])
    rel = '2026/2026-10-05/A.JPG'
    family, jpg = _seed_free_file(db, rel, b'jpeg-camera')
    (root/rel).parent.mkdir(parents=True)
    (root/rel).write_bytes(b'jpeg-camera')
    raw_rel = rel.replace('.JPG', '.RAF')
    (root/raw_rel).write_bytes(b'raw-camera')
    sha = hashlib.sha256(b'raw-camera').hexdigest()
    with database_connection(db) as c:
        c.execute('''INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,
          original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,
          current_root_kind,created_at,updated_at)
          VALUES ('J',?,?,?,'A.RAF','.RAF','raw',10,?,?,'shared_workspace',?,?)''',
          (family,raw_rel,raw_rel,sha,sha,NOW,NOW))
    backfill_library_inventory(reg,database_path=db,library_id='main',claim_all_owned=False)
    return db,reg,ws,root,rel,family,jpg


def origin(reg):
    with sqlite3.connect(reg) as c:
        return {table:c.execute('SELECT * FROM '+table+' ORDER BY 1,2').fetchall()
                for table in ('source_families','canonical_families','source_family_members','source_media')}


def remove_and_confirm(db,ws,root,rel):
    reconcile_central_free_stock(db,ws,library_id='main',excluded_family_ids=set())
    (root/rel).unlink()
    for _ in range(2):
        result=reconcile_central_free_stock(db,ws,library_id='main',excluded_family_ids=set())
    assert result['deleted_file_count']==1


def test_confirmed_partial_loss_restart_preserves_origin(tmp_path):
    db,reg,ws,root,rel,*_=seed(tmp_path)
    before=origin(reg)
    raw=root/rel.replace('.JPG','.RAF'); identity=raw.stat().st_ino
    remove_and_confirm(db,ws,root,rel)
    for _ in range(2):
        process=subprocess.run([sys.executable,'-c',
          'from pathlib import Path;from app.global_library_inventory import backfill_library_inventory;'
          'import sys;backfill_library_inventory(Path(sys.argv[1]),database_path=Path(sys.argv[2]),library_id="main",claim_all_owned=False)',str(reg),str(db)],capture_output=True,text=True)
        assert process.returncode==0,process.stderr
        assert origin(reg)==before
    assert raw.read_bytes()==b'raw-camera' and raw.stat().st_ino==identity


@pytest.mark.parametrize('change',['no_audit','wrong_job','wrong_family','wrong_hash','wrong_size','wrong_member','wrong_library','wrong_audit_library'])
def test_conflicting_partial_origin_blocks(tmp_path,change):
    db,reg,ws,root,rel,*_=seed(tmp_path)
    remove_and_confirm(db,ws,root,rel)
    with database_connection(db) as c:
        if change=='no_audit':c.execute("DELETE FROM audit_log WHERE action='central_file_deletion_confirmed'")
        elif change in ('wrong_job','wrong_family','wrong_audit_library'):
            row=c.execute("SELECT id,details_json FROM audit_log WHERE action='central_file_deletion_confirmed'").fetchone()
            data=json.loads(row['details_json'])
            data['family_key' if change=='wrong_family' else 'library_id']='foreign'
            if change=='wrong_job':c.execute("UPDATE audit_log SET job_id=NULL WHERE id=?",(row['id'],))
            else:c.execute('UPDATE audit_log SET details_json=? WHERE id=?',(json.dumps(data),row['id']))
        elif change=='wrong_hash':c.execute("UPDATE files SET sha256_original=?",('f'*64,))
        elif change=='wrong_size':c.execute('UPDATE files SET source_size_bytes=999')
        elif change=='wrong_library':
            with sqlite3.connect(reg) as r:r.execute("UPDATE source_families SET metadata_json=?",(json.dumps({'library_id':'other','job_id':'J'}),))
        elif change=='wrong_member':c.execute("UPDATE files SET original_relative_path='foreign.RAF'")
    before=origin(reg)
    with pytest.raises(LibraryRegistryError):
        backfill_library_inventory(reg,database_path=db,library_id='main',claim_all_owned=False)
    assert origin(reg)==before


def test_whole_family_loss_still_validates_audits(tmp_path):
    db,reg,ws,root,rel,*_=seed(tmp_path)
    before=origin(reg)
    remove_and_confirm(db,ws,root,rel)
    remove_and_confirm(db,ws,root,rel.replace('.JPG','.RAF'))
    backfill_library_inventory(reg,database_path=db,library_id='main',claim_all_owned=False)
    assert origin(reg)==before
    with database_connection(db) as c:c.execute("DELETE FROM audit_log WHERE action='central_file_deletion_confirmed'")
    with pytest.raises(LibraryRegistryError):
        backfill_library_inventory(reg,database_path=db,library_id='main',claim_all_owned=False)


def test_rc12_legacy_audit_is_sufficient_without_new_fields(tmp_path):
    db,reg,ws,root,rel,*_=seed(tmp_path)
    before=origin(reg)
    remove_and_confirm(db,ws,root,rel)
    with database_connection(db) as c:
        row=c.execute("SELECT id,details_json FROM audit_log WHERE action='central_file_deletion_confirmed'").fetchone()
        data=json.loads(row['details_json'])
        for key in ('original_relative_path','sha256_original','source_size_bytes'):data.pop(key)
        c.execute('UPDATE audit_log SET details_json=? WHERE id=?',(json.dumps(data),row['id']))
    backfill_library_inventory(reg,database_path=db,library_id='main',claim_all_owned=False)
    assert origin(reg)==before


def test_atomic_state_replacement_during_read(tmp_path,monkeypatch):
    """Exact interleaving: writer publishes between JSON load and second ACL check."""
    from app import root_operations as ro
    path=tmp_path/'state.json'
    ro._write(path,{'generation':0})
    original=ro.private_check_acl
    state_checks=0
    def exchange(fd,trusted,**kwargs):
        nonlocal state_checks
        if kwargs.get('path')==path:
            state_checks+=1
            if state_checks==2:ro._write(path,{'generation':1})
        return original(fd,trusted,**kwargs)
    monkeypatch.setattr(ro,'private_check_acl',exchange)
    assert ro._read(path)=={'generation':1}


def test_new_secondary_after_confirmed_loss_uses_original_family(tmp_path):
    from app.global_stock import project_import_job
    from app.library_registry import adopt_main_library,register_library,ensure_library_identity
    db,reg,ws,root,rel,*_=seed(tmp_path)
    layout=ensure_workspace_layout(ws)
    archive=tmp_path/'archive';archive.mkdir()
    main_work=Path(layout['workspaces_root'])/'main';main_work.mkdir()
    adopt_main_library(reg,database_path=db,workspace_root=ws,work_root=main_work,archive_root=archive)
    remove_and_confirm(db,ws,root,rel)
    second=tmp_path/'second.sqlite3';initialize_database(second);ensure_library_identity(second,'second')
    second_work=Path(layout['workspaces_root'])/'second';second_work.mkdir()
    second_archive=tmp_path/'archive-second';second_archive.mkdir()
    register_library(reg,library_id='second',display_name='Second',database_path=second,
        workspace_root=ws,work_root=second_work,archive_root=second_archive)
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='completed' WHERE id='J'")
    project_import_job(db,second,'J')
    with sqlite3.connect(reg) as c:expected=c.execute("SELECT canonical_family_id FROM source_families WHERE source_family_key='main:J:F'").fetchone()[0]
    for _ in range(2):
        backfill_library_inventory(reg,database_path=second,library_id='second',claim_all_owned=False)
        with sqlite3.connect(reg) as c:assert c.execute("SELECT canonical_family_id FROM source_families WHERE source_family_key='second:J:F'").fetchone()[0]==expected
    # A later, unaudited local loss of the surviving member remains blocked.
    with database_connection(second) as c:c.execute('DELETE FROM files')
    with pytest.raises(LibraryRegistryError):
        backfill_library_inventory(reg,database_path=second,library_id='second',claim_all_owned=False)
