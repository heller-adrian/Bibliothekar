"""0.44.4: dauerhafte Auftragsannahme, Wiederaufnahme und sichere Dateirücknahme."""
import hashlib
import json
import os
import sqlite3
from pathlib import Path

import pytest

from app import background_mutation_cancel as queue
from app import applied_neutralization as neutral
from app import main
from app.database import initialize_database
from app.events_ui import EVENTS_HTML
from app.ui_shell import BIBLIOTHEKAR_0443_CSS, BIBLIOTHEKAR_0443_JS, apply_shell


def _db(path: Path):
    initialize_database(path)
    # Fixture-Kennung ohne echte Importdaten; nur die Queue-/Mutationstabelle
    # wird geprüft, deshalb werden keine Archive oder Jobs angelegt.
    with sqlite3.connect(path) as db:
        db.execute(
            """INSERT INTO event_mutations(
                id,job_id,anchor_event_id,mutation_kind,status,
                affected_event_ids_json,original_state_json,target_state_json,
                created_at,updated_at
            ) VALUES('mut','job','evt','edit','pending_apply','[]','{}','{}',
                     datetime('now'),datetime('now'))"""
        )


def test_0443_queue_durable_idempotent_and_recoverable(tmp_path):
    db = tmp_path / "library.sqlite3"
    _db(db)
    original = queue.enqueue(db, "job", "mut")
    duplicate = queue.enqueue(db, "job", "mut")
    assert original["id"] == duplicate["id"]
    assert original["status"] == "queued"
    assert queue.claim_next(db)["status"] == "running"
    assert queue.claim_next(db) is None
    assert queue.recover_interrupted(db) == 1
    assert queue.claim_next(db)["id"] == original["id"]
    queue.finish(db, original["id"])
    assert queue.get(db, original["id"])["status"] == "completed"
    assert queue.enqueue(db, "job", "mut")["id"] == original["id"]
    assert queue.claim_next(db) is None


def test_0443_failed_queue_can_retry_without_duplicate(tmp_path):
    db = tmp_path / "library.sqlite3"
    _db(db)
    op = queue.enqueue(db, "job", "mut")
    queue.claim_next(db)
    queue.finish(db, op["id"], error="Kollision")
    assert queue.get(db, op["id"])["error_message"] == "Kollision"
    assert queue.enqueue(db, "job", "mut")["status"] == "queued"
    assert queue.claim_next(db)["id"] == op["id"]


def test_0443_queue_is_separated_by_library(tmp_path):
    one, two = tmp_path/"one.sqlite3", tmp_path/"two.sqlite3"
    _db(one)
    _db(two)
    assert queue.enqueue(one, "job", "mut")["status"] == "queued"
    assert queue.list_visible(two) == []
    assert queue.enqueue(two, "job", "mut")["status"] == "queued"
    assert queue.claim_next(one)["status"] == "running"
    assert queue.claim_next(two)["status"] == "running"


def _restore_fixture(tmp_path, monkeypatch, *, two_links=False):
    root = tmp_path / "work"
    src = root/"Nicht zugeordnet"/"A.jpg"
    dst = root/"2026"/"01 - Ereignis"/"A.jpg"
    src.parent.mkdir(parents=True)
    dst.parent.mkdir(parents=True)
    content = b"deterministic-camera-file" * 32
    src.write_bytes(content)
    if two_links:
        os.link(src, dst)
    monkeypatch.setattr(neutral, "shared_work_root", lambda _: root)
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files (id INTEGER,job_id TEXT,current_relative_path TEXT,current_root_kind TEXT)")
    conn.execute("INSERT INTO files VALUES (1,'job','Nicht zugeordnet/A.jpg','shared_workspace')")
    state = {
        "target_state_json": json.dumps({"_neutralized_files": [{
            "neutral_relative_path": "Nicht zugeordnet/A.jpg",
            "old_relative_path": "2026/01 - Ereignis/A.jpg",
            "file_id": 1, "size_bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }]}),
        "job_id": "job",
    }
    return root, src, dst, conn, state


def test_0443_restoration_is_idempotent_after_file_was_moved(tmp_path, monkeypatch):
    root, src, dst, conn, state = _restore_fixture(tmp_path, monkeypatch)
    assert neutral.restore_neutralized_files(conn, root, state) == 1
    assert not src.exists() and dst.is_file()
    assert neutral.restore_neutralized_files(conn, root, state) == 1
    assert not src.exists() and dst.is_file()


def test_0443_recovery_handles_crash_between_link_and_unlink(tmp_path, monkeypatch):
    root, src, dst, conn, state = _restore_fixture(tmp_path, monkeypatch, two_links=True)
    assert src.exists() and dst.exists()
    assert neutral.restore_neutralized_files(conn, root, state) == 1
    assert not src.exists() and dst.exists()


def test_0443_recovery_refuses_a_foreign_conflicting_file(tmp_path, monkeypatch):
    root, src, dst, conn, state = _restore_fixture(tmp_path, monkeypatch)
    dst.write_bytes(b"unrelated")
    with pytest.raises(ValueError, match="fremd belegt"):
        neutral.restore_neutralized_files(conn, root, state)
    assert src.exists() and dst.read_bytes() == b"unrelated"


def test_0443_backend_accepts_without_performing_inline_cancel(tmp_path, monkeypatch):
    db = tmp_path/"library.sqlite3"
    _db(db)
    monkeypatch.setattr(main, "current_database_file", lambda: db)
    result = main.api_cancel_event_mutation("job", "mut")
    assert result["status"] == "queued"
    assert queue.claim_next(db)["id"] == result["id"]
    assert queue.get(db, result["id"])["status"] == "running"


def test_0443_global_status_and_navigation_contract():
    html = apply_shell(EVENTS_HTML, active_area="workspace", subarea="events")
    assert 'id="bk-background-cancel-notice"' in html
    assert '"/api/background-activity?library="' in html
    assert 'window.__bkLibraryId' in BIBLIOTHEKAR_0443_JS
    assert ".bk-cancel-spinner" in BIBLIOTHEKAR_0443_CSS
    assert 'new Event("bk-cancellation-queued")' in EVENTS_HTML
    assert "mandatoryMutationContext=null;" in EVENTS_HTML
    assert 'Verwerfauftrag angenommen.' in EVENTS_HTML
    assert hasattr(main, "process_background_mutation_cancel")
