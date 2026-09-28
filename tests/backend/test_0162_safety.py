import hashlib
from pathlib import Path

from app.database import connect, initialize_database, get_event_edit_context
from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change, EventChangeApplyError
from app.event_change_request import propose_event_change, get_event_change_files

NOW = "2026-07-24T12:00:00"


def seed_archived(db: Path):
    with connect(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
                  ("j","sd_import","approved_sd","completed","done",NOW,NOW))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,notes,edited_at)
                     VALUES ('e','j',NULL,'parent','Rom','2026-07-24T00:00:00','2026-07-24T23:59:59',0,'07-24 - Rom','archived',?,?,?,?,?,?,?,?,?)""",
                  (NOW,NOW,"event",0,1,NOW,NOW,"",NOW))
        fid=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','fam','IMG','complete','2026-07-24T12:00:00','high')").lastrowid
        data=b'x'*100
        sha=hashlib.sha256(data).hexdigest()
        c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,selected_capture_source,capture_time_confidence,review_status,metadata_write_status,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ('j',fid,'2026/07-24 - Rom/Alle/IMG.jpg','2026/07-24 - Rom/Alle/IMG.jpg','IMG.jpg','jpg','jpeg',len(data),sha,sha,'2026-07-24T12:00:00','metadata','high','confirmed','not_requested',NOW,NOW))
        c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('e',?,NULL,'manual',?)",(fid,NOW))
    return fid, data


def test_archived_uses_full_editor_and_change_request(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db); fid,_=seed_archived(db)
    ctx=get_event_edit_context(db,'j','e')
    assert ctx['structural_editable'] is True
    assert ctx['archived_change_request'] is True
    cr=propose_event_change(db,'j','e',{
        'event_kind':'event','event_name':'Rom bearbeitet','parent_folder':'07-24 - Rom bearbeitet',
        'child_folder':'','child_event_name':'','uses_time_range':False,'preserve_day_folders':False,
        'start_date':'2026-07-24','end_date':'2026-07-24','start_time':None,'end_time':None,
        'selected_day_keys':['2026-07-24'],'selected_family_ids':[fid],
        'selected_file_count':1,'selected_family_count':1,
    }, event_name='Rom bearbeitet')
    files=get_event_change_files(db,cr['change_request_id'])
    assert len(files)==1
    assert files[0]['old_path']=='2026/07-24 - Rom/Alle/IMG.jpg'
    assert files[0]['new_path']=='2026/07-24 - Rom bearbeitet/Alle/IMG.jpg'
    assert '...' not in files[0]['new_path']


def test_archive_finish_is_read_only_and_requires_manual_target(tmp_path):
    db=tmp_path/'db.sqlite3'; initialize_database(db); fid,data=seed_archived(db)
    archive=tmp_path/'archive'; archive.mkdir()
    old=archive/'2026/07-24 - Rom/Alle/IMG.jpg'; old.parent.mkdir(parents=True); old.write_bytes(data)
    cr=propose_event_change(db,'j','e',{
        'event_kind':'event','event_name':'Rom bearbeitet','parent_folder':'07-24 - Rom bearbeitet',
        'child_folder':'','uses_time_range':False,'preserve_day_folders':False,
        'start_date':'2026-07-24','end_date':'2026-07-24','selected_family_ids':[fid],
        'selected_day_keys':['2026-07-24'],'selected_file_count':1,'selected_family_count':1,
    }, event_name='Rom bearbeitet')
    crid=cr['change_request_id']; confirm_event_change(db,crid)
    check=verify_event_change(db,crid,archive)
    assert check['complete'] is False
    assert old.exists()  # App hat nichts angefasst.
    new=archive/'2026/07-24 - Rom bearbeitet/Alle/IMG.jpg'; new.parent.mkdir(parents=True); old.rename(new)
    (archive/'2026/07-24 - Rom bearbeitet/Sortiert').mkdir()
    (archive/'2026/07-24 - Rom bearbeitet/Export').mkdir()
    old.parent.rmdir()
    old.parent.parent.rmdir()
    check=verify_event_change(db,crid,archive)
    assert check['complete'] is True
    result=finish_event_change(db,crid,archive)
    assert result['archive_read_only'] is True
    assert result['files_changed_by_app']==0
    assert new.exists()
    with connect(db) as c:
        row=c.execute("SELECT name,folder_name FROM events WHERE id='e'").fetchone()
        assert row['name']=='Rom bearbeitet'
        assert row['folder_name']=='07-24 - Rom bearbeitet'
