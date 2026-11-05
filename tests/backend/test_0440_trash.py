from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from app.central_stock_reconcile import reconcile_central_free_stock
from app.database import (
    create_job, database_connection, initialize_database, list_job_day_groups,
)
from app.planning import list_job_available_families
from app.storage_config import (
    StorageSettingsError, load_storage_settings, normalize_storage_settings,
    save_storage_settings, storage_paths,
)
from app.trash import (
    TRASH_CONFIRMATION, empty_trash_filesystem, purge_trash_database,
    reconcile_trash_inventory,
)
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-08T12:00:00+00:00"


def _fixture(tmp_path: Path, monkeypatch):
    config = tmp_path / "settings.json"
    config.write_text('{}')
    monkeypatch.setenv("KAMERA_CONFIG", str(config))
    db = tmp_path / "library.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    paths = ensure_workspace_layout(workspace)
    from app.library_registry import initialize_library_registry, register_library, ensure_library_identity
    registry = tmp_path / "registry.sqlite3"
    monkeypatch.setenv("KAMERA_REGISTRY_DATABASE", str(registry))
    initialize_library_registry(registry)
    ensure_library_identity(db, "main")
    work = Path(paths["workspaces_root"]) / "main"
    work.mkdir(exist_ok=True)
    archive = tmp_path / "archive"
    archive.mkdir()
    register_library(registry, library_id="main", display_name="Fixture",
                     database_path=db, workspace_root=workspace, work_root=work,
                     archive_root=archive, is_main=True)
    create_job(
        db, job_id="J", kind="sd_import",
        trigger_type="approved_sd", source_path="/source",
        working_path=str(workspace), operation="folder_import",
    )
    return db, workspace, paths


def _file(db: Path, relative: str, data: bytes) -> int:
    digest = hashlib.sha256(data).hexdigest()
    with database_connection(db) as c:
        family = c.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence)
               VALUES ('J',?,?,'complete','2026-10-08T10:00:00','high')""",
            ("family-"+relative, Path(relative).stem),
        )
        file = c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at)
               VALUES ('J',?,?,?,?,'.JPG','jpeg',?,?,?,
                       '2026-10-08T10:00:00','qa','high','not_required',
                       'not_requested','shared_workspace',?,?)""",
            (
                int(family.lastrowid), relative, relative, Path(relative).name,
                len(data), digest, digest, NOW, NOW,
            ),
        )
        return int(file.lastrowid)


def test_0440_default_four_managed_paths_and_rename(tmp_path: Path, monkeypatch):
    _db, workspace, paths = _fixture(tmp_path, monkeypatch)
    assert Path(paths["trash_root"]).is_dir()
    assert set(load_storage_settings()) == {
        "backup_directory_name", "workspaces_directory_name",
        "metadata_directory_name", "trash_directory_name",
    }
    moved = Path(paths["trash_root"]) / "Familie" / "A.JPG"
    moved.parent.mkdir()
    moved.write_bytes(b"manual-finder")
    inode=moved.stat().st_ino
    with pytest.raises(StorageSettingsError):
        save_storage_settings({"trash_directory_name": "Aussortiert"})
    ensure_workspace_layout(workspace)
    assert storage_paths(workspace)["trash_root"] == workspace / "Trash"
    assert moved.read_bytes() == b"manual-finder" and moved.stat().st_ino == inode
    assert not (workspace / "Aussortiert").exists()
    assert not (workspace / "Papierkorb").exists()
    assert TRASH_CONFIRMATION == "PAPIERKORB ENDGÜLTIG LEEREN"
    with pytest.raises(StorageSettingsError):
        normalize_storage_settings({"trash_directory_name": "Library Workspaces"})


