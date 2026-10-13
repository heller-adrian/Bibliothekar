"""0.53.1 regression tests: trash provenance, selection, rendering contracts."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

from app.database import database_connection, get_job
from app.trash import TrashError
from app.trash_import import stage_trash_import
from app.trash_selective import delete_selected_trash_files, recover_trash_deletions
from tests.backend.test_0440_trash import _fixture, _file


def test_0531_unknown_trash_stages_without_deleting_original(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    root = Path(paths["trash_root"])
    (root / "2026-01-05").mkdir()
    original = root / "2026-01-05" / "IMG_001.JPG"
    original.write_bytes(b"foreign photo")
    item = stage_trash_import(db, workspace, ["2026-01-05/IMG_001.JPG"])
    assert item["queued_file_count"] == 1
    assert original.read_bytes() == b"foreign photo"
    job = get_job(db, item["job_id"])
    assert job["operation"] == "trash_import"
    assert Path(job["source_path"],"2026-01-05/IMG_001.JPG").read_bytes() == b"foreign photo"


def test_0531_unknown_duplicate_pending_is_rejected(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    (Path(paths["trash_root"]) / "A.JPG").write_bytes(b"picture")
    stage_trash_import(db, workspace, ["A.JPG"])
    with pytest.raises(TrashError, match="bereits"):
        stage_trash_import(db, workspace, ["A.JPG"])


def test_0531_selected_delete_leaves_other_entries(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    root=Path(paths["trash_root"])
    (root / "A.JPG").write_bytes(b"remove")
    (root / "B.JPG").write_bytes(b"keep")
    (root / ".DS_Store").write_bytes(b"system")
    result=delete_selected_trash_files([db],workspace,["A.JPG",".DS_Store"])
    assert result["deleted_file_count"]==2
    assert not (root/"A.JPG").exists()
    assert not (root/".DS_Store").exists()
    assert (root/"B.JPG").read_bytes()==b"keep"
    assert recover_trash_deletions(workspace)["recovered_paths"]==[]


def test_0531_selection_blocks_outside_path(tmp_path, monkeypatch):
    db, workspace, paths = _fixture(tmp_path, monkeypatch)
    (Path(paths["trash_root"])/"A.JPG").write_bytes(b"keep")
    with pytest.raises(TrashError):
        delete_selected_trash_files([db],workspace,["../A.JPG"])
    assert (Path(paths["trash_root"])/"A.JPG").read_bytes()==b"keep"


def test_0531_preview_ui_and_tasks_contract():
    from app.workspace_ui import WORKSPACE_HTML
    from app.trash_ui import TRASH_HTML
    from app.events_ui import EVENTS_HTML
    from app import main
    from app.database import list_global_tasks
    assert "Saved target structure" not in WORKSPACE_HTML
    assert "Physical actual inventory" in WORKSPACE_HTML
    assert "Physical directory layout differs" in WORKSPACE_HTML
    assert "archive_pending" in list_global_tasks.__code__.co_consts.__repr__()
    assert "/api/trash/empty-selection" in {r.path for r in main.app.routes}
    assert "/api/event-structure-changes/{change_id}/undo" in {r.path for r in main.app.routes}
    assert "Gesamten Papierkorb leeren" in TRASH_HTML
    assert "Auswahl leeren" in TRASH_HTML
    assert "Änderungen rückgängig machen" in EVENTS_HTML
