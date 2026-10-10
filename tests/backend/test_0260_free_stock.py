"""Physical free-stock boundaries across events, jobs, and years."""

import hashlib
from pathlib import Path

import pytest

from app.database import (
    database_connection,
    delete_planned_event,
    initialize_database,
    update_event_definition,
)
from app.free_stock_layout import FreeStockLayoutError, canonical_free_directory
from app.archive_reassignment_segments import proposed_ranges
from app.event_reassignment import (
    _create_new_event,
    assign_event_reassignments,
    list_event_reassignments,
)
from app.obsolete_structure import cleanup_obsolete_structure
from app.sort_apply import CONFIRMATION_PHRASE, SortApplyError
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from tests.backend.test_0165_timeline import add_family, seed_job


def test_library_wide_event_and_no_event_split_one_day(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        for job_id in ("first", "second"):
            connection.execute(
                """INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at)
                   VALUES (?,'sd_import','manual','completed','done','now','now')""",
                (job_id,),
            )
        connection.execute(
            """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind)
               VALUES ('event','first','parent','Morning','2026-07-23T09:00:00',
                   '2026-07-23T11:00:59',0,'Morning','applied','now','now','event')"""
        )
        connection.execute(
            """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind)
               VALUES ('collection','second','parent','No event','2026-07-23T15:00:00',
                   '2026-07-23T16:00:59',0,'No event','archived','now','now','no_event')"""
        )
        connection.execute(
            """INSERT INTO event_time_segments(event_id,job_id,day_key,start_time,end_time,
                   start_datetime,end_datetime,source,created_at,updated_at)
               VALUES ('collection','second','2026-07-23','15:00','16:00',
                   '2026-07-23T15:00:00','2026-07-23T16:00:59','user','now','now')"""
        )
        expected = {
            "2026-07-23T08:00:00": "2026/2026-07-23 · 00-00–08-59",
            "2026-07-23T13:00:00": "2026/2026-07-23 · 11-01–14-59",
            "2026-07-23T20:00:00": "2026/2026-07-23 · 16-01–23-59",
            "2025-12-31T20:00:00": "2025/2025-12-31",
            "2026-01-01T08:00:00": "2026/2026-01-01",
        }
        for capture, directory in expected.items():
            assert str(canonical_free_directory(connection, capture)) == directory


def test_only_empty_known_free_source_directories_are_removed(tmp_path):
    root = tmp_path / "Arbeitsbereich"
    old = root / "2026" / "2026-07-23 · 00-00–12-59"
    destination = root / "2026" / "2026-07-23 · 00-00–08-59" / "photo.JPG"
    old.mkdir(parents=True)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"photo")
    source = old / "photo.JPG"
    cleanup_obsolete_structure(root, [source], [destination], set())
    assert not old.exists()
    assert destination.read_bytes() == b"photo"

    old.mkdir()
    (old / "unknown.txt").write_text("foreign")
    cleanup_obsolete_structure(root, [source], [destination], set())
    assert (old / "unknown.txt").read_text() == "foreign"


