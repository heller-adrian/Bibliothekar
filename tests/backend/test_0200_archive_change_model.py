from pathlib import Path
import hashlib

from app.archive_locations import (
    record_family_anchor,
    record_verified_file_location,
    resolve_archived_file_relative_path,
)
from app.database import initialize_database, database_connection
from app.main import APP_VERSION
from app.events_ui import EVENTS_HTML


def _seed(db: Path):
    now = "2026-09-10T00:00:00+00:00"
    data = b"verified"
    sha = hashlib.sha256(data).hexdigest()
    with database_connection(db) as c:
        c.execute("INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)", (now, now))
        fid = int(c.execute("INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j','F','F','complete','2026-07-23T09:47:52','high')").lastrowid)
        file_id = int(c.execute("""INSERT INTO files(job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,size_bytes,sha256_original,sha256_current,selected_capture_time,capture_time_confidence,created_at,updated_at)
            VALUES ('j',?,'DCIM/a.JPG','2026/07-23 - Test/Alle/a.JPG','a.JPG','.JPG','jpeg',?,?,?,'2026-07-23T09:47:52','high',?,?)""", (fid, len(data), sha, sha, now, now)).lastrowid)
        c.execute("""INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at,timeline_model)
            VALUES ('e','j','parent','Test','2026-07-23T00:00:00','2026-07-23T23:59:59',0,'07-23 - Test','archived',?,?,'event',0,1,?,?, 'continuous')""", (now, now, now, now))
        c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('e',?,NULL,'manual',?)", (fid, now))
        c.commit()
    return fid, file_id, data, now


def test_0200_version_and_schema(tmp_path):
    assert APP_VERSION >= "0.20.0"
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as c:
        assert c.execute("SELECT 1 FROM schema_versions WHERE version=21").fetchone() is not None
        cols = {r['name'] for r in c.execute("PRAGMA table_info(event_archive_verified_file_locations)")}
        assert {'event_id','family_id','file_id','relative_path','verified_at'} <= cols


def test_resolver_prefers_exact_verified_path(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    fid, file_id, data, now = _seed(db)
    root = tmp_path / "archive"
    exact = root / '2026' / '07-23 - Test' / 'Sortiert' / 'a.JPG'
    exact.parent.mkdir(parents=True)
    exact.write_bytes(data)
    with database_connection(db) as c:
        record_family_anchor(c, 'e', fid, ['2026/07-23 - Test/Sortiert/a.JPG'], now)
        record_verified_file_location(c, 'e', fid, file_id, '2026/07-23 - Test/Sortiert/a.JPG', now)
    rel = resolve_archived_file_relative_path(db, root, event_id='e', family_id=fid, file_id=file_id, filename='a.JPG', fallback_anchor='wrong')
    assert rel == '2026/07-23 - Test/Sortiert/a.JPG'


def test_resolver_falls_back_to_stable_anchor_after_manual_sort(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    fid, file_id, data, now = _seed(db)
    root = tmp_path / "archive"
    moved = root / '2026' / '07-23 - Test' / 'Export' / 'a.JPG'
    moved.parent.mkdir(parents=True)
    moved.write_bytes(data)
    with database_connection(db) as c:
        record_family_anchor(c, 'e', fid, ['2026/07-23 - Test/Alle/a.JPG'], now)
        record_verified_file_location(c, 'e', fid, file_id, '2026/07-23 - Test/Alle/a.JPG', now)
    rel = resolve_archived_file_relative_path(db, root, event_id='e', family_id=fid, file_id=file_id, filename='a.JPG', fallback_anchor='wrong')
    assert rel == '2026/07-23 - Test/Export/a.JPG'


def test_change_request_ui_uses_backend_assistant_operations():
    assert '/assistant' in EVENTS_HTML
    assert 'assistant.operations' in EVENTS_HTML
    assert 'Dateien innerhalb der Kamerabibliothek verschieben' in Path("app/archive_change_assistant.py").read_text()
