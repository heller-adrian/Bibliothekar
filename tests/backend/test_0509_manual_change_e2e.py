"""0.50.9 manual multi-input end-to-end on temporary filesystem only."""
from __future__ import annotations

import hashlib
import json
import shutil
import pytest
from pathlib import Path

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot, layout_paths
from app.event_leaf_layouts import stored_leaf_layouts
from app.event_structure_changes import detect_event_structure_change, confirm_applied_structure_change
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW, seed_job, seed_event, seed_family, seed_file_for_family
)


def test_0509_applied_parent_and_child_use_distinct_layouts(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work_root = shared_work_root(workspace)

    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn,status="applied")
        seed_family(conn,content=b"parent",current_path="2026/07-23 - Trip/Alle/A.JPG")
        conn.execute(
            """INSERT INTO events(
                id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                preserve_day_folders,revision,applied_at,time_model_version,timeline_model
            ) VALUES ('child','j','e','child','Part B',
                '2026-07-23T14:00:00','2026-07-23T20:00:00',1,
                'Part B','applied',?,?,'event',0,1,?,2,'continuous')""",
            (NOW,NOW,NOW),
        )
        family = conn.execute(
            """INSERT INTO file_families(
                job_id,family_key,original_stem,status,selected_capture_time,
                capture_time_confidence
            ) VALUES ('j','B','B','complete','2026-07-23T15:00:00','high')"""
        ).lastrowid
        file_id=seed_file_for_family(
            conn,family_id=family,content=b"child",
            current_path="2026/07-23 - Trip/Part B/Alle/B.JPG",filename="B.JPG"
        )
        conn.execute("UPDATE files SET selected_capture_time='2026-07-23T15:00:00',current_root_kind='shared_workspace' WHERE id=?", (file_id,))
        conn.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('child',?,NULL,'manual',?)",
            (family,NOW),
        )
        conn.execute("UPDATE files SET current_root_kind='shared_workspace' WHERE family_id<>?",(family,))
        ensure_event_layout_snapshot(conn,"e",now=NOW)

    event_root = work_root/"2026"/"07-23 - Trip"
    for leaf, folders in [("",("Alle","Sortiert","Export")),("Part B",("Alle","Export"))]:
        for name in folders:
            (event_root/leaf/name).mkdir(parents=True,exist_ok=True)
    (event_root/"Alle"/"A.JPG").write_bytes(b"parent")
    (event_root/"Part B"/"Alle"/"B.JPG").write_bytes(b"child")

    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    change=detect_event_structure_change(db,"e")
    assert change is not None
    assert change["status"]=="pending"
    leafs=change["detected"]["leaf_layouts"]
    assert {x["leaf_key"] for x in leafs}=={"e","child"}
    assert {x["leaf_key"]:x["input_options"] for x in leafs}["child"]==["Alle","Export"]

    done=confirm_applied_structure_change(
        db,workspace,change["id"],input_path="Alle",
        input_paths={"e":"Alle","child":"Alle"},app_version="0.50.9",
    )
    assert done["status"]=="completed"
    document=json.loads((event_root/"event.json").read_text())
    assert len(document["leaf_folder_layouts"])==2
    with database_connection(db) as conn:
        leaves=stored_leaf_layouts(conn,"e")
    assert leaves["e"]["input_path"]=="Alle"
    assert leaves["child"]["input_path"]=="Alle"
    assert set(layout_paths(leaves["child"]["layout"])) == {"Alle", "Export"}

    # 0.52.0 screenshot regression: a deleted empty child Export must appear
    # under Saved To Be, but NEVER under the physical IST inventory.
    (event_root/"Part B"/"Export").rmdir()
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    from app import main
    monkeypatch.setattr(main, "current_database_file", lambda: db)
    monkeypatch.setattr(main, "current_workspace_root", lambda: workspace)
    monkeypatch.setattr(main, "current_archive_root", lambda: tmp_path/"unused-archive")
    monkeypatch.setattr(main, "refresh_live_event_inventories", lambda *a, **kw: {"errors":[]})
    structure=main.api_event_structure("j","e")
    assert "Part B" in structure["structure_text"] and "Export" in structure["structure_text"]
    assert "Part B/Export" in structure["physical_state"]["directory_removed"]
    assert "Part B/Export" not in structure["physical_state"]["directories"]
    assert structure["physical_state"]["available"] is True

    (event_root/"Part B"/"Export").mkdir()
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    assert detect_event_structure_change(db,"e") is None

    # A file-only manual rename does not change the event's directory tree.
    # It still has to update the portable document, not just SQLite paths.
    old_file=event_root/"Part B"/"Alle"/"B.JPG"
    old_file.rename(event_root/"Part B"/"Alle"/"B_renamed.JPG")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    from app.event_structure_changes import detect_all_event_structure_changes
    detect_all_event_structure_changes(db,workspace)
    updated=json.loads((event_root/"event.json").read_text())
    assert any(
        row["relative_path"].endswith("/B_renamed.JPG")
        for row in updated["files"]
    )


    # An image physically located in a child event but captured outside its
    # time window must NEVER be adopted as a permitted organization move.
    with database_connection(db) as conn:
        conn.execute(
            "UPDATE file_families SET selected_capture_time='2026-07-24T15:00:00' WHERE id=?",
            (family,),
        )
        conn.execute(
            "UPDATE files SET selected_capture_time='2026-07-24T15:00:00' WHERE id=?",
            (file_id,),
        )
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    detect_event_structure_change(db,"e")
    with database_connection(db) as conn:
        notice=conn.execute(
            "SELECT details_json,action_required FROM external_change_notices WHERE notice_key=?",
            (f"placement:{file_id}",),
        ).fetchone()
    assert notice is not None
    assert notice["action_required"] == 1
    assert json.loads(notice["details_json"])["reason"]=="capture_outside_subevent"


