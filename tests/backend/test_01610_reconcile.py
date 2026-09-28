from pathlib import Path
import hashlib

from tests.backend.archive_change_helpers import copy_prepared_event_document
from app.database import initialize_database, database_connection
from app.workspace_reconcile import build_workspace_reconcile_plan, prepare_workspace_reconcile_run, execute_workspace_reconcile_run
from app.sort_apply import CONFIRMATION_PHRASE
from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
from app.events_ui import EVENTS_HTML

NOW='2026-09-08T12:00:00+00:00'

def seed(db:Path, workspace:Path):
    initialize_database(db)
    work=workspace/'Arbeitsbereich'; work.mkdir(parents=True)
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','event_sort_applied','folder_import','TEST',?,?)",(NOW,NOW))
        families=[]
        for key,ts in [('F1','2026-07-19T18:10:00'),('F2','2026-07-19T18:20:00')]:
            fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(key,key,ts)).lastrowid)
            families.append(fid)
        # Desired index after expanding A and trimming B.
        for eid,name,child_start,child_end,child_folder in [
            ('a','A','2026-07-19T18:00:00','2026-07-19T18:30:59','18-00 - 18-30 - A'),
            ('b','B','2026-07-19T18:31:00','2026-07-19T23:59:59','18-31 - 23-59 - B'),
        ]:
            c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,resort_required)
                         VALUES (?,'j','parent',?,'2026-07-19T00:00:00','2026-07-19T23:59:59',0,?,'applied',?,?,'event',0,2,?,1)""",(eid,name,f'07-19 - {name}',NOW,NOW,NOW))
            c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at)
                         VALUES (?,'j',?,'child',?,?,?,1,?,'applied',?,?,'event',0,2,?)""",(eid+'c',eid,name,child_start,child_end,child_folder,NOW,NOW,NOW))
        # Both families now belong to A in the desired SQLite state.
        for fid in families:
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('ac',?,NULL,'date_time_range',?)",(fid,NOW))
        # B remembers that F2 fell out and targets A.
        c.execute("""INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at,target_event_id,target_status,target_kind,target_name,target_folder_name,target_preserve_day_folders,target_linkage_kind,reassigned_at)
                     VALUES ('b','j',?,?, 'a','applied','cascade_event','A','07-19 - A',0,'',?)""",(families[1],NOW,NOW))
        old_paths=[
            '2026/07-19 - A/18-00 - 18-15 - A/Alle/F1.JPG',
            '2026/07-19 - B/18-16 - 23-59 - B/Alle/F2.JPG',
        ]
        for fid,rel,payload,ts in zip(families,old_paths,[b'one',b'two'],['2026-07-19T18:10:00','2026-07-19T18:20:00']):
            path=work/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(payload)
            digest=hashlib.sha256(payload).hexdigest()
            c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,selected_capture_source,capture_time_confidence,review_status,metadata_write_status,created_at,updated_at,current_root_kind)
                         VALUES ('j',?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required','not_requested',?,?,'shared_workspace')""",
                      (fid,rel,rel,Path(rel).name,len(payload),digest,digest,ts,'DateTimeOriginal',NOW,NOW))
        c.commit()
    return families


