"""0.53.0: Papierkorb-Wiederherstellung ausschließlich mit isolierten QA-Dateien."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from app.database import database_connection, initialize_database, create_job
from app.trash import TrashError, reconcile_trash_inventory
from app.trash_restore import restore_trash_files
from tests.backend.test_0440_trash import _fixture, _file


def _put(db: Path, workspace: Path, paths: dict, name: str, content: bytes):
    relative = f"2026/2026-10-08/{name}"
    file_id = _file(db, relative, content)
    trash = Path(paths["trash_root"]) / "Gesichtet"
    trash.mkdir(exist_ok=True)
    (trash / name).write_bytes(content)
    assert reconcile_trash_inventory(db, workspace)["tracked_file_count"] >= 1
    return file_id, trash / name, Path(paths["backup_root"]) / relative


def test_0530_restore_selected_preserves_unselected(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    a, trash_a, target_a = _put(db, workspace, paths, "A.JPG", b"one")
    b, trash_b, target_b = _put(db, workspace, paths, "B.JPG", b"two")
    result = restore_trash_files(
        [db], workspace, relative_paths=["Gesichtet/A.JPG"]
    )
    assert result["restored_file_count"] == 1
    assert target_a.read_bytes() == b"one"
    assert not trash_a.exists()
    assert trash_b.read_bytes() == b"two"
    assert not target_b.exists()
    with database_connection(db) as c:
        assert tuple(c.execute(
            "SELECT current_root_kind,current_relative_path FROM files WHERE id=?",
            (a,),
        ).fetchone()) == ("shared_workspace", "2026/2026-10-08/A.JPG")
        assert c.execute("SELECT current_root_kind FROM files WHERE id=?", (b,)).fetchone()[0] == "trash"


def test_0530_restore_all_to_day_stock(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    _put(db, workspace, paths, "A.JPG", b"one")
    _put(db, workspace, paths, "B.JPG", b"two")
    result = restore_trash_files([db], workspace)
    assert result["restored_file_count"] == 2
    assert reconcile_trash_inventory(db, workspace)["file_count"] == 0
    assert (Path(paths["backup_root"]) / "2026/2026-10-08/B.JPG").read_bytes() == b"two"


def test_0530_unknown_blocks_bulk_without_moving_known(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    _, trash_a, target = _put(db, workspace, paths, "A.JPG", b"one")
    (Path(paths["trash_root"]) / "unknown.txt").write_text("not catalogued")
    with pytest.raises(TrashError, match="Nicht katalogisierte"):
        restore_trash_files([db], workspace)
    assert trash_a.exists()
    assert not target.exists()


def test_0530_rejects_collision_before_move(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    _, trash_a, target = _put(db, workspace, paths, "A.JPG", b"one")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"occupied")
    with pytest.raises(TrashError, match="existiert bereits"):
        restore_trash_files([db], workspace)
    assert trash_a.read_bytes() == b"one"
    assert target.read_bytes() == b"occupied"


def test_0530_corruption_is_not_restored(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    _, trash_a, target = _put(db, workspace, paths, "A.JPG", b"one")
    trash_a.write_bytes(b"two")
    with pytest.raises(TrashError, match="Prüfsumme"):
        restore_trash_files([db], workspace, relative_paths=["Gesichtet/A.JPG"])
    assert trash_a.exists() and not target.exists()


def test_0530_rejects_symlink_and_path_traversal(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    outside = tmp_path / "private"
    outside.write_bytes(b"safe")
    os.symlink(outside, Path(paths["trash_root"]) / "link")
    with pytest.raises(TrashError):
        restore_trash_files([db], workspace, relative_paths=["../private"])
    with pytest.raises(TrashError):
        restore_trash_files([db], workspace, relative_paths=["link"])
    assert outside.read_bytes() == b"safe"


def test_0530_cross_library_rows_follow_the_same_file(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    other = tmp_path / "other.sqlite3"
    initialize_database(other)
    create_job(
        other, job_id="J", kind="sd_import",
        trigger_type="approved_sd", source_path="/source",
        working_path=str(workspace), operation="folder_import",
    )
    _put(db, workspace, paths, "A.JPG", b"one")
    _file(other, "2026/2026-10-08/A.JPG", b"one")
    result = restore_trash_files([db, other], workspace)
    assert result["restored_file_count"] == 1
    for database in (db, other):
        with database_connection(database) as c:
            assert tuple(c.execute(
                "SELECT current_root_kind,current_relative_path FROM files"
            ).fetchone()) == ("shared_workspace", "2026/2026-10-08/A.JPG")


def test_0530_second_move_failure_reverts_first(tmp_path, monkeypatch):
    import app.trash_restore as module
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    _put(db, workspace, paths, "A.JPG", b"one")
    _put(db, workspace, paths, "B.JPG", b"two")
    original = module._move_checked
    calls = 0

    def broken(src, target, digest):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated failure")
        return original(src, target, digest)

    monkeypatch.setattr(module, "_move_checked", broken)
    with pytest.raises(TrashError, match="fehlgeschlagen"):
        restore_trash_files([db], workspace)
    assert (Path(paths["trash_root"]) / "Gesichtet/A.JPG").read_bytes() == b"one"
    assert not (Path(paths["backup_root"]) / "2026/2026-10-08/A.JPG").exists()
    with database_connection(db) as c:
        assert c.execute(
            "SELECT COUNT(*) FROM files WHERE current_root_kind='trash'"
        ).fetchone()[0] == 2


def test_0530_ui_and_endpoint_contract():
    from app import main
    from app.trash_ui import TRASH_HTML
    routes = {route.path for route in main.app.routes}
    assert "/api/trash/restore" in routes
    assert 'id="trash-restore-button"' in TRASH_HTML
    assert 'id="trash-select-button"' in TRASH_HTML
    assert 'id="trash-select-all-button"' in TRASH_HTML
    assert "Alle wiederherstellen" in TRASH_HTML
    assert "Auswahl wiederherstellen" in TRASH_HTML
    assert '"relative_paths"' not in TRASH_HTML or "relative_paths:" in TRASH_HTML
