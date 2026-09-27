from pathlib import Path

from app.database import database_connection, delete_planned_event
from app.event_reassignment import assign_event_reassignments, list_event_reassignments
from app.events_ui import EVENTS_HTML
from tests.backend.test_0171_stability import _seed_two_planned, NOW


def _make_applied(db: Path):
    fids = _seed_two_planned(db)
    with database_connection(db) as c:
        c.execute("UPDATE events SET status='applied',applied_at=? WHERE id IN ('a','ac','b','bc')", (NOW,))
        c.commit()
    return fids


def _segments(db: Path):
    return list_event_reassignments(db, 'j', 'b')['reassignment_segments']



def test_delete_reassignment_new_event_ignores_source_event_being_deleted(tmp_path):
    db = tmp_path / 'db.sqlite3'
    fids = _make_applied(db)
    result = delete_planned_event(db, 'j', 'b')
    assert result['reassignment_required'] is False
    assert result['removed_family_ids'] == fids[4:]
    with database_connection(db) as c:
        source = c.execute(
            "SELECT pending_delete,resort_required,status FROM events WHERE id='b'"
        ).fetchone()
        assert tuple(source) == (1, 1, 'applied')
        assert c.execute(
            "SELECT COUNT(*) FROM event_assignments WHERE event_id='b'"
        ).fetchone()[0] == 0
        assert c.execute(
            "SELECT COUNT(*) FROM event_reapply_removed_families "
            "WHERE event_id='b' AND target_event_id IS NULL"
        ).fetchone()[0] == len(fids[4:])
        assert c.execute(
            "SELECT status FROM event_mutations WHERE anchor_event_id='b' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0] == 'pending_apply'
def test_delete_reassignment_new_no_event_ignores_source_event_being_deleted(tmp_path):
    db = tmp_path / 'db.sqlite3'
    fids = _make_applied(db)
    delete_planned_event(db, 'j', 'b')
    with database_connection(db) as c:
        c.execute("UPDATE events SET resort_required=0 WHERE id='b'")

    reassigned = assign_event_reassignments(
        db, 'j', 'b', fids[4:], target_mode='new_no_event', segments=_segments(db)
    )
    assert reassigned['pending_family_count'] == 0
    with database_connection(db) as c:
        target_id = reassigned['target']['event_id']
        target = c.execute("SELECT event_kind,status FROM events WHERE id=?", (target_id,)).fetchone()
        assert tuple(target) == ('no_event', 'planned')
        assert c.execute("SELECT COUNT(*) FROM event_time_segments WHERE event_id=?", (target_id,)).fetchone()[0] == 1
        assert c.execute("SELECT status FROM event_mutations WHERE anchor_event_id='b'").fetchone()[0] == 'pending_apply'


def test_ui_keeps_delete_action_visible_but_disabled_during_open_mutation():
    assert 'Offene Änderung dieser Sicherung zuerst abschließen oder verwerfen' in EVENTS_HTML
    assert '<button type="button" class="danger-button" disabled' in EVENTS_HTML
