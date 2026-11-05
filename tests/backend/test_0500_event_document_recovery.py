"""BA-01: durable SQLite/event.json recovery boundary tests.

Every byte and SQLite row is generated inside tmp_path. No NAS data involved.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.database import (
    database_connection,
    get_event_edit_context,
    list_global_tasks,
    update_event_definition,
)
from app.event_document import (
    build_event_document_from_db,
    read_event_document,
    write_event_document,
)
from app.event_document_sync import (
    recover_event_document_sync_tasks,
    sync_event_document_task,
)
from tests.backend.test_0250_continuous import setup, create, payload, attach_files


def _applied_event(tmp_path):
    db = tmp_path / "camera.sqlite3"
    workspace = tmp_path / "workspace"
    setup(db, ["2026-07-23T10:00:00"])
    event = create(db, payload("2026-07-23T00:00", "2026-07-23T23:59"))["parent_event"]
    attach_files(db, workspace, event["id"])
    document = build_event_document_from_db(db, workspace, "j", event["id"])
    assert document is not None
    path = write_event_document(workspace, document, app_version="0.50.0")
    return db, workspace, event, path


def _rename(db, workspace, event, name="Neuer Anzeigename"):
    return update_event_definition(
        db, "j", event["id"], None, event_name=name, notes="Nachweis",
        expected_revision=int(event["revision"]),
        workspace_path=workspace, app_version="0.50.0",
    )


def test_0500_event_json_failure_is_durable_and_retryable(tmp_path, monkeypatch):
    db, workspace, event, path = _applied_event(tmp_path)
    old_bytes = path.read_bytes()
    import app.event_document_sync as sync_module

    def fail_document(*_args, **_kwargs):
        raise OSError("synthetic disk write failure")

    with monkeypatch.context() as faults:
        faults.setattr(sync_module, "write_event_document", fail_document)
        result = _rename(db, workspace, event)

    assert result["event"]["revision"] == 2
    assert result["event_document_sync_pending"] is True
    assert "synthetic disk" in result["event_document_sync_error"]
    assert path.read_bytes() == old_bytes

    with database_connection(db) as connection:
        task = connection.execute(
            "SELECT revision,status,attempts FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()
        assert tuple(task) == (2, "blocked", 1)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert any(t["kind"] == "event_document_sync" for t in list_global_tasks(db))

    repaired = recover_event_document_sync_tasks(db, workspace, app_version="0.50.0")
    assert repaired == {"recovered": 1, "blocked": 0}
    updated_document = read_event_document(path)
    assert updated_document["event"]["revision"] == 2
    assert updated_document["event"]["name"] == "Neuer Anzeigename"
    assert updated_document["event"]["notes"] == "Nachweis"
    assert updated_document["source_app_version"] == "0.50.0"
    assert not any(t["kind"] == "event_document_sync" for t in list_global_tasks(db))
    assert recover_event_document_sync_tasks(db, workspace) == {"recovered": 0, "blocked": 0}


def test_0500_crash_after_sqlite_commit_before_document_replacement(tmp_path):
    db, workspace, event, path = _applied_event(tmp_path)
    previous = path.read_bytes()
    child = """