@pytest.mark.parametrize('english_work_root', [False, True])
def test_0509_archived_parent_and_child_replacement_is_read_only(tmp_path: Path, english_work_root: bool):
    """A prepared archived multi-input change is committed only after SHA verification."""
    from app.event_structure_changes import (
        prepare_archived_structure_change,verify_archived_structure_change
    )
    db=tmp_path/"archive.sqlite3"
    workspace=tmp_path/"workspace"
    archive=tmp_path/"archive"
    workspace.mkdir()
    archive.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work_root = workspace / "Library Workspaces" / "main" if english_work_root else None
    if work_root is not None:
        work_root.mkdir(parents=True)
    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn,status="archived")
        seed_family(conn,content=b"parent",current_path="2026/07-23 - Trip/Alle/A.JPG")
        conn.execute(
            """INSERT INTO events(
                 id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                 uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                 preserve_day_folders,revision,applied_at,archived_at,time_model_version,timeline_model
               ) VALUES ('child','j','e','child','Part B',
                 '2026-07-23T14:00:00','2026-07-23T20:00:00',1,
                 'Part B','archived',?,?,'event',0,1,?,?,2,'continuous')""",
            (NOW,NOW,NOW,NOW),
        )
        family=conn.execute(
            """INSERT INTO file_families(
                 job_id,family_key,original_stem,status,selected_capture_time,
                 capture_time_confidence
               ) VALUES ('j','B','B','complete','2026-07-23T15:00:00','high')"""
        ).lastrowid
        fid=seed_file_for_family(
            conn,family_id=family,content=b"child",
            current_path="2026/07-23 - Trip/Part B/Alle/B.JPG",filename="B.JPG"
        )
        conn.execute("UPDATE files SET selected_capture_time='2026-07-23T15:00:00' WHERE id=?",(fid,))
        conn.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('child',?,NULL,'manual',?)",
            (family,NOW),
        )
        ensure_event_layout_snapshot(conn,"e",now=NOW)
    root=archive/"2026"/"07-23 - Trip"
    for leaf,names in [("",("Alle","Sortiert","Export")),("Part B",("Alle","Export"))]:
        for name in names:
            (root/leaf/name).mkdir(parents=True,exist_ok=True)
    (root/"Alle"/"A.JPG").write_bytes(b"parent")
    (root/"Part B"/"Alle"/"B.JPG").write_bytes(b"child")

    scan_event_inventory(db,archive,"j","e",root_kind="camera_archive",persist=True,fast_refresh=False)
    detected=detect_event_structure_change(db,"e")
    assert detected and detected["status"]=="pending"
    assert {row["leaf_key"] for row in detected["detected"]["leaf_layouts"]}=={"e","child"}
    prepared=prepare_archived_structure_change(
        db,workspace,detected["id"],
        input_path="Alle",input_paths={"e":"Alle","child":"Alle"},
        app_version="0.50.9",work_root=work_root,
    )
    helper=Path(prepared["prepared_event_json_path"])
    if work_root is not None:
        assert helper.is_relative_to(work_root / "Assign Later")
        assert not (workspace / "Arbeitsbereich" / "Später zuordnen").exists()
    assert helper.is_file()
    assert not (root/"event.json").exists()
    prepared_bytes=helper.read_bytes()
    if english_work_root:
        from app.event_structure_changes import EventStructureChangeError
        (root/"event.json").write_bytes(b'{"source":"untrusted"}')
        with pytest.raises(EventStructureChangeError, match="entspricht"):
            verify_archived_structure_change(
                db,archive,workspace,detected["id"],work_root=work_root
            )
        with database_connection(db) as conn:
            assert conn.execute(
                "SELECT status FROM event_structure_changes WHERE id=?",
                (detected["id"],),
            ).fetchone()[0]=="prepared"
    (root/"event.json").write_bytes(prepared_bytes)
    confirmed=verify_archived_structure_change(
        db,archive,workspace,detected["id"],work_root=work_root
    )
    assert confirmed["status"]=="completed"
    assert confirmed["archive_read_only"]
    with database_connection(db) as conn:
        leafs=stored_leaf_layouts(conn,"e")
        assert leafs["child"]["input_path"]=="Alle"
    assert not helper.exists()