def test_archived_v2_child_is_organizational_not_a_new_free_interval(tmp_path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at)
               VALUES ('j','sd_import','manual','completed','done','now','now')"""
        )
        connection.execute(
            """INSERT INTO events(id,job_id,event_level,name,start_datetime,
                   end_datetime,uses_time_range,folder_name,status,created_at,
                   updated_at,event_kind,time_model_version,archived_at)
               VALUES ('parent','j','parent','Parent','2026-07-23T09:00:00',
                   '2026-07-23T19:00:59',0,'Parent','archived','now','now',
                   'event',2,'now')"""
        )
        connection.execute(
            """INSERT INTO events(id,job_id,parent_event_id,event_level,name,
                   start_datetime,end_datetime,uses_time_range,folder_name,status,
                   created_at,updated_at,event_kind,archived_at)
               VALUES ('child','j','parent','child','Morning',
                   '2026-07-23T09:00:00','2026-07-23T11:00:59',1,
                   'Morning','archived','now','now','event','now')"""
        )
        with pytest.raises(FreeStockLayoutError, match="belegten Zeitraum"):
            canonical_free_directory(connection, "2026-07-23T14:00:00")
    request = {
        "event_kind": "event", "time_model_version": 2,
        "start_date": "2026-07-23", "end_date": "2026-07-23",
        "start_time": "09:00", "end_time": "19:00", "uses_time_range": 1,
        "child_segments_json": '[{"name":"Evening","start_time":"16:00","end_time":"18:00"}]',
    }
    assert proposed_ranges(request) == [
        ("2026-07-23T09:00:00", "2026-07-23T19:00:59")
    ]


def _seed_cross_job_shift(tmp_path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    root = workspace / "Arbeitsbereich"
    initialize_database(db)
    with database_connection(db) as connection:
        for job_id in ("first", "second"):
            incoming = workspace / "imports" / job_id
            incoming.mkdir(parents=True)
            connection.execute(
                """INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,
                       working_path,created_at,updated_at)
                   VALUES (?,'sd_import','manual','completed','event_sort_applied',
                       'folder_import',?,'now','now')""",
                (job_id, str(incoming)),
            )
        for event_id, job_id, start, end, folder in (
            ("first-event", "first", "09:00:00", "11:00:59", "07-23 - First"),
            ("second-event", "second", "15:00:00", "17:00:59", "07-23 - Second"),
        ):
            connection.execute(
                """INSERT INTO events(id,job_id,event_level,name,start_datetime,
                       end_datetime,uses_time_range,folder_name,status,created_at,
                       updated_at,event_kind,revision,applied_at,time_model_version)
                   VALUES (?,?,'parent',? ,?,?,0,?,'applied','now','now',
                       'event',1,'now',2)""",
                (event_id, job_id, folder,
                 "2026-07-23T" + start, "2026-07-23T" + end, folder),
            )
        file_ids = {}
        for job_id, key, capture, relative, content, event_id in (
            ("first", "event", "2026-07-23T10:00:00",
             "2026/07-23 - First/Alle/event.JPG", b"event", "first-event"),
            ("second", "other", "2026-07-23T16:00:00",
             "2026/07-23 - Second/Alle/other.JPG", b"other", "second-event"),
            ("second", "free", "2026-07-23T13:00:00",
             "2026/2026-07-23 · 11-01–14-59/free.JPG", b"free", None),
            ("first", "free2", "2026-07-23T14:00:00",
             "2026/2026-07-23 · 11-01–14-59/free2.JPG", b"free2", None),
        ):
            family_id = int(connection.execute(
                """INSERT INTO file_families(job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence)
                   VALUES (?,?,?,'complete',?,'high')""",
                (job_id, key, key, capture),
            ).lastrowid)
            if event_id:
                connection.execute(
                    """INSERT INTO event_assignments(event_id,family_id,file_id,
                           assignment_source,created_at)
                       VALUES (?,?,NULL,'date_range','now')""",
                    (event_id, family_id),
                )
            digest = hashlib.sha256(content).hexdigest()
            file_ids[key] = int(connection.execute(
                """INSERT INTO files(job_id,family_id,original_relative_path,
                       current_relative_path,original_filename,extension,media_type,
                       size_bytes,sha256_original,sha256_current,selected_capture_time,
                       selected_capture_source,capture_time_confidence,review_status,
                       metadata_write_status,created_at,updated_at,current_root_kind)
                   VALUES (?,?,?,?,?,'.JPG','jpeg',?,?,?,?,'DateTimeOriginal',
                       'high','not_required','not_requested','now','now','shared_workspace')""",
                (job_id, family_id, relative, relative, relative.rsplit('/', 1)[-1],
                 len(content), digest, digest, capture),
            ).lastrowid)
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return db, workspace, file_ids


def _shift_first_event(db, workspace):
    update_event_definition(
        db, "first", "first-event",
        {"selected_family_ids": [1], "start_date": "2026-07-23",
         "end_date": "2026-07-23", "start_time": "09:30", "end_time": "11:30",
         "uses_time_range": True, "parent_folder": "07-23 - First",
         "child_folder": "", "child_event_name": "", "event_kind": "event",
         "preserve_day_folders": False},
        event_name="07-23 - First", notes="", expected_revision=1,
        workspace_path=workspace,
    )


def test_reconcile_shift_renormalizes_cross_job_free_file(tmp_path):
    db, workspace, file_ids = _seed_cross_job_shift(tmp_path)
    root = workspace / "Arbeitsbereich"
    old_free = root / "2026/2026-07-23 · 11-01–14-59/free.JPG"
    foreign = root / "2026/unbekannt/keep.txt"
    foreign.parent.mkdir()
    foreign.write_text("keep")
    _shift_first_event(db, workspace)
    plan = build_workspace_reconcile_plan(db, "first", "first-event", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    free_entry = next(item for item in plan["files"] if item["file_id"] == file_ids["free"])
    assert free_entry["destination_relative_path"] == (
        "2026/2026-07-23 · 11-31–14-59/free.JPG"
    )
    run = prepare_workspace_reconcile_run(
        db, "first", "first-event", workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)
    assert not old_free.exists()
    assert not old_free.parent.exists()
    central = workspace / "SD-Kartensicherungen"
    assert (central / free_entry["destination_relative_path"]).read_bytes() == b"free"
    assert (central / "2026/2026-07-23 · 11-31–14-59/free2.JPG").read_bytes() == b"free2"
    assert foreign.read_text() == "keep"
    with database_connection(db) as connection:
        row = connection.execute(
            "SELECT current_relative_path,job_id FROM files WHERE id=?",
            (file_ids["free"],),
        ).fetchone()
        assert tuple(row) == (free_entry["destination_relative_path"], "second")


def test_cross_job_reconcile_rolls_back_after_late_destination_collision(tmp_path, monkeypatch):
    import app.workspace_reconcile as reconcile

    db, workspace, file_ids = _seed_cross_job_shift(tmp_path)
    _shift_first_event(db, workspace)
    plan = build_workspace_reconcile_plan(db, "first", "first-event", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    moving = [item for item in plan["files"] if item["status"] == "move"]
    assert {item["file_id"] for item in moving} == {file_ids["free"], file_ids["free2"]}
    before = {}
    with database_connection(db) as connection:
        for row in connection.execute(
            "SELECT id,current_relative_path,current_root_kind FROM files ORDER BY id"
        ):
            before[int(row["id"])] = (row["current_relative_path"], row["current_root_kind"])
    run = prepare_workspace_reconcile_run(
        db, "first", "first-event", workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    real_move = reconcile._move_without_overwrite
    attempted = 0

    def collide_on_second(source, destination, entry):
        nonlocal attempted
        attempted += 1
        if attempted == 2:
            Path(destination).write_bytes(b"foreign")
        return real_move(source, destination, entry)

    monkeypatch.setattr(reconcile, "_move_without_overwrite", collide_on_second)
    with pytest.raises(SortApplyError):
        execute_workspace_reconcile_run(db, run["id"], workspace)
    assert attempted == 2
    first, second = moving
    assert Path(first["source_absolute_path"]).read_bytes() == b"free"
    assert not Path(first["destination_absolute_path"]).exists()
    assert Path(second["source_absolute_path"]).read_bytes() == b"free2"
    assert Path(second["destination_absolute_path"]).read_bytes() == b"foreign"
    with database_connection(db) as connection:
        after = {
            int(row["id"]): (row["current_relative_path"], row["current_root_kind"])
            for row in connection.execute(
                "SELECT id,current_relative_path,current_root_kind FROM files ORDER BY id"
            )
        }
        assert after == before
        assert connection.execute(
            "SELECT status FROM sort_runs WHERE id=?", (run["id"],)
        ).fetchone()[0] == "failed"



def test_deleting_one_of_two_events_merges_free_stock_across_jobs(tmp_path):
    from app.database import list_global_tasks
    db, workspace, file_ids = _seed_cross_job_shift(tmp_path)
    root = workspace / "Arbeitsbereich"
    old_free = root / "2026/2026-07-23 · 11-01–14-59"
    result = delete_planned_event(db, "first", "first-event")
    assert result["reassignment_required"] is False
    plan = build_workspace_reconcile_plan(db, "first", "first-event", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    by_id = {item["file_id"]: item for item in plan["files"]}
    for key in ("event", "free", "free2"):
        assert by_id[file_ids[key]]["destination_relative_path"].startswith(
            "2026/2026-07-23 · 00-00–14-59/"
        )
    run = prepare_workspace_reconcile_run(
        db, "first", "first-event", workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)
    assert not old_free.exists()
    central = workspace / "SD-Kartensicherungen"
    for key in ("event", "free", "free2"):
        assert (central / by_id[file_ids[key]]["destination_relative_path"]).read_bytes() == key.encode()
    assert (root / "2026/07-23 - Second/Alle/other.JPG").read_bytes() == b"other"
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='first-event'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE job_id='first'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id='first-event'"
        ).fetchone()[0] == 0
    tasks = list_global_tasks(db)
    assert not any(task["kind"] in {"reassignment","resort"} for task in tasks)
    # Freier datierter Bestand ist seit 0.42.1 eine globale Aufgabe über alle
    # Import-/Korrekturjobs. Die durch das bestätigte Löschen freigegebene
    # Familie bleibt via released_free_families ausgeschlossen; die beiden
    # bereits vorher freien Familien aus "first" und "second" werden gemeinsam
    # gezählt statt als job-spezifische Karten dargestellt.
    unassigned = [task for task in tasks if task["kind"] == "unassigned_families"]
    assert len(unassigned) == 1
    assert unassigned[0]["family_count"] == 2
    assert unassigned[0]["job_count"] == 2
    assert unassigned[0]["detail"] == "2 Familien · freier Tagesbestand"
    assert unassigned[0]["href"] == "/workspace?task=free"
@pytest.mark.parametrize("preserve", [False, True])
def test_reassignment_new_event_uses_explicit_day_folder_option(tmp_path, preserve):
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    first = add_family(db, "first", "2026-12-31T10:00:00")
    second = add_family(db, "second", "2027-01-01T12:00:00")
    target = _create_new_event(
        db, "j", [first, second], "Jahreswechsel",
        preserve_day_folders=preserve,
    )
    assert target["preserve_day_folders"] is preserve
    with database_connection(db) as connection:
        event = connection.execute(
            "SELECT preserve_day_folders,start_datetime,end_datetime FROM events WHERE id=?",
            (target["event_id"],),
        ).fetchone()
        assert bool(event["preserve_day_folders"]) is preserve
        assert event["start_datetime"][:10] == "2026-12-31"
        assert event["end_datetime"][:10] == "2027-01-01"


def test_reassignment_year_boundary_creates_separate_no_event_months(tmp_path):
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    december = add_family(db, "december", "2026-12-31T22:00:00")
    january = add_family(db, "january", "2027-01-01T02:00:00")
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision)
               VALUES ('source','j','parent','Quelle','2026-12-31T00:00:00',
                   '2027-01-01T23:59:59',0,'Quelle','planned','now','now','event',0,1)"""
        )
        for fid, day in ((december, "2026-12-31"), (january, "2027-01-01")):
            connection.execute(
                """INSERT INTO event_reapply_removed_families(
                       event_id,job_id,family_id,released_start_datetime,
                       released_end_datetime,created_at)
                   VALUES ('source','j',?,?,?,?)""",
                (fid, f"{day}T00:00:00", f"{day}T23:59:59", "now"),
            )
        connection.commit()

    for fid, day, year, month in (
        (december, "2026-12-31", "2026", "12"),
        (january, "2027-01-01", "2027", "01"),
    ):
        state = list_event_reassignments(db, "j", "source")
        segment = next(item for item in state["reassignment_segments"] if item["day_key"] == day)
        result = assign_event_reassignments(
            db, "j", "source", [fid], target_mode="new_no_event", segments=[segment],
        )
        assert result["target"]["folder_name"] == f"{month} - No Event"
        with database_connection(db) as connection:
            target = connection.execute(
                "SELECT start_datetime,event_kind FROM events WHERE id=?",
                (result["target"]["event_id"],),
            ).fetchone()
            assert target["start_datetime"][:4] == year
            assert target["event_kind"] == "no_event"
    assert list_event_reassignments(db, "j", "source")["family_count"] == 0



