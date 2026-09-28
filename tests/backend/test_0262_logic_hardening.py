from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.archive_locations import ArchiveLocationError, archive_path_without_symlinks
from app.archive_transfer import (
    ArchiveVerificationError,
    list_archive_candidates,
    verify_event_archive,
)
from app.database import database_connection, initialize_database
from app.event_change_apply import (
    EventChangeApplyError,
    cancel_event_change,
    confirm_event_change,
    finish_event_change,
    verify_event_change,
)
from app.event_change_request import get_event_change_files, propose_event_change
from app.event_reassignment import _create_new_no_event, assign_event_reassignments
from app.event_suggestions import accept_event_suggestion, list_event_suggestions
from app.main import _applied_edit_is_metadata_only
from app.sort_apply import recover_interrupted_sort_runs
from app.ssd_release import SsdReleaseError, release_event_ssd


NOW = "2026-09-23T12:00:00+00:00"


def seed_job(connection, job_id: str) -> None:
    connection.execute(
        """INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at)
           VALUES (?,'sd_import','manual','completed','done',?,?)""",
        (job_id, NOW, NOW),
    )


def seed_event(
    connection,
    *,
    event_id: str,
    job_id: str,
    status: str,
    start: str = "2026-07-23T00:00:00",
    end: str = "2026-07-23T23:59:59",
    folder: str = "07-23 - Event",
    name: str = "Event",
    preserve: bool = False,
    resort_required: int = 0,
) -> None:
    connection.execute(
        """INSERT INTO events(
               id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
               uses_time_range,folder_name,status,created_at,updated_at,event_kind,
               preserve_day_folders,revision,applied_at,archived_at,resort_required,
               time_model_version,timeline_model
           ) VALUES (?,?,NULL,'parent',?,?,?,0,?,?,?,?, 'event',?,1,?,?,?,2,'continuous')""",
        (
            event_id,
            job_id,
            name,
            start,
            end,
            folder,
            status,
            NOW,
            NOW,
            int(preserve),
            NOW if status in {"applied", "archived"} else None,
            NOW if status == "archived" else None,
            int(resort_required),
        ),
    )


def seed_family_file(
    connection,
    *,
    job_id: str,
    family_key: str,
    capture: str,
    current_path: str,
    content: bytes,
) -> tuple[int, int]:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (?,?,?,'complete',?,'high')""",
            (job_id, family_key, family_key, capture),
        ).lastrowid
    )
    digest = hashlib.sha256(content).hexdigest()
    filename = Path(current_path).name
    file_id = int(
        connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?, 'DateTimeOriginal',
                         'high','not_required','not_requested',?,?,'shared_workspace')""",
            (
                job_id,
                family_id,
                "DCIM/" + filename,
                current_path,
                filename,
                len(content),
                digest,
                digest,
                capture,
                NOW,
                NOW,
            ),
        ).lastrowid
    )
    return family_id, file_id


def assign(connection, event_id: str, family_id: int) -> None:
    connection.execute(
        """INSERT INTO event_assignments(
               event_id,family_id,file_id,assignment_source,created_at
           ) VALUES (?,?,NULL,'manual',?)""",
        (event_id, family_id, NOW),
    )


