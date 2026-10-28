"""RC14: real WAL writer exclusion, staged publication and catalogue truth."""
import sqlite3
import hashlib
import json
import pytest
from pathlib import Path
from tests.backend.test_rc13_provenance import seed
from tests.backend.test_f14_root_operations import fixture


def staged_case(fixture, count=6):
    from app.database import create_job, database_connection
    from app.storage_config import storage_paths
    from app.global_library_inventory import family_content_fingerprint
    from app.library_registry import register_source_backup
    case,ws,reg,dbs,_=fixture;db=dbs[0];job='RC14_IMPORT'
    central=storage_paths(ws)['backup_root'];stage=central/'.incoming'/job
    original=stage/'Original';original.mkdir(parents=True)
    (stage/'Protocol').mkdir();logs=case/'logs';logs.mkdir()
    create_job(db,job_id=job,kind='sd_import',trigger_type='manual',source_path='/synthetic/card',working_path=str(central),operation='folder_import')
    register_source_backup(reg,backup_id='main:'+job,source_kind='import',source_identity='cardRC14',backup_path='/synthetic/card')
    plan=[];groups={};now='2026-10-28T10:00:00Z'
    with database_connection(db) as c:
        c.execute("UPDATE jobs SET state='failed',stage='failed',progress_current=900,progress_total=1000,source_signature='cardRC14',error_message='database is locked' WHERE id=?",(job,))
        family_count=count-3 if count==3892 else count
        ids={}
        for i in range(family_count):
            ids[i]=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES (?,?,?,'complete','2026-10-28T10:00:00','high')",(job,'F'+str(i),'F'+str(i))).lastrowid
        for i in range(count):
            family=i if i<family_count else i-family_count
            rel=f'D{i:04d}.JPG';data=b'original-'+str(i).encode();p=original/rel;p.write_bytes(data);sha=hashlib.sha256(data).hexdigest()
            item={'source_relative_path':rel,'destination_relative_path':'2026/2026-10-28/'+rel,
                  'sha256':sha,'size_bytes':len(data),'inode':[p.stat().st_dev,p.stat().st_ino]}
            plan.append(item);groups.setdefault(family,[]).append((i,rel,sha,len(data)))
            c.execute('''INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,
                extension,media_type,size_bytes,source_size_bytes,sha256_original,sha256_current,current_root_kind,
                selected_capture_time,capture_time_confidence,review_status,metadata_write_status,created_at,updated_at)
                VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,'job_root','2026-10-28T10:00:00','high','not_required','not_requested',?,?)''',
                (job,ids[family],rel,rel,rel,len(data),len(data),sha,sha,now,now))
    # Bulk fixture construction represents the exact immutable admission result,
    # without paying 4,000 individual connection setups just to prepare a test.
    with sqlite3.connect(reg) as c:
        for family,members in groups.items():
            fp=family_content_fingerprint([{'sha256':x[2],'size_bytes':x[3],'media_type':'jpeg'} for x in members]);canon='CF'+str(family)
            source='main:'+job+':F'+str(family)
            c.execute('INSERT INTO canonical_families VALUES (?,?,?,?)',(canon,fp,now,now))
            c.execute('INSERT INTO source_families VALUES (?,?,?,?,?,?,?)',(source,'main:'+job,'F'+str(family),canon,json.dumps({'library_id':'main','job_id':job}),now,now))
            for order,(i,rel,sha,size) in enumerate(members):
                media='M'+str(i)
                c.execute('INSERT INTO source_media VALUES (?,?,?,?,?,?,?,?,?)',(media,'main:'+job,rel,size,sha,'jpeg','{}',now,now))
                c.execute('INSERT INTO source_family_members VALUES (?,?,?,?,?)',(source,media,'member',order,now))
    (stage/'move-journal.json').write_text(json.dumps({'format':1,'root':str(central.resolve()),'files':plan}))
    return db,reg,ws,central,stage,logs,job,plan


@pytest.mark.parametrize('count',[6,3892])
def test_rc13_staged_zero_published_resume_preserves_origin(fixture,count):
    from app.import_recovery import qualify,resume,retain_completed_evidence
    from app.database import update_import_file_paths,database_connection
    from app.inventory_availability import available_families
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture,count)
    with sqlite3.connect(reg) as c:
        before={t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in ('source_families','canonical_families','source_media','source_family_members')}
    proof=qualify(db,reg,ws,logs,job)
    assert proof['staged_file_count']==count and proof['published_file_count']==0
    assert not available_families(db,ws)
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='organizing' WHERE id=?",(job,))
    result=resume(db,reg,ws,logs,job,path_callback=lambda p:update_import_file_paths(db,job,p,working_path=str(central)),history_callback=lambda p:None,progress_callback=lambda *a:None)
    assert result['organization']['file_count']==count
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='completed' WHERE id=?",(job,))
    retain_completed_evidence(db,reg,ws,logs,job)
    assert not stage.exists() and (central/'.import-history'/job/'move-journal.json').exists()
    assert len(available_families(db,ws))==(3889 if count==3892 else count)
    for item in plan:
        p=central/item['destination_relative_path']
        assert [p.stat().st_dev,p.stat().st_ino]==item['inode']
        assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
    with sqlite3.connect(reg) as c:
        assert before=={t:c.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall() for t in before}


