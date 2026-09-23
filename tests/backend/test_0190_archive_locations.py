from pathlib import Path
import pytest

from app.archive_locations import (
    ArchiveLocationError,
    stable_anchor_from_file_path,
    resolve_archived_file_relative_path,
    record_family_anchor,
)
from app.database import initialize_database, database_connection, create_planned_event


def _seed_job_family(db: Path, *, day="2026-07-24", stem="F1") -> int:
    now="2026-09-09T12:00:00+00:00"
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(stem,stem,f"{day}T12:00:00")).lastrowid)
        c.commit()
    return fid


def test_stable_anchor_ignores_sort_branch():
    assert stable_anchor_from_file_path("2026/07-23 - Test/Alle/a.JPG") == "2026/07-23 - Test"
    assert stable_anchor_from_file_path("2026/07-23 - Test/Tag/Sortiert/a.JPG") == "2026/07-23 - Test/Tag"
    assert stable_anchor_from_file_path("2026/07-23 - Test/09-10 - Kind/Export/a.JPG") == "2026/07-23 - Test/09-10 - Kind"


def test_resolve_uses_verified_anchor_and_finds_file_after_manual_sort(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db); fid=_seed_job_family(db)
    now="2026-09-09T12:00:00+00:00"
    with database_connection(db) as c:
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                     VALUES ('e','j','parent','Test','2026-07-24T00:00:00','2026-07-24T23:59:59',0,'07-24 - Test','archived',?,?,'event',0,1,'continuous')""",(now,now))
        record_family_anchor(c,'e',fid,["2026/07-24 - Test/Alle/a.JPG"],now)
        c.commit()
    root=tmp_path/'archive'; (root/'2026'/'07-24 - Test'/'Sortiert').mkdir(parents=True)
    (root/'2026'/'07-24 - Test'/'Sortiert'/'a.JPG').write_bytes(b'x')
    rel=resolve_archived_file_relative_path(db,root,event_id='e',family_id=fid,filename='a.JPG',fallback_anchor='wrong')
    assert rel == '2026/07-24 - Test/Sortiert/a.JPG'


def test_resolve_blocks_ambiguous_file(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db); fid=_seed_job_family(db)
    now="2026-09-09T12:00:00+00:00"
    with database_connection(db) as c:
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                     VALUES ('e','j','parent','Test','2026-07-24T00:00:00','2026-07-24T23:59:59',0,'07-24 - Test','archived',?,?,'event',0,1,'continuous')""",(now,now))
        record_family_anchor(c,'e',fid,["2026/07-24 - Test/Alle/a.JPG"],now)
        c.commit()
    root=tmp_path/'archive'
    for branch in ('Alle','Sortiert'):
        p=root/'2026'/'07-24 - Test'/branch; p.mkdir(parents=True,exist_ok=True); (p/'a.JPG').write_bytes(b'x')
    with pytest.raises(ArchiveLocationError, match='mehrfach'):
        resolve_archived_file_relative_path(db,root,event_id='e',family_id=fid,filename='a.JPG',fallback_anchor='')


def test_no_event_second_collection_same_month_is_blocked(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    now="2026-09-09T12:00:00+00:00"
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        ids=[]
        for n,day in enumerate(('2026-07-24','2026-07-25'),1):
            ids.append(int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",(f'F{n}',f'F{n}',f'{day}T12:00:00')).lastrowid))
        c.commit()
    def preview(fid,day):
        return {'event_kind':'no_event','event_name':'Ohne Ereignis','parent_folder':'07 - Ohne Ereignis','child_folder':None,'child_event_name':None,'uses_time_range':False,'preserve_day_folders':False,'start_date':day,'end_date':day,'start_time':None,'end_time':None,'no_event_segments':[{'day_key':day,'start_time':'00:00','end_time':'23:59','start_datetime':f'{day}T00:00:00','end_datetime':f'{day}T23:59:59'}],'selected_day_keys':[day],'selected_family_ids':[fid],'selected_file_count':0,'selected_family_count':1,'structure_lines':[]}
    create_planned_event(db,'j',preview(ids[0],'2026-07-24'))
    with pytest.raises(ValueError, match='existiert bereits'):
        create_planned_event(db,'j',preview(ids[1],'2026-07-25'))


def test_schema_contains_archive_anchor_migration(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    with database_connection(db) as c:
        assert c.execute("SELECT 1 FROM schema_versions WHERE version=20").fetchone() is not None
        cols={r['name'] for r in c.execute('PRAGMA table_info(event_archive_family_anchors)')}
        assert {'event_id','family_id','anchor_relative_path','verified_at'} <= cols


def test_change_plan_uses_actual_archive_location_not_stale_db_path(tmp_path):
    from app.event_change_request import _compute_event_plan
    import hashlib
    db=tmp_path/'db.sqlite3'; initialize_database(db)
    now='2026-09-09T12:00:00+00:00'
    data=b'archive-data'; sha=hashlib.sha256(data).hexdigest()
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",(now,now))
        fid=int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','F','F','complete','2026-07-23T09:47:52','high')").lastrowid)
        file_id=int(c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,capture_time_confidence,created_at,updated_at)
                               VALUES ('j',?,'DCIM/a.JPG','2026/07-23 - Test/Alle/a.JPG','a.JPG','.JPG','jpeg',?,?,?,'2026-07-23T09:47:52','high',?,?)""",(fid,len(data),sha,sha,now,now)).lastrowid)
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                     VALUES ('e','j','parent','Test','2026-07-23T00:00:00','2026-07-23T23:59:59',0,'07-23 - Test','archived',?,?,'event',0,1,?,?, 'continuous')""",(now,now,now,now))
        c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('e',?,NULL,'manual',?)",(fid,now))
        c.commit()
    root=tmp_path/'archive'; actual=root/'2026'/'07-23 - Test'/'09-00 - 15-00 - Test'/'Sortiert'; actual.mkdir(parents=True)
    (actual/'a.JPG').write_bytes(data)
    preview={'parent_folder':'07-23 - Test','child_folder':'09-00 - 10-00 - Test','preserve_day_folders':False,'start_date':'2026-07-23','selected_family_ids':[fid]}
    plan=_compute_event_plan(db,'j','e',preview,archive_root=root)
    row=plan['families_with_plans'][0]
    assert row['file_id']==file_id
    assert row['old_path']=='2026/07-23 - Test/09-00 - 15-00 - Test/Sortiert/a.JPG'
    assert row['new_path']=='2026/07-23 - Test/09-00 - 10-00 - Test/Sortiert/a.JPG'
