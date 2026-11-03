"""Pre.6.1: externally renamed camera files must be explicitly accepted or undone."""
from pathlib import Path
import pytest

from app.database import database_connection, list_global_tasks
from app.event_structure_changes import detect_all_event_structure_changes
from app.external_changes import (
    accept_external_filename_rename,
    list_external_change_state,
    repair_external_notice,
    ExternalChangeError,
)
from app.live_inventory import refresh_live_event_inventories
from app.workspace_layout import shared_work_root
from tests.backend.test_pre6_truenas_acceptance import seed_collection


def setup_renamed_file(tmp_path, monkeypatch):
    db, ws, central, event, _ = seed_collection(tmp_path, monkeypatch)
    work = shared_work_root(ws)
    with database_connection(db) as c:
        # seed_collection creates 8 applied files first, then 16 free ones.
        row = c.execute(
            "SELECT id,current_relative_path FROM files "
            "WHERE current_root_kind='shared_workspace' ORDER BY id LIMIT 1"
        ).fetchone()
        assert row, "Applied event must contain a known camera file"
        file_id = int(row["id"])
        old_rel = str(row["current_relative_path"])
    old = work / old_rel
    assert old.is_file()
    new = old.with_name("manual-" + old.name)
    old.rename(new)
    return db, ws, central, work, event, file_id, old, new, old_rel


def run_inventory(db, ws, archive):
    result = refresh_live_event_inventories(db, ws, archive)
    assert not result["errors"], result
    structures = detect_all_event_structure_changes(db, ws)
    assert not structures["errors"], structures
    return list_external_change_state(db)


def test_manual_rename_requires_explicit_accept_and_survives_scans(tmp_path, monkeypatch):
    db, ws, central, work, event, file_id, old, new, old_rel = (
        setup_renamed_file(tmp_path, monkeypatch)
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    state = run_inventory(db, ws, archive)
    for _ in range(2):
        assert state["required_count"] == 1, state
        notice = state["required"][0]
        assert notice["kind"] == "filename_rename"
        assert notice["repairable"] is True
        assert notice["details"]["expected_relative_path"] == old_rel
        assert notice["details"]["observed_relative_path"] != old_rel
        with database_connection(db) as c:
            assert c.execute(
                "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
            ).fetchone()[0] == old_rel
        assert new.is_file() and not old.exists()
        state = run_inventory(db, ws, archive)

    assert any(t["kind"] == "placement_conflicts" for t in list_global_tasks(db))
    result = accept_external_filename_rename(
        db, state["required"][0]["id"], library_work_root=work
    )
    assert result["status"] == "resolved"
    with database_connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
        ).fetchone()[0] == new.relative_to(work).as_posix()
        assert c.execute(
            "SELECT status FROM event_document_sync_tasks WHERE event_id=?",
            (event["id"],),
        ).fetchone()[0] == "pending"
    assert run_inventory(db, ws, archive)["required_count"] == 0
    assert new.is_file() and not old.exists()


def test_manual_rename_undo_is_sha_verified_without_overwrite(tmp_path, monkeypatch):
    db, ws, central, work, event, file_id, old, new, old_rel = (
        setup_renamed_file(tmp_path, monkeypatch)
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    notice = run_inventory(db, ws, archive)["required"][0]
    original_bytes = new.read_bytes()
    undone = repair_external_notice(
        db, notice["id"], central_root=central, library_work_root=work
    )
    assert undone["status"] == "repaired"
    assert old.read_bytes() == original_bytes and not new.exists()
    assert run_inventory(db, ws, archive)["required_count"] == 0


def test_accept_rejects_changed_bytes_and_preserves_task(tmp_path, monkeypatch):
    db, ws, central, work, event, file_id, old, new, old_rel = (
        setup_renamed_file(tmp_path, monkeypatch)
    )
    archive = tmp_path / "archive"
    archive.mkdir()
    notice = run_inventory(db, ws, archive)["required"][0]
    new.write_bytes(new.read_bytes() + b"tampered")
    with pytest.raises(ExternalChangeError):
        accept_external_filename_rename(
            db, notice["id"], library_work_root=work
        )
    assert list_external_change_state(db)["required_count"] == 1
    assert not old.exists()
    with database_connection(db) as c:
        assert c.execute(
            "SELECT current_relative_path FROM files WHERE id=?", (file_id,)
        ).fetchone()[0] == old_rel
