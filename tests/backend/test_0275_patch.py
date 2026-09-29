"""0.27.5: Importintegration, Archiv-Nebenbestand und Statusregeln."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from app.database import (
    create_job,
    database_connection,
    get_event_edit_context,
    initialize_database,
    update_event_definition,
    update_import_file_paths,
)
from app.event_structure import build_event_preview
from app.main import folder_import_display_label
from app.planning import list_job_planning_overview, list_global_released_archive_groups
from app.released_archive_maintenance import normalize_released_archive_stock
from app.event_change_apply import (
    cancel_event_change,
    confirm_event_change,
    finish_event_change,
    verify_event_change,
)
from app.event_change_request import propose_event_change
from app.archive_reversal import prepare_archive_reversal
from app.archive_release_stock import (
    verify_archive_release_copies,
    verify_archive_release_removal,
)
from tests.backend.archive_change_helpers import copy_prepared_event_document
from tests.backend.test_0271_archive_assistant import _seed, _preview, NOW
from tests.backend.test_0271_archive_release_stock import _release_case, _copy_release_rows
from tests.backend.test_0250_continuous import (
    attach_files,
    create,
    payload,
    setup,
)

ROOT = Path(__file__).resolve().parents[2]


def test_0275_folder_import_persists_workspace_root_and_family_day(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    create_job(
        db,
        job_id="folder",
        kind="sd_import",
        trigger_type="manual",
        source_path="/source",
        working_path="/workspace/Arbeitsbereich",
        operation="folder_import",
        source_volume_label="SD_TEST_20260725",
    )
    sha = hashlib.sha256(b"camera").hexdigest()
    with database_connection(db) as connection:
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               ) VALUES ('folder','A','A','complete',NULL,'missing')"""
        ).lastrowid)
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES ('folder',?,'DCIM/A.JPG','DCIM/A.JPG','A.JPG','.JPG',
                         'jpeg',6,?,?,NULL,NULL,'missing','not_required',
                         'not_requested',?,?,'job_root')""",
            (family_id, sha, sha, NOW, NOW),
        )
        connection.commit()

    plan = [{
        "source_relative_path": "DCIM/A.JPG",
        "destination_relative_path": "2026/2026-07-25/20260725_101112_Fuji-X-E5.JPG",
        "selected_capture_time": "2026-07-25T10:11:12",
        "capture_time_confidence": "high",
    }]
    result = update_import_file_paths(
        db, "folder", plan, working_path="/workspace/Arbeitsbereich"
    )
    assert result["updated_family_count"] == 1

    with database_connection(db) as connection:
        file_row = connection.execute(
            "SELECT current_relative_path,current_root_kind,selected_capture_time "
            "FROM files WHERE job_id='folder'"
        ).fetchone()
        family_row = connection.execute(
            "SELECT selected_capture_time,capture_time_confidence "
            "FROM file_families WHERE id=?",
            (family_id,),
        ).fetchone()
    assert file_row["current_root_kind"] == "shared_workspace"
    assert file_row["current_relative_path"].startswith("2026/2026-07-25/")
    assert file_row["selected_capture_time"] == "2026-07-25T10:11:12"
    assert tuple(family_row) == ("2026-07-25T10:11:12", "high")

    overview = list_job_planning_overview(db, "folder")
    cards = overview["available_day_groups"]
    assert len(cards) == 1
    assert cards[0]["day_key"] == "2026-07-25"
    assert cards[0]["family_ids"] == [family_id]


def test_0275_human_import_labels_keep_technical_ids_separate():
    organization = {
        "capture_start_date": "2026-07-22",
        "capture_end_date": "2026-07-25",
        "devices": [{"name": "Fuji X-E5", "family_count": 20}],
    }
    sd = folder_import_display_label(
        {"trigger_type": "approved_sd", "source_volume_label": "TECH-001"},
        organization,
    )
    drive = folder_import_display_label(
        {"trigger_type": "usb_key", "source_volume_label": "PHOTO-DISK"},
        organization,
    )
    folder = folder_import_display_label(
        {"trigger_type": "manual", "source_volume_label": "SD_TEST_20260725"},
        organization,
    )
    assert sd == "Fuji X-E5 - 2026.07.22 - 2026.07.25"
    assert drive == "PHOTO-DISK - 2026.07.22 - 2026.07.25"
    assert folder == "SD_TEST_20260725"


def _finish_release_case(case: dict) -> None:
    confirm_event_change(case["db"], case["cr_id"], case["archive"], case["workspace"])
    rows = _copy_release_rows(case)
    assert verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    for row in rows:
        (case["archive"] / row["old_path"]).unlink()
    assert verify_archive_release_removal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    copy_prepared_event_document(
        case["db"], case["workspace"], case["archive"], case["cr_id"]
    )
    assert verify_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )["complete"]
    finish_event_change(case["db"], case["cr_id"], case["archive"], case["workspace"])


def test_0275_partial_reuse_renames_remaining_released_segment(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    _finish_release_case(case)

    result = normalize_released_archive_stock(
        case["db"],
        case["workspace"],
        [("2026-07-22T20:01:00", "2026-07-22T21:00:00")],
    )
    assert result["updated_family_count"] == 1
    assert result["moved_file_count"] == 2

    with database_connection(case["db"]) as connection:
        marker = connection.execute(
            """SELECT released_start_datetime,released_end_datetime
               FROM released_free_families
               WHERE family_id=?""",
            (case["late_family"],),
        ).fetchone()
        camera = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (case["late_file"],),
        ).fetchone()
        asset = connection.execute(
            "SELECT current_relative_path FROM released_archive_assets WHERE family_id=?",
            (case["late_family"],),
        ).fetchone()
    assert marker["released_start_datetime"] == "2026-07-22T21:00:01"
    assert marker["released_end_datetime"] == "2026-07-22T23:59:59"
    assert "2026-07-22 · 21-00–23-59" in camera["current_relative_path"]
    assert "2026-07-22 · 21-00–23-59" in asset["current_relative_path"]
    assert (case["work"] / camera["current_relative_path"]).is_file()
    assert (case["work"] / asset["current_relative_path"]).is_file()

    group = next(
        item for item in list_global_released_archive_groups(case["db"])
        if case["late_family"] in item["family_ids"]
    )
    assert group["start_time"] == "21:00"
    assert group["end_time"] == "23:59"


def test_0275_unknown_extra_can_be_removed_then_verified_and_reversal_has_backup(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    extra_rel = f"2026/{folder}/event 1.json"
    extra_payload = b'{"manual":"copy"}\n'
    extra_sha = hashlib.sha256(extra_payload).hexdigest()
    extra_path = archive / extra_rel
    extra_path.write_bytes(extra_payload)

    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, None),
        event_name="Test Archiv 2", notes="extra-file-test",
        archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    # Force the exact unresolved side-file scenario independently from metadata
    # heuristics. It existed when the change began and therefore must be backed up.
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO event_change_asset_reviews(
                   change_request_id,asset_kind,source_file_id,family_id,
                   old_path,new_path,action,expected_size_bytes,expected_sha256,
                   verification_status,created_at,updated_at
               ) VALUES (?,'other',NULL,NULL,?,'','unresolved',?,?,'pending',?,?)""",
            (cr_id, extra_rel, len(extra_payload), extra_sha, NOW, NOW),
        )
        connection.commit()

    confirm_event_change(db, cr_id, archive, workspace)
    first = verify_event_change(db, cr_id, archive, workspace)
    extra_review = next(
        row for row in first["files"]
        if row["old_path"] == extra_rel and row.get("action") == "unresolved"
    )
    assert extra_review["status"] == "needs_assignment"
    assert "Zusätzliche Datei ohne SOLL-Ziel" in extra_review["message"]
    assert extra_rel in extra_review["message"]

    extra_path.unlink()
    second = verify_event_change(db, cr_id, archive, workspace)
    extra_review = next(
        row for row in second["files"]
        if row["old_path"] == extra_rel and row.get("action") == "unresolved"
    )
    assert extra_review["status"] == "verified"
    assert "entfernt" in extra_review["message"]

    cancelled = cancel_event_change(db, cr_id, archive, workspace)
    assert cancelled["reversal_required"] is True
    prepared = prepare_archive_reversal(db, archive, workspace, cr_id)
    restore = next(
        operation for operation in prepared["operations"]
        if operation["kind"] == "restore_from_ssd"
    )
    assert "event 1.json" in restore["items"]


