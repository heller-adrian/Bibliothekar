"""Pre.7 regression contracts on a wholly isolated camera and archive fixture.

No test is permitted to write the real archive or TrueNAS mounts.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.database import database_connection, initialize_database
from app.event_document import build_event_document_from_db
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot
from app.event_structure_changes import (
    EventStructureChangeError, detect_event_structure_change,
)
from app.manual_archive_structure_undo import (
    set_archived_structure_review_mode, verify_archived_structure_undo,
)
from app.manual_event_undo import undo_manual_applied_change
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import seed_job, seed_event, seed_family
from tests.backend.test_pre61_manual_rename import setup_renamed_file, run_inventory
from app.external_changes import (
    acknowledge_external_notices, list_external_change_state,
)


def _physical_event(tmp_path, *, archived):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn, status="archived" if archived else "applied")
        _family, file_id = seed_family(
            conn, content=b"original-JPG",
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        if not archived:
            conn.execute(
                "UPDATE files SET current_root_kind='shared_workspace' WHERE id=?",
                (file_id,),
            )
        ensure_event_layout_snapshot(conn, "e")
    root = archive if archived else shared_work_root(workspace)
    event = root / "2026" / "07-23 - Trip"
    for name in ("Alle", "Sortiert", "Export"):
        (event / name).mkdir(parents=True, exist_ok=True)
    (event / "Alle" / "A.JPG").write_bytes(b"original-JPG")
    document = build_event_document_from_db(
        db, workspace, "j", "e", include_archived=archived,
    )
    assert document is not None
    (event / "event.json").write_text(json.dumps(document), encoding="utf-8")
    kind = "camera_archive" if archived else "shared_workspace"
    scan_event_inventory(db, root, "j", "e", root_kind=kind,
                         persist=True, update_known_file_locations=False,
                         fast_refresh=False)
    assert detect_event_structure_change(db, "e") is None
    renamed = event.with_name("07-23 - Manually Renamed")
    event.rename(renamed)
    scan_event_inventory(db, root, "j", "e", root_kind=kind,
                         persist=True, update_known_file_locations=False,
                         fast_refresh=False)
    task = detect_event_structure_change(db, "e")
    assert task is not None, "A real root rename must be detected"
    assert task["detected"].get("root_rename"), task["detected"]
    return db, workspace, archive, event, renamed, task["id"]


def test_pre7_dismiss_does_not_accept_filename_and_survives_repeated_scans(tmp_path, monkeypatch):
    db, ws, _central, root, _event, file_id, old, new, old_rel = (
        setup_renamed_file(tmp_path, monkeypatch)
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    notice = run_inventory(db, ws, archive)["required"][0]
    assert notice["kind"] == "filename_rename"
    acknowledge_external_notices(db, [notice["id"]])
    for _ in range(2):
        run_inventory(db, ws, archive)
        state = list_external_change_state(db)
        assert state["required_count"] == 1
        assert state["unseen_required_count"] == 0
        with database_connection(db) as conn:
            assert conn.execute(
                "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
            ).fetchone()[0] == old_rel
        assert not old.exists() and new.is_file()


def test_pre7_applied_undo_restores_root_and_blocks_occupied_target(tmp_path):
    db, workspace, _archive, original, renamed, change_id = _physical_event(
        tmp_path, archived=False,
    )
    original.mkdir()
    with pytest.raises(EventStructureChangeError):
        undo_manual_applied_change(db, workspace, change_id)
    assert renamed.is_dir() and original.is_dir()
    original.rmdir()
    result = undo_manual_applied_change(db, workspace, change_id)
    assert result["status"] == "restored"
    assert original.joinpath("Alle", "A.JPG").read_bytes() == b"original-JPG"
    assert not renamed.exists()


def test_pre7_archive_undo_is_manual_and_persisted(tmp_path):
    db, workspace, archive, original, renamed, change_id = _physical_event(
        tmp_path, archived=True,
    )
    root = shared_work_root(workspace)
    selected = set_archived_structure_review_mode(
        db, workspace, root, change_id, "undo",
    )
    assert selected["review_mode"] == "undo"
    assert renamed.is_dir() and not original.exists()
    with pytest.raises(EventStructureChangeError):
        verify_archived_structure_undo(db, archive, change_id)
    # Only the user changes the read-only archive. The app must observe it.
    renamed.rename(original)
    result = verify_archived_structure_undo(db, archive, change_id)
    assert result["status"] == "restored"
    assert original.joinpath("Alle", "A.JPG").read_bytes() == b"original-JPG"
    with database_connection(db) as conn:
        assert conn.execute(
            "SELECT status FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()[0] == "cancelled"


def test_pre7_archive_rejects_mode_switch_without_owned_staging(tmp_path):
    db, workspace, archive, original, renamed, change_id = _physical_event(
        tmp_path, archived=True,
    )
    root = shared_work_root(workspace)
    with pytest.raises(EventStructureChangeError):
        set_archived_structure_review_mode(
            db, workspace, root, change_id, "invalid",
        )
    assert renamed.is_dir() and not original.exists()
    with database_connection(db) as conn:
        assert conn.execute(
            "SELECT status FROM event_structure_changes WHERE id=?", (change_id,)
        ).fetchone()[0] == "pending"
