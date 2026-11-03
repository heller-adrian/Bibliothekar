"""Focused external camera rename approval and refusal (pre.6.1)."""
import hashlib
import json
import sqlite3

import pytest

from app import external_changes


def _connection(path):
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _setup(tmp_path, monkeypatch, *, archive=False, central=False):
    from app import root_operations
    monkeypatch.setattr(root_operations, "validate_active_roots", lambda: None)
    monkeypatch.setattr(external_changes, "database_connection", _connection)
    called = []
    from app import event_document_sync
    monkeypatch.setattr(
        event_document_sync,
        "queue_event_document_sync",
        lambda c, job, event, rev, **kw: called.append((job, event, rev)),
    )
    workspace = tmp_path / "work"
    directory = workspace / "2026" / "07-19 - Test" / "All"
    directory.mkdir(parents=True)
    actual = directory / "incorrect.JPG"
    payload = b"original-jpeg-byte-contents"
    actual.write_bytes(payload)
    root_kind = "camera_archive" if archive else (
        "central_stock" if central else "shared_workspace"
    )
    before = "2026/07-19 - Test/All/original.JPG"
    after = "2026/07-19 - Test/All/incorrect.JPG"
    path = tmp_path / "db.sqlite3"
    with _connection(path) as c:
        c.executescript("""
            CREATE TABLE files(
                id INTEGER PRIMARY KEY,job_id TEXT,current_relative_path TEXT,
                current_root_kind TEXT,updated_at TEXT);
            CREATE TABLE events(
                id TEXT PRIMARY KEY,job_id TEXT,status TEXT,revision INTEGER,
                updated_at TEXT,edited_at TEXT);
            CREATE TABLE external_change_notices(
                id TEXT PRIMARY KEY,status TEXT,kind TEXT,root_kind TEXT,
                event_id TEXT,file_id INTEGER,job_id TEXT,details_json TEXT,
                repairable INTEGER,action_required INTEGER,acknowledged_at TEXT,
                updated_at TEXT,completed_at TEXT);
            CREATE TABLE audit_log(job_id TEXT,action TEXT,entity_type TEXT,
                entity_id TEXT,details_json TEXT,created_at TEXT);
        """)
        c.execute("INSERT INTO files VALUES(1,'JOB',?,?,'')", (
            before, "shared_workspace" if central else root_kind
        ))
        c.execute("INSERT INTO events VALUES('E','JOB','applied',1,'','')")
        c.execute(
            """INSERT INTO external_change_notices
               VALUES('N','open','file_rename',?,'E',1,'JOB',?,1,1,NULL,'',NULL)""",
            (root_kind, json.dumps({
                "expected_relative_path": before,
                "observed_relative_path": after,
                "expected_root_kind":root_kind,
                "observed_root_kind":root_kind,
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })),
        )
    return path, workspace, actual, called


def test_explicit_accept_keeps_bytes_and_updates_catalog(tmp_path, monkeypatch):
    db, root, actual, queued = _setup(tmp_path, monkeypatch)
    result = external_changes.accept_external_file_rename(
        db, "N", library_work_root=root
    )
    assert result["status"] == "resolved"
    assert actual.read_bytes() == b"original-jpeg-byte-contents"
    assert queued == [("JOB", "E", 2)]
    with _connection(db) as c:
        file_row = c.execute("SELECT current_relative_path FROM files").fetchone()
        event_row = c.execute("SELECT revision FROM events").fetchone()
        assert file_row[0].endswith("/incorrect.JPG")
        assert event_row[0] == 2
        assert c.execute("SELECT count(*) FROM audit_log").fetchone()[0] == 1


def test_modified_file_refuses_approval(tmp_path, monkeypatch):
    db, root, actual, queued = _setup(tmp_path, monkeypatch)
    actual.write_bytes(b"altered")
    with pytest.raises(external_changes.ExternalChangeError, match="Dateiinhalt"):
        external_changes.accept_external_file_rename(
            db, "N", library_work_root=root
        )
    assert not queued
    with _connection(db) as c:
        assert c.execute("SELECT status FROM external_change_notices").fetchone()[0] == "open"
        assert c.execute("SELECT current_relative_path FROM files").fetchone()[0].endswith("/original.JPG")


