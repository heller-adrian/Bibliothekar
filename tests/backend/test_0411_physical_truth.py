from __future__ import annotations

from pathlib import Path
import hashlib

from app.central_stock_reconcile import reconcile_central_free_stock
from app.database import create_job, database_connection, initialize_database
from app.operation_batches import create_apply_batch
from app.sort_apply import CONFIRMATION_PHRASE
from app.workspace_layout import ensure_workspace_layout


NOW = "2026-10-05T20:00:00+00:00"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _seed_free_file(db: Path, relative: str, data: bytes) -> tuple[int, int]:
    create_job(
        db,
        job_id="J",
        kind="sd_import",
        trigger_type="approved_sd",
        source_path="/source",
        working_path="/workspace",
        operation="folder_import",
    )
    with database_connection(db) as connection:
        # This helper represents successfully published free stock.
        connection.execute("UPDATE jobs SET state='completed' WHERE id='J'")
        family = connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence)
               VALUES ('J','F','F','complete','2026-10-05T12:00:00','high')"""
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
                family_id, relative, relative, Path(relative).name, len(data),
                _sha(data), _sha(data), "2026-10-05T12:00:00", NOW, NOW,
            ),
        )
        return family_id, int(file_row.lastrowid)


def test_0411_central_missing_needs_two_complete_scans(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    relative = "2026/2026-10-05/A.JPG"
    family_id, file_id = _seed_free_file(db, relative, b"camera")
    target = central / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"camera")
    reconcile_central_free_stock(db, workspace, library_id="main", excluded_family_ids=set())

    target.unlink()
    first = reconcile_central_free_stock(db, workspace, library_id="main", excluded_family_ids=set())
    assert first["pending_missing_count"] == 1
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (file_id,)).fetchone()

    second = reconcile_central_free_stock(db, workspace, library_id="main", excluded_family_ids=set())
    assert second["deleted_file_count"] == 1
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (file_id,)).fetchone() is None
        assert connection.execute("SELECT 1 FROM file_families WHERE id=?", (family_id,)).fetchone() is None


def test_0411_moved_free_file_is_not_misread_as_deletion(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    initialize_database(db)
    layout = ensure_workspace_layout(workspace)
    central = Path(layout["backup_root"])

    relative = "2026/2026-10-05/A.JPG"
    _family_id, file_id = _seed_free_file(db, relative, b"camera-move")
    source = central / relative
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"camera-move")
    reconcile_central_free_stock(db, workspace, library_id="main", excluded_family_ids=set())

    wrong = central / "2026/2026-10-06/A.JPG"
    wrong.parent.mkdir(parents=True, exist_ok=True)
    source.replace(wrong)
    result = reconcile_central_free_stock(db, workspace, library_id="main", excluded_family_ids=set())
    assert result["misplaced_file_count"] == 1
    with database_connection(db) as connection:
        assert connection.execute("SELECT 1 FROM files WHERE id=?", (file_id,)).fetchone()
        notice = connection.execute(
            "SELECT kind,repairable FROM external_change_notices WHERE status='open' AND file_id=?",
            (file_id,),
        ).fetchone()
    assert notice is not None
    assert str(notice["kind"]) == "placement_conflict"
    assert int(notice["repairable"]) == 1


def test_0411_operation_batch_is_durable_before_execution(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    create_job(
        db, job_id="J", kind="sd_import", trigger_type="approved_sd",
        source_path="/source", working_path="/workspace", operation="folder_import",
    )
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

    batch = create_apply_batch(
        db,
        [{"job_id":"J","event_id":"E","plan_token":"TOKEN"}],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    assert batch["status"] == "queued"
    assert batch["item_count"] == 1
    assert batch["items"][0]["status"] == "pending"


def test_0411_workspace_uses_server_side_apply_batch():
    source = Path("app/workspace_ui.py").read_text(encoding="utf-8")
    assert "/api/operation-batches/apply-events" in source
    assert "/api/operation-batches/active" in source
