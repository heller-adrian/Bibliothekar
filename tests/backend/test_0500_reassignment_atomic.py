"""0.50.0 BA-08: transactional event-family reassignment.

All tests operate on temporary, synthetic SQLite databases.
"""
import json

import pytest

from app.database import database_connection, delete_planned_event
from app.event_reassignment import (
    assign_event_reassignments, list_event_reassignments,
)
from tests.backend.test_0172_reassignment_target_state import _make_applied
from tests.backend.test_0163_reassignment import (
    seed, edit_drop_second,
)


def _applied_source(tmp_path):
    db = tmp_path / "reassign.sqlite3"
    family_ids = _make_applied(db)
    delete_planned_event(db, "j", "b")
    with database_connection(db) as connection:
        connection.execute("UPDATE events SET resort_required=0 WHERE id='b'")
    segments = list_event_reassignments(db, "j", "b")["reassignment_segments"]
    return db, family_ids[4:], segments


@pytest.mark.parametrize("target_mode", ["new_event", "new_no_event"])
def test_0500_new_target_rolls_back_if_final_queue_update_fails(
    tmp_path, monkeypatch, target_mode,
):
    db, selected, segments = _applied_source(tmp_path)
    before = {}
    with database_connection(db) as connection:
        before["events"] = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        before["assignments"] = connection.execute(
            "SELECT COUNT(*) FROM event_assignments"
        ).fetchone()[0]
        before["pending"] = connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families "
            "WHERE event_id='b' AND target_event_id IS NULL"
        ).fetchone()[0]

    import app.event_mutation as mutation
    def fault(*args, **kwargs):
        raise RuntimeError("BA08 injected transaction failure")
    monkeypatch.setattr(mutation, "advance_job_mutation_after_reassignment", fault)
    with pytest.raises(RuntimeError, match="BA08 injected"):
        assign_event_reassignments(
            db, "j", "b", selected, target_mode=target_mode,
            new_event_name="Neuer Zeitabschnitt" if target_mode == "new_event" else None,
            segments=segments,
        )
    with database_connection(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before["events"]
        assert connection.execute("SELECT COUNT(*) FROM event_assignments").fetchone()[0] == before["assignments"]
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families "
            "WHERE event_id='b' AND target_event_id IS NULL"
        ).fetchone()[0] == before["pending"]
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='event_families_reassigned'"
        ).fetchone()[0] == 0
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("target_mode", ["new_event", "new_no_event"])
def test_0500_new_target_retries_reuse_identical_commit(tmp_path, target_mode):
    db, selected, segments = _applied_source(tmp_path)
    kwargs = dict(
        target_mode=target_mode,
        new_event_name="Neuer Zeitabschnitt" if target_mode == "new_event" else None,
        segments=segments,
    )
    first = assign_event_reassignments(db, "j", "b", selected, **kwargs)
    with database_connection(db) as connection:
        before = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        assignments = connection.execute("SELECT COUNT(*) FROM event_assignments").fetchone()[0]
    second = assign_event_reassignments(db, "j", "b", selected, **kwargs)
    assert second["idempotent_replay"] is True
    assert second["target"]["event_id"] == first["target"]["event_id"]
    with database_connection(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == before
        assert connection.execute("SELECT COUNT(*) FROM event_assignments").fetchone()[0] == assignments
        assert connection.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action='event_families_reassigned'"
        ).fetchone()[0] == 1


def test_0500_existing_no_event_target_rolls_back_if_queue_fails(tmp_path, monkeypatch):
    db = tmp_path / "target.sqlite3"
    ids = seed(db, source_status="applied")
    edit_drop_second(db, ids)
    with database_connection(db) as connection:
        connection.execute("UPDATE events SET resort_required=0 WHERE id='src'")
    segments = list_event_reassignments(db, "j", "src")["reassignment_segments"]
    with database_connection(db) as connection:
        prior = connection.execute(
            "SELECT revision FROM events WHERE id='target'"
        ).fetchone()[0]
        assignments = connection.execute(
            "SELECT COUNT(*) FROM event_assignments WHERE event_id='target'"
        ).fetchone()[0]

    import app.event_mutation as mutation
    def fault(*args, **kwargs):
        raise RuntimeError("BA08 injected failure")
    monkeypatch.setattr(mutation, "advance_job_mutation_after_reassignment", fault)
    with pytest.raises(RuntimeError, match="BA08 injected"):
        assign_event_reassignments(
            db, "j", "src", [ids[1]], target_mode="existing_no_event",
            target_event_id="target", segments=segments,
        )
    with database_connection(db) as connection:
        assert connection.execute("SELECT revision FROM events WHERE id='target'").fetchone()[0] == prior
        assert connection.execute(
            "SELECT COUNT(*) FROM event_assignments WHERE event_id='target'"
        ).fetchone()[0] == assignments
        assert connection.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families "
            "WHERE event_id='src' AND target_event_id IS NULL"
        ).fetchone()[0] == 1


def test_0500_new_event_commit_in_external_transaction_can_be_reversed(tmp_path):
    from app.database import create_planned_event
    from app.event_structure import build_event_preview
    from app.planning import list_job_available_families

    db = tmp_path / "parent.sqlite3"
    selected = seed(db, source_status="planned")
    # Use only one family and explicitly ignore the existing source event;
    # the parent write must stay pending inside the caller's transaction.
    available = [
        row for row in list_job_available_families(db, "j")
        if int(row["family_id"]) == selected[0]
    ]
    if not available:
        pytest.skip("fixture has no free family before editing")
    preview = build_event_preview({
        "event_kind": "event", "event_name": "Test",
        "start_date": "2026-09-07", "end_date": "2026-09-07",
        "start_time": "09:00", "end_time": "11:00",
        "uses_time_range": True, "selected_family_ids": [selected[0]]
    }, available)
    with pytest.raises(RuntimeError, match="rollback marker"):
        with database_connection(db) as connection:
            connection.execute("BEGIN IMMEDIATE")
            create_planned_event(
                db, "j", preview, ignore_event_ids={"src"},
                transaction_connection=connection,
            )
            raise RuntimeError("rollback marker")
    with database_connection(db) as connection:
        assert connection.execute("SELECT COUNT(*) FROM events WHERE name='Test'").fetchone()[0] == 0
