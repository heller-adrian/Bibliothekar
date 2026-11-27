import hashlib

import pytest

from app import archive_inventory_scan as scan
from app.archive_transfer import latest_archive_verification
from app.database import database_connection, initialize_database
from tests.backend.test_0263_event_inventory import NOW, seed_event, seed_job


def hash_bytes(content):
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def archive(tmp_path):
    db = tmp_path / "catalogue.sqlite3"
    initialize_database(db)
    root = tmp_path / "archive"
    event = root / "2026/07-23 - Trip"
    event.mkdir(parents=True)
    expected = {
        "same.jpg": b"same",
        "missing.jpg": b"missing",
        "old.jpg": b"moved",
        "different.jpg": b"before",
    }
    with database_connection(db) as connection:
        seed_job(connection)
        seed_event(connection, status="archived")
        connection.execute("""
            INSERT INTO event_archive_verifications(
                id,job_id,event_id,status,archive_root,file_count,created_at,updated_at,completed_at
            ) VALUES ('receipt','j','e','verified',?,4,?,?,?)
            """, (str(root), NOW, NOW, NOW))
        connection.executemany("""
            INSERT INTO event_archive_verification_assets(
                verification_id,asset_kind,source_event_relative_path,expected_relative_path,
                expected_size_bytes,expected_sha256,status
            ) VALUES ('receipt','export',?,?,?,?,'verified')
            """, [(name, f"2026/07-23 - Trip/{name}", len(data), hash_bytes(data)) for name, data in expected.items()])
    (event / "same.jpg").write_bytes(expected["same.jpg"])
    (event / "different.jpg").write_bytes(b"change")  # Same length as the recorded content.
    (event / "renamed.jpg").write_bytes(expected["old.jpg"])
    (event / "new.jpg").write_bytes(b"new")
    (root / "unassigned.jpg").write_bytes(b"unknown location")
    (event / "event.json").write_bytes(b"administrative document")
    return db, root


def contents(root):
    return {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_scan_detects_changes_without_rewriting_files_catalogue_or_proof(archive):
    db, root = archive
    before = contents(root)
    assert scan.status(db)["status"] == "idle"
    queued = scan.enqueue(db)
    assert scan.enqueue(db) == queued
    assert scan.run(db, root.parent, root, lambda: False)
    result = scan.status(db)
    assert result["status"] == "completed"
    assert result["id"] == queued["id"]
    assert (result["checked"], result["total"], result["percent"]) == (5, 5, 100)
    assert result["last_success_at"]
    assert result["result"] == dict(added=1, missing=1, moved=1, changed=1, unassigned=1)
    assert not scan.run.__wrapped__(db, root.parent, root, lambda: False)
    assert contents(root) == before
    proof = latest_archive_verification(db, "j", "e")
    assert proof["error_message"] == "verification_invalidated_by_archive_scan"
    assert proof["details"]["supersedes_verification_id"] == "receipt"
    with database_connection(db) as connection:
        assert connection.execute("SELECT status FROM event_archive_verifications WHERE id='receipt'").fetchone()[0] == "verified"
        assert connection.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM external_change_notices WHERE status='open'").fetchone()[0] == 2


def test_restart_reuses_job_and_failure_preserves_last_success(archive, monkeypatch):
    db, root = archive
    queued = scan.enqueue(db)
    original_hash = scan.bound_sha256

    def interrupted(*args, **kwargs):
        raise InterruptedError("container stopping")

    monkeypatch.setattr(scan, "bound_sha256", interrupted)
    assert scan.run.__wrapped__(db, root.parent, root, lambda: False)
    state = scan.status(db)
    assert (state["id"], state["attempt"], state["status"]) == (queued["id"], 1, "interrupted")
    assert scan.enqueue(db) == state
    assert latest_archive_verification(db, "j", "e")["verified"]
    # Model a killed process whose persisted state says running. A new
    # reservation proves no worker owns that reservation any longer.
    with database_connection(db) as connection:
        scan._save(connection, dict(state, status="running"))
    monkeypatch.setattr(scan, "bound_sha256", original_hash)
    assert scan.run.__wrapped__(db, root.parent, root, lambda: False)
    resumed = scan.status(db)
    assert (resumed["id"], resumed["attempt"], resumed["status"]) == (queued["id"], 2, "completed")
    (root / "unsafe").symlink_to(root / "unassigned.jpg")
    scan.enqueue(db)
    assert scan.run.__wrapped__(db, root.parent, root, lambda: False)
    failed = scan.status(db)
    assert failed["status"] == "failed"
    assert failed["last_success_at"] == resumed["last_success_at"]
    assert failed["result"] == resumed["result"]
    assert "unsafe" in failed["error"]


def test_identical_content_with_multiple_candidates_stays_unassigned():
    events = {"e": ("j", "Trip", "2026/Trip", 1, "proof")}
    expected = {"2026/Trip/a.jpg": {("e", 1, "h")}}
    actual = {"2026/Trip/b.jpg": (1, "h"), "2026/Trip/c.jpg": (1, "h")}
    groups = scan._findings(events, expected, actual)
    assert groups["e"]["counts"] == {"missing": 1, "unassigned": 2}
