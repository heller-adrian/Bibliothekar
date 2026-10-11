"""0.50.8: regression guards for removed/renamed children and archive cleanup."""
from contextlib import contextmanager
from pathlib import Path
import json

from app.database import create_job, database_connection, initialize_database
from app.sort_plan import (
    _observed_organization_path,
    _reapply_original_child_folder_names,
)
from app import archive_staging


def test_0475_removed_child_is_not_treated_as_user_organization():
    inventory = {"event_relative_path": "2025-12-04 - Teil 04/Alle/IMG.JPG"}
    assert _observed_organization_path(
        inventory, child_folder_names={"2025-12-04 - Teil 04"}
    ).as_posix() == "Alle"
    assert _observed_organization_path(
        {"event_relative_path": "2025-12-04 - Teil 04/2025-12-04/Alle/IMG.JPG"},
        child_folder_names={"2025-12-04 - Teil 04"},
    ).as_posix() == "Alle"


def test_0475_keeps_real_user_organization_when_child_was_removed():
    assert _observed_organization_path(
        {"event_relative_path": "Eigenes/Sortiert/IMG.JPG"},
        child_folder_names={"2025-12-04 - Teil 04"},
    ).as_posix() == "Eigenes/Sortiert"


def test_0475_original_children_survive_sqlite_soll_change(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    create_job(
        db, job_id="J", kind="sd_import", trigger_type="approved_sd",
        source_path="/source", working_path="/workspace",
        operation="folder_import",
    )
    old_state = {"events": [
        {"id": "E", "parent_event_id": None, "folder_name": "Erste Hälfte"},
        {"id": "C", "parent_event_id": "E", "folder_name": "Teil 04"},
    ]}
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO event_mutations(
                   id,job_id,anchor_event_id,mutation_kind,status,
                   affected_event_ids_json,original_state_json,target_state_json,
                   created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            ("M", "J", "E", "edit", "pending_apply", '["E"]',
             json.dumps(old_state), "{}", "2026-10-09", "2026-10-09"),
        )
    assert _reapply_original_child_folder_names(db, "J", "E") == {"Teil 04"}
    assert _reapply_original_child_folder_names(db, "J", "other") == set()


def test_0475_archived_empty_child_is_in_manual_removal_plan(monkeypatch, tmp_path):
    class FakeCursor:
        def fetchall(self):
            return [{"folder_name": "Teil 04"}, {"folder_name": "Erhalten"}]
    class FakeConnection:
        def execute(self, sql, args):
            assert "SELECT folder_name FROM events" in sql
            assert args == ("E",)
            return FakeCursor()
    @contextmanager
    def fake_connection(_):
        yield FakeConnection()
    monkeypatch.setattr(archive_staging, "database_connection", fake_connection)
    monkeypatch.setattr(
        archive_staging, "_current_event_root",
        lambda db, eid: archive_staging.PurePosixPath("2025", "Ereignis"),
    )
    preview = {
        "start_date": "2025-12-04", "parent_folder": "Ereignis",
        "subevents": [{"folder_name": "Erhalten"}],
    }
    result = archive_staging._obsolete_directories_from_plan(
        tmp_path / "db.sqlite3", "E", preview,
        {"families_with_plans": [], "assets_with_plans": []},
    )
    assert result == ["2025/Ereignis/Teil 04"]


def test_0475_release_and_background_dock_contract():
    from app import __version__, main
    from app.ui_shell import BIBLIOTHEKAR_0444_JS, BIBLIOTHEKAR_0450_CSS
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == "0.50.8"
    assert 'bk-activity-progress' in BIBLIOTHEKAR_0444_JS
    assert 'progress_percent' in BIBLIOTHEKAR_0444_JS
    assert "Liberation Mono" in BIBLIOTHEKAR_0450_CSS
    assert ".change-target-tree" in BIBLIOTHEKAR_0450_CSS


def test_0475_background_dock_uses_existing_batch_progress(monkeypatch, tmp_path):
    from app import background_activity

    class Cursor:
        def __init__(self, rows):
            self.rows = rows
        def fetchall(self):
            return self.rows

    class Connection:
        def execute(self, sql):
            if "FROM operation_batches" in sql:
                return Cursor([{
                    "id": "B", "status": "running",
                    "item_count": 2, "completed_item_count": 0,
                }])
            if "FROM sort_runs" in sql or "FROM jobs" in sql:
                return Cursor([])
            raise AssertionError(sql)

    @contextmanager
    def fake_connection(_):
        yield Connection()

    monkeypatch.setattr(background_activity, "database_connection", fake_connection)
    monkeypatch.setattr(
        background_activity, "get_operation_batch",
        lambda db, batch_id: {"progress_percent": 37},
    )
    monkeypatch.setattr(background_activity, "list_visible", lambda db, limit: [])
    operations = background_activity.current_activity(
        tmp_path / "library.db", tmp_path / "imports.db"
    )["operations"]
    assert len(operations) == 1
    assert operations[0]["progress_percent"] == 37


def test_0475_removed_applied_subevent_is_physically_flattened(tmp_path):
    """Reproduce Teil-04/Alle -> Alle across the actual verified reconcile run."""
    import hashlib
    from app.database import update_event_definition
    from app.event_document import build_event_document_from_db, write_event_document
    from app.sort_apply import CONFIRMATION_PHRASE
    from app.workspace_reconcile import (
        build_workspace_reconcile_plan, execute_workspace_reconcile_run,
        prepare_workspace_reconcile_run,
    )

    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    root = workspace / "Arbeitsbereich"
    root.mkdir(parents=True)
    (workspace / "imports" / "j").mkdir(parents=True)
    initialize_database(db)
    child_root = root / "2025" / "Ereignis" / "Teil 04"
    initial_paths = {
        "CHILD.JPG": "2025/Ereignis/Teil 04/Alle/CHILD.JPG",
        "PARENT.JPG": "2025/Ereignis/Alle/PARENT.JPG",
    }
    families = []
    with database_connection(db) as c:
        c.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,working_path,
                   created_at,updated_at
               ) VALUES('j','sd_import','manual','completed','event_sort_applied',
                        'folder_import',?,'now','now')""",
            (str(workspace / "imports" / "j"),),
        )
        c.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision,applied_at,time_model_version
               ) VALUES('E','j','parent','Ereignis','2025-12-04T00:00:00',
                        '2026-01-02T23:59:59',0,'Ereignis',
                        'applied','now','now','event',0,1,'now',2)"""
        )
        c.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,
                   end_datetime,uses_time_range,folder_name,status,created_at,
                   updated_at,event_kind,preserve_day_folders,revision,applied_at,
                   time_model_version
               ) VALUES('C','j','E','child','Teil 04','2025-12-04T14:00:00',
                        '2025-12-04T16:00:59',1,'Teil 04',
                        'applied','now','now','event',0,1,'now',2)"""
        )
        for name, capture, eid in (
            ("CHILD.JPG", "2025-12-04T15:00:00", "C"),
            ("PARENT.JPG", "2025-12-05T12:00:00", "E"),
        ):
            relative = initial_paths[name]
            content = name.encode()
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            fid = int(c.execute(
                """INSERT INTO file_families(
                       job_id,family_key,original_stem,status,
                       selected_capture_time,capture_time_confidence
                   ) VALUES('j',?,?,'complete',?,'high')""",
                (name, name, capture),
            ).lastrowid)
            families.append(fid)
            c.execute(
                """INSERT INTO event_assignments(
                       event_id,family_id,file_id,assignment_source,created_at
                   ) VALUES(?,?,NULL,'date_time_range','now')""",
                (eid, fid),
            )
            digest = hashlib.sha256(content).hexdigest()
            c.execute(
                """INSERT INTO files(
                       job_id,family_id,original_relative_path,current_relative_path,
                       original_filename,extension,media_type,size_bytes,
                       sha256_original,sha256_current,selected_capture_time,
                       selected_capture_source,capture_time_confidence,
                       review_status,metadata_write_status,created_at,updated_at,
                       current_root_kind
                   ) VALUES('j',?,?,?,?,'.JPG','jpeg',?,?,?,?,'DateTimeOriginal',
                            'high','not_required','not_requested','now','now',
                            'shared_workspace')""",
                (fid, relative, relative, name, len(content), digest, digest, capture),
            )
        c.commit()

    write_event_document(
        workspace, build_event_document_from_db(db, workspace, "j", "E")
    )
    change = update_event_definition(
        db, "j", "E",
        {
            "selected_family_ids": families,
            "start_date": "2025-12-04", "end_date": "2026-01-02",
            "start_time": "00:00", "end_time": "23:59",
            "uses_time_range": False, "parent_folder": "Ereignis",
            "child_folder": "", "event_kind": "event",
            "preserve_day_folders": False,
        },
        event_name="Ereignis", notes="", expected_revision=1,
        workspace_path=workspace,
    )
    assert change["resort_required"]
    plan = build_workspace_reconcile_plan(db, "j", "E", workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    dests = {str(f["destination_relative_path"]) for f in plan["files"]}
    assert "2025/Ereignis/Alle/CHILD.JPG" in dests
    assert "2025/Ereignis/Alle/PARENT.JPG" in dests
    assert all("/Teil 04/" not in path for path in dests)
    run = prepare_workspace_reconcile_run(
        db, "j", "E", workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    execute_workspace_reconcile_run(db, run["id"], workspace)
    assert (root / "2025/Ereignis/Alle/CHILD.JPG").read_bytes() == b"CHILD.JPG"
    assert (root / "2025/Ereignis/Alle/PARENT.JPG").read_bytes() == b"PARENT.JPG"
    assert not child_root.exists()
    with database_connection(db) as c:
        children = c.execute(
            "SELECT COUNT(*) FROM events WHERE parent_event_id='E'"
        ).fetchone()[0]
        paths = {
            str(row[0]) for row in c.execute(
                "SELECT current_relative_path FROM files WHERE job_id='j'"
            )
        }
    assert children == 0
    assert paths == dests