def seed_archived_change_fixture(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    archive.mkdir()
    data = b"archive-change-data"
    old_rel = "2026/07-23 - Old/Alle/a.JPG"
    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(
            connection,
            event_id="e",
            job_id="j",
            status="archived",
            folder="07-23 - Old",
            name="Old",
        )
        family_id, file_id = seed_family_file(
            connection,
            job_id="j",
            family_key="F",
            capture="2026-07-23T12:00:00",
            current_path=old_rel,
            content=data,
        )
        assign(connection, "e", family_id)
    old_path = archive / old_rel
    old_path.parent.mkdir(parents=True)
    old_path.write_bytes(data)
    preview = {
        "event_kind": "event",
        "event_name": "New",
        "parent_folder": "07-23 - New",
        "start_date": "2026-07-23",
        "end_date": "2026-07-23",
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "selected_family_ids": [family_id],
        "selected_day_keys": ["2026-07-23"],
    }
    request = propose_event_change(
        db,
        "j",
        "e",
        preview,
        event_name="New",
        archive_root=archive,
    )
    return db, archive, data, family_id, file_id, request["change_request_id"]


def test_0262_symlink_archive_path_never_releases_ssd_source(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    archive.mkdir()
    data = b"camera"
    rel = "2026/07-23 - Event/Alle/a.JPG"
    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(connection, event_id="e", job_id="j", status="applied")
        family_id, _ = seed_family_file(
            connection,
            job_id="j",
            family_key="F",
            capture="2026-07-23T12:00:00",
            current_path=rel,
            content=data,
        )
        assign(connection, "e", family_id)

    source = workspace / "Arbeitsbereich" / rel
    source.parent.mkdir(parents=True)
    source.write_bytes(data)

    real = archive / "real" / "a.JPG"
    real.parent.mkdir(parents=True)
    real.write_bytes(data)
    linked = archive / rel
    linked.parent.mkdir(parents=True)
    linked.symlink_to(real)

    with pytest.raises(ArchiveLocationError, match="Symlinks"):
        archive_path_without_symlinks(archive, rel)

    with pytest.raises(ArchiveVerificationError, match="Symlinks"):
        verify_event_archive(db, archive, "j", "e")

    with pytest.raises(SsdReleaseError, match="Symlinks"):
        release_event_ssd(db, workspace, archive, "j", "e")

    assert source.read_bytes() == data


def test_0262_finished_archive_change_updates_general_file_path(tmp_path):
    db, archive, _data, _family_id, file_id, cr_id = seed_archived_change_fixture(tmp_path)
    reviews = get_event_change_files(db, cr_id)
    assert len(reviews) == 1
    review = reviews[0]

    old_path = archive / review["old_path"]
    new_path = archive / review["new_path"]
    new_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.rename(new_path)
    event_root = new_path.parents[1]
    (event_root / "Sortiert").mkdir(exist_ok=True)
    (event_root / "Export").mkdir(exist_ok=True)
    old_path.parent.rmdir()
    old_path.parent.parent.rmdir()

    with database_connection(db) as connection:
        connection.execute(
            "UPDATE event_change_file_reviews SET confirmed=1 WHERE change_request_id=?",
            (cr_id,),
        )
    confirm_event_change(db, cr_id)
    result = finish_event_change(db, cr_id, archive)
    assert result["status"] == "archiviert"

    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert tuple(row) == (review["new_path"], "camera_archive")


def test_0262_confirmed_archive_change_cannot_disappear_after_manual_work(tmp_path):
    db, archive, data, _family_id, _file_id, cr_id = seed_archived_change_fixture(tmp_path)
    review = get_event_change_files(db, cr_id)[0]
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE event_change_file_reviews SET confirmed=1 WHERE change_request_id=?",
            (cr_id,),
        )
    confirm_event_change(db, cr_id)

    # A manual copy/move has begun: target exists. The work item must remain.
    target = archive / review["new_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    with pytest.raises(EventChangeApplyError, match="manuelle Änderungen"):
        cancel_event_change(db, cr_id, archive)

    target.unlink()
    result = cancel_event_change(db, cr_id, archive)
    assert result["status"] == "abgebrochen"


def test_0262_missing_legacy_sha_never_counts_as_verified(tmp_path):
    db, archive, data, _family_id, _file_id, cr_id = seed_archived_change_fixture(tmp_path)
    review = get_event_change_files(db, cr_id)[0]
    target = archive / review["new_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE event_change_file_reviews SET expected_sha256='' WHERE id=?",
            (review["id"],),
        )
    result = verify_event_change(db, cr_id, archive)
    assert result["complete"] is False
    assert result["files"][0]["status"] == "missing_sha256"


def test_0262_real_ui_metadata_payload_stays_metadata_only():
    context = {
        "event": {
            "status": "applied",
            "applied_at": NOW,
            "event_kind": "event",
            "preserve_day_folders": 0,
            "start_datetime": "2026-07-23T00:00:00",
            "end_datetime": "2026-07-23T23:59:59",
            "uses_time_range": 0,
            "time_model_version": 2,
        },
        "child_events": [],
        "time_segments": [],
    }
    payload = {
        "event_kind": "event",
        "event_name": "Nur neuer Name",
        "notes": "Nur neue Notiz",
        "start_date": "2026-07-23",
        "end_date": "2026-07-23",
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": True,
        "preserve_day_folders": False,
        "subevents": [],
    }
    assert _applied_edit_is_metadata_only(context, payload) is True


def test_0262_later_import_gets_reachable_cross_job_normal_target(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    data = b"later"
    with database_connection(db) as connection:
        seed_job(connection, "old")
        seed_job(connection, "new")
        seed_event(
            connection,
            event_id="target",
            job_id="old",
            status="applied",
            start="2026-07-23T10:00:00",
            end="2026-07-23T12:00:59",
            folder="07-23 - Target",
            name="Target",
        )
        family_id, _ = seed_family_file(
            connection,
            job_id="new",
            family_key="LATE",
            capture="2026-07-23T11:00:00",
            current_path="2026/free/LATE.JPG",
            content=data,
        )

    suggestions = list_event_suggestions(db, "new")
    assert len(suggestions) == 1
    assert suggestions[0]["target_event_id"] == "target"
    assert suggestions[0]["family_ids"] == [family_id]

    accepted = accept_event_suggestion(db, "new", [family_id], "target")
    with database_connection(db) as connection:
        followup = connection.execute(
            "SELECT job_id,linked_event_id,linkage_kind,status FROM events WHERE id=?",
            (accepted["event_id"],),
        ).fetchone()
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()
    assert tuple(followup) == ("new", "target", "applied_followup", "planned")
    assert assignment["event_id"] == accepted["event_id"]


def seed_interrupted_run(tmp_path: Path, *, ambiguous: bool = False):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source_root.mkdir()
    target_root.mkdir()
    data = b"move-me"
    sha = hashlib.sha256(data).hexdigest()
    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(connection, event_id="e", job_id="j", status="planned")
        family_id, file_id = seed_family_file(
            connection,
            job_id="j",
            family_key="F",
            capture="2026-07-23T12:00:00",
            current_path="old/a.JPG",
            content=data,
        )
        assign(connection, "e", family_id)
        connection.execute(
            """INSERT INTO sort_runs(
                   id,job_id,event_id,plan_token,status,phase,source_root,target_root,
                   file_count,verified_file_count,move_count,moved_file_count,
                   directory_count,created_directory_count,total_size_bytes,
                   verified_bytes,moved_bytes,error_message,details_json,
                   created_at,started_at,updated_at,completed_at,run_kind
               ) VALUES (
                   'run','j','e','token','interrupted','crash',?,?,1,1,1,1,
                   0,0,?, ?, ?,NULL,'{}',?,?,?,NULL,'initial'
               )""",
            (
                str(source_root),
                str(target_root),
                len(data),
                len(data),
                len(data),
                NOW,
                NOW,
                NOW,
            ),
        )
        connection.execute(
            """INSERT INTO sort_operations(
                   sort_run_id,sequence_number,file_id,source_relative_path,
                   destination_relative_path,expected_size_bytes,expected_sha256,status
               ) VALUES ('run',1,?,'old/a.JPG','new/a.JPG',?,?,'destination_verified')""",
            (file_id, len(data), sha),
        )

    destination = target_root / "new" / "a.JPG"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(data)
    source = source_root / "old" / "a.JPG"
    if ambiguous:
        source.parent.mkdir(parents=True)
        source.write_bytes(b"different")
    return db, source, destination, data


def test_0262_interrupted_sort_run_rolls_back_from_persisted_journal(tmp_path):
    db, source, destination, data = seed_interrupted_run(tmp_path)
    result = recover_interrupted_sort_runs(db)
    assert result == {"recovered": 1, "blocked": 0}
    assert source.read_bytes() == data
    assert not destination.exists()
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT status FROM sort_runs WHERE id='run'"
        ).fetchone()[0] == "rolled_back"
        assert connection.execute(
            "SELECT status FROM sort_operations WHERE sort_run_id='run'"
        ).fetchone()[0] == "rolled_back"


def test_0262_ambiguous_interrupted_sort_run_remains_safely_blocked(tmp_path):
    db, source, destination, _data = seed_interrupted_run(tmp_path, ambiguous=True)
    result = recover_interrupted_sort_runs(db)
    assert result == {"recovered": 0, "blocked": 1}
    assert source.exists()
    assert destination.exists()
    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT status,phase FROM sort_runs WHERE id='run'"
        ).fetchone()
    assert row["status"] == "interrupted"
    assert "nicht eindeutig" in row["phase"]


def test_0262_resort_required_blocks_archive_verification_and_ready_state(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    archive = tmp_path / "archive"
    archive.mkdir()
    with database_connection(db) as connection:
        seed_job(connection, "j")
        seed_event(
            connection,
            event_id="e",
            job_id="j",
            status="applied",
            resort_required=1,
        )

    summary = list_archive_candidates(db, archive)
    candidate = next(item for item in summary["candidates"] if item["event_id"] == "e")
    assert candidate["ssd_release_ready"] is False
    assert "Nachsortierung" in candidate["ssd_release_block_reason"]

    with pytest.raises(ArchiveVerificationError, match="Nachsortierung"):
        verify_event_archive(db, archive, "j", "e")


def test_0262_legacy_new_no_event_keeps_explicit_day_folder_choice(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "j")
        family_id, _ = seed_family_file(
            connection,
            job_id="j",
            family_key="F",
            capture="2026-07-23T12:00:00",
            current_path="2026/free/F.JPG",
            content=b"x",
        )
    result = _create_new_no_event(
        db,
        "j",
        [family_id],
        preserve_day_folders=True,
    )
    assert result["preserve_day_folders"] is True
    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT preserve_day_folders,event_kind FROM events WHERE id=?",
            (result["event_id"],),
        ).fetchone()
    assert tuple(row) == (1, "no_event")


def queue_family_for_reassignment(connection, *, job_id: str, source_event_id: str, family_id: int) -> None:
    connection.execute(
        """INSERT INTO event_reapply_removed_families(
               event_id,job_id,family_id,created_at
           ) VALUES (?,?,?,?)""",
        (source_event_id, job_id, family_id, NOW),
    )


def test_0262_reassignment_to_cross_job_normal_event_creates_local_followup(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "old")
        seed_job(connection, "new")
        seed_event(
            connection,
            event_id="target",
            job_id="old",
            status="planned",
            start="2026-07-23T10:00:00",
            end="2026-07-23T12:00:59",
            folder="07-23 - Target",
            name="Target",
            preserve=True,
        )
        seed_event(
            connection,
            event_id="source",
            job_id="new",
            status="planned",
            start="2026-07-23T00:00:00",
            end="2026-07-23T23:59:59",
            folder="07-23 - Source",
            name="Source",
        )
        family_id, _ = seed_family_file(
            connection,
            job_id="new",
            family_key="LATE",
            capture="2026-07-23T11:00:00",
            current_path="2026/free/LATE.JPG",
            content=b"x",
        )
        queue_family_for_reassignment(
            connection,
            job_id="new",
            source_event_id="source",
            family_id=family_id,
        )

    result = assign_event_reassignments(
        db,
        "new",
        "source",
        [family_id],
        target_mode="existing_event",
        target_event_id="target",
    )
    followup_id = result["target"]["event_id"]
    assert followup_id != "target"
    with database_connection(db) as connection:
        event = connection.execute(
            """SELECT job_id,linked_event_id,linkage_kind,status,preserve_day_folders
               FROM events WHERE id=?""",
            (followup_id,),
        ).fetchone()
        assignment = connection.execute(
            "SELECT event_id FROM event_assignments WHERE family_id=?",
            (family_id,),
        ).fetchone()
    assert tuple(event) == ("new", "target", "planned_extension", "planned", 1)
    assert assignment["event_id"] == followup_id


def test_0262_cross_job_no_event_extension_inherits_day_folder_choice(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        seed_job(connection, "old")
        seed_job(connection, "new")
        seed_event(
            connection,
            event_id="target",
            job_id="old",
            status="planned",
            start="2026-07-01T00:00:00",
            end="2026-07-31T23:59:59",
            folder="07 - Ohne Ereignis",
            name="Ohne Ereignis",
            preserve=True,
        )
        connection.execute(
            """UPDATE events
               SET event_kind='no_event',timeline_model='segments'
               WHERE id='target'"""
        )
        seed_event(
            connection,
            event_id="source",
            job_id="new",
            status="planned",
            start="2026-07-23T00:00:00",
            end="2026-07-23T23:59:59",
            folder="07-23 - Source",
            name="Source",
        )
        family_id, _ = seed_family_file(
            connection,
            job_id="new",
            family_key="LATE",
            capture="2026-07-23T11:00:00",
            current_path="2026/free/LATE.JPG",
            content=b"x",
        )
        queue_family_for_reassignment(
            connection,
            job_id="new",
            source_event_id="source",
            family_id=family_id,
        )

    result = assign_event_reassignments(
        db,
        "new",
        "source",
        [family_id],
        target_mode="existing_no_event",
        target_event_id="target",
    )
    followup_id = result["target"]["event_id"]
    with database_connection(db) as connection:
        event = connection.execute(
            """SELECT event_kind,preserve_day_folders,linked_event_id,linkage_kind
               FROM events WHERE id=?""",
            (followup_id,),
        ).fetchone()
    assert tuple(event) == ("no_event", 1, "target", "planned_extension")
