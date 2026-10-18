"""Real English/legacy SQL classification with physical media and catalogue checks."""
from pathlib import Path
import hashlib,json
import pytest
from app.database import database_connection
from app.planning import _load_family_stats, list_global_released_archive_groups
from app.central_stock_reconcile import reconcile_central_free_stock
from app.storage_config import storage_paths
from tests.backend.test_f14_fixed_storage import home,stable
from tests.backend.test_0412_consistency_semantics import _seed_free_file
from tests.backend.test_0327_patch import _seed_job,_add_family_file,NOW

@pytest.mark.parametrize('name',['No Date','Ohne_Datum'])
def test_f14_real_undated_reconcile_and_planning(home,tmp_path,name):
    case,ws,reg,db,ctx=home;content=b'synthetic-undated-original'
    family,fid,_=_seed_free_file(db,family_key='UNDATED',filename='A.JPG',day='2026-10-10',data=content)
    rel=name+'/A.JPG';source=storage_paths(ws)['backup_root']/rel;source.parent.mkdir();source.write_bytes(content);inode=source.stat().st_ino
    with database_connection(db) as c:c.execute('UPDATE files SET current_relative_path=? WHERE id=?',(rel,fid))
    stats=_load_family_stats(db,'J');assert next(r for r in stats if r['family_id']==family)['physically_undated']==1
    result=reconcile_central_free_stock(db,ws,library_id='main',excluded_family_ids=set())
    assert result['ready'] and result['deleted_file_count']==0 and result['misplaced_file_count']==0
    assert source.read_bytes()==content and source.stat().st_ino==inode
    with database_connection(db) as c:assert c.execute('SELECT current_relative_path FROM files WHERE id=?',(fid,)).fetchone()[0]==rel
    (tmp_path/'evidence.json').write_text(json.dumps(stable(case),indent=2))

@pytest.mark.parametrize('name',['Assign Later','Später zuordnen'])
def test_f14_real_assign_later_is_not_reclassified_as_free_stock(home,tmp_path,name):
    case,ws,reg,db,ctx=home;content=b'synthetic-assigned-later'
    family,fid,_=_seed_free_file(db,family_key='LATER',filename='A.JPG',day='2026-10-10',data=content)
    rel=name+'/A.JPG';source=storage_paths(ws)['backup_root']/rel;source.parent.mkdir();source.write_bytes(content);inode=source.stat().st_ino
    with database_connection(db) as c:c.execute('UPDATE files SET current_relative_path=? WHERE id=?',(rel,fid))
    result=reconcile_central_free_stock(db,ws,library_id='main',excluded_family_ids=set())
    assert result['ready'] and result['deleted_file_count']==0 and result['misplaced_file_count']==0
    assert source.read_bytes()==content and source.stat().st_ino==inode
    with database_connection(db) as c:assert c.execute('SELECT current_relative_path FROM files WHERE id=?',(fid,)).fetchone()[0]==rel
    (tmp_path/'evidence.json').write_text(json.dumps(stable(case),indent=2))

@pytest.mark.parametrize('name',['Released Archive Files','Freigewordene Archivdateien'])
def test_f14_real_released_archive_group_query_includes_both_names(home,tmp_path,name):
    case,ws,reg,db,ctx=home;content=b'synthetic-released-original';rel=name+'/2026/2026-07-25/A.JPG'
    with database_connection(db) as c:
        _seed_job(c,'new')
        family,fid=_add_family_file(c,job_id='new',family_key='REL',capture='2026-07-25T11:38:13',relative_path=rel,payload=content,root_kind='shared_workspace')
        c.execute('INSERT INTO released_free_families(job_id,family_id,released_start_datetime,released_end_datetime,created_at,archive_origin) VALUES (?,?,?,?,?,1)',('new',family,'2026-07-25T00:00:00','2026-07-25T23:59:59',NOW))
    source=storage_paths(ws)['backup_root']/rel;source.parent.mkdir(parents=True);source.write_bytes(content);inode=source.stat().st_ino
    groups=list_global_released_archive_groups(db)
    assert groups,groups
    assert source.read_bytes()==content and source.stat().st_ino==inode
    with database_connection(db) as c:
        assert c.execute('SELECT current_relative_path FROM files WHERE id=?',(fid,)).fetchone()[0]==rel
        assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not c.execute('PRAGMA foreign_key_check').fetchall()
    (tmp_path/'evidence.json').write_text(json.dumps({'groups':groups,'state':stable(case)},indent=2))
