from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.database import database_connection, initialize_database
from app.event_reapply import prepare_reapply_sort_run
from app.sort_apply import CONFIRMATION_PHRASE, execute_sort_run
from app.sort_plan import build_event_sort_plan


NOW = "2026-09-24T12:00:00+00:00"


def _seed(
    tmp_path: Path,
    *,
    folder: str,
    physical_folder: str | None = None,
    with_mutation: bool = False,
):
    workspace = tmp_path / "workspace"
    work = workspace / "Arbeitsbereich"
    work.mkdir(parents=True)
    db = tmp_path / "db.sqlite3"
    initialize_database(db)

    physical_folder = physical_folder or folder
    root = work / "2023" / physical_folder
    (root / "Alle").mkdir(parents=True)
    (root / "Sortiert").mkdir(parents=True)

    payloads = {
        "Alle/IMG.JPG": b"jpg-original",
        "Sortiert/IMG.RAF": b"raf-original",
    }
    for rel, payload in payloads.items():
        (root / rel).write_bytes(payload)
    (root / "Sortiert" / "IMG.xmp").write_bytes(b"<xmp>lightroom</xmp>")

    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   created_at,updated_at
               ) VALUES (
                   'j','sd_import','manual','completed','event_sort_applied',
                   'folder_import','TEST',?,?
               )""",
            (NOW, NOW),
        )
        family_id = int(connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (
                   'j','DCIM/IMG','IMG','complete',
                   '2023-01-01T10:00:00','high'
               )"""
        ).lastrowid)
        connection.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,resort_required
               ) VALUES (
                   'e','j','parent','Reapply XMP',
                   '2023-01-01T00:00:00','2023-01-01T23:59:59',0,
                   ?,'applied',?,?,'event',1,2,?,1
               )""",
            (folder, NOW, NOW, NOW),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (family_id, NOW),
        )

        file_ids = {}
        for rel, payload in payloads.items():
            name = Path(rel).name
            extension = Path(name).suffix
            media_type = "raw" if extension.lower() == ".raf" else "jpeg"
            digest = hashlib.sha256(payload).hexdigest()
            file_ids[name] = int(connection.execute(
                """INSERT INTO files(
                       job_id,family_id,original_relative_path,current_relative_path,
                       original_filename,extension,media_type,size_bytes,
                       sha256_original,sha256_current,selected_capture_time,
                       selected_capture_source,capture_time_confidence,review_status,
                       metadata_write_status,created_at,updated_at,current_root_kind
                   ) VALUES (
                       'j',?,?,?,?,?,?,?,?,?,'2023-01-01T10:00:00',
                       'DateTimeOriginal','high','not_required','not_requested',
                       ?,?,'shared_workspace'
                   )""",
                (
                    family_id,
                    "DCIM/" + name,
                    f"2023/{physical_folder}/{rel}",
                    name,
                    extension,
                    media_type,
                    len(payload),
                    digest,
                    digest,
                    NOW,
                    NOW,
                ),
            ).lastrowid)

        if with_mutation:
            original_state = {
                "events": [{
                    "id": "e",
                    "job_id": "j",
                    "parent_event_id": None,
                    "event_level": "parent",
                    "folder_name": physical_folder,
                    "start_datetime": "2023-01-01T00:00:00",
                    "end_datetime": "2023-01-01T23:59:59",
                    "status": "applied",
                }]
            }
            connection.execute(
                """INSERT INTO event_mutations(
                       id,job_id,anchor_event_id,mutation_kind,status,
                       affected_event_ids_json,original_state_json,target_state_json,
                       created_at,updated_at
                   ) VALUES (
                       'm','j','e','edit','pending_apply','["e"]',?,'{}',?,?
                   )""",
                (json.dumps(original_state), NOW, NOW),
            )

    return workspace, db, root, family_id, file_ids


def _disable_metadata_probe(monkeypatch):
    monkeypatch.setattr(
        "app.event_inventory.analyze_tree",
        lambda _root: {"files": []},
    )


def test_0265_reapply_finds_old_event_root_and_keeps_lightroom_branch(tmp_path, monkeypatch):
    _disable_metadata_probe(monkeypatch)
    workspace, db, _root, family_id, _file_ids = _seed(
        tmp_path,
        folder="01-01 - New Event",
        physical_folder="01-01 - Old Event",
        with_mutation=True,
    )

    plan = build_event_sort_plan(
        db,
        "j",
        "e",
        workspace,
        allow_reapply=True,
    )

    assert plan["summary"]["ready"] is True
    assert plan["summary"]["camera_file_count"] == 2
    assert plan["summary"]["asset_count"] == 1
    assert plan["summary"]["xmp_count"] == 1
    assert not any(item["code"] == "family_split_target" for item in plan["blockers"])

    by_name = {
        Path(item["source_relative_path"]).name: item
        for item in plan["files"]
    }
    assert by_name["IMG.JPG"]["destination_relative_path"].endswith(
        "01-01 - New Event/2023-01-01/Alle/IMG.JPG"
    )
    assert by_name["IMG.RAF"]["destination_relative_path"].endswith(
        "01-01 - New Event/2023-01-01/Sortiert/IMG.RAF"
    )

    assert len(plan["assets"]) == 1
    xmp = plan["assets"][0]
    assert xmp["asset_kind"] == "xmp"
    assert xmp["family_id"] == family_id
    assert xmp["destination_relative_path"].endswith(
        "01-01 - New Event/2023-01-01/Sortiert/IMG.xmp"
    )

    run = prepare_reapply_sort_run(
        db,
        "j",
        "e",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    with database_connection(db) as connection:
        asset = connection.execute(
            """SELECT asset_kind,family_id,source_relative_path,
                      destination_relative_path,status
               FROM sort_asset_operations
               WHERE sort_run_id=?""",
            (run["id"],),
        ).fetchone()
    assert asset is not None
    assert asset["asset_kind"] == "xmp"
    assert int(asset["family_id"]) == family_id
    assert asset["source_relative_path"].endswith(
        "01-01 - Old Event/Sortiert/IMG.xmp"
    )
    assert asset["destination_relative_path"].endswith(
        "01-01 - New Event/2023-01-01/Sortiert/IMG.xmp"
    )


def test_0265_confirmed_reapply_moves_and_verifies_xmp_with_family(tmp_path, monkeypatch):
    _disable_metadata_probe(monkeypatch)
    workspace, db, old_root, family_id, _file_ids = _seed(
        tmp_path,
        folder="01-01 - Reapply Event",
    )

    plan = build_event_sort_plan(
        db,
        "j",
        "e",
        workspace,
        allow_reapply=True,
    )
    assert plan["summary"]["ready"] is True
    assert plan["summary"]["file_count"] == 3
    assert plan["summary"]["move_count"] == 3
    assert plan["assets"][0]["family_id"] == family_id

    run = prepare_reapply_sort_run(
        db,
        "j",
        "e",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(db, run["id"], workspace)

    target_root = (
        workspace
        / "Arbeitsbereich"
        / "2023"
        / "01-01 - Reapply Event"
        / "2023-01-01"
    )
    assert (target_root / "Alle" / "IMG.JPG").read_bytes() == b"jpg-original"
    assert (target_root / "Sortiert" / "IMG.RAF").read_bytes() == b"raf-original"
    assert (target_root / "Sortiert" / "IMG.xmp").read_bytes() == b"<xmp>lightroom</xmp>"
    assert not (old_root / "Alle" / "IMG.JPG").exists()
    assert not (old_root / "Sortiert" / "IMG.RAF").exists()
    assert not (old_root / "Sortiert" / "IMG.xmp").exists()

    with database_connection(db) as connection:
        event = connection.execute(
            "SELECT resort_required,status FROM events WHERE id='e'"
        ).fetchone()
        asset = connection.execute(
            """SELECT status,asset_kind,family_id
               FROM sort_asset_operations
               WHERE sort_run_id=?""",
            (run["id"],),
        ).fetchone()
        run_row = connection.execute(
            "SELECT status,verified_file_count,moved_file_count,file_count FROM sort_runs WHERE id=?",
            (run["id"],),
        ).fetchone()

    assert tuple(event) == (0, "applied")
    assert asset["status"] == "destination_verified"
    assert asset["asset_kind"] == "xmp"
    assert int(asset["family_id"]) == family_id
    assert run_row["status"] == "applied"
    assert int(run_row["verified_file_count"]) == 3
    assert int(run_row["moved_file_count"]) == 3
    assert int(run_row["file_count"]) == 3