import os, sys
from pathlib import Path
from app.database import update_event_definition
import app.event_document_sync as sync_module
sync_module.write_event_document = lambda *_a, **_k: os._exit(42)
update_event_definition(
    Path(sys.argv[1]), "j", sys.argv[3], None,
    event_name="Nach Prozessabbruch", notes="persistent",
    expected_revision=1, workspace_path=Path(sys.argv[2]),
    app_version="0.50.0",
)
"""
    process = subprocess.run(
        [sys.executable, "-c", child, str(db), str(workspace), event["id"]],
        capture_output=True, text=True, check=False,
    )
    assert process.returncode == 42, process.stderr
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT revision FROM events WHERE id=?", (event["id"],)
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT revision,status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[:] == (2, "pending")
    assert path.read_bytes() == previous

    assert recover_event_document_sync_tasks(db, workspace)["recovered"] == 1
    document = read_event_document(path)
    assert document["event"]["revision"] == 2
    assert document["event"]["name"] == "Nach Prozessabbruch"
    assert recover_event_document_sync_tasks(db, workspace) == {"recovered": 0, "blocked": 0}


def test_0500_missing_applied_directory_stays_blocked_without_ghost_folder(
    tmp_path,
):
    db, workspace, event, path = _applied_event(tmp_path)
    missing_directory = path.parent
    parked_directory = tmp_path / "parked"
    missing_directory.rename(parked_directory)

    result = _rename(db, workspace, event)
    assert result["event_document_sync_pending"] is True
    assert not missing_directory.exists()
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[0] == "blocked"

    parked_directory.rename(missing_directory)
    assert recover_event_document_sync_tasks(db, workspace)["recovered"] == 1
    assert read_event_document(path)["event"]["revision"] == 2


def test_0500_successful_metadata_edit_finalizes_outbox(tmp_path):
    db, workspace, event, path = _applied_event(tmp_path)
    result = _rename(db, workspace, event)
    assert result["event"]["revision"] == 2
    assert result["event_document_sync_pending"] is False
    assert read_event_document(path)["event"]["revision"] == 2
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT status,revision FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[:] == ("completed", 2)
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_0500_crash_after_document_replace_before_sqlite_ack(tmp_path):
    db, workspace, event, path = _applied_event(tmp_path)
    child = """
import os, sys
from pathlib import Path
from app.database import update_event_definition
import app.event_document_sync as module
original = module.write_event_document
def replace_then_crash(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(42)
module.write_event_document = replace_then_crash
update_event_definition(
    Path(sys.argv[1]), "j", sys.argv[3], None,
    event_name="Vor Quittierung", notes="replace erfolgt",
    expected_revision=1, workspace_path=Path(sys.argv[2]),
    app_version="0.50.0",
)
"""
    process = subprocess.run(
        [sys.executable, "-c", child, str(db), str(workspace), event["id"]],
        capture_output=True, text=True, check=False,
    )
    assert process.returncode == 42, process.stderr
    assert read_event_document(path)["event"]["revision"] == 2
    with database_connection(db) as connection:
        # The document was fsync'ed but the SQLite completion transaction
        # was never committed. Recovery must tolerate and finish that state.
        assert connection.execute(
            "SELECT revision,status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[:] == (2, "pending")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert recover_event_document_sync_tasks(db, workspace)["recovered"] == 1
    assert read_event_document(path)["event"]["revision"] == 2
    assert recover_event_document_sync_tasks(db, workspace) == {
        "recovered": 0, "blocked": 0,
    }


def test_0500_later_edit_supersedes_pending_revision(tmp_path, monkeypatch):
    db, workspace, event, path = _applied_event(tmp_path)
    import app.event_document_sync as module

    with monkeypatch.context() as faults:
        faults.setattr(module, "write_event_document", lambda *_a, **_kw: (
            (_ for _ in ()).throw(OSError("first write failed"))
        ))
        first = _rename(db, workspace, event, name="Zwischenstand")
    assert first["event_document_sync_pending"] is True

    next_edit = dict(first["event"])
    second = _rename(db, workspace, next_edit, name="Endstand")
    assert second["event"]["revision"] == 3
    assert second["event_document_sync_pending"] is False
    assert read_event_document(path)["event"]["name"] == "Endstand"
    assert read_event_document(path)["event"]["revision"] == 3
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT revision,status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[:] == (3, "completed")
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("existing_content", [
    '{"source":"external","event":{"id":"stranger"}}',
    '{"broken":',
])
def test_0500_foreign_or_corrupt_document_is_preserved(
    tmp_path, existing_content,
):
    db, workspace, event, path = _applied_event(tmp_path)
    path.write_text(existing_content, encoding="utf-8")
    result = _rename(db, workspace, event)
    assert result["event"]["revision"] == 2
    assert result["event_document_sync_pending"] is True
    assert path.read_text(encoding="utf-8") == existing_content
    assert recover_event_document_sync_tasks(db, workspace)["blocked"] == 1
    assert path.read_text(encoding="utf-8") == existing_content
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[0] == "blocked"
