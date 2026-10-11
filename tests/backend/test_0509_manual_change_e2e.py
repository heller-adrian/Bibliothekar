"""0.50.9 manual multi-input end-to-end on temporary filesystem only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.database import database_connection, initialize_database
from app.event_inventory import scan_event_inventory
from app.event_layout import ensure_event_layout_snapshot
from app.event_leaf_layouts import stored_leaf_layouts
from app.event_structure_changes import detect_event_structure_change, confirm_applied_structure_change
from app.workspace_layout import ensure_workspace_layout, shared_work_root
from tests.backend.test_0263_event_inventory import (
    NOW, seed_job, seed_event, seed_family, seed_file_for_family
)


def test_0509_applied_parent_and_child_use_distinct_layouts(tmp_path: Path):
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
    assert "Sortiert" not in leaves["child"]["layout"]["nodes"][0]["name"]
    scan_event_inventory(db,work_root,"j","e",root_kind="shared_workspace",persist=True,fast_refresh=False)
    assert detect_event_structure_change(db,"e") is None
