from pathlib import Path
import hashlib
import pytest

from app.database import initialize_database, database_connection, delete_planned_event
from app.event_mutation import (
    capture_job_event_state,
    begin_mutation,
    set_mutation_target,
    cancel_mutation,
)
from app.workspace_reconcile import build_workspace_reconcile_plan
from app.events_ui import EVENTS_HTML
from tests.backend.test_01610_reconcile import seed, NOW


def _simple_applied(db: Path):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) "
            "VALUES ('j','sd_import','manual','completed','event_sort_applied','folder_import','TEST',?,?)",
            (NOW, NOW),
        )
        fid = int(c.execute(
            "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) "
            "VALUES ('j','F1','F1','complete','2026-07-19T10:00:00','high')"
        ).lastrowid)
        c.execute(
            """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,
               created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,resort_required)
               VALUES ('e','j','parent','Original','2026-07-19T00:00:00','2026-07-19T23:59:59',0,
               '07-19 - Original','applied',?,?,'event',0,1,?,0)""",
            (NOW, NOW, NOW),
        )
        c.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('e',?,NULL,'date_range',?)",
            (fid, NOW),
        )
        c.commit()
    return fid


def test_schema_019_has_durable_mutations(tmp_path):
    db = tmp_path / 'db.sqlite3'
    info = initialize_database(db)
    assert 19 in info['applied_versions']
    with database_connection(db) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_mutations'").fetchone()


def test_pending_mutation_can_restore_original_event_graph(tmp_path):
    db = tmp_path / 'db.sqlite3'
    fid = _simple_applied(db)
    with database_connection(db) as c:
        original = capture_job_event_state(c, 'j')
        mid = begin_mutation(
            c, job_id='j', anchor_event_id='e', mutation_kind='edit',
            affected_event_ids=['e'], original_state=original, status='pending_apply',
        )
        c.execute("UPDATE events SET name='Changed',folder_name='07-19 - Changed',resort_required=1 WHERE id='e'")
        c.execute("DELETE FROM event_assignments WHERE event_id='e'")
        c.execute(
            "INSERT INTO event_reapply_removed_families(event_id,job_id,family_id,created_at) VALUES ('e','j',?,?)",
            (fid, NOW),
        )
        set_mutation_target(c, mid, capture_job_event_state(c, 'j'), status='pending_reassignment')
        c.commit()
    with database_connection(db) as c:
        result = cancel_mutation(c, mid, 'j')
        c.commit()
        assert result['status'] == 'cancelled'
        event = c.execute("SELECT name,folder_name,resort_required FROM events WHERE id='e'").fetchone()
        assert tuple(event) == ('Original', '07-19 - Original', 0)
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='e' AND family_id=?", (fid,)).fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM event_reapply_removed_families WHERE job_id='j'").fetchone()[0] == 0
        assert c.execute("SELECT status FROM event_mutations WHERE id=?", (mid,)).fetchone()[0] == 'cancelled'


def test_active_mutation_blocks_delete_in_same_job(tmp_path):
    db = tmp_path / 'db.sqlite3'
    _simple_applied(db)
    with database_connection(db) as c:
        mid = begin_mutation(
            c, job_id='j', anchor_event_id='e', mutation_kind='edit',
            affected_event_ids=['e'], original_state=capture_job_event_state(c, 'j'), status='pending_apply',
        )
        set_mutation_target(c, mid, capture_job_event_state(c, 'j'))
        c.commit()
    with pytest.raises(ValueError, match='noch nicht abgeschlossene Ereignisänderung'):
        delete_planned_event(db, 'j', 'e')


def test_reconcile_recovers_file_even_when_old_basename_changed(tmp_path):
    db = tmp_path / 'db.sqlite3'
    workspace = tmp_path / 'workspace'
    seed(db, workspace)
    work = workspace / 'Arbeitsbereich'
    old = work / '2026/07-19 - B/18-16 - 23-59 - B/Alle/F2.JPG'
    renamed = work / '2026/legacy-renamed/Alle/20260719_182000_Fuji-X-E5.JPG'
    renamed.parent.mkdir(parents=True, exist_ok=True)
    old.replace(renamed)
    plan = build_workspace_reconcile_plan(db, 'j', 'a', workspace)
    assert plan['summary']['ready'] is True
    target = next(f for f in plan['files'] if int(f['family_id']) == 2)
    assert target['source_relative_path'] == '2026/legacy-renamed/Alle/20260719_182000_Fuji-X-E5.JPG'
    assert any(w.get('code') == 'stale_current_path_recovered' for w in plan['warnings'])


def test_events_ui_exposes_mutation_cancel_action():
    assert 'noch neu zuzuordnen' in EVENTS_HTML
    assert 'Änderung verwerfen' in EVENTS_HTML
    assert '/event-mutations/' in EVENTS_HTML
