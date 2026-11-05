from __future__ import annotations

from app.archive_staging import staging_directory_name
from app.workspace_layout import shared_work_root

from pathlib import Path

import pytest

from app.database import database_connection
from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
from app.event_change_request import get_event_change_files, propose_event_change
from app.event_inventory import scan_event_inventory
from app.archive_staging import required_event_document_for_request
from tests.backend.archive_change_helpers import copy_prepared_event_document
from tests.backend.test_0271_archive_assistant import _preview, _seed
from tests.backend.test_0283_structure_simplification import (
    _archived_layout_preview,
    _seed_archived_layout_event,
)


def test_0284_successful_archive_change_removes_helper_tree_with_finder_metadata(tmp_path: Path):
    db, workspace, archive, folder, old_family, _new_family, _incoming = _seed(
        tmp_path, full_archive_triplet=True
    )
    proposed = propose_event_change(
        db,
        "old",
        "archive",
        _preview(folder, old_family, None),
        event_name="Test Archiv 2",
        notes="Metadatenänderung",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)

    helper_root = (
        shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace)) / "2026" / folder
    )
    assert (helper_root / "event.json").is_file()

    # Finder/SMB may create metadata simply because the helper tree was opened.
    (helper_root / ".DS_Store").write_bytes(b"finder")
    (helper_root / "._event.json").write_bytes(b"appledouble")
    (helper_root.parent / ".DS_Store").write_bytes(b"finder-year")

    copy_prepared_event_document(db, workspace, archive, cr_id)
    finished = finish_event_change(db, cr_id, archive, workspace)
    assert finished["status"] == "archiviert"
    assert finished["ssd_cleanup_warnings"] == []

    assert not helper_root.exists()
    assert not helper_root.parent.exists()
    assert (shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace))).is_dir()


@pytest.mark.parametrize(
    ("camera_name", "export_name"),
    [
        ("A Kopie.JPG", "A.jpg"),
        ("A copy 2.JPG", "A.jpg"),
        ("A (1).JPG", "A.jpg"),
        ("A 1.JPG", "A.jpg"),
        ("A.JPG", "A Kopie.jpg"),
        ("A.JPG", "A (1).jpg"),
        ("A.JPG", "A 1.jpg"),
    ],
)
def test_0284_archive_verification_accepts_os_collision_names(
    tmp_path: Path, camera_name: str, export_name: str
):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    event_root, family_id, state = _seed_archived_layout_event(
        db, workspace, archive, structure_enabled=True
    )

    proposed = propose_event_change(
        db,
        "j",
        "e",
        _archived_layout_preview(family_id, state, False),
        event_name="Trip",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)

    # Simulate the filename choices made by Finder/Windows when both JPEGs
    # land in the flat event folder in either copy order.
    (event_root / "Export" / "A.jpg").replace(event_root / export_name)
    (event_root / "Alle" / "A.JPG").replace(event_root / camera_name)
    (event_root / "Alle" / "A.xmp").replace(event_root / "A.xmp")
    (event_root / "Alle").rmdir()
    (event_root / "Sortiert").rmdir()
    (event_root / "Export").rmdir()

    spec = required_event_document_for_request(db, cr_id)
    assert spec is not None
    staged_document = (
        shared_work_root(workspace) / staging_directory_name(shared_work_root(workspace)) / spec["target_relative_path"]
    )
    (archive / spec["target_relative_path"]).write_bytes(staged_document.read_bytes())

    verified = verify_event_change(db, cr_id, archive, workspace)
    camera_review = next(
        row for row in verified["files"] if row.get("file_id") is not None
    )
    export_review = next(
        row for row in verified["files"] if row.get("asset_kind") == "export"
    )
    assert camera_review["new_path"].endswith("/" + camera_name)
    assert export_review["new_path"].endswith("/" + export_name)

    if camera_name != "A.JPG":
        # The camera file is listed in portable event.json. If Finder/Windows
        # renamed that file, Bibliothekar prepares a corrected helper document
        # instead of silently leaving a stale archive manifest.
        assert verified["complete"] is False
        assert verified["event_document"]["status"] in {
            "size_mismatch", "sha256_mismatch"
        }
        (archive / spec["target_relative_path"]).write_bytes(
            staged_document.read_bytes()
        )
        verified = verify_event_change(db, cr_id, archive, workspace)

    assert verified["complete"] is True
    finished = finish_event_change(db, cr_id, archive, workspace)
    assert finished["status"] == "archiviert"

    with database_connection(db) as connection:
        camera_path = connection.execute(
            "SELECT current_relative_path FROM files WHERE family_id=?",
            (family_id,),
        ).fetchone()["current_relative_path"]
    assert camera_path.endswith("/" + camera_name)

    inventory = scan_event_inventory(
        db,
        archive,
        "j",
        "e",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )
    export_row = next(
        row for row in inventory["files"] if row["filename"] == export_name
    )
    assert export_row["asset_kind"] == "export"
    assert export_row["family_id"] == family_id