def test_connected_applied_events_are_one_reconciliation_and_execute_atomically(tmp_path):
    db=tmp_path/'db.sqlite3'; workspace=tmp_path/'workspace'; families=seed(db,workspace)
    plan=build_workspace_reconcile_plan(db,'j','a',workspace)
    assert plan['summary']['ready'] is True
    assert plan['event_ids']==['a','b']
    assert plan['summary']['file_count']==2
    by_name={Path(f['destination_relative_path']).name:f for f in plan['files']}
    assert '18-00 - 18-30 - A' in str(by_name['F2.JPG']['destination_relative_path'])
    run=prepare_workspace_reconcile_run(db,'j','a',workspace,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
    execute_workspace_reconcile_run(db,run['id'],workspace)
    assert not (workspace/'Arbeitsbereich/2026/07-19 - B/18-16 - 23-59 - B/Alle/F2.JPG').exists()
    assert (workspace/'Arbeitsbereich/2026/07-19 - A/18-00 - 18-30 - A/Alle/F2.JPG').read_bytes()==b'two'
    with database_connection(db) as c:
        assert c.execute("SELECT resort_required FROM events WHERE id='a'").fetchone()[0]==0
        assert c.execute("SELECT resort_required FROM events WHERE id='b'").fetchone()[0]==0
        assert c.execute("SELECT COUNT(*) FROM event_reapply_removed_families WHERE job_id='j'").fetchone()[0]==0
        assert c.execute("SELECT status FROM sort_runs WHERE id=?",(run['id'],)).fetchone()[0]=='applied'


def test_applied_ui_uses_workspace_reconciliation_not_single_event_reapply():
    assert '/reconcile-plan' in EVENTS_HTML
    assert '"reconcile-sort"' in EVENTS_HTML
    assert 'plan._reconcile' in EVENTS_HTML
    assert 'id="sort-apply-confirmation"' in EVENTS_HTML
    assert 'id="sort-apply-button"' in EVENTS_HTML

def test_archived_removed_family_returns_to_free_ssd_stock(tmp_path):
    from app.event_change_request import propose_event_change, get_event_change_files
    from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
    db=tmp_path/'archive.sqlite3'; initialize_database(db); workspace=tmp_path/'workspace'; (workspace/'Arbeitsbereich').mkdir(parents=True)
    archive=tmp_path/'archive'; archive.mkdir()
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','event_ssd_released','folder_import','TEST',?,?)",(NOW,NOW))
        fids=[]
        for key,ts in [('X1','2026-07-19T18:10:00'),('X2','2026-07-19T19:10:00')]:
            fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(key,key,ts)).lastrowid); fids.append(fid)
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at)
                     VALUES ('arch','j','parent','Alt','2026-07-19T00:00:00','2026-07-19T23:59:59',0,'07-19 - Alt','archived',?,?,'event',0,1,?,?)""",(NOW,NOW,NOW,NOW))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at)
                     VALUES ('archc','j','arch','child','Alt','2026-07-19T18:00:00','2026-07-19T19:30:59',1,'18-00 - 19-30 - Alt','archived',?,?,'event',0,1,?,?)""",(NOW,NOW,NOW,NOW))
        for fid,key,payload,ts in zip(fids,['X1','X2'],[b'x1',b'x2'],['2026-07-19T18:10:00','2026-07-19T19:10:00']):
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('archc',?,NULL,'manual',?)",(fid,NOW))
            rel=f'2026/07-19 - Alt/18-00 - 19-30 - Alt/Alle/{key}.JPG'; path=archive/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(payload); digest=hashlib.sha256(payload).hexdigest()
            c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,selected_capture_source,capture_time_confidence,review_status,metadata_write_status,created_at,updated_at,current_root_kind)
                         VALUES ('j',?,?,?,?,'JPG','jpeg',?,?,?,?,?,'high','not_required','not_requested',?,?,'camera_archive')""",(fid,rel,rel,f'{key}.JPG',len(payload),digest,digest,ts,'DateTimeOriginal',NOW,NOW))
        c.commit()

    preview={'event_kind':'event','event_name':'Alt','start_date':'2026-07-19','end_date':'2026-07-19','uses_time_range':True,'start_time':'18:00','end_time':'18:30','child_event_name':'Alt','parent_folder':'07-19 - Alt','child_folder':'18-00 - 18-30 - Alt','preserve_day_folders':False,'selected_family_ids':[fids[0]],'selected_day_keys':['2026-07-19']}
    cr=propose_event_change(db,'j','arch',preview,event_name='Alt'); crid=cr['change_request_id']
    confirm_event_change(db,crid,archive,workspace)
    reviews=get_event_change_files(db,crid)
    released=next(r for r in reviews if r['family_id']==fids[1] and r['action']=='delete')
    source=archive/str(released['old_path'])
    target=workspace/'Arbeitsbereich'/str(released['workspace_release_path'])
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(source.read_bytes())
    assert verify_archive_release_copies(db,archive,workspace,crid)['complete']
    source.unlink()
    assert verify_archive_release_removal(db,archive,workspace,crid)['complete']

    # Die verbleibende Familie wird nach dem neuen SOLL innerhalb des Archivs umsortiert.
    for r in get_event_change_files(db,crid):
        if r['action']!='move':
            continue
        old=archive/str(r['old_path']); new=archive/str(r['new_path'])
        if old.exists() and old!=new:
            new.parent.mkdir(parents=True,exist_ok=True); old.replace(new)
    main_child=archive/'2026/07-19 - Alt/18-00 - 18-30 - Alt'
    (main_child/'Sortiert').mkdir(parents=True,exist_ok=True)
    (main_child/'Export').mkdir(parents=True,exist_ok=True)
    old_child=archive/'2026/07-19 - Alt/18-00 - 19-30 - Alt'
    if (old_child/'Alle').exists(): (old_child/'Alle').rmdir()
    if old_child.exists(): old_child.rmdir()

    copy_prepared_event_document(db, workspace, archive, crid)
    assert verify_event_change(db,crid,archive,workspace)['complete']
    done=finish_event_change(db,crid,archive,workspace)
    assert done['released_family_ids']==[fids[1]]
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE family_id=?",(fids[1],)).fetchone()[0]==0
        row=c.execute("SELECT current_root_kind,current_relative_path FROM files WHERE family_id=?",(fids[1],)).fetchone()
        assert row['current_root_kind']=='shared_workspace'
        assert str(row['current_relative_path']).startswith('Freigewordene Archivdateien/')


def test_migration_018_persists_archive_no_event_segments(tmp_path):
    db=tmp_path/'m.sqlite3'; info=initialize_database(db)
    assert 18 in info['applied_versions']
    with database_connection(db) as c:
        cols={r['name'] for r in c.execute('PRAGMA table_info(event_change_requests)').fetchall()}
        assert 'no_event_segments' in cols
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_change_reassignments'").fetchone()


def test_archived_no_event_edit_keeps_true_segments_and_releases_removed_family(tmp_path):
    from app.event_change_request import propose_event_change, get_event_change_files
    from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
    db=tmp_path/'noevent.sqlite3'; initialize_database(db); workspace=tmp_path/'workspace'; (workspace/'Arbeitsbereich').mkdir(parents=True)
    archive=tmp_path/'archive'; archive.mkdir()
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','event_ssd_released','folder_import','TEST',?,?)",(NOW,NOW))
        fids=[]
        for key,ts in [('N1','2026-07-22T09:00:00'),('N2','2026-07-22T11:00:00')]:
            fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(key,key,ts)).lastrowid); fids.append(fid)
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                     VALUES ('no','j','parent','Ohne Ereignis','2026-07-22T08:00:00','2026-07-22T12:00:59',0,'07 - Ohne Ereignis','archived',?,?,'no_event',0,1,?,?,'segments')""",(NOW,NOW,NOW,NOW))
        c.execute("INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at) VALUES ('no','j','2026-07-22','08:00','12:00','2026-07-22T08:00:00','2026-07-22T12:00:59','user',?,?)",(NOW,NOW))
        for fid,key,payload,ts in zip(fids,['N1','N2'],[b'n1',b'n2'],['2026-07-22T09:00:00','2026-07-22T11:00:00']):
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('no',?,NULL,'manual',?)",(fid,NOW))
            rel=f'2026/07 - Ohne Ereignis/Alle/{key}.JPG'; path=archive/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(payload); digest=hashlib.sha256(payload).hexdigest()
            c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,selected_capture_source,capture_time_confidence,review_status,metadata_write_status,created_at,updated_at,current_root_kind)
                         VALUES ('j',?,?,?,?,'JPG','jpeg',?,?,?,?,?,'high','not_required','not_requested',?,?,'camera_archive')""",(fid,rel,rel,f'{key}.JPG',len(payload),digest,digest,ts,'DateTimeOriginal',NOW,NOW))
        c.commit()

    preview={'event_kind':'no_event','event_name':'Ohne Ereignis','start_date':'2026-07-22','end_date':'2026-07-22','uses_time_range':False,'parent_folder':'07 - Ohne Ereignis','child_folder':None,'preserve_day_folders':False,'selected_family_ids':[fids[0]],'selected_day_keys':['2026-07-22'],'no_event_segments':[{'day_key':'2026-07-22','start_time':'08:00','end_time':'10:00'}]}
    cr=propose_event_change(db,'j','no',preview,event_name='Ohne Ereignis'); crid=cr['change_request_id']
    confirm_event_change(db,crid,archive,workspace)
    released=next(r for r in get_event_change_files(db,crid) if r['family_id']==fids[1] and r['action']=='delete')
    source=archive/str(released['old_path']); target=workspace/'Arbeitsbereich'/str(released['workspace_release_path'])
    target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(source.read_bytes())
    assert verify_archive_release_copies(db,archive,workspace,crid)['complete']
    source.unlink()
    assert verify_archive_release_removal(db,archive,workspace,crid)['complete']
    copy_prepared_event_document(db, workspace, archive, crid)
    assert verify_event_change(db,crid,archive,workspace)['complete']
    done=finish_event_change(db,crid,archive,workspace)
    assert done['released_family_ids']==[fids[1]]
    with database_connection(db) as c:
        segs=c.execute("SELECT day_key,start_time,end_time FROM event_time_segments WHERE event_id='no' ORDER BY id").fetchall()
        assert [(r['day_key'],r['start_time'],r['end_time']) for r in segs]==[('2026-07-22','08:00','10:00')]
        ev=c.execute("SELECT start_datetime,end_datetime,event_kind,timeline_model FROM events WHERE id='no'").fetchone()
        assert ev['start_datetime']=='2026-07-22T08:00:00'
        assert ev['end_datetime']=='2026-07-22T10:00:59'
        assert ev['event_kind']=='no_event'


def test_reconcile_recovers_stale_current_path_by_unique_size_and_sha(tmp_path):
    db=tmp_path/'db.sqlite3'; workspace=tmp_path/'workspace'; seed(db,workspace)
    work=workspace/'Arbeitsbereich'
    old=work/'2026/07-19 - B/18-16 - 23-59 - B/Alle/F2.JPG'
    actual=work/'2026/legacy-no-event/Alle/F2.JPG'
    actual.parent.mkdir(parents=True,exist_ok=True)
    old.replace(actual)
    # SQLite intentionally still points to the old path: this models the
    # production legacy state seen after older reassignment workflows.
    plan=build_workspace_reconcile_plan(db,'j','a',workspace)
    assert plan['summary']['ready'] is True
    f2=next(f for f in plan['files'] if Path(f['destination_relative_path']).name=='F2.JPG')
    assert f2['source_relative_path']=='2026/legacy-no-event/Alle/F2.JPG'
    assert any(w.get('code')=='stale_current_path_recovered' and int(w.get('file_id'))==int(f2['file_id']) for w in plan['warnings'])
    assert plan['source_root']==str(work)
    assert plan['target_root']==str(work)
    assert plan['summary']['same_filesystem'] is True
    assert plan['summary']['available_bytes'] > 0
    run=prepare_workspace_reconcile_run(db,'j','a',workspace,expected_plan_token=plan['plan_token'],confirmation_phrase=CONFIRMATION_PHRASE)
    execute_workspace_reconcile_run(db,run['id'],workspace)
    final=work/'2026/07-19 - A/18-00 - 18-30 - A/Alle/F2.JPG'
    assert final.read_bytes()==b'two'
    with database_connection(db) as c:
        row=c.execute("SELECT current_relative_path,current_root_kind FROM files WHERE original_filename='F2.JPG'").fetchone()
        assert row['current_relative_path']=='2026/07-19 - A/18-00 - 18-30 - A/Alle/F2.JPG'
        assert row['current_root_kind']=='shared_workspace'


def test_reconcile_does_not_guess_when_stale_source_has_two_identical_matches(tmp_path):
    db=tmp_path/'db.sqlite3'; workspace=tmp_path/'workspace'; seed(db,workspace)
    work=workspace/'Arbeitsbereich'
    old=work/'2026/07-19 - B/18-16 - 23-59 - B/Alle/F2.JPG'
    p1=work/'2026/recovery-a/Alle/F2.JPG'; p2=work/'2026/recovery-b/Alle/F2.JPG'
    p1.parent.mkdir(parents=True,exist_ok=True); p2.parent.mkdir(parents=True,exist_ok=True)
    data=old.read_bytes(); old.unlink(); p1.write_bytes(data); p2.write_bytes(data)
    plan=build_workspace_reconcile_plan(db,'j','a',workspace)
    assert plan['summary']['ready'] is False
    codes=[b.get('code') for b in plan['blockers']]
    assert 'source_missing' in codes
    assert 'source_recovery_ambiguous' in codes
