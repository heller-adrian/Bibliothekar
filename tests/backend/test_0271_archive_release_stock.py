"""0.27.1: freigewordene Archivaufnahmen sicher auf SSD zurückholen."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from app.archive_change_assistant import build_archive_change_assistant
from app.archive_release_stock import (
    describe_archive_release_stock,
    verify_archive_release_copies,
    verify_archive_release_removal,
)
from app.database import database_connection
from app.event_change_apply import (
    EventChangeApplyError,
    cancel_event_change,
    confirm_event_change,
    finish_event_change,
    verify_event_change,
)
from app.event_change_request import get_event_change_files, propose_event_change
from app.planning import list_global_released_archive_groups
from app.sort_plan import build_event_sort_plan
from tests.backend.test_0271_archive_assistant import _seed, NOW


def _release_case(tmp_path: Path, *, with_asset: bool = False):
    db, workspace, archive, folder, keep_family, _, _ = _seed(
        tmp_path, full_archive_triplet=True
    )
    work = workspace / "Arbeitsbereich"
    backup_root = workspace / "SD-Kartensicherungen" / "old"
    backup_root.mkdir(parents=True, exist_ok=True)

    late_payload = b"late-camera"
    late_sha = hashlib.sha256(late_payload).hexdigest()
    late_rel = f"2026/{folder}/Alle/late.JPG"

    with database_connection(db) as c:
        c.execute(
            "UPDATE jobs SET working_path=? WHERE id='old'",
            (str(backup_root),),
        )
        late_family = int(c.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES ('old','LATE','LATE','complete',
                         '2026-07-22T21:30:00','high')"""
        ).lastrowid)
        late_file = int(c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES ('old',?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required',
                         'not_requested',?,?,'camera_archive')""",
            (
                late_family, late_rel, late_rel, "late.JPG",
                len(late_payload), late_sha, late_sha,
                "2026-07-22T21:30:00", "DateTimeOriginal", NOW, NOW,
            ),
        ).lastrowid)
        c.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('archive',?,NULL,'date_range',?)""",
            (late_family, NOW),
        )
        c.commit()

    late_path = archive / late_rel
    late_path.parent.mkdir(parents=True, exist_ok=True)
    late_path.write_bytes(late_payload)

    preview = {
        "event_kind": "event",
        "event_name": "Test Archiv 2",
        "parent_folder": folder,
        "child_folder": "",
        "uses_time_range": True,
        "preserve_day_folders": False,
        "start_date": "2026-07-22",
        "end_date": "2026-07-22",
        "start_time": "00:00",
        "end_time": "20:00",
        "selected_day_keys": [],
        "selected_family_ids": [keep_family],
        "subevents": [],
    }
    proposed = propose_event_change(
        db, "old", "archive", preview,
        event_name="Test Archiv 2",
        archive_root=archive,
        workspace_path=workspace,
    )
    cr_id = proposed["change_request_id"]

    asset_info = None
    if with_asset:
        asset_payload = b"released-export"
        asset_sha = hashlib.sha256(asset_payload).hexdigest()
        asset_rel = f"2026/{folder}/Export/late-export.JPG"
        (archive / asset_rel).write_bytes(asset_payload)
        with database_connection(db) as c:
            c.execute(
                """INSERT INTO event_change_asset_reviews(
                       change_request_id,asset_kind,source_file_id,family_id,
                       old_path,new_path,action,expected_size_bytes,expected_sha256,
                       verification_status,created_at,updated_at
                   ) VALUES (?,?,?,?,?,'','unresolved',?,?,'pending',?,?)""",
                (
                    cr_id, "export", late_file, late_family, asset_rel,
                    len(asset_payload), asset_sha, NOW, NOW,
                ),
            )
        asset_info = {
            "path": asset_rel,
            "payload": asset_payload,
            "sha": asset_sha,
        }

    return {
        "db": db,
        "workspace": workspace,
        "archive": archive,
        "work": work,
        "folder": folder,
        "keep_family": keep_family,
        "late_family": late_family,
        "late_file": late_file,
        "late_path": late_rel,
        "late_payload": late_payload,
        "late_sha": late_sha,
        "cr_id": cr_id,
        "asset": asset_info,
    }


