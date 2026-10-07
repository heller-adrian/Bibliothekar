from __future__ import annotations

from pathlib import Path
import hashlib

from app.central_stock_reconcile import reconcile_central_free_stock
from app.archive_transfer import verify_event_archive
from app.event_inventory import scan_event_inventory
from app.live_inventory import refresh_live_event_inventories
from app.database import (
    create_job,
    create_planned_event,
    database_connection,
    initialize_database,
    list_global_tasks,
)
from app.external_changes import (
    acknowledge_external_notices,
    list_external_change_state,
    repair_external_conflicts,
)
from app.operation_batches import create_apply_batch
from app.physical_state import reconcile_missing_files
from app.sort_apply import CONFIRMATION_PHRASE
from app.ssd_release import finalize_manually_moved_event_if_verified
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-06T16:30:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _ensure_job(db: Path) -> None:
    with database_connection(db) as connection:
        if connection.execute(
            "SELECT 1 FROM jobs WHERE id='J'"
        ).fetchone():
            return
    create_job(
        db,
        job_id="J",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path="/workspace",
        operation="folder_import",
    )


def _seed_free_file(
    db: Path,
    *,
    family_key: str,
    filename: str,
    day: str,
    data: bytes,
) -> tuple[int, int, str]:
    _ensure_job(db)
    relative = f"{day[:4]}/{day}/{filename}"
    digest = _sha(data)
    with database_connection(db) as connection:
        family = connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence)
               VALUES ('J',?,?, 'complete',?, 'high')""",
            (
                family_key,
                Path(filename).stem,
                f"{day}T12:00:00",
            ),
        )
        family_id = int(family.lastrowid)
        file_row = connection.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,current_root_kind,created_at,updated_at)
               VALUES ('J',?,?,?,?,'.JPG','jpeg',?,?,?,?, 'qa','high',
                       'not_required','not_requested','shared_workspace',?,?)""",
            (
                family_id,
                relative,
                relative,
                filename,
                len(data),
                digest,
                digest,
                f"{day}T12:00:00",
                NOW,
                NOW,
            ),
        )
    return family_id, int(file_row.lastrowid), relative


def _event_preview(family_id: int, day: str) -> dict:
    return {
        "event_kind": "event",
        "event_name": "Testereignis",
        "start_date": day,
        "end_date": day,
        "start_time": "00:00",
        "end_time": "23:59",
        "uses_time_range": False,
        "preserve_day_folders": False,
        "parent_folder": f"{day[5:7]}.{day[8:10]} - Testereignis",
        "child_folder": None,
        "child_event_name": None,
        "selected_family_ids": [family_id],
        "structure_lines": [],
    }


def test_0412_individual_deletion_is_silent_and_not_a_task(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    _family_id, file_id, relative = _seed_free_file(
        db,
        family_key="A",
        filename="A.JPG",
        day="2026-10-05",
        data=b"single-delete",
    )
    path = central / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"single-delete")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    path.unlink()
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    second = reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    assert second["deleted_file_count"] == 1

    state = list_external_change_state(db)
    assert state["required_count"] == 0
    assert state["informational_count"] == 0
    assert all(
        task["kind"] != "placement_conflicts"
        for task in list_global_tasks(db)
    )
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT 1 FROM files WHERE id=?",
            (file_id,),
        ).fetchone() is None


def test_0412_wrong_day_is_one_persistent_task_and_can_be_repaired(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])
    work = Path(layout["work_root"])

    _family_id, file_id, relative = _seed_free_file(
        db,
        family_key="A",
        filename="A.JPG",
        day="2026-10-05",
        data=b"wrong-day",
    )
    source = central / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"wrong-day")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    wrong = central / "2026/2026-10-06/A.JPG"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    source.replace(wrong)
    result = reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    assert result["misplaced_file_count"] == 1

    state = list_external_change_state(db)
    assert state["required_count"] == 1
    assert state["unseen_required_count"] == 1
    tasks = [
        task
        for task in list_global_tasks(db)
        if task["kind"] == "placement_conflicts"
    ]
    assert len(tasks) == 1
    assert tasks[0]["conflict_count"] == 1

    acknowledge_external_notices(
        db,
        [state["required"][0]["id"]],
    )
    after_ignore = list_external_change_state(db)
    assert after_ignore["required_count"] == 1
    assert after_ignore["unseen_required_count"] == 0
    assert any(
        task["kind"] == "placement_conflicts"
        for task in list_global_tasks(db)
    )

    repaired = repair_external_conflicts(
        db,
        central_root=central,
        library_work_root=work,
    )
    assert repaired["repaired_count"] == 1
    assert (central / relative).read_bytes() == b"wrong-day"
    assert not wrong.exists()
    assert list_external_change_state(db)["required_count"] == 0
    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(row["current_relative_path"]) == relative


