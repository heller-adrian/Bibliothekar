"""Physical Applied expansion across occupied and remaining free stock."""

import hashlib
import json

from app.database import database_connection, initialize_database, update_event_definition
from app.event_document import build_event_document_from_db, write_event_document
from app.sort_apply import CONFIRMATION_PHRASE
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)


def test_applied_expansion_moves_new_family_and_renormalizes_remaining_free_stock(tmp_path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    root = workspace / "Arbeitsbereich"
    root.mkdir(parents=True)
    incoming = workspace / "imports" / "j"
    incoming.mkdir(parents=True)
    initialize_database(db)
    families = {}
    files = {}
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,working_path,
                   created_at,updated_at) VALUES
                   ('j','sd_import','manual','completed','event_sort_applied',
                    'folder_import',?,'now','now')""",
            (str(incoming),),
        )
        for event_id, name, start, end in (
            ("event", "Test", "2026-07-19T13:00:00", "2026-07-19T15:00:59"),
            ("other", "Andere", "2026-07-20T10:00:00", "2026-07-20T11:00:59"),
        ):
            connection.execute(
                """INSERT INTO events(id,job_id,event_level,name,start_datetime,
                       end_datetime,uses_time_range,folder_name,status,created_at,
                       updated_at,event_kind,preserve_day_folders,revision,applied_at,
                       time_model_version)
                   VALUES (?,'j','parent',?,?,?,0,?,'applied','now','now',
                       'event',0,1,'now',2)""",
                (event_id, name, start, end, f"07-{start[8:10]} - {name}"),
            )
        for key, capture, relative, content in (
            ("inside", "2026-07-19T10:00:00", "2026/2026-07-19 · 00-00–12-59/INSIDE.JPG", b"inside"),
            ("event", "2026-07-19T14:00:00", "2026/07-19 - Test/Alle/EVENT.JPG", b"event"),
            ("outside", "2026-07-19T20:00:00", "2026/2026-07-19 · 15-01–23-59/OUTSIDE.JPG", b"outside"),
        ):
            family_id = int(connection.execute(
                """INSERT INTO file_families(job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence)
                   VALUES ('j',?,?,'complete',?,'high')""",
                (key, key, capture),
            ).lastrowid)
            families[key] = family_id
            if key == "event":
                connection.execute(
                    """INSERT INTO event_assignments(event_id,family_id,file_id,
                           assignment_source,created_at)
                       VALUES ('event',?,NULL,'date_range','now')""",
                    (family_id,),
                )
            digest = hashlib.sha256(content).hexdigest()
            file_id = int(connection.execute(
                """INSERT INTO files(job_id,family_id,original_relative_path,
                       current_relative_path,original_filename,extension,media_type,
                       size_bytes,sha256_original,sha256_current,selected_capture_time,
                       selected_capture_source,capture_time_confidence,review_status,
                       metadata_write_status,created_at,updated_at,current_root_kind)
                   VALUES ('j',?,?,?,?,'.JPG','jpeg',?,?,?,?,'DateTimeOriginal',
                       'high','not_required','not_requested','now','now','shared_workspace')""",
                (family_id, relative, relative, relative.rsplit("/", 1)[-1],
                 len(content), digest, digest, capture),
            ).lastrowid)
            files[file_id] = content
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        connection.commit()

    document_path = write_event_document(
        workspace, build_event_document_from_db(db, workspace, "j", "event")
    )
    old_document = document_path.read_bytes()
    old_outside = root / "2026/2026-07-19 · 15-01–23-59/OUTSIDE.JPG"
    with database_connection(db) as connection:
        other_before = tuple(connection.execute(
            "SELECT start_datetime,end_datetime,status,revision FROM events WHERE id='other'"
        ).fetchone())

    update_event_definition(
        db, "j", "event",
        {"selected_family_ids": [families["inside"], families["event"]],
         "start_date": "2026-07-19", "end_date": "2026-07-19",
         "start_time": "09:00", "end_time": "18:00", "uses_time_range": True,
         "parent_folder": "07-19 - Test", "child_folder": "", "child_event_name": "",
         "event_kind": "event", "preserve_day_folders": False},
        event_name="Test", notes="", expected_revision=1, workspace_path=workspace,
    )
    assert old_outside.is_file()
    assert document_path.read_bytes() == old_document
    plan = build_workspace_reconcile_plan(db, "j", "event", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    run = prepare_workspace_reconcile_run(
        db, "j", "event", workspace,
        expected_plan_token=plan["plan_token"], confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)

    with database_connection(db) as connection:
        rows = connection.execute(
            "SELECT id,family_id,current_relative_path,sha256_current FROM files WHERE job_id='j'"
        ).fetchall()
        other_after = tuple(connection.execute(
            "SELECT start_datetime,end_datetime,status,revision FROM events WHERE id='other'"
        ).fetchone())
        assigned = {int(row[0]) for row in connection.execute(
            "SELECT family_id FROM event_assignments WHERE event_id='event'"
        )}
    assert other_after == other_before
    assert assigned == {families["inside"], families["event"]}
    assert len(rows) == len(files) == len(list(root.rglob("*.JPG"))) == 3
    for row in rows:
        payload = files[int(row["id"])]
        path = root / row["current_relative_path"]
        assert path.read_bytes() == payload
        assert row["sha256_current"] == hashlib.sha256(payload).hexdigest()
        if int(row["family_id"]) == families["outside"]:
            assert row["current_relative_path"] == "2026/2026-07-19 · 18-01–23-59/OUTSIDE.JPG"
        else:
            assert row["current_relative_path"].startswith("2026/07-19 - Test/Alle/")
    assert not old_outside.exists()
    document = json.loads(document_path.read_text())
    assert document["event"]["start_datetime"] == "2026-07-19T09:00:00"
    assert document["event"]["end_datetime"] == "2026-07-19T18:00:59"