def _copy_release_rows(case):
    rows = [
        row for row in get_event_change_files(case["db"], case["cr_id"])
        if str(row.get("workspace_release_path") or "")
    ]
    for row in rows:
        source = case["archive"] / row["old_path"]
        target = case["work"] / row["workspace_release_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return rows


def test_0271_release_stock_copy_remove_finish_and_reappear_globally(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    db, workspace, archive, work, cr_id = (
        case["db"], case["workspace"], case["archive"], case["work"], case["cr_id"]
    )

    before = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert before["phase"] == "prepare"
    assert before["release_stock"]["required"] is True
    assert before["release_stock"]["stage"] == "copy_to_ssd"

    confirm_event_change(db, cr_id, archive, workspace)
    rows = _copy_release_rows(case)
    assert len(rows) == 2
    assert all(
        str(row["workspace_release_path"]).startswith(
            "Freigewordene Archivdateien/2026/2026-07-22 · 20-01–23-59/"
        )
        for row in rows
    )

    copied = verify_archive_release_copies(db, archive, workspace, cr_id)
    assert copied["complete"] is True
    assert copied["verified_file_count"] == 2
    assert all((archive / row["old_path"]).is_file() for row in rows)

    middle = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert middle["release_stock"]["stage"] == "remove_archive"

    for row in rows:
        (archive / row["old_path"]).unlink()

    removed = verify_archive_release_removal(db, archive, workspace, cr_id)
    assert removed["complete"] is True

    after = build_archive_change_assistant(db, archive, workspace, cr_id)
    assert after["release_stock"]["stage"] == "complete"

    verification = verify_event_change(db, cr_id, archive, workspace)
    assert verification["complete"] is True
    result = finish_event_change(db, cr_id, archive, workspace)
    assert case["late_family"] in result["released_family_ids"]

    with database_connection(db) as c:
        file_row = c.execute(
            "SELECT current_root_kind,current_relative_path FROM files WHERE id=?",
            (case["late_file"],),
        ).fetchone()
        assert file_row["current_root_kind"] == "shared_workspace"
        assert str(file_row["current_relative_path"]).startswith(
            "Freigewordene Archivdateien/"
        )
        assert c.execute(
            """SELECT COUNT(*) FROM event_assignments
               WHERE family_id=?""",
            (case["late_family"],),
        ).fetchone()[0] == 0
        marker = c.execute(
            """SELECT released_start_datetime,released_end_datetime
               FROM released_free_families
               WHERE job_id='old' AND family_id=?""",
            (case["late_family"],),
        ).fetchone()
        assert marker is not None
        assert marker["released_start_datetime"] == "2026-07-22T20:01:00"
        assert marker["released_end_datetime"] == "2026-07-22T23:59:59"
        asset = c.execute(
            """SELECT current_relative_path,asset_kind,sha256
               FROM released_archive_assets
               WHERE job_id='old' AND family_id=?""",
            (case["late_family"],),
        ).fetchone()
        assert asset is not None
        assert asset["asset_kind"] == "export"
        assert str(asset["current_relative_path"]).startswith(
            "Freigewordene Archivdateien/"
        )

    assert (work / file_row["current_relative_path"]).is_file()
    assert (work / asset["current_relative_path"]).is_file()

    groups = list_global_released_archive_groups(db)
    group = next(
        item for item in groups
        if case["late_family"] in item["family_ids"]
    )
    assert group["job_id"] == "old"
    assert group["start_time"] == "20:01"
    assert group["end_time"] == "23:59"
    assert group["file_count"] == 2


def test_0271_release_copy_requires_correct_sha_before_archive_removal(tmp_path: Path):
    case = _release_case(tmp_path)
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    row = next(
        row for row in get_event_change_files(case["db"], case["cr_id"])
        if row["action"] == "delete"
    )
    target = case["work"] / row["workspace_release_path"]
    target.write_bytes(b"wrong")

    bad = verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert bad["complete"] is False
    assert bad["files"][0]["status"] in {
        "release_size_mismatch", "release_sha256_mismatch"
    }
    assert (case["archive"] / row["old_path"]).is_file()

    target.write_bytes(case["late_payload"])
    good = verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )
    assert good["complete"] is True


def test_0271_cancel_cleans_release_copy_only_while_archive_original_is_intact(tmp_path: Path):
    case = _release_case(tmp_path)
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    rows = _copy_release_rows(case)
    release_path = case["work"] / rows[0]["workspace_release_path"]
    assert release_path.is_file()

    cancelled = cancel_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    assert cancelled["status"] == "abgebrochen"
    assert not release_path.exists()
    assert (case["archive"] / rows[0]["old_path"]).is_file()

    case2 = _release_case(tmp_path / "second")
    confirm_event_change(
        case2["db"], case2["cr_id"], case2["archive"], case2["workspace"]
    )
    rows2 = _copy_release_rows(case2)
    (case2["archive"] / rows2[0]["old_path"]).unlink()
    with pytest.raises(EventChangeApplyError, match="ursprünglichen|Archiv"):
        cancel_event_change(
            case2["db"], case2["cr_id"], case2["archive"], case2["workspace"]
        )
    assert (case2["work"] / rows2[0]["workspace_release_path"]).is_file()


def test_0271_released_stock_can_be_sorted_again_with_released_asset(tmp_path: Path):
    case = _release_case(tmp_path, with_asset=True)
    confirm_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )
    rows = _copy_release_rows(case)
    assert verify_archive_release_copies(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    for row in rows:
        (case["archive"] / row["old_path"]).unlink()
    assert verify_archive_release_removal(
        case["db"], case["archive"], case["workspace"], case["cr_id"]
    )["complete"]
    assert verify_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )["complete"]
    finish_event_change(
        case["db"], case["cr_id"], case["archive"], case["workspace"]
    )

    with database_connection(case["db"]) as c:
        c.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision,timeline_model,time_model_version
               ) VALUES ('later','old',NULL,'parent','Später',
                         '2026-07-22T20:01:00','2026-07-22T23:59:59',1,
                         '07-22 - Später','planned',?,?,'event',0,1,'continuous',2)""",
            (NOW, NOW),
        )
        c.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('later',?,NULL,'date_time_range',?)""",
            (case["late_family"], NOW),
        )

    plan = build_event_sort_plan(
        case["db"], "old", "later", case["workspace"], verify_sha256=True
    )
    assert plan["summary"]["ready"], plan["blockers"]
    camera = next(
        item for item in plan["files"]
        if item["family_id"] == case["late_family"]
    )
    assert camera["current_root_kind"] == "shared_workspace"
    assert camera["source_relative_path"].startswith(
        "Freigewordene Archivdateien/"
    )
    asset = next(
        item for item in plan["assets"]
        if item["family_id"] == case["late_family"]
    )
    assert asset["source_root_kind"] == "shared_workspace"
    assert asset["released_archive_asset_id"] is not None
    assert "/Export/" in "/" + asset["destination_relative_path"]
