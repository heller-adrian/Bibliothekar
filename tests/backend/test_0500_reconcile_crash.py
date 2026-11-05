"""BA-07: real-process crash boundary for workspace reconciliation.

Uses only tmp_path with synthetic files and SQLite. Never touches the NAS.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from app.database import database_connection, get_event_edit_context, update_event_definition
from app.event_structure import build_event_preview
from app.sort_apply import CONFIRMATION_PHRASE, mark_incomplete_sort_runs_interrupted, recover_interrupted_sort_runs
from app.workspace_reconcile import (
    build_workspace_reconcile_plan,
    execute_workspace_reconcile_run,
    prepare_workspace_reconcile_run,
)
from tests.backend.test_0250_continuous import setup, create, payload, attach_files


def _seed_reconcile(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    workspace = tmp_path / "workspace"
    setup(db, ["2026-07-23T10:00:00", "2026-07-23T14:00:00", "2026-07-23T18:00:00"])
    event = create(db, payload("2026-07-23T00:00", "2026-07-23T23:59"))["parent_event"]
    attach_files(db, workspace, event["id"])
    edited_payload = payload()
    preview = build_event_preview(
        edited_payload, get_event_edit_context(db, "j", event["id"])["families"]
    )
    update_event_definition(
        db, "j", event["id"], preview,
        event_name="Urlaub", notes="", expected_revision=1,
        workspace_path=workspace,
    )
    plan = build_workspace_reconcile_plan(db, "j", event["id"], workspace)
    assert plan["summary"]["ready"], plan["blockers"]
    assert plan["summary"]["move_count"] > 0
    run = prepare_workspace_reconcile_run(
        db, "j", event["id"], workspace,
        expected_plan_token=plan["plan_token"],
        confirmation_phrase=CONFIRMATION_PHRASE,
    )
    return db, workspace, plan, run


def test_0500_crash_after_path_commit_keeps_canonical_files(tmp_path):
    db, workspace, plan, run = _seed_reconcile(tmp_path)
    child_script = """
import os, sys
from pathlib import Path
import app.obsolete_structure as obsolete
from app.workspace_reconcile import execute_workspace_reconcile_run
obsolete.cleanup_obsolete_structure = lambda *args, **kwargs: os._exit(42)
execute_workspace_reconcile_run(Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3]))
"""
    proc = subprocess.run(
        [sys.executable, "-c", child_script, str(db), str(run["id"]), str(workspace)],
        capture_output=True, text=True, check=False,
    )
    assert proc.returncode == 42, proc.stderr
    # A process restart must not incorrectly reverse paths confirmed by SQLite.
    mark_incomplete_sort_runs_interrupted(db)
    recover_interrupted_sort_runs(db)
    with database_connection(db) as connection:
        for item in plan["files"]:
            row = connection.execute(
                "SELECT current_relative_path FROM files WHERE id=?",
                (int(item["file_id"]),),
            ).fetchone()
            assert row is not None
            assert row["current_relative_path"] == item["destination_relative_path"]
            assert Path(item["destination_absolute_path"]).is_file()
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


def test_0500_exception_before_commit_reverses_moves(tmp_path, monkeypatch):
    import app.event_mutation as mutation

    db, workspace, plan, run = _seed_reconcile(tmp_path)
    originals = {
        int(row["file_id"]): Path(row["source_absolute_path"])
        for row in plan["files"]
    }

    def break_before_commit(*_args, **_kwargs):
        raise RuntimeError("test fault before commit")

    monkeypatch.setattr(mutation, "mark_job_mutation_completed", break_before_commit)
    with pytest.raises(RuntimeError, match="test fault before commit"):
        execute_workspace_reconcile_run(db, run["id"], workspace)

    with database_connection(db) as connection:
        for item in plan["files"]:
            row = connection.execute(
                "SELECT current_relative_path FROM files WHERE id=?",
                (int(item["file_id"]),),
            ).fetchone()
            assert row is not None
            assert row["current_relative_path"] == item["source_relative_path"]
            assert originals[int(item["file_id"])].is_file()