def test_cross_job_no_event_workspace_target_finishes_applied_reassignment(tmp_path):
    from app.database import assign_free_families_to_existing_no_event, list_global_tasks
    from app.sort_apply import execute_sort_run, prepare_sort_run
    from app.sort_plan import build_event_sort_plan
    from tests.backend.test_0167_tasks_and_no_event import (
        add_family as add_other_family,
        create_no_event,
        seed_job as seed_other_job,
    )
    from tests.backend.test_0250_continuous import attach_files, create, payload, setup

    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    setup(db, ["2026-07-23T10:00:00"])
    source = create(db, payload("2026-07-23T00:00", "2026-07-23T23:59"))["parent_event"]
    attach_files(db, workspace, source["id"])
    seed_other_job(db, "other", "OTHER")
    other_family = add_other_family(db, "other", "OTHER", "2026-07-15T09:00:00")
    other_target = create_no_event(db, "other", other_family, "2026-07-15")

    delete_planned_event(db, "j", source["id"])
    source_plan = build_workspace_reconcile_plan(db, "j", source["id"], workspace)
    assert source_plan["summary"]["ready"], source_plan["blockers"]
    source_run = prepare_workspace_reconcile_run(
        db, "j", source["id"], workspace,
        expected_plan_token=source_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, source_run["id"], workspace)
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM events WHERE id=?", (source["id"],)
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE job_id='j'"
        ).fetchone()[0] == 1

    result = assign_free_families_to_existing_no_event(
        db, "j", other_target["id"],
        [{"day_key": "2026-07-23", "start_time": "00:00", "end_time": "23:59"}],
    )
    assert result["cross_job"] is True
    target_id = result["event_id"]
    list_global_tasks(db)
    with database_connection(db) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM released_free_families WHERE job_id='j'"
        ).fetchone()[0] == 0
    target_plan = build_event_sort_plan(db, "j", target_id, workspace)
    assert target_plan["summary"]["ready"], target_plan["blockers"]
    target_run = prepare_sort_run(
        db, "j", target_id, workspace,
        expected_plan_token=target_plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_sort_run(db, target_run["id"], workspace)

    with database_connection(db) as connection:
        target = connection.execute(
            "SELECT status,event_kind,linked_event_id,job_id FROM events WHERE id=?", (target_id,)
        ).fetchone()
        assert target_id == other_target["id"]
        assert tuple(target) == ("applied", "no_event", None, "other")
        segments = connection.execute(
            "SELECT day_key,start_time,end_time FROM event_time_segments WHERE event_id=? ORDER BY day_key,start_time",
            (target_id,),
        ).fetchall()
        assert [tuple(row) for row in segments] == [
            ("2026-07-15", "08:00", "12:00"),
            ("2026-07-23", "00:00", "23:59"),
        ]
        file_row = connection.execute(
            "SELECT current_relative_path,sha256_current FROM files WHERE job_id='j'"
        ).fetchone()
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id=?",
            (source["id"],),
        ).fetchone()[0] == 0
    path = workspace / "Arbeitsbereich" / file_row["current_relative_path"]
    assert path.read_bytes() == b"1"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == file_row["sha256_current"]
    assert len(list((workspace / "Arbeitsbereich").rglob("1.JPG"))) == 1