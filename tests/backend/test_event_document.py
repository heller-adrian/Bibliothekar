import json
import pytest
from pathlib import Path
from datetime import datetime, timezone
from app.event_document import (
    write_event_document,
    read_event_document,
    build_event_document_from_db,
    event_document_matches_db,
    sync_event_document_after_change
)
from app.database import connect

@pytest.fixture
def test_env(tmp_path):
    workspace = tmp_path / "workspace"
    import app.workspace_layout
    work_dir = workspace / app.workspace_layout.WORK_DIRECTORY_NAME
    work_dir.mkdir(parents=True)
    
    db_path = tmp_path / "test.db"
    
    with connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE jobs (
                id TEXT PRIMARY KEY, kind TEXT, trigger_type TEXT, state TEXT, stage TEXT,
                source_path TEXT, working_path TEXT, progress_current INTEGER, progress_total INTEGER,
                progress_message TEXT, operation TEXT, source_volume_label TEXT, source_signature TEXT,
                source_fingerprint TEXT, created_at TEXT, updated_at TEXT
            );
            CREATE TABLE events (
                id TEXT PRIMARY KEY, job_id TEXT, parent_event_id TEXT, event_level TEXT, name TEXT,
                start_datetime TEXT, end_datetime TEXT, uses_time_range INTEGER, folder_name TEXT,
                status TEXT, created_at TEXT, updated_at TEXT, event_kind TEXT, preserve_day_folders INTEGER,
                revision INTEGER, applied_at TEXT, archived_at TEXT, notes TEXT, edited_at TEXT,
                linkage_kind TEXT
            );
            CREATE TABLE file_families (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, family_key TEXT,
                selected_capture_time TEXT, capture_time_confidence REAL
            );
            CREATE TABLE files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, family_id INTEGER,
                current_relative_path TEXT, original_filename TEXT, size_bytes INTEGER,
                sha256_current TEXT, sha256_original TEXT, review_status TEXT
            );
            CREATE TABLE event_assignments (
                event_id TEXT, family_id INTEGER, file_id INTEGER,
                assignment_source TEXT, created_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id),
                FOREIGN KEY(family_id) REFERENCES file_families(id)
            );
        """)

    return {
        "workspace": workspace,
        "db_path": db_path,
        "job_id": "TEST_JOB_123"
    }

def test_write_and_read_event_document(test_env):
    ws = test_env["workspace"]
    doc = {
        "document_version": 1,
        "event": {
            "id": "evt_1",
            "name": "Test Event",
            "start_date": "2023-01-01",
            "folder_name": "test_folder",
            "status": "applied",
            "applied_at": "2023-01-01T12:00:00Z",
            "revision": 1
        },
        "families": [],
        "files": []
    }
    
    path = write_event_document(ws, doc)
    assert path.exists()
    
    read_doc = read_event_document(path)
    assert read_doc["event"]["id"] == "evt_1"
    assert read_doc["event"]["name"] == "Test Event"

def test_event_document_matches_db(test_env):
    ws = test_env["workspace"]
    db = test_env["db_path"]
    job_id = test_env["job_id"]
    event_id = "evt_sync_1"
    
    with connect(db) as conn:
        conn.execute("INSERT INTO jobs (id, kind, trigger_type, state, stage, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                     (job_id, "folder_import", "manual", "completed", "completed", "2023-01-01T00:00:00", "2023-01-01T00:00:00"))
        
        # Fixed bindings: count matches the question marks
        conn.execute("""
            INSERT INTO events (id, job_id, event_level, name, start_datetime, end_datetime, folder_name, status, 
                               created_at, updated_at, event_kind, preserve_day_folders, revision, applied_at)
            VALUES (?, ?, 'parent', ?, ?, ?, ?, 'applied', ?, ?, 'event', 0, 1, ?)
        """, (event_id, job_id, "Test Event", "2023-01-01T00:00:00", "2023-01-02T00:00:00", "test_folder", "2023-01-01T00:00:00", "2023-01-01T00:00:00", "2023-01-01T00:00:00"))
        
        conn.execute("INSERT INTO file_families (id, job_id, family_key, selected_capture_time) VALUES (?, ?, ?, ?)",
                     (1, job_id, "fam_1", "2023-01-01T10:00:00"))
        
        conn.execute("INSERT INTO event_assignments (event_id, family_id, assignment_source, created_at) VALUES (?, ?, ?, ?)",
                     (event_id, 1, "date_range", "2023-01-01T00:00:00"))

        conn.execute("""
            INSERT INTO files (job_id, family_id, current_relative_path, original_filename,
                               size_bytes, sha256_original, sha256_current, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, 1, "Alle/2023-01-01/IMG_0001.RAF", "IMG_0001.RAF",
              42000000, "abc123", "abc123", "required"))

    doc = {
        "event": {
            "id": event_id,
            "name": "Test Event",
            "event_kind": "event",
            "start_date": "2023-01-01",
            "end_date": "2023-01-02",
            "uses_time_range": False,
            "preserve_day_folders": False,
            "folder_name": "test_folder",
            "status": "applied",
            "applied_at": "2023-01-01T00:00:00",
            "revision": 1
        },
        "families": [{"family_id": 1, "family_key": "fam_1", "selected_capture_time": "2023-01-01T10:00:00", "file_count": 0, "total_size_bytes": 0}],
        "files": []
    }

    result = event_document_matches_db(db, ws, job_id, event_id, doc)
    assert result["ok"] is True
    
    doc["event"]["name"] = "Mismatched Name"
    result = event_document_matches_db(db, ws, job_id, event_id, doc)
    assert result["ok"] is False
    assert "name" in result["mismatches"]

