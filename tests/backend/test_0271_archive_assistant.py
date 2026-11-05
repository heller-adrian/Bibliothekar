"""0.27.1: variabler Archiv-Assistent und echte IST→SOLL-Hilfsstruktur."""
from __future__ import annotations

from tests.backend.legacy_storage_fixture import provision_legacy_storage

import hashlib
import shutil
from pathlib import Path

from tests.backend.archive_change_helpers import copy_prepared_event_document
from app.archive_change_assistant import build_archive_change_assistant
from app.database import database_connection, initialize_database
from app.event_change_apply import confirm_event_change, finish_event_change, verify_event_change
from app.event_change_request import get_event_change_files, propose_event_change


NOW = "2026-09-28T13:00:00+00:00"


def _seed(tmp_path: Path, *, full_archive_triplet: bool = False):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    work = workspace / "Arbeitsbereich"
    work.mkdir(parents=True)
    archive.mkdir()
    initialize_database(db)
    provision_legacy_storage(workspace)

    folder = "07-22 - Test Archiv 2"
    old_rel = f"2026/{folder}/Alle/alt.JPG"
    incoming_rel = "2026/2026-07-24/neu.JPG"
    old_payload = b"alt"
    new_payload = b"neu"
    old_sha = hashlib.sha256(old_payload).hexdigest()
    new_sha = hashlib.sha256(new_payload).hexdigest()

    with database_connection(db) as c:
        for job in ("old", "new"):
            c.execute(
                """INSERT INTO jobs(
                       id,kind,trigger_type,state,stage,operation,source_volume_label,
                       created_at,updated_at
                   ) VALUES (?, 'sd_import','manual','completed','done','folder_import',?,?,?)""",
                (job, job, NOW, NOW),
            )
        old_family = int(c.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES ('old','ALT','ALT','complete','2026-07-22T12:00:00','high')"""
        ).lastrowid)
        new_family = int(c.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES ('new','NEU','NEU','complete','2026-07-24T10:00:00','high')"""
        ).lastrowid)
        c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES ('old',?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required',
                         'not_requested',?,?,'camera_archive')""",
            (old_family, old_rel, old_rel, "alt.JPG", len(old_payload), old_sha, old_sha,
             "2026-07-22T12:00:00", "DateTimeOriginal", NOW, NOW),
        )
        c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES ('new',?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required',
                         'not_requested',?,?,'shared_workspace')""",
            (new_family, incoming_rel, incoming_rel, "neu.JPG", len(new_payload), new_sha, new_sha,
             "2026-07-24T10:00:00", "DateTimeOriginal", NOW, NOW),
        )
        c.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision,applied_at,archived_at,timeline_model,time_model_version
               ) VALUES ('archive','old',NULL,'parent','Test Archiv 2',
                         '2026-07-22T00:00:00','2026-07-22T23:59:59',0,?,'archived',
                         ?,?,'event',0,1,?,?, 'continuous',2)""",
            (folder, NOW, NOW, NOW, NOW),
        )
        c.execute(
            """INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at)
               VALUES ('archive',?,NULL,'date_range',?)""",
            (old_family, NOW),
        )
        c.commit()

    old_path = archive / old_rel
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_bytes(old_payload)
    if full_archive_triplet:
        (archive / "2026" / folder / "Sortiert").mkdir()
        (archive / "2026" / folder / "Export").mkdir()

    incoming = work / incoming_rel
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_bytes(new_payload)
    return db, workspace, archive, folder, old_family, new_family, incoming_rel


def _preview(folder: str, old_family: int, new_family: int | None):
    ids = [old_family] + ([new_family] if new_family is not None else [])
    return {
        "event_kind": "event",
        "event_name": "Test Archiv 2",
        "parent_folder": folder,
        "child_folder": "",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "start_date": "2026-07-22",
        "end_date": "2026-07-24" if new_family is not None else "2026-07-22",
        "start_time": "00:00",
        "end_time": "23:59",
        "selected_day_keys": [],
        "selected_family_ids": ids,
    }


def test_0271_existing_triplet_stages_only_branch_with_new_files(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    helper = workspace / "Arbeitsbereich" / "Später zuordnen" / "2026" / folder
    assert proposed["preparation_required"] is True
    assert not helper.exists()

    before = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert before["phase"] == "prepare"
    assert before["preparation"]["missing_directories"] == []

    confirm_event_change(db, cr_id, archive, workspace)
    assert (helper / "Alle" / "neu.JPG").is_file()
    assert not (helper / "Sortiert").exists()
    assert not (helper / "Export").exists()

    after = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert after["phase"] == "finder"
    assert [item["kind"] for item in after["operations"]] == ["copy_files", "replace_event_document"]
    assert after["operations"][0]["items"] == ["neu.JPG"]
    assert after["operations"][0]["target"].endswith("/Alle")
    assert after["operations"][1]["items"] == ["event.json"]


def test_0271_metadata_only_change_prepares_new_event_document(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(tmp_path)
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, None),
        event_name="Test Archiv 2", notes="nur Notiz",
        archive_root=archive, workspace_path=workspace,
    )
    assert proposed["preparation_required"] is True
    assert proposed["status"] == "aenderbar_vorschlagen"
    assistant = build_archive_change_assistant(db, archive, workspace, proposed["change_request_id"])
    assert assistant["phase"] == "prepare"
    confirm_event_change(db, proposed["change_request_id"], archive, workspace)
    prepared = build_archive_change_assistant(db, archive, workspace, proposed["change_request_id"])
    assert prepared["phase"] == "finder"
    assert [item["kind"] for item in prepared["operations"]] == ["replace_event_document"]
    assert (workspace / "Arbeitsbereich" / "Später zuordnen" / "2026" / folder / "event.json").is_file()

def test_0271_finish_keeps_source_day_when_other_file_remains(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, incoming_rel = _seed(
        tmp_path, full_archive_triplet=True
    )
    work = workspace / "Arbeitsbereich"
    sibling = work / "2026" / "2026-07-24" / "bleibt.JPG"
    sibling.write_bytes(b"bleibt")

    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    rows = get_event_change_files(db, cr_id)
    for row in rows:
        if row["source_root_kind"] != "shared_workspace":
            continue
        staged = work / row["workspace_staging_path"]
        target = archive / row["new_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(staged.read_bytes())

    copy_prepared_event_document(db, workspace, archive, cr_id)
    assert verify_event_change(db, cr_id, archive)["complete"] is True
    finish_event_change(db, cr_id, archive, workspace)

    assert not (work / incoming_rel).exists()
    assert sibling.is_file()
    assert sibling.parent.is_dir()


def test_0271_verify_requires_touched_empty_branch_directories(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(tmp_path)
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, new_family),
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)
    work = workspace / "Arbeitsbereich"
    rows = get_event_change_files(db, cr_id)
    incoming = next(row for row in rows if row["source_root_kind"] == "shared_workspace")
    staged = work / incoming["workspace_staging_path"]
    target = archive / incoming["new_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(staged.read_bytes())

    first = verify_event_change(db, cr_id, archive)
    assert first["complete"] is False
    assert first["missing_directory_count"] == 2
    assert {item["path"] for item in first["directories"] if item["status"] == "missing"} == {
        f"2026/{folder}/Sortiert",
        f"2026/{folder}/Export",
    }

    (archive / "2026" / folder / "Sortiert").mkdir()
    (archive / "2026" / folder / "Export").mkdir()
    second = verify_event_change(db, cr_id, archive)
    assert second["complete"] is True
    assert second["missing_directory_count"] == 0


def test_0271_new_child_is_one_folder_copy_action(tmp_path: Path):
    db, workspace, archive, folder, old_family, new_family, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    preview = _preview(folder, old_family, new_family)
    preview["uses_time_range"] = True
    preview["subevents"] = [{
        "name": "Teil B",
        "start_datetime": "2026-07-24T00:00:00",
        "end_datetime": "2026-07-24T23:59:59",
    }]
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2", archive_root=archive, workspace_path=workspace,
    )
    assistant = build_archive_change_assistant(
        db, archive, workspace, proposed["change_request_id"]
    )
    assert assistant["phase"] == "prepare"
    operations = assistant["operations"]
    assert len(operations) == 1
    assert operations[0]["kind"] == "copy_helper_folders"
    assert set(operations[0]["items"]) == {
        "07-24 00-00 - 07-24 23-59 - Teil B",
        "event.json",
    }
    assert operations[0]["target"] == f"Kamerabibliothek/2026/{folder}"
    assert set(operations[0]["sources"]) == {
        f"Arbeitsbereich/Später zuordnen/2026/{folder}/07-24 00-00 - 07-24 23-59 - Teil B",
        f"Arbeitsbereich/Später zuordnen/2026/{folder}/event.json",
    }


def test_0271_verify_requires_obsolete_old_event_folder_to_be_removed(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    new_folder = "07-22 - Test Archiv 2 umbenannt"
    preview = _preview(folder, old_family, None)
    preview["parent_folder"] = new_folder
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2 umbenannt",
        archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    assistant = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert [item["kind"] for item in assistant["operations"]] == [
        "copy_helper_folders", "move_archive_files", "remove_directories"
    ]
    assert assistant["obsolete_directories"] == [f"2026/{folder}"]

    old_file = archive / "2026" / folder / "Alle" / "alt.JPG"
    new_file = archive / "2026" / new_folder / "Alle" / "alt.JPG"
    new_file.parent.mkdir(parents=True, exist_ok=True)
    old_file.replace(new_file)
    (archive / "2026" / new_folder / "Sortiert").mkdir()
    (archive / "2026" / new_folder / "Export").mkdir()

    confirm_event_change(db, cr_id, archive, workspace)
    first = verify_event_change(db, cr_id, archive)
    assert first["complete"] is False
    assert first["remaining_obsolete_directory_count"] == 1
    assert first["obsolete_directories"][0]["path"] == f"2026/{folder}"

    shutil.rmtree(archive / "2026" / folder)
    second = verify_event_change(db, cr_id, archive)
    assert second["complete"] is True
    assert second["remaining_obsolete_directory_count"] == 0


def test_0326_assistant_hides_obsolete_directory_that_is_already_gone(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    new_folder = "07-22 - Test Archiv 2 umbenannt"
    preview = _preview(folder, old_family, None)
    preview["parent_folder"] = new_folder
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2 umbenannt",
        archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]

    shutil.rmtree(archive / "2026" / folder)
    assistant = build_archive_change_assistant(
        db, archive, workspace, cr_id, scan_live=True
    )

    assert assistant["obsolete_directories"] == [f"2026/{folder}"]
    assert "remove_directories" not in [
        item["kind"] for item in assistant["operations"]
    ]


def test_0326_assistant_uses_explicit_library_path_labels(tmp_path: Path):
    db, workspace, archive, folder, old_family, _, _ = _seed(tmp_path)
    proposed = propose_event_change(
        db, "old", "archive", _preview(folder, old_family, None),
        event_name="Test Archiv 2", notes="nur Notiz",
        archive_root=archive, workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]
    confirm_event_change(db, cr_id, archive, workspace)

    assistant = build_archive_change_assistant(
        db,
        archive,
        workspace,
        cr_id,
        archive_display_root="Testarchiv",
        work_display_root="Testarbeitsbereich",
        backup_display_root="SD-Kartensicherungen",
    )

    assert assistant["path_labels"] == {
        "archive_root": "Testarchiv",
        "work_root": "Testarbeitsbereich",
        "backup_root": "SD-Kartensicherungen",
        "staging_root": "Testarbeitsbereich/Später zuordnen",
    }
    operation = next(
        item for item in assistant["operations"]
        if item["kind"] == "replace_event_document"
    )
    assert operation["source"].startswith("Testarbeitsbereich/Später zuordnen/")
    assert operation["target"].startswith("Testarchiv/")