def test_0412_whole_day_folder_is_one_information_notice(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    for key, name, data in (
        ("A", "A.JPG", b"a"),
        ("B", "B.JPG", b"b"),
    ):
        _family, _file, relative = _seed_free_file(
            db,
            family_key=key,
            filename=name,
            day="2026-10-05",
            data=data,
        )
        path = central / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    day_dir = central / "2026/2026-10-05"
    for child in list(day_dir.iterdir()):
        child.unlink()
    day_dir.rmdir()

    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    state = list_external_change_state(db)
    assert state["required_count"] == 0
    assert state["unseen_informational_count"] == 1
    notice = state["unseen_informational"][0]
    assert notice["kind"] == "central_directory_deleted"
    assert notice["details"]["deleted_file_count"] == 2
    assert all(
        task["kind"] != "placement_conflicts"
        for task in list_global_tasks(db)
    )

    acknowledge_external_notices(db, [notice["id"]])
    assert list_external_change_state(db)["informational_count"] == 0


def test_0412_running_batch_is_not_a_global_task(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    _ensure_job(db)
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO events(
                   id,job_id,event_level,parent_event_id,name,start_datetime,
                   end_datetime,folder_name,event_kind,preserve_day_folders,
                   status,created_at,updated_at)
               VALUES ('E','J','parent',NULL,'Test','2026-10-05T00:00:00',
                       '2026-10-05T23:59:59','10.05 - Test','event',0,
                       'planned',?,?)""",
            (NOW, NOW),
        )
    create_apply_batch(
        db,
        [{"job_id": "J", "event_id": "E", "plan_token": "TOKEN"}],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    assert all(
        task["kind"] != "operation_batch"
        for task in list_global_tasks(db)
    )
    assert all(
        task["kind"] != "running_sort"
        for task in list_global_tasks(db)
    )


def test_0412_same_event_move_to_archive_becomes_archive_candidate(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    family_id, file_id, relative = _seed_free_file(
        db,
        family_key="A",
        filename="A.JPG",
        day="2026-10-05",
        data=b"archive-candidate",
    )
    planned = create_planned_event(
        db,
        "J",
        _event_preview(family_id, "2026-10-05"),
    )
    event_id = str(planned["parent_event"]["id"])
    digest = _sha(b"archive-candidate")
    with database_connection(db) as connection:
        connection.execute(
            """UPDATE events
               SET status='applied',applied_at=?,updated_at=?
               WHERE id=?""",
            (NOW, NOW, event_id),
        )
        event = dict(connection.execute(
            "SELECT * FROM events WHERE id=?",
            (event_id,),
        ).fetchone())
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,current_root_kind='shared_workspace'
               WHERE id=?""",
            (
                f"2026/{event['folder_name']}/A.JPG",
                file_id,
            ),
        )
        connection.execute(
            """INSERT INTO event_inventory_files(
                   event_id,job_id,root_kind,relative_path,event_relative_path,
                   filename,extension,asset_kind,known_file_id,family_id,
                   source_file_id,size_bytes,sha256,selected_capture_time,
                   selected_capture_source,capture_time_confidence,scanned_at)
               VALUES (?,?, 'camera_archive',?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id,
                "J",
                f"2026/{event['folder_name']}/A.JPG",
                "A.JPG",
                "A.JPG",
                ".JPG",
                "camera_original",
                file_id,
                family_id,
                None,
                len(b"archive-candidate"),
                digest,
                "2026-10-05T12:00:00",
                "qa",
                "high",
                NOW,
            ),
        )
        result = reconcile_missing_files(
            connection,
            event,
            "shared_workspace",
            [file_id],
            now=NOW,
        )
    assert result["pending"] == [file_id]
    state = list_external_change_state(db)
    assert state["required_count"] == 0
    assert state["unseen_informational_count"] == 1
    assert state["unseen_informational"][0]["kind"] == "archive_transfer_candidate"


def test_0412_shell_has_single_consistency_dialog_contract():
    source = Path("app/ui_shell.py").read_text(encoding="utf-8")
    assert 'id="bk-external-change-dialog"' in source
    assert "/api/external-change-notices/repair-all" in source
    assert "Die Aufgabe „Dateizuordnung prüfen“ bleibt offen" in source
    assert "data-bk-notice-repair" not in source


def test_0412_ohne_datum_is_one_way_manual_correction_route(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    _family_id, file_id, relative = _seed_free_file(
        db,
        family_key="UNDATED-ROUNDTRIP",
        filename="ROUNDTRIP.JPG",
        day="2026-10-05",
        data=b"undated-roundtrip",
    )
    source = central / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"undated-roundtrip")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    undated = central / "Ohne_Datum" / "ROUNDTRIP.JPG"
    undated.parent.mkdir(parents=True, exist_ok=True)
    source.replace(undated)
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(row["current_relative_path"]) == "Ohne_Datum/ROUNDTRIP.JPG"
    assert list_external_change_state(db)["required_count"] == 0

    source.parent.mkdir(parents=True, exist_ok=True)
    undated.replace(source)
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    state = list_external_change_state(db)
    assert state["required_count"] == 1
    conflict = state["required"][0]
    assert conflict["details"]["force_repair"] is True
    assert conflict["details"]["expected_relative_path"] == "Ohne_Datum/ROUNDTRIP.JPG"

    acknowledge_external_notices(db, [conflict["id"]])
    assert list_external_change_state(db)["unseen_required_count"] == 1

    repaired = repair_external_conflicts(
        db,
        central_root=central,
        library_work_root=Path(layout["work_root"]),
    )
    assert repaired["repaired_count"] == 1
    assert undated.read_bytes() == b"undated-roundtrip"
    assert not source.exists()


def test_0412_archived_file_moved_to_day_stock_stays_read_only(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    family_id, file_id, _relative = _seed_free_file(
        db,
        family_key="ARCHIVE-READONLY",
        filename="ARCHIVE.JPG",
        day="2026-10-05",
        data=b"archive-readonly",
    )
    planned = create_planned_event(
        db,
        "J",
        _event_preview(family_id, "2026-10-05"),
    )
    event_id = str(planned["parent_event"]["id"])
    archive_relative = "2026/10.05 - Testereignis/ARCHIVE.JPG"
    with database_connection(db) as connection:
        connection.execute(
            """UPDATE events
               SET status='archived',applied_at=?,archived_at=?,updated_at=?
               WHERE id=?""",
            (NOW, NOW, NOW, event_id),
        )
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,
                   current_root_kind='camera_archive',
                   updated_at=?
               WHERE id=?""",
            (archive_relative, NOW, file_id),
        )

    wrong = central / "2026/2026-10-06/ARCHIVE.JPG"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    wrong.write_bytes(b"archive-readonly")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    state = list_external_change_state(db)
    assert state["required_count"] == 1
    conflict = state["required"][0]
    assert conflict["repairable"] is False
    assert conflict["details"]["expected_root_kind"] == "camera_archive"
    assert conflict["details"]["observed_root_kind"] == "central_stock"


def test_0413_planned_event_does_not_create_physical_placement_conflict(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    family_id, _file_id, relative = _seed_free_file(
        db,
        family_key="PLANNED-STAYS-FREE",
        filename="PLANNED.JPG",
        day="2026-10-05",
        data=b"planned-stays-free",
    )
    source = central / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"planned-stays-free")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    create_planned_event(
        db,
        "J",
        _event_preview(family_id, "2026-10-05"),
    )
    result = reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    assert result["misplaced_file_count"] == 0
    assert source.is_file()
    assert list_external_change_state(db)["required_count"] == 0


def test_0413_real_manual_archive_move_is_detected_verified_and_finalized(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    archive.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    work_root = Path(layout["work_root"])

    family_id, file_id, _relative = _seed_free_file(
        db,
        family_key="MANUAL-ARCHIVE",
        filename="ARCHIVE-MOVE.JPG",
        day="2026-10-05",
        data=b"manual-archive-move",
    )
    planned = create_planned_event(
        db,
        "J",
        _event_preview(family_id, "2026-10-05"),
    )
    event_id = str(planned["parent_event"]["id"])
    with database_connection(db) as connection:
        connection.execute(
            """UPDATE events
               SET status='applied',applied_at=?,updated_at=?
               WHERE id=?""",
            (NOW, NOW, event_id),
        )
        event = dict(connection.execute(
            "SELECT * FROM events WHERE id=?",
            (event_id,),
        ).fetchone())
        event_relative = f"2026/{event['folder_name']}/ARCHIVE-MOVE.JPG"
        connection.execute(
            """UPDATE files
               SET current_relative_path=?,
                   current_root_kind='shared_workspace',
                   updated_at=?
               WHERE id=?""",
            (event_relative, NOW, file_id),
        )

    source_root = work_root / "2026" / str(event["folder_name"])
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "ARCHIVE-MOVE.JPG").write_bytes(b"manual-archive-move")
    scan_event_inventory(
        db,
        work_root,
        "J",
        event_id,
        root_kind="shared_workspace",
        persist=True,
        update_known_file_locations=False,
        fast_refresh=False,
    )

    archive_event_root = archive / "2026" / str(event["folder_name"])
    archive_event_root.parent.mkdir(parents=True, exist_ok=True)
    source_root.replace(archive_event_root)

    refreshed = refresh_live_event_inventories(
        db,
        workspace,
        archive,
        event_id=event_id,
    )
    assert refreshed["events"][event_id]["archive_transfer_candidate"] is True
    state = list_external_change_state(db)
    assert state["unseen_informational_count"] == 1
    assert state["unseen_informational"][0]["kind"] == "archive_transfer_candidate"

    verification = verify_event_archive(
        db,
        archive,
        "J",
        event_id,
        workspace_path=workspace,
    )
    assert verification["verified"] is True
    assert verification["workspace_source_missing"] is True

    final = finalize_manually_moved_event_if_verified(
        db,
        workspace,
        archive,
        "J",
        event_id,
        verification,
    )
    assert final["manual_archive_finalized"] is True
    with database_connection(db) as connection:
        event_row = connection.execute(
            "SELECT status FROM events WHERE id=?",
            (event_id,),
        ).fetchone()
        file_row = connection.execute(
            "SELECT current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(event_row["status"]) == "archived"
    assert str(file_row["current_root_kind"]) == "camera_archive"
    assert (archive_event_root / "ARCHIVE-MOVE.JPG").is_file()

def test_0414_manual_restore_can_be_verified_after_database_followed_ist(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])
    work = Path(layout["work_root"])

    _family_id, file_id, relative = _seed_free_file(
        db,
        family_key="MANUAL-RESTORE",
        filename="MANUAL.JPG",
        day="2026-10-05",
        data=b"manual-restore",
    )
    expected = central / relative
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.write_bytes(b"manual-restore")
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )

    observed = central / "2026/2026-10-06/MANUAL.JPG"
    observed.parent.mkdir(parents=True, exist_ok=True)
    expected.replace(observed)
    reconcile_central_free_stock(
        db, workspace, library_id="main", excluded_family_ids=set()
    )
    state = list_external_change_state(db)
    assert state["required_count"] == 1
    with database_connection(db) as connection:
        current = connection.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert str(current["current_relative_path"]) == "2026/2026-10-06/MANUAL.JPG"

    # Simulate the documented manual fallback before clicking "Erneut prüfen".
    expected.parent.mkdir(parents=True, exist_ok=True)
    observed.replace(expected)
    repaired = repair_external_conflicts(
        db,
        central_root=central,
        library_work_root=work,
    )
    assert repaired["repaired_count"] == 1
    assert repaired["skipped"] == []
    assert expected.read_bytes() == b"manual-restore"
    with database_connection(db) as connection:
        current = connection.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
    assert tuple(current) == (relative, "shared_workspace")
    assert list_external_change_state(db)["required_count"] == 0

