from pathlib import Path
import json
import pytest

from app.database import initialize_database, database_connection, delete_planned_event, update_event_definition
from app.event_mutation import (
    capture_job_event_state,
    begin_mutation,
    set_mutation_target,
    maybe_complete_planned_cascade_after_initial_apply,
    cancel_mutation,
)
from app.event_timeline import _set_continuous_event_interval
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML

NOW = "2026-09-08T20:00:00+00:00"


def _seed_two_planned(db: Path):
    initialize_database(db)
    times = [
        "2026-07-19T17:11:37", "2026-07-19T17:32:29",
        "2026-07-19T17:51:50", "2026-07-19T19:25:23",
        "2026-07-19T19:31:56", "2026-07-19T19:45:45",
        "2026-07-19T20:08:06", "2026-07-19T21:58:09",
    ]
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) "
            "VALUES ('j','sd_import','manual','completed','organized_verified','folder_import','TEST',?,?)",
            (NOW, NOW),
        )
        fids=[]
        for idx, capture in enumerate(times, 1):
            fid=int(c.execute(
                "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) "
                "VALUES ('j',?,?, 'complete',?,'high')",
                (f"F{idx}", f"F{idx}", capture),
            ).lastrowid)
            fids.append(fid)
        for eid,name,start,end,folder in [
            ('a','Test 19A','2026-07-19T17:00:00','2026-07-19T19:30:59','17-00 - 19-30 - Nachmittag'),
            ('b','Test 19B','2026-07-19T19:31:00','2026-07-19T22:31:59','19-31 - 22-31 - Abend'),
        ]:
            c.execute(
                """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,
                   created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                   VALUES (?,?, 'parent',?,'2026-07-19T00:00:00','2026-07-19T23:59:59',0,?,'planned',?,?,'event',0,1,'continuous')""",
                (eid,'j',name,f"07-19 - {name}",NOW,NOW),
            )
            c.execute(
                """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,
                   created_at,updated_at,event_kind,preserve_day_folders,revision,timeline_model)
                   VALUES (?,?,?,'child',?,?,?,1,?,'planned',?,?,'event',0,1,'continuous')""",
                (eid+'c','j',eid, 'Nachmittag' if eid=='a' else 'Abend', start,end,folder,NOW,NOW),
            )
        for fid in fids[:4]:
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('ac',?,NULL,'date_time_range',?)",(fid,NOW))
        for fid in fids[4:]:
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES ('bc',?,NULL,'date_time_range',?)",(fid,NOW))
        c.commit()
    return fids


def test_cascade_interval_rebuilds_membership_and_visible_child_folder(tmp_path):
    db=tmp_path/'db.sqlite3'
    _seed_two_planned(db)
    with database_connection(db) as c:
        removed=_set_continuous_event_interval(c,'b','2026-07-19T19:46:00','2026-07-19T22:31:59',NOW)
        assert len(removed)==2
        row=c.execute("SELECT start_datetime,end_datetime,folder_name FROM events WHERE id='bc'").fetchone()
        assert tuple(row)==('2026-07-19T19:46:00','2026-07-19T22:31:59','19-46 - 22-31 - Abend')
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='bc'").fetchone()[0]==2
        # Expansion must be rebuilt from capture times, not stale old assignments.
        _set_continuous_event_interval(c,'b','2026-07-19T19:31:00','2026-07-19T22:31:59',NOW)
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='bc'").fetchone()[0]==4


def test_planned_cascade_mutation_blocks_delete_until_all_affected_applied(tmp_path):
    db=tmp_path/'db.sqlite3'
    _seed_two_planned(db)
    with database_connection(db) as c:
        original=capture_job_event_state(c,'j')
        mid=begin_mutation(c,job_id='j',anchor_event_id='a',mutation_kind='cascade',affected_event_ids=['a','b'],original_state=original,status='pending_apply')
        set_mutation_target(c,mid,capture_job_event_state(c,'j'),status='pending_apply')
        c.commit()
    with pytest.raises(ValueError, match='noch nicht abgeschlossene Ereignisänderung'):
        delete_planned_event(db,'j','a')
    with database_connection(db) as c:
        c.execute("UPDATE events SET status='applied',applied_at=? WHERE id IN ('a','ac')",(NOW,))
        maybe_complete_planned_cascade_after_initial_apply(c,'j')
        assert c.execute("SELECT status FROM event_mutations WHERE id=?",(mid,)).fetchone()[0]=='pending_apply'
        c.execute("UPDATE events SET status='applied',applied_at=? WHERE id IN ('b','bc')",(NOW,))
        maybe_complete_planned_cascade_after_initial_apply(c,'j')
        assert c.execute("SELECT status FROM event_mutations WHERE id=?",(mid,)).fetchone()[0]=='completed'



def test_real_planned_cascade_is_durable_consistent_and_cancellable(tmp_path):
    db=tmp_path/'db.sqlite3'
    fids=_seed_two_planned(db)
    preview={
        'event_kind':'event',
        'uses_time_range':True,
        'start_date':'2026-07-19',
        'end_date':'2026-07-19',
        'start_time':'17:00',
        'end_time':'19:45',
        'parent_folder':'07-19 - Test 19A',
        'child_folder':'17-00 - 19-45 - Nachmittag',
        'child_event_name':'Nachmittag',
        'preserve_day_folders':False,
        'selected_family_ids':fids[:6],
    }
    result=update_event_definition(
        db,'j','a',preview,event_name='Test 19A',notes='',expected_revision=1,
        cascade_confirmed=True,
    )
    assert result['mutation_id']
    assert result['resort_required'] is False
    assert result['cascade']['affected_event_ids']==['b']
    with database_connection(db) as c:
        mutation=c.execute("SELECT * FROM event_mutations WHERE id=?",(result['mutation_id'],)).fetchone()
        assert mutation['status']=='pending_apply'
        assert set(json.loads(mutation['affected_event_ids_json']))=={'a','b'}
        b=c.execute("SELECT start_datetime,end_datetime,folder_name FROM events WHERE id='bc'").fetchone()
        assert tuple(b)==('2026-07-19T19:46:00','2026-07-19T22:31:59','19-46 - 22-31 - Abend')
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='ac'").fetchone()[0]==6
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='bc'").fetchone()[0]==2
    with pytest.raises(ValueError, match='noch nicht abgeschlossene Ereignisänderung'):
        delete_planned_event(db,'j','a')
    with database_connection(db) as c:
        cancel_mutation(c,result['mutation_id'],'j')
        c.commit()
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='ac'").fetchone()[0]==4
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='bc'").fetchone()[0]==4
        b=c.execute("SELECT start_datetime,end_datetime,folder_name FROM events WHERE id='bc'").fetchone()
        assert tuple(b)==('2026-07-19T19:31:00','2026-07-19T22:31:59','19-31 - 22-31 - Abend')

def test_ui_does_not_auto_reconcile_planned_only_cascade_and_task_is_specific():
    assert 'item => String(item.status || "") === "applied"' in EVENTS_HTML
    assert 'Gemeinsame Planänderung gespeichert' in EVENTS_HTML
    assert 'Dieses geplante Ereignis anwenden' in WORKSPACE_HTML
    assert 'andere geplante Ereignisse bleiben unangetastet' in WORKSPACE_HTML
