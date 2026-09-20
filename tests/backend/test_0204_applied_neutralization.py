from pathlib import Path
import hashlib

from app.database import database_connection, initialize_database, update_event_definition
from app.event_mutation import cancel_mutation
from app.main import APP_VERSION

NOW = "2026-09-10T20:00:00+00:00"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed(tmp_path: Path, *, no_event: bool = False):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereich"
    work.mkdir(parents=True)
    (workspace / "SD-Kartensicherungen").mkdir()
    initialize_database(db)
    event_kind = "no_event" if no_event else "event"
    folder = "09 - Ohne Ereignis" if no_event else "09-07 - Quelle"
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at) VALUES ('j','sd_import','manual','completed','done',?,?)", (NOW,NOW))
        c.execute("""INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
                     VALUES ('src','j',NULL,'parent',?,'2026-09-07T00:00:00','2026-09-08T23:59:59',0,?,'applied',?,?,?,0,1,?,NULL,?)""",
                  ('Ohne Ereignis' if no_event else 'Quelle', folder, NOW, NOW, event_kind, NOW, 'segments' if no_event else 'continuous'))
        if no_event:
            for day in ('2026-09-07','2026-09-08'):
                c.execute("""INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,start_datetime,end_datetime,source,created_at,updated_at)
                             VALUES ('src','j',?,'00:00','23:59',?,?, 'user',?,?)""",
                          (day, day+'T00:00:00', day+'T23:59:59', NOW, NOW))
        ids=[]
        for n, day in ((1,'2026-09-07'),(2,'2026-09-08')):
            fid=c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",
                          (f'f{n}',f'IMG{n}',day+'T11:00:00')).lastrowid
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('src',?,NULL,'date_range',?)",(fid,NOW))
            ids.append(fid)
            for ext, payload in (("JPG", f"jpg-{n}".encode()), ("RAF", f"raf-{n}".encode())):
                name=f"2026090{6+n}_110000_Fuji-X-E5.{ext}"
                rel=f"2026/{folder}/Alle/{name}"
                path=work / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
                sha=_digest(payload)
                c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,capture_time_confidence,created_at,updated_at,current_root_kind)
                             VALUES ('j',?,?,?,?,?,?,?,?,?,?, 'high',?,?,'shared_workspace')""",
                          (fid, f"orig/{name}", rel, name, '.'+ext.lower(), 'raw' if ext=='RAF' else 'jpeg', len(payload), sha, sha, day+'T11:00:00', NOW, NOW))
        c.commit()
    return db, workspace, ids, folder


def _edit(db, workspace, ids, folder, *, no_event=False):
    preview={
        'selected_family_ids':[ids[0]],
        'start_date':'2026-09-07','end_date':'2026-09-07',
        'start_time':'00:00','end_time':'23:59','uses_time_range':False,
        'parent_folder':folder,'child_folder':'','child_event_name':'',
        'event_kind':'no_event' if no_event else 'event','preserve_day_folders':False,
    }
    if no_event:
        preview['no_event_segments']=[{'day_key':'2026-09-07','start_time':'00:00','end_time':'23:59'}]
    return update_event_definition(db,'j','src',preview,event_name='Ohne Ereignis' if no_event else 'Quelle',notes='',expected_revision=1,workspace_path=workspace,app_version=APP_VERSION)


def _assert_neutralized(db, workspace, removed_id):
    root=workspace/'Arbeitsbereich'
    expected=[]
    with database_connection(db) as c:
        rows=c.execute("SELECT current_relative_path FROM files WHERE family_id=? ORDER BY id",(removed_id,)).fetchall()
        rels=[str(r['current_relative_path']) for r in rows]
    assert len(rels)==2
    assert all(r.startswith('Nicht zugeordnet/2026/09/') for r in rels)
    assert all((root/r).is_file() for r in rels)
    return rels


def test_version_0204():
    assert APP_VERSION == '0.22.3'


def test_applied_normal_event_removed_family_moves_to_neutral_workspace(tmp_path):
    db,workspace,ids,folder=_seed(tmp_path,no_event=False)
    result=_edit(db,workspace,ids,folder,no_event=False)
    assert result['removed_family_ids']==[ids[1]]
    assert result['neutralized_file_count']==2
    _assert_neutralized(db,workspace,ids[1])
    assert not any((workspace/'Arbeitsbereich'/f'2026/{folder}/Alle').glob('20260908_*'))


def test_applied_no_event_removed_family_moves_to_same_neutral_rule(tmp_path):
    db,workspace,ids,folder=_seed(tmp_path,no_event=True)
    result=_edit(db,workspace,ids,folder,no_event=True)
    assert result['removed_family_ids']==[ids[1]]
    assert result['neutralized_file_count']==2
    _assert_neutralized(db,workspace,ids[1])


def test_cancel_applied_edit_restores_neutralized_files_and_paths(tmp_path):
    db,workspace,ids,folder=_seed(tmp_path,no_event=False)
    result=_edit(db,workspace,ids,folder,no_event=False)
    neutral=_assert_neutralized(db,workspace,ids[1])
    with database_connection(db) as c:
        c.execute('BEGIN IMMEDIATE')
        cancelled=cancel_mutation(c,result['mutation_id'],'j',workspace_path=workspace)
        c.commit()
    assert cancelled['restored_file_count']==2
    assert all(not (workspace/'Arbeitsbereich'/r).exists() for r in neutral)
    with database_connection(db) as c:
        rels=[str(r['current_relative_path']) for r in c.execute("SELECT current_relative_path FROM files WHERE family_id=? ORDER BY id",(ids[1],)).fetchall()]
        assignment=c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='src' AND family_id=?",(ids[1],)).fetchone()[0]
    assert all(r.startswith(f'2026/{folder}/Alle/') for r in rels)
    assert assignment==1
    assert not (workspace/'Arbeitsbereich'/'Nicht zugeordnet'/'2026'/'09').exists()
    assert not (workspace/'Arbeitsbereich'/'Nicht zugeordnet'/'2026').exists()
