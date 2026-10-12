"""0.52.1: synthetic on-disk Undo and dismissal regressions.

No production volumes or databases are ever opened by these tests.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot
from app.event_structure_changes import (
    detect_event_structure_change, confirm_applied_structure_change,
)
from app.external_changes import (
    list_external_change_state, repair_external_conflicts, acknowledge_external_notices,
)
from app.manual_structure_undo import undo_empty_folder_change
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW, seed_job, seed_event, seed_family, seed_file_for_family,
)


def _seed(tmp_path: Path, *, child_file_branch: str = "Alle"):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work = shared_work_root(workspace)
    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn, status="applied")
        parent_family, parent_file = seed_family(
            conn, content=b"parent", current_path="2026/07-23 - Trip/Alle/A.JPG"
        )
        conn.execute("UPDATE files SET current_root_kind='shared_workspace' WHERE id=?", (parent_file,))
        conn.execute("""INSERT INTO events(
            id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
            uses_time_range,folder_name,status,created_at,updated_at,event_kind,
            preserve_day_folders,revision,applied_at,time_model_version,timeline_model
        ) VALUES('child','j','e','child','Part B',
            '2026-07-23T14:00:00','2026-07-23T20:00:00',1,
            'Part B','applied',?,?,'event',0,1,?,2,'continuous')""", (NOW,NOW,NOW))
        fid = conn.execute("""INSERT INTO file_families(
            job_id,family_key,original_stem,status,selected_capture_time,
            capture_time_confidence
        ) VALUES('j','B','B','complete','2026-07-23T15:00:00','high')""").lastrowid
        child_file = seed_file_for_family(
            conn, family_id=fid, content=b"child",
            current_path=f"2026/07-23 - Trip/Part B/{child_file_branch}/B.JPG",
            filename="B.JPG",
        )
        conn.execute(
            "UPDATE files SET current_root_kind='shared_workspace',selected_capture_time='2026-07-23T15:00:00' WHERE id=?",
            (child_file,),
        )
        conn.execute("""INSERT INTO event_assignments(event_id,family_id,file_id,
            assignment_source,created_at) VALUES ('child',?,NULL,'manual',?)""", (fid,NOW))
        ensure_event_layout_snapshot(conn, "e", now=NOW)
    root = work / "2026" / "07-23 - Trip"
    for folder in ("Alle","Export","Sortiert","Part B/Alle","Part B/Export","Part B/Sortiert"):
        (root/folder).mkdir(parents=True, exist_ok=True)
    (root/"Alle"/"A.JPG").write_bytes(b"parent")
    (root/"Part B"/child_file_branch/"B.JPG").write_bytes(b"child")
    scan_event_inventory(db, work, "j", "e", root_kind="shared_workspace", persist=True, fast_refresh=False)
    baseline = detect_event_structure_change(db,"e")
    if baseline and baseline["status"]=="pending":
        confirm_applied_structure_change(
            db,workspace,baseline["id"],input_path="Alle",
            input_paths={"e":"Alle","child":"Alle"},app_version="0.52.1"
        )
    return db,workspace,work,root,child_file


@pytest.mark.parametrize("original_branch",["Alle","Export","Sortiert"])
def test_0521_repair_files_recreates_all_empty_child_folders(tmp_path,original_branch):
    db,workspace,work,root,file_id=_seed(tmp_path,child_file_branch=original_branch)
    moved=root/"Alle"/"B.JPG"
    (root/"Part B"/original_branch/"B.JPG").rename(moved)
    shutil.rmtree(root/"Part B")
    scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    task=detect_event_structure_change(db,"e")
    assert task is not None and task["status"]=="blocked"
    notices=list_external_change_state(db)
    assert any(n["file_id"]==file_id for n in notices["required"])
    undone=repair_external_conflicts(
        db,central_root=tmp_path/"unused",library_work_root=work
    )
    assert undone["skipped"]==[],undone
    assert undone["repaired_count"]>=1
    assert (root/"Part B"/original_branch/"B.JPG").read_bytes()==b"child"
    assert not moved.exists()
    assert all((root/"Part B"/folder).is_dir() for folder in ("Alle","Export","Sortiert"))
    scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    assert detect_event_structure_change(db,"e") is None
    with database_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE id='child'").fetchone()[0]==1
        assert conn.execute("SELECT event_id FROM event_assignments WHERE family_id=(SELECT family_id FROM files WHERE id=?)",(file_id,)).fetchone()[0]=="child"


def test_0521_empty_export_and_sorted_folder_undo(tmp_path):
    db,workspace,work,root,_=_seed(tmp_path)
    (root/"Part B"/"Export").rmdir()
    (root/"Part B"/"Sortiert").rmdir()
    scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    change=detect_event_structure_change(db,"e")
    assert change and change["status"]=="pending"
    assert {"Part B/Export","Part B/Sortiert"}.issubset(set(change["detected"]["directory_removed"]))
    undone=undo_empty_folder_change(db,work,change["id"])
    assert undone["status"]=="restored"
    assert (root/"Part B"/"Export").is_dir()
    assert (root/"Part B"/"Sortiert").is_dir()
    assert detect_event_structure_change(db,"e") is None


def test_0521_missing_child_originals_are_notice_not_impossible_repair(tmp_path):
    db,workspace,work,root,file_id=_seed(tmp_path)
    shutil.rmtree(root/"Part B")
    for _ in range(2):
        scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
        detect_event_structure_change(db,"e")
    state=list_external_change_state(db)
    deletion=[x for x in state["informational"] if x["kind"]=="event_directory_deleted"]
    assert deletion and deletion[0]["repairable"] is False
    assert not any(x.get("file_id")==file_id and x["repairable"] for x in state["required"])
    acknowledged=acknowledge_external_notices(db,[deletion[0]["id"]])
    assert not any(x["id"]==deletion[0]["id"] for x in acknowledged["unseen_informational"])


def test_0521_acknowledged_conflict_not_reopened_on_identical_repeat(tmp_path):
    db,workspace,work,root,file_id=_seed(tmp_path)
    (root/"Part B"/"Alle"/"B.JPG").rename(root/"Alle"/"B.JPG")
    scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    detect_event_structure_change(db,"e")
    before=list_external_change_state(db)
    notice=next(n for n in before["required"] if n["file_id"]==file_id)
    after=acknowledge_external_notices(db,[notice["id"]])
    assert not any(n["id"]==notice["id"] for n in after["unseen_required"])
    scan_event_inventory(db,work,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    detect_event_structure_change(db,"e")
    again=list_external_change_state(db)
    assert any(n["id"]==notice["id"] for n in again["required"])
    assert not any(n["id"]==notice["id"] for n in again["unseen_required"])