def test_sync_event_document_after_change(test_env):
    ws = test_env["workspace"]
    db = test_env["db_path"]
    job_id = test_env["job_id"]
    event_id = "evt_sync_2"
    
    with connect(db) as conn:
        conn.execute("INSERT INTO jobs (id, kind, trigger_type, state, stage, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                     (job_id, "folder_import", "manual", "completed", "completed", "2023-01-01T00:00:00", "2023-01-01T00:00:00"))
        
        # Fixed bindings: count matches the question marks
        conn.execute("""
            INSERT INTO events (id, job_id, event_level, name, start_datetime, end_datetime, folder_name, status, 
                               created_at, updated_at, event_kind, preserve_day_folders, revision, applied_at)
            VALUES (?, ?, 'parent', ?, ?, ?, ?, 'applied', ?, ?, 'event', 0, 1, ?)
        """, (event_id, job_id, "Sync Event", "2023-01-01T00:00:00", "2023-01-02T00:00:00", "sync_folder", "2023-01-01T00:00:00", "2023-01-01T00:00:00", "2023-01-01T00:00:00"))
        
        conn.execute("INSERT INTO file_families (id, job_id, family_key, selected_capture_time) VALUES (?, ?, ?, ?)",
                     (10, job_id, "fam_sync", "2023-01-01T10:00:00"))
        
        conn.execute("INSERT INTO event_assignments (event_id, family_id, assignment_source, created_at) VALUES (?, ?, ?, ?)",
                     (event_id, 10, "date_range", "2023-01-01T00:00:00"))

        conn.execute("""
            INSERT INTO files (job_id, family_id, current_relative_path, original_filename,
                               size_bytes, sha256_original, sha256_current, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, 10, "Alle/2023-01-01/IMG_0010.RAF", "IMG_0010.RAF",
              38000000, "def456", "def456", "required"))

    sync_event_document_after_change(db, ws, job_id, event_id)
    
    import app.workspace_layout
    expected_path = ws / app.workspace_layout.WORK_DIRECTORY_NAME / "2023" / "sync_folder" / "event.json"
    assert expected_path.exists()
    
    doc = read_event_document(expected_path)
    assert doc["event"]["id"] == event_id
    assert doc["event"]["name"] == "Sync Event"
