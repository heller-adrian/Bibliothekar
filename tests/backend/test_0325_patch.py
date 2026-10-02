from __future__ import annotations

import json
from pathlib import Path

from app import main, ui_shell
from app.archive_release_copy import create_archive_release_copies
from app.archive_release_stock import (
    describe_archive_release_stock,
    verify_archive_release_copies,
)
from app.database import get_event_edit_context
from app.event_change_apply import cancel_event_change, confirm_event_change
from app.event_inventory import scan_event_inventory
from app.events_ui import EVENTS_HTML
from app.obsolete_structure import cleanup_obsolete_structure
from tests.backend.test_0271_archive_assistant import _seed
from tests.backend.test_0271_archive_release_stock import _release_case


def test_0325_live_archive_metadata_overrides_stale_database_time(
    tmp_path: Path,
    monkeypatch,
):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path,
        full_archive_triplet=True,
    )

    def fake_analyze_tree(_root: Path):
        return {
            "files": [
                {
                    "relative_path": "Alle/alt.JPG",
                    "filename": "alt.JPG",
                    "media_type": "jpeg",
                    "selected_capture_time": "2026-07-22T19:25:23+02:00",
                    "selected_capture_source": "EXIF:ExifIFD:DateTimeOriginal",
                    "capture_time_confidence": "high",
                    "metadata_candidates": [],
                }
            ]
        }

    monkeypatch.setattr("app.event_inventory.analyze_tree", fake_analyze_tree)

    inventory = scan_event_inventory(
        db,
        archive,
        "old",
        "archive",
        root_kind="camera_archive",
        persist=True,
        update_known_file_locations=False,
    )
    camera = next(
        row for row in inventory["files"]
        if row.get("known_file_id") is not None
    )
    assert camera["family_id"] == old_family
    assert camera["selected_capture_time"] == "2026-07-22T19:25:23+02:00"
    assert camera["selected_capture_source"] == "EXIF:ExifIFD:DateTimeOriginal"

    context = get_event_edit_context(
        db,
        "old",
        "archive",
        workspace_path=workspace,
    )
    family = next(
        row for row in context["families"]
        if int(row["family_id"]) == old_family
    )
    assert family["assigned_here"] is True
    assert family["selected_capture_time"] == "2026-07-22T19:25:23+02:00"
    assert family["day_key"] == "2026-07-22"
    assert family["live_capture_conflict"] is False


def test_0325_release_copy_is_created_verified_and_removed_on_cancel(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    db = case["db"]
    archive = case["archive"]
    workspace = case["workspace"]
    cr_id = case["cr_id"]

    confirm_event_change(db, cr_id, archive, workspace)
    before = describe_archive_release_stock(db, cr_id)
    assert before["stage"] == "copy_to_ssd"

    copied = create_archive_release_copies(db, archive, workspace, cr_id)
    assert copied["complete"] is True
    assert copied["copied_file_count"] == 2

    created = describe_archive_release_stock(db, cr_id)
    assert created["stage"] == "verify_copy"
    assert created["copies_created"] is True
    for row in created["rows"]:
        target = case["central"] / row["workspace_release_path"]
        assert target.is_file()

    verified = verify_archive_release_copies(db, archive, workspace, cr_id)
    assert verified["complete"] is True
    assert describe_archive_release_stock(db, cr_id)["stage"] == "remove_archive"

    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["status"] == "abgebrochen"
    assert cancelled["reversal_required"] is False

    release_root = case["central"] / "Freigewordene Archivdateien"
    assert release_root.is_dir()
    assert not any(path.is_file() for path in release_root.rglob("*"))


def test_0325_cleanup_removes_empty_custom_folder_from_old_event_document(
    tmp_path: Path,
):
    root = tmp_path / "Arbeitsbereich"
    event_root = root / "2026" / "07-24 - Test"
    custom = event_root / "Test"
    custom.mkdir(parents=True)
    document = {
        "source": "kamera-automatisierung",
        "event": {
            "id": "E1",
            "preserve_day_folders": False,
        },
        "child_events": [],
        "folder_layout": {
            "structure_enabled": True,
            "input_path": "Test",
            "layout": {
                "version": 2,
                "nodes": [
                    {"id": "custom-test", "name": "Test", "children": []}
                ],
            },
        },
    }
    (event_root / "event.json").write_text(
        json.dumps(document),
        encoding="utf-8",
    )

    removed = cleanup_obsolete_structure(
        root,
        [],
        [],
        {"E1"},
        managed_event_roots=[event_root],
        desired_directories=[event_root],
    )

    assert not custom.exists()
    assert event_root.is_dir()
    assert str(custom) in removed


def test_0325_ui_and_version_contract():
    assert main.DEPLOYMENT_VERSION == "0.32.5"
    assert "0.32.5 · Kern 0.28.7" in ui_shell._shell_markup(
        "workspace",
        "events",
    )
    assert "SSD-Kopien anlegen" in EVENTS_HTML
    assert "/release-copy/create" in EVENTS_HTML
    assert "Schritt 1 von 2" in EVENTS_HTML
    assert "Schritt 2 von 2" in EVENTS_HTML
    assert "Schritt 1 von 3" not in EVENTS_HTML
    assert "Schritt 2 von 3" not in EVENTS_HTML
    assert "friendlyWorkspacePath" in EVENTS_HTML
    assert "structure-change-verify-feedback" in EVENTS_HTML