@pytest.mark.parametrize('damage',['changed_bytes','foreign_target','symlink','unknown_file','unknown_envelope','unknown_protocol','missing_origin'])
def test_recovery_ambiguity_keeps_all_evidence(fixture,damage):
    from app.import_recovery import qualify
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    first=stage/'Original'/plan[0]['source_relative_path']
    if damage=='changed_bytes':first.write_bytes(b'foreign')
    elif damage=='foreign_target':
        p=central/plan[0]['destination_relative_path'];p.parent.mkdir(parents=True);p.write_bytes(b'foreign')
    elif damage=='symlink':first.unlink();first.symlink_to('/etc/passwd')
    elif damage=='unknown_file':(stage/'Original/foreign.JPG').write_bytes(b'foreign')
    elif damage=='unknown_envelope':(stage/'foreign.txt').write_bytes(b'foreign')
    elif damage=='unknown_protocol':(stage/'Protocol/foreign.txt').write_bytes(b'foreign')
    else:
        with sqlite3.connect(reg) as c:c.execute('DELETE FROM source_family_members')
    before=(stage/'move-journal.json').read_bytes()
    with pytest.raises((RuntimeError,OSError)):qualify(db,reg,ws,logs,job)
    assert (stage/'move-journal.json').read_bytes()==before


def test_reconcile_hash_does_not_hold_catalogue_writer(tmp_path, monkeypatch):
    from app import central_stock_reconcile as stock
    db,reg,ws,root,*_=seed(tmp_path)
    (root/'unknown.JPG').write_bytes(b'unknown bytes')
    original=stock._sha256_file
    calls=[]
    def measured(path):
        # Deterministic stand-in for a slow NAS hash overlapping import progress.
        with sqlite3.connect(db,timeout=.02) as writer:
            writer.execute('BEGIN IMMEDIATE')
            writer.execute("UPDATE jobs SET progress_message='concurrent import progress'")
        calls.append(str(path))
        return original(path)
    monkeypatch.setattr(stock,'_sha256_file',measured)
    stock.reconcile_central_free_stock(db,ws,library_id='main')
    assert calls


def test_import_progress_retries_a_real_short_wal_writer(fixture):
    import threading,time
    from app.database import update_job_progress,get_job,connect,database_connection
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    with database_connection(db) as c:c.execute("UPDATE jobs SET state='organizing' WHERE id=?",(job,))
    held=threading.Event()
    def other_writer():
        with sqlite3.connect(db) as c:
            c.execute('BEGIN IMMEDIATE');held.set();time.sleep(.35)
    worker=threading.Thread(target=other_writer);worker.start();assert held.wait(2)
    update_job_progress(db,job,state='organizing',stage='workspace_moving',current=900,total=1000,message='Progress after bounded retry')
    worker.join(2);assert not worker.is_alive()
    assert get_job(db,job)['progress_message']=='Progress after bounded retry'
    with connect(db) as c:assert c.execute('PRAGMA busy_timeout').fetchone()[0]==30000


def test_tasks_exclude_failed_and_missing_physical_families(fixture):
    from app.database import list_global_tasks,database_connection
    from app.inventory_availability import available_families
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    tasks=list_global_tasks(db,eligible_family_ids=available_families(db,ws))
    assert not any(t['kind']=='unassigned_families' for t in tasks)

    with database_connection(db) as c:
        c.execute("UPDATE jobs SET state='completed' WHERE id=?",(job,))
        c.execute("UPDATE files SET current_root_kind='shared_workspace'")
    # A completed label alone cannot make missing physical copies free stock.
    tasks=list_global_tasks(db,eligible_family_ids=available_families(db,ws))
    assert not any(t['kind']=='unassigned_families' for t in tasks)


def test_failed_publication_is_not_reconciled_as_file_loss(fixture):
    from app.database import database_connection
    from app.central_stock_reconcile import reconcile_central_free_stock
    db,reg,ws,central,stage,logs,job,plan=staged_case(fixture)
    # Crash/rollback after path callback committed, before job completion.
    with database_connection(db) as c:
        for item in plan:
            c.execute("UPDATE files SET current_root_kind='shared_workspace',current_relative_path=? WHERE job_id=? AND original_relative_path=?",(item['destination_relative_path'],job,item['source_relative_path']))
    for _ in range(2):
        result=reconcile_central_free_stock(db,ws,library_id='main')
        assert result['deleted_file_count']==0
    with database_connection(db) as c:
        assert c.execute('SELECT COUNT(*) FROM files WHERE job_id=?',(job,)).fetchone()[0]==6