def test_0440_finder_move_is_not_active_stock(tmp_path: Path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    central = Path(paths["backup_root"])
    relative = "2026/2026-10-08/A.JPG"
    data = b"finder-smb-image"
    file_id = _file(db, relative, data)
    source = central / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(data)

    assert list_job_available_families(db, "J")
    trash_path = Path(paths["trash_root"]) / "Auswahl" / "A.JPG"
    trash_path.parent.mkdir(parents=True)
    source.replace(trash_path)
    state = reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    assert state["ready"] is True
    assert state["trash_file_count"] == 1
    with database_connection(db) as c:
        current = c.execute(
            "SELECT current_root_kind,current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        assert tuple(current) == ("trash", "Auswahl/A.JPG")
    assert list_job_available_families(db, "J") == []
    assert list_job_day_groups(db, "J") == []
    again = reconcile_trash_inventory(db, workspace)
    assert again["file_count"] == 1
    assert again["adopted_file_count"] == 0
    assert again["tracked_file_count"] == 1


def test_0440_mixed_unknown_files_and_manual_empty(tmp_path: Path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    central = Path(paths["backup_root"])
    data = b"family-original"
    relative = "2026/2026-10-08/A.JPG"
    file_id = _file(db, relative, data)
    source = central / relative
    source.parent.mkdir(parents=True)
    source.write_bytes(data)
    root = Path(paths["trash_root"])
    (root / "Andere").mkdir()
    (root / "Andere" / "unknown.txt").write_text("untracked")
    (root / "A.JPG").write_bytes(data)
    source.unlink()
    state = reconcile_trash_inventory(db, workspace)
    assert state["file_count"] == 2
    assert state["tracked_file_count"] == 1
    assert state["untracked_file_count"] == 1
    assert state["directory_count"] == 1
    empty_trash_filesystem(workspace)
    assert list(root.iterdir()) == []
    deleted = purge_trash_database(db)
    assert deleted["deleted_file_rows"] == 1
    with database_connection(db) as c:
        assert c.execute("SELECT 1 FROM files WHERE id=?", (file_id,)).fetchone() is None
    assert reconcile_trash_inventory(db, workspace)["entry_count"] == 0


def test_0440_empty_does_not_follow_symlink(tmp_path: Path, monkeypatch):
    _db, workspace, paths = _fixture(tmp_path, monkeypatch)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("never delete")
    root = Path(paths["trash_root"])
    os.symlink(outside, root / "linked")
    state = reconcile_trash_inventory(_db, workspace)
    assert any(item["entry_type"] == "symlink" for item in state["entries"])
    empty_trash_filesystem(workspace)
    assert (outside / "keep.txt").read_text() == "never delete"
    assert not (root / "linked").is_symlink()


def test_0440_menu_and_page_contract():
    from app import main
    from app.ui_shell import _shell_markup
    from app.trash_ui import TRASH_HTML

    assert 'href="/trash"' in _shell_markup("trash", None)
    assert 'id="bk-storage-trash-name"' not in _shell_markup("trash", None)
    assert "/api/trash" in TRASH_HTML
    assert "/api/trash/empty" in TRASH_HTML
    assert "Gesamten Papierkorb leeren" in TRASH_HTML
    assert "active_area=\"trash\"" in Path(main.__file__).read_text()


def test_0440_root_symlink_is_rejected_before_deletion(tmp_path: Path, monkeypatch):
    from app.trash import TrashError, trash_root

    _db, workspace, paths = _fixture(tmp_path, monkeypatch)
    target = tmp_path / "protected"
    target.mkdir()
    (target / "keep.txt").write_text("protected")
    root = Path(paths["trash_root"])
    root.rmdir()
    root.symlink_to(target, target_is_directory=True)
    with pytest.raises(TrashError):
        trash_root(workspace)
    with pytest.raises(TrashError):
        empty_trash_filesystem(workspace)
    assert (target / "keep.txt").read_text() == "protected"


def test_0440_compatibility_workspace_uses_physical_root(tmp_path: Path, monkeypatch):
    from app import main,trash as trash_module
    from app.library_context import resolve_library_context

    _db, workspace, paths = _fixture(tmp_path, monkeypatch)
    context=resolve_library_context(Path(os.environ['KAMERA_REGISTRY_DATABASE']),'main')
    compat=main.compatibility_workspace_root(context)
    assert trash_module.trash_root(compat) == Path(paths["trash_root"])
    assert not (compat / "Papierkorb").exists()


def test_0440_sqlite_migration_preserves_references(tmp_path: Path, monkeypatch):
    db, _workspace, _paths = _fixture(tmp_path, monkeypatch)
    with database_connection(db) as connection:
        schema = str(connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='files'"
        ).fetchone()[0])
        assert "'trash'" in schema
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        versions = {
            int(row[0])
            for row in connection.execute("SELECT version FROM schema_versions")
        }
        assert 48 in versions