def test_0275_applied_edit_invalidates_prior_archive_verification(tmp_path: Path):
    db = tmp_path / "db"
    workspace = tmp_path / "workspace"
    setup(db, [
        "2026-07-23T10:00:00",
        "2026-07-23T14:00:00",
        "2026-07-23T18:00:00",
    ])
    event = create(db, payload("2026-07-23T00:00", "2026-07-23T23:59"))["parent_event"]
    attach_files(db, workspace, event["id"])
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO event_archive_verifications(
                   id,job_id,event_id,status,archive_root,file_count,
                   verified_file_count,total_size_bytes,verified_size_bytes,
                   missing_file_count,mismatched_file_count,details_json,
                   error_message,created_at,updated_at,completed_at
               ) VALUES ('verified-before','j',?,'verified','/archive',3,3,3,3,0,0,
                         '{}',NULL,'2026-09-28T12:00:00','2026-09-28T12:00:00',
                         '2026-09-28T12:00:00')""",
            (event["id"],),
        )
        connection.commit()

    preview = build_event_preview(
        payload("2026-07-23T13:00", "2026-07-23T15:00"),
        get_event_edit_context(db, "j", event["id"])["families"],
    )
    update_event_definition(
        db, "j", event["id"], preview,
        event_name="Urlaub", notes="", expected_revision=1,
        workspace_path=workspace,
    )

    with database_connection(db) as connection:
        rows = connection.execute(
            """SELECT id,status,error_message,details_json
               FROM event_archive_verifications
               WHERE event_id=? ORDER BY created_at,id""",
            (event["id"],),
        ).fetchall()
    assert len(rows) == 2
    assert rows[0]["status"] == "verified"
    assert rows[-1]["status"] == "failed"
    assert rows[-1]["error_message"] == "verification_invalidated_by_edit"
    assert '"reason": "structural_applied_edit"' in rows[-1]["details_json"]


def test_0275_ui_rules_for_archive_patch():
    transfer = (ROOT / "app" / "transfer_ui.py").read_text()
    events = (ROOT / "app" / "events_ui.py").read_text()
    assistant = (ROOT / "app" / "archive_change_assistant.py").read_text()

    assert "archive-verify-button" in transfer
    assert "background:var(--warning) !important" in transfer
    assert "Erneut prüfen" in transfer

    assert "#change-request-dialog details > summary::before" in events
    assert 'font-size:19px' in events
    assert events.count('#change-request-dialog details > summary::before') == 1
    assert "showReversalError(error.message)" in events
    assert 'id="reversal-inline-error"' in events or '"#reversal-inline-error"' in events

    assert "Die bestehende event.json im Archiv durch die vorbereitete neue" in assistant
    assert "keine zweite " in assistant
