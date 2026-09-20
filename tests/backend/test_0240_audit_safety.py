import hashlib
from pathlib import Path

import pytest

import app.applied_neutralization as neutralization
import app.event_document as event_document
from app.applied_neutralization import AppliedNeutralizationError
from app.database import database_connection, initialize_database
from app.sort_apply import (
    CONFIRMATION_PHRASE,
    SortApplyError,
    execute_sort_run,
    prepare_sort_run,
)
from app.sort_plan import build_event_sort_plan
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from tests.backend.test_01610_reconcile import seed as seed_reconcile
from tests.backend.test_0204_applied_neutralization import _seed as seed_neutralization


NOW = "2026-09-21T00:00:00+00:00"


def _seed_initial_sort(tmp_path: Path):
    db = tmp_path / "initial.sqlite3"
    workspace = tmp_path / "workspace"
    incoming = workspace / "incoming"
    work = workspace / "Arbeitsbereich"
    incoming.mkdir(parents=True)
    work.mkdir(parents=True)
    initialize_database(db)

    payload = b"initial-sort"
    source = incoming / "IMG.JPG"
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    with database_connection(db) as c:
        c.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   working_path,created_at,updated_at
               ) VALUES (
                   'j','folder_import','manual','completed','organized_verified',
                   'folder_import','TEST',?,?,?
               )""",
            (str(incoming), NOW, NOW),
        )
        fid = int(c.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,selected_capture_time,
                   capture_time_confidence
               ) VALUES (
                   'j','F1','IMG','complete','2026-07-19T10:00:00','high'
               )"""
        ).lastrowid)
        c.execute(
            """INSERT INTO events(
                   id,job_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,
                   event_kind,preserve_day_folders,revision
               ) VALUES (
                   'e','j','parent','Test','2026-07-19T00:00:00',
                   '2026-07-19T23:59:59',0,'07-19 - Test','planned',
                   ?,?,'event',0,1
               )""",
            (NOW, NOW),
        )
        c.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('e',?,NULL,'date_range',?)""",
            (fid, NOW),
        )
        file_id = int(c.execute(
            """INSERT INTO files(
                   job_id,family_id,original_relative_path,current_relative_path,
                   original_filename,extension,media_type,size_bytes,
                   sha256_original,sha256_current,selected_capture_time,
                   selected_capture_source,capture_time_confidence,review_status,
                   metadata_write_status,created_at,updated_at,current_root_kind
               ) VALUES (
                   'j',?,'IMG.JPG','IMG.JPG','IMG.JPG','.JPG','jpeg',?,
                   ?,?,'2026-07-19T10:00:00','DateTimeOriginal','high',
                   'not_required','not_requested',?,?,'job_root'
               )""",
            (fid, len(payload), digest, digest, NOW, NOW),
        ).lastrowid)
        c.commit()

    return db, workspace, incoming, work, file_id, payload


def test_0240_reconcile_refuses_new_target_blocker_after_prepare(tmp_path: Path):
    db = tmp_path / "reconcile.sqlite3"
    workspace = tmp_path / "workspace"
    seed_reconcile(db, workspace)

    plan = build_workspace_reconcile_plan(db, "j", "a", workspace)
    assert plan["summary"]["ready"] is True
    moving = next(item for item in plan["files"] if item["status"] == "move")

    run = prepare_workspace_reconcile_run(
        db,
        "j",
        "a",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )

    source = Path(moving["source_absolute_path"])
    destination = Path(moving["destination_absolute_path"])
    original_relative = str(moving["source_relative_path"])
    foreign = b"foreign-target"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(foreign)

    with pytest.raises(SortApplyError, match="Blocker"):
        execute_workspace_reconcile_run(db, run["id"], workspace)

    assert source.exists()
    assert destination.read_bytes() == foreign
    with database_connection(db) as c:
        file_row = c.execute(
            "SELECT current_relative_path FROM files WHERE id=?",
            (int(moving["file_id"]),),
        ).fetchone()
        run_row = c.execute(
            "SELECT status FROM sort_runs WHERE id=?",
            (run["id"],),
        ).fetchone()
    assert file_row["current_relative_path"] == original_relative
    assert run_row["status"] == "failed"


def test_0240_event_document_failure_keeps_committed_sort_consistent(
    tmp_path: Path,
    monkeypatch,
):
    db, workspace, incoming, work, file_id, payload = _seed_initial_sort(tmp_path)

    plan = build_event_sort_plan(db, "j", "e", workspace)
    assert plan["summary"]["ready"] is True
    destination_relative = str(plan["files"][0]["destination_relative_path"])
    destination = work / destination_relative

    run = prepare_sort_run(
        db,
        "j",
        "e",
        workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )

    def fail_event_document(*args, **kwargs):
        raise OSError("simulierter event.json-Schreibfehler")

    monkeypatch.setattr(
        event_document,
        "sync_event_document_after_change",
        fail_event_document,
    )

    # A02: the sort itself is already safely committed; event.json failure is
    # recorded as a warning and must not roll the physical files back.
    execute_sort_run(db, run["id"], workspace)

    assert not (incoming / "IMG.JPG").exists()
    assert destination.read_bytes() == payload

    with database_connection(db) as c:
        file_row = c.execute(
            "SELECT current_relative_path,current_root_kind FROM files WHERE id=?",
            (file_id,),
        ).fetchone()
        event_row = c.execute(
            "SELECT status,applied_at FROM events WHERE id='e'"
        ).fetchone()
        run_row = c.execute(
            "SELECT status,error_message,details_json FROM sort_runs WHERE id=?",
            (run["id"],),
        ).fetchone()
        audit = c.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='event_document_sync_failed' AND entity_id='e'"
        ).fetchone()[0]

    assert file_row["current_relative_path"] == destination_relative
    assert file_row["current_root_kind"] == "shared_workspace"
    assert event_row["status"] == "applied"
    assert event_row["applied_at"] is not None
    assert run_row["status"] == "applied"
    assert "event.json" in str(run_row["error_message"])
    assert "event_document_sync_error" in str(run_row["details_json"])
    assert audit == 1


def test_0240_neutralization_hash_failure_rolls_back_just_moved_file(
    tmp_path: Path,
    monkeypatch,
):
    db, workspace, ids, folder = seed_neutralization(tmp_path, no_event=False)
    removed_id = ids[1]
    root = workspace / "Arbeitsbereich"

    with database_connection(db) as c:
        before = [
            str(row["current_relative_path"])
            for row in c.execute(
                "SELECT current_relative_path FROM files WHERE family_id=? ORDER BY id",
                (removed_id,),
            ).fetchall()
        ]

    real_sha = neutralization._sha256

    def fail_only_after_move(path: Path) -> str:
        if "Nicht zugeordnet" in path.parts:
            return "0" * 64
        return real_sha(path)

    monkeypatch.setattr(neutralization, "_sha256", fail_only_after_move)

    with pytest.raises(AppliedNeutralizationError, match="nach Neutralisierung"):
        neutralization.neutralize_removed_applied_families(
            db,
            workspace,
            job_id="j",
            event_id="src",
            family_ids=[removed_id],
            mutation_id=None,
        )

    with database_connection(db) as c:
        after = [
            str(row["current_relative_path"])
            for row in c.execute(
                "SELECT current_relative_path FROM files WHERE family_id=? ORDER BY id",
                (removed_id,),
            ).fetchall()
        ]

    assert after == before
    assert all((root / rel).is_file() for rel in before)
    neutral_dir = root / "Nicht zugeordnet" / "2026" / "09"
    if neutral_dir.exists():
        assert not any(neutral_dir.iterdir())


def test_0240_workspace_apply_button_has_explicit_blue_override():
    from app.ui_shell import BIBLIOTHEKAR_CSS

    assert 'body[data-bk-area="workspace"] #apply-saved-event-button {' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-blue) !important;' in BIBLIOTHEKAR_CSS