def test_0509_manual_child_dissolution_is_blocked_not_misread_as_rename(tmp_path: Path):
    """Finder/SMB placement does not authorize a semantic event edit."""
    from app.event_structure_changes import (
        EventStructureChangeError, get_structure_change,
    )
    import pytest

    db=tmp_path/"db.sqlite3"
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work_root=shared_work_root(workspace)

    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn,status="applied")
        _parent_family_id,parent_file_id=seed_family(
            conn,content=b"parent",
            current_path="2026/07-23 - Trip/Alle/A.JPG",
        )
        conn.execute(
            "UPDATE files SET current_root_kind='shared_workspace' WHERE id=?",
            (parent_file_id,),
        )
        conn.execute("""INSERT INTO events(
           id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
           uses_time_range,folder_name,status,created_at,updated_at,event_kind,
           preserve_day_folders,revision,applied_at,time_model_version,timeline_model
        ) VALUES('child','j','e','child','Part B',
         '2026-07-23T14:00:00','2026-07-23T20:00:00',1,
         'Part B','applied',?,?,'event',0,1,?,2,'continuous')""",
         (NOW,NOW,NOW))
        family_id=conn.execute("""INSERT INTO file_families(
             job_id,family_key,original_stem,status,selected_capture_time,
             capture_time_confidence
          ) VALUES('j','B','B','complete','2026-07-23T15:00:00','high')""").lastrowid
        file_id=seed_file_for_family(conn,family_id=family_id,content=b"child",
                 current_path="2026/07-23 - Trip/Part B/Alle/B.JPG",filename="B.JPG")
        conn.execute("UPDATE files SET current_root_kind='shared_workspace',selected_capture_time='2026-07-23T15:00:00' WHERE id=?",(file_id,))
        conn.execute("""INSERT INTO event_assignments(event_id,family_id,file_id,
                     assignment_source,created_at) VALUES('child',?,NULL,'manual',?)""",
                     (family_id,NOW))
        ensure_event_layout_snapshot(conn,"e",now=NOW)
    root=work_root/"2026"/"07-23 - Trip"
    for folder in ["Alle","Sortiert","Export","Part B/Alle","Part B/Sortiert","Part B/Export"]:
        (root/folder).mkdir(parents=True,exist_ok=True)
    (root/"Alle"/"A.JPG").write_bytes(b"parent")
    (root/"Part B"/"Alle"/"B.JPG").write_bytes(b"child")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    first=detect_event_structure_change(db,"e")
    if first and first["status"]=="pending":
        confirm_applied_structure_change(
            db,workspace,first["id"],input_path="Alle",
            input_paths={"child":"Alle"},app_version="0.50.9",
        )

    (root/"Part B"/"Alle"/"B.JPG").rename(root/"Alle"/"B.JPG")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    shell_task=detect_event_structure_change(db,"e")
    assert not (shell_task and shell_task["detected"]["semantic_change_candidates"]), (
        "An empty but still existing child shell must NOT be treated as dissolved."
    )
    shutil.rmtree(root/"Part B")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    task=detect_event_structure_change(db,"e")
    assert task is not None and task["status"]=="blocked"
    assert task["detected"]["semantic_change_candidates"]
    assert task["detected"]["semantic_change_candidates"][0]["child_event_id"]=="child"
    with pytest.raises(EventStructureChangeError):
        confirm_applied_structure_change(
            db,workspace,task["id"],input_path="Alle",
            app_version="0.50.9"
        )
    with database_connection(db) as conn:
        child=conn.execute("SELECT folder_name FROM events WHERE id='child'").fetchone()
        assigned=conn.execute("SELECT event_id FROM event_assignments WHERE family_id=?",(family_id,)).fetchone()
        assert child["folder_name"]=="Part B"
        assert assigned["event_id"]=="child"
    # A reviewed, explicit edit may dissolve exactly that child. An ordinary
    # edit without the matching task cannot bypass the physical conflict.
    from app.event_structure_changes import (
        validate_guided_structure_edit, assert_no_open_structure_change,
    )
    with database_connection(db) as conn:
        rows=conn.execute("""SELECT DISTINCT ea.family_id FROM event_assignments ea
                 JOIN events ev ON ev.id=ea.event_id
                 WHERE COALESCE(ev.parent_event_id,ev.id)='e'""").fetchall()
        family_ids=[int(row[0]) for row in rows]
        parent=conn.execute("SELECT * FROM events WHERE id='e'").fetchone()
        preview={
            "event_kind":"event",
            "parent_folder":str(parent["folder_name"]),
            "start_date":str(parent["start_datetime"])[:10],
            "end_date":str(parent["end_datetime"])[:10],
            "selected_family_ids":family_ids,
            "subevents":[],
        }
        with pytest.raises(EventStructureChangeError):
            assert_no_open_structure_change(conn,"e")
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],{**preview,"preserve_day_folders":True}
            )
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],{**preview,
                    "uses_time_range":True,"start_time":"10:00","end_time":"23:59"}
            )
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],preview,expected_root_kind="shared_workspace"
            )
        with pytest.raises(EventStructureChangeError):
            assert_no_open_structure_change(
                conn,"e",guided_change_id=task["id"],preview=preview
            )
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],{**preview,"selected_family_ids":[]}
            )
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],{**preview,"start_date":"2026-07-22"}
            )
        with pytest.raises(EventStructureChangeError):
            validate_guided_structure_edit(
                conn,"e",task["id"],{**preview,"subevents":[{
                    "id":"child","name":"Part B",
                    "start_datetime":"2026-07-23T14:00:00",
                    "end_datetime":"2026-07-23T20:00:00"
                }]}
            )
    # The preflight MUST NOT mutate any assignment or the event graph.
    from app.manual_subevent_restoration import restore_applied_subevents
    restored=restore_applied_subevents(db,workspace,task["id"])
    assert restored["file_count"]==1
    assert (root/"Part B"/"Alle"/"B.JPG").read_bytes()==b"child"
    assert (root/"Part B"/"Export").is_dir(), "Empty Export leaf must be restored."
    assert (root/"Part B"/"Sortiert").is_dir()
    assert not (root/"Alle"/"B.JPG").exists()
    assert get_structure_change(db,task["id"])["status"]=="cancelled"

    # The former semantic-approval shortcut must stay disabled in 0.52.1.
    (root/"Part B"/"Alle"/"B.JPG").rename(root/"Alle"/"B.JPG")
    shutil.rmtree(root/"Part B")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    proposal=detect_event_structure_change(db,"e")
    assert proposal is not None and proposal["status"]=="blocked"
    from app.database import update_event_definition
    with database_connection(db) as conn:
        parent=dict(conn.execute("SELECT * FROM events WHERE id='e'").fetchone())
        families=[int(r[0]) for r in conn.execute("SELECT DISTINCT family_id FROM event_assignments WHERE family_id IS NOT NULL")]
    with pytest.raises(EventStructureChangeError):
        update_event_definition(
            db,"j","e",{
                "start_date":"2026-07-23","end_date":"2026-07-23",
                "start_time":"00:00","end_time":"23:59","uses_time_range":False,
                "parent_folder":parent["folder_name"],"event_kind":"event",
                "preserve_day_folders":False,"subevents":[],
                "selected_family_ids":families,
            },event_name=str(parent["name"]),notes=str(parent["notes"] or ""),
            expected_revision=int(parent["revision"]),
            workspace_path=workspace,app_version="0.52.1",
            guided_structure_change_id=proposal["id"],
        )
    with database_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE id='child'").fetchone()[0]==1

