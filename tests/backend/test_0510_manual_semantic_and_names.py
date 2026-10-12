"""0.51.0: explicit manual structural handoff on an isolated SQLite/workspace."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.database import (
    database_connection, initialize_database, update_event_definition,
)
from app.event_inventory import scan_event_inventory
from app.event_structure_changes import (
    EventStructureChangeError, detect_event_structure_change,
)
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW, seed_job, seed_event, seed_family, seed_file_for_family
)


def test_0510_dissolved_child_requires_explicit_safe_edit(tmp_path: Path):
    db=tmp_path/"db.sqlite3"
    workspace=tmp_path/"workspace"
    workspace.mkdir()
    initialize_database(db)
    ensure_workspace_layout(workspace)
    work_root=shared_work_root(workspace)
    with database_connection(db) as conn:
        seed_job(conn)
        seed_event(conn,status="applied")
        parent_family,parent_file=seed_family(
            conn,content=b"parent",current_path="2026/07-23 - Trip/Alle/A.JPG"
        )
        conn.execute("UPDATE files SET current_root_kind='shared_workspace' WHERE id=?",(parent_file,))
        conn.execute("""INSERT INTO events(
            id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
            uses_time_range,folder_name,status,created_at,updated_at,event_kind,
            preserve_day_folders,revision,applied_at,time_model_version,timeline_model
        ) VALUES('child','j','e','child','Part B',
          '2026-07-23T14:00:00','2026-07-23T20:00:00',1,'Part B',
          'applied',?,?,'event',0,1,?,2,'continuous')""",(NOW,NOW,NOW))
        child_family=conn.execute("""INSERT INTO file_families(
            job_id,family_key,original_stem,status,selected_capture_time,
            capture_time_confidence
        ) VALUES('j','B','B','complete','2026-07-23T15:00:00','high')""").lastrowid
        child_file=seed_file_for_family(
            conn,family_id=child_family,content=b"child",
            current_path="2026/07-23 - Trip/Part B/Alle/B.JPG",filename="B.JPG"
        )
        conn.execute("""UPDATE files SET current_root_kind='shared_workspace',
          selected_capture_time='2026-07-23T15:00:00' WHERE id=?""",(child_file,))
        conn.execute("""INSERT INTO event_assignments(event_id,family_id,file_id,
          assignment_source,created_at) VALUES ('child',?,NULL,'manual',?)""",(child_family,NOW))
    root=work_root/"2026"/"07-23 - Trip"
    for folder in ["Alle","Export","Sortiert","Part B/Alle","Part B/Export","Part B/Sortiert"]:
        (root/folder).mkdir(parents=True,exist_ok=True)
    (root/"Alle"/"A.JPG").write_bytes(b"parent")
    (root/"Part B"/"Alle"/"B.JPG").write_bytes(b"child")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    initial=detect_event_structure_change(db,"e")
    if initial and initial["status"]=="pending":
        from app.event_structure_changes import confirm_applied_structure_change
        confirm_applied_structure_change(
            db,workspace,initial["id"],input_path="Alle",
            input_paths={"e":"Alle","child":"Alle"},app_version="0.51.0",
        )
    (root/"Part B"/"Alle"/"B.JPG").rename(root/"Alle"/"B.JPG")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    incomplete=detect_event_structure_change(db,"e")
    assert not (incomplete and incomplete["detected"].get("semantic_change_candidates"))
    # Deleting the actual *whole* subtree, including empty Export/Sorted,
    # is the security precondition newly required by 0.52.0.
    import shutil
    shutil.rmtree(root/"Part B")
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    task=detect_event_structure_change(db,"e")
    assert task and task["status"]=="blocked"
    assert task["detected"]["semantic_change_candidates"]
    with database_connection(db) as conn:
        revision=conn.execute("SELECT revision FROM events WHERE id='e'").fetchone()[0]
    preview={
        "event_kind":"event","parent_folder":"07-23 - Trip",
        "start_date":"2026-07-23","end_date":"2026-07-23",
        "start_time":"00:00","end_time":"23:59",
        "uses_time_range":True,"preserve_day_folders":False,
        "selected_family_ids":[parent_family,child_family],
        "subevents":[],
    }
    with pytest.raises(EventStructureChangeError):
        update_event_definition(
            db,"j","e",preview,event_name="Trip",notes="",
            expected_revision=revision,workspace_path=workspace,
        )
    with database_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE id='child'").fetchone()[0]==1

    with pytest.raises(EventStructureChangeError):
        update_event_definition(
            db,"j","e",preview,event_name="Trip",notes="",
            expected_revision=revision,workspace_path=workspace,
            guided_structure_change_id=task["id"],
        )
    with database_connection(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM events WHERE id='child'").fetchone()[0]==1
        assert conn.execute(
            "SELECT status FROM event_structure_changes WHERE id=?", (task["id"],)
        ).fetchone()[0]=="blocked"



@pytest.mark.parametrize("kind,legacy,english",[
    ("undated","Ohne_Datum","No Date"),
    ("metadata_general","Allgemein","General"),
    ("metadata_multiple","Mehrfachkorrektur","Batch Correction"),
    ("assign_later","Später zuordnen","Assign Later"),
    ("released_archive","Freigewordene Archivdateien","Released Archive Files"),
    ("reversal","Rückänderung","Reversal"),
    ("restoration","Wiederherstellung","Restoration"),
])
def test_0510_english_new_and_legacy_folders(tmp_path,kind,legacy,english):
    from app.managed_directory_names import directory_name
    assert directory_name(tmp_path,kind)==english
    (tmp_path/legacy).mkdir()
    assert directory_name(tmp_path,kind)==legacy
    (tmp_path/english).mkdir()
    (tmp_path/english/"data.bin").write_bytes(b"data")
    assert directory_name(tmp_path,kind)==english
    (tmp_path/legacy/"older.bin").write_bytes(b"legacy")
    from app.managed_directory_names import AmbiguousManagedDirectoryError
    with pytest.raises(AmbiguousManagedDirectoryError):
        directory_name(tmp_path,kind)