def test_archive_requires_manual_review(tmp_path, monkeypatch):
    db, root, actual, queued = _setup(tmp_path, monkeypatch, archive=True)
    with pytest.raises(external_changes.ExternalChangeError, match="Archiv"):
        external_changes.accept_external_file_rename(
            db, "N", library_work_root=root
        )
    assert actual.is_file()
    assert not queued


def test_recreated_old_name_blocks_adoption(tmp_path, monkeypatch):
    db, root, actual, queued = _setup(tmp_path, monkeypatch)
    (actual.parent / "original.JPG").write_bytes(b"other-content")
    with pytest.raises(external_changes.ExternalChangeError, match="belegt"):
        external_changes.accept_external_file_rename(
            db, "N", library_work_root=root
        )
    assert not queued


def test_central_stock_rename_accepts_without_event_mutation(tmp_path, monkeypatch):
    db, root, actual, queued = _setup(tmp_path, monkeypatch, central=True)
    result = external_changes.accept_external_file_rename(
        db, "N", library_work_root=root, central_root=root,
    )
    assert result["status"] == "resolved"
    assert actual.is_file()
    assert queued == []
    with _connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files"
        ).fetchone()[0].endswith("/incorrect.JPG")
        assert c.execute("SELECT revision FROM events").fetchone()[0] == 1



def test_real_applied_event_rename_creates_task_then_accepts(tmp_path, monkeypatch):
    from tests.backend.test_pre6_truenas_acceptance import seed_collection
    from app.database import database_connection, list_global_tasks
    from app.workspace_layout import shared_work_root
    from app.live_inventory import refresh_live_event_inventories
    from app.event_structure_changes import detect_all_event_structure_changes
    from app.external_changes import list_external_change_state

    db, ws, central, event, _ = seed_collection(tmp_path, monkeypatch)
    with database_connection(db) as c:
        row = c.execute(
            "SELECT id,current_relative_path FROM files "
            "WHERE original_filename='OLD0.JPG'"
        ).fetchone()
        file_id, expected = int(row["id"]), str(row["current_relative_path"])
    root = shared_work_root(ws)
    old_file = root / expected
    new_file = old_file.with_name("manually-renamed.JPG")
    before = old_file.read_bytes()
    old_file.rename(new_file)

    refresh_live_event_inventories(db, ws, tmp_path / "unused-archive")
    detect_all_event_structure_changes(db, ws)
    notices = [
        n for n in list_external_change_state(db)["required"]
        if n["kind"] == "file_rename" and int(n["file_id"]) == file_id
    ]
    assert len(notices) == 1
    assert any(t["kind"] == "placement_conflicts" for t in list_global_tasks(db))
    with database_connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
        ).fetchone()[0] == expected
    external_changes.accept_external_file_rename(
        db, notices[0]["id"], library_work_root=root
    )
    with database_connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
        ).fetchone()[0].endswith("manually-renamed.JPG")
        assert c.execute(
            "SELECT status FROM external_change_notices WHERE id=?",
            (notices[0]["id"],)
        ).fetchone()[0] == "resolved"
    assert new_file.read_bytes() == before


def test_real_central_stock_rename_creates_task_then_undoes(tmp_path, monkeypatch):
    from tests.backend.test_pre6_truenas_acceptance import seed_collection
    from app.database import database_connection
    from app.workspace_layout import shared_work_root
    from app.central_stock_reconcile import reconcile_central_free_stock
    from app.external_changes import list_external_change_state

    db, ws, central, event, incoming = seed_collection(tmp_path, monkeypatch)
    _, file_id, rel = incoming[0]
    original = central / rel
    renamed = original.with_name("renamed-free.JPG")
    content = original.read_bytes()
    original.rename(renamed)
    result = reconcile_central_free_stock(db, ws, library_id="main")
    assert result["misplaced_file_count"] == 1
    notices = [
        notice for notice in list_external_change_state(db)["required"]
        if notice["kind"] == "file_rename"
        and int(notice["file_id"]) == file_id
    ]
    assert len(notices) == 1
    external_changes.repair_external_notice(
        db, notices[0]["id"],
        central_root=central, library_work_root=shared_work_root(ws),
    )
    assert original.read_bytes() == content
    assert not renamed.exists()
    with database_connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
        ).fetchone()[0] == rel
