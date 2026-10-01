from pathlib import Path
import hashlib
import pytest

from app.database import database_connection, initialize_database, delete_planned_event
from app.archive_reassignment import assign_archive_reassignments, list_archive_reassignments
from app.event_change_apply import (
    EventChangeApplyError, confirm_event_change, finish_event_change,
    verify_event_change,
)
from app.events_ui import EVENTS_HTML
from app.workspace_ui import WORKSPACE_HTML

NOW = "2026-09-08T12:00:00+00:00"


def seed_job(db: Path, job_id="j"):
    initialize_database(db)
    with database_connection(db) as c:
        c.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,source_volume_label,created_at,updated_at) "
            "VALUES (?, 'sd_import','manual','completed','done','folder_import','TEST',?,?)",
            (job_id, NOW, NOW),
        )
        c.commit()


def add_family(db: Path, ts="2026-07-19T19:11:36") -> int:
    with database_connection(db) as c:
        fid = c.execute(
            "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) "
            "VALUES ('j','F1','F1','complete',?,'high')",
            (ts,),
        ).lastrowid
        c.commit()
        return int(fid)


def add_parent_event(db: Path, event_id: str, status: str, fid: int, *, archived=False):
    applied_at = NOW if status in {"applied", "archived"} else None
    archived_at = NOW if archived or status == "archived" else None
    with database_connection(db) as c:
        c.execute(
            """INSERT INTO events(
                id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,
                created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at,archived_at
            ) VALUES (?, 'j','parent',?,'2026-07-19T00:00:00','2026-07-19T23:59:59',0,?,?,?,?,'event',0,1,?,?)""",
            (event_id, event_id, f"07-19 - {event_id}", status, NOW, NOW, applied_at, archived_at),
        )
        c.execute(
            "INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?, ?, NULL, 'date_range', ?)",
            (event_id, fid, NOW),
        )
        c.commit()


def add_file(db: Path, fid: int, rel: str, payload: bytes=b"camera-test"):
    digest = hashlib.sha256(payload).hexdigest()
    with database_connection(db) as c:
        c.execute(
            """INSERT INTO files(
                job_id,family_id,original_relative_path,current_relative_path,original_filename,extension,media_type,
                size_bytes,sha256_original,sha256_current,selected_capture_time,selected_capture_source,
                capture_time_confidence,review_status,metadata_write_status,created_at,updated_at,current_root_kind
            ) VALUES ('j',?,?,?,?,'.JPG','jpeg',?,?,?,?,?,'high','not_required','not_requested',?,?,'camera_archive')""",
            (fid, rel, rel, Path(rel).name, len(payload), digest, digest, "2026-07-19T19:11:36", "DateTimeOriginal", NOW, NOW),
        )
        c.commit()
    return payload, digest


def test_migration_017_and_direct_creation_ui(tmp_path):
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM schema_versions WHERE version=17").fetchone()[0] == 1
        event_cols = {r["name"] for r in c.execute("PRAGMA table_info(events)")}
        cr_cols = {r["name"] for r in c.execute("PRAGMA table_info(event_change_requests)")}
    assert "pending_delete" in event_cols
    assert "delete_event" in cr_cols
    assert "newEventButton.disabled = !workspace;" in WORKSPACE_HTML
    assert "noEventButton.disabled = !workspace;" in WORKSPACE_HTML
    assert "data-segment-day" in WORKSPACE_HTML
    assert ".no-event-segment" in EVENTS_HTML
    assert "Ereignis löschen" in EVENTS_HTML



def test_applied_delete_becomes_reassignment_then_verified_delete(tmp_path):
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    fid = add_family(db)
    add_parent_event(db, "applied", "applied", fid)

    result = delete_planned_event(db, "j", "applied")
    assert result["pending_delete"] is True
    assert result["reassignment_required"] is False
    assert result["removed_family_ids"] == [fid]
    with database_connection(db) as c:
        event = c.execute("SELECT pending_delete,resort_required,status FROM events WHERE id='applied'").fetchone()
        assert tuple(event) == (1, 1, "applied")
        assert c.execute("SELECT COUNT(*) FROM event_assignments WHERE event_id='applied'").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM event_reapply_removed_families WHERE event_id='applied' AND family_id=?", (fid,)).fetchone()[0] == 1
        assert c.execute(
            "SELECT status FROM event_mutations WHERE anchor_event_id='applied' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()[0] == "pending_apply"
def test_archived_delete_returns_files_to_ssd_and_finishes_without_app_writing_archive(tmp_path):
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    fid = add_family(db)
    add_parent_event(db, "arch", "archived", fid, archived=True)
    old_rel = "2026/07-19 - arch/Alle/F1.JPG"
    payload, digest = add_file(db, fid, old_rel)
    archive = tmp_path / "archive"
    source = archive / old_rel
    source.parent.mkdir(parents=True)
    source.write_bytes(payload)

    result = delete_planned_event(db, "j", "arch")
    assert result["pending_delete"] is True
    assert result["archive_read_only"] is True
    assert result["reassignment_required"] is True
    cr_id = result["change_request_id"]
    with database_connection(db) as c:
        cr = c.execute("SELECT delete_event,status FROM event_change_requests WHERE id=?", (cr_id,)).fetchone()
        assert tuple(cr) == (1, "aenderbar_vorschlagen")
        review = c.execute("SELECT old_path,new_path,action,expected_sha256 FROM event_change_file_reviews WHERE change_request_id=?", (cr_id,)).fetchone()
        assert review["old_path"] == old_rel
        assert review["new_path"] == ""
        assert review["action"] == "delete"
        assert review["expected_sha256"] == digest
    workspace = tmp_path / "workspace"
    (workspace / "Arbeitsbereich").mkdir(parents=True)
    confirm_event_change(db, cr_id, archive, workspace)
    with database_connection(db) as c:
        review = c.execute(
            "SELECT old_path,workspace_release_path,action FROM event_change_file_reviews WHERE change_request_id=?",
            (cr_id,),
        ).fetchone()
        assert review["action"] == "delete"
        release_rel = str(review["workspace_release_path"])
    target = workspace / "SD-Kartensicherungen" / release_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())

    from app.archive_release_stock import verify_archive_release_copies, verify_archive_release_removal
    assert verify_archive_release_copies(db, archive, workspace, cr_id)["complete"]
    source.unlink()
    assert verify_archive_release_removal(db, archive, workspace, cr_id)["complete"]
    # Entfernte Ereignisordner müssen vor Abschluss leer bzw. verschwunden sein.
    source.parent.rmdir()
    source.parent.parent.rmdir()
    assert verify_event_change(db, cr_id, archive, workspace)["complete"]
    done = finish_event_change(db, cr_id, archive, workspace)
    assert done["event_deleted"] is True
    assert done["files_changed_by_app"] == 0
    assert done["released_family_ids"] == [fid]
    assert target.read_bytes() == payload
    with database_connection(db) as c:
        assert c.execute("SELECT COUNT(*) FROM events WHERE id='arch'").fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM event_change_requests WHERE id=?", (cr_id,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM audit_log WHERE action='archived_event_deleted_after_release'").fetchone()[0] == 1
        row=c.execute("SELECT current_relative_path,current_root_kind FROM files WHERE family_id=?",(fid,)).fetchone()
        assert row["current_relative_path"] == release_rel
        assert row["current_root_kind"] == "shared_workspace"


def test_direct_event_creation_uses_date_time_without_day_selection(tmp_path):
    from app.event_structure import build_event_preview
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    f1 = add_family(db, "2026-07-19T19:11:36")
    with database_connection(db) as c:
        f2 = c.execute(
            "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) "
            "VALUES ('j','F2','F2','complete','2026-07-19T20:02:14','high')"
        ).lastrowid
        c.commit()
    families = [
        {"family_id":f1,"has_date":True,"day_key":"2026-07-19","selected_capture_time":"2026-07-19T19:11:36","file_count":2},
        {"family_id":f2,"has_date":True,"day_key":"2026-07-19","selected_capture_time":"2026-07-19T20:02:14","file_count":2},
    ]
    preview = build_event_preview({
        "event_kind":"event","event_name":"Direkt","start_date":"2026-07-19","end_date":"2026-07-19",
        "uses_time_range":True,"child_event_name":"Abend","start_time":"20:00","end_time":"20:10",
        "preserve_day_folders":False,"selected_day_keys":[],
    }, families)
    assert preview["selected_family_ids"] == [f2]


def test_manual_no_event_segment_works_without_day_selection(tmp_path):
    from app.event_structure import build_event_preview
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    f1 = add_family(db, "2026-07-19T19:11:36")
    families = [{"family_id":f1,"has_date":True,"day_key":"2026-07-19","selected_capture_time":"2026-07-19T19:11:36","file_count":2}]
    preview = build_event_preview({
        "event_kind":"no_event","no_event_segments":[{"day_key":"2026-07-19","start_time":"19:00","end_time":"19:30"}],
        "selected_day_keys":[],
    }, families)
    assert preview["event_kind"] == "no_event"
    assert preview["selected_family_ids"] == [f1]


def test_applied_cascade_marks_all_affected_events_for_reapply(tmp_path):
    from app.database import update_event_definition
    db = tmp_path / "db.sqlite3"
    seed_job(db)
    with database_connection(db) as c:
        ids = []
        for key, ts in [("A1","2026-07-19T18:10:00"),("B1","2026-07-19T18:20:00")]:
            ids.append(int(c.execute(
                "INSERT INTO file_families(job_id,family_key,original_stem,status,selected_capture_time,capture_time_confidence) VALUES ('j',?,?, 'complete',?,'high')",
                (key,key,ts),
            ).lastrowid))
        for eid,name,start,end,fid in [
            ("a","A","2026-07-19T18:00:00","2026-07-19T18:15:59",ids[0]),
            ("b","B","2026-07-19T18:16:00","2026-07-19T23:59:59",ids[1]),
        ]:
            c.execute(
                """INSERT INTO events(id,job_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at)
                   VALUES (?, 'j','parent',?,'2026-07-19T00:00:00','2026-07-19T23:59:59',0,?,'applied',?,?,'event',0,1,?)""",
                (eid,name,f"07-19 - {name}",NOW,NOW,NOW),
            )
            c.execute(
                """INSERT INTO events(id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,uses_time_range,folder_name,status,created_at,updated_at,event_kind,preserve_day_folders,revision,applied_at)
                   VALUES (?, 'j',?,'child',?,?,?,1,?,'applied',?,?,'event',0,1,?)""",
                (eid+"c",eid,name,start,end,f"{start[11:16]} - {end[11:16]} - {name}",NOW,NOW,NOW),
            )
            c.execute("INSERT INTO event_assignments(event_id,family_id,file_id,assignment_source,created_at) VALUES (?, ?, NULL, 'date_time_range', ?)", (eid+"c",fid,NOW))
        c.commit()

    import pytest
    with database_connection(db) as c:
        before=[tuple(r) for r in c.execute('SELECT * FROM events ORDER BY id')]
        assignments=[tuple(r) for r in c.execute('SELECT * FROM event_assignments ORDER BY id')]
    with pytest.raises(ValueError,match='nicht mehr zulässig'):
        result = update_event_definition(
            db,"j","a",{
                "selected_family_ids":ids,
                "start_date":"2026-07-19","end_date":"2026-07-19",
                "uses_time_range":True,"start_time":"18:00","end_time":"18:30",
                "child_event_name":"A","parent_folder":"07-19 - A","child_folder":"18-00 - 18-30 - A",
                "event_kind":"event","preserve_day_folders":False,
            }, event_name="A", notes="", expected_revision=1, cascade_confirmed=True,
        )

    with database_connection(db) as c:
        assert [tuple(r) for r in c.execute('SELECT * FROM events ORDER BY id')]==before
        assert [tuple(r) for r in c.execute('SELECT * FROM event_assignments ORDER BY id')]==assignments
        assert c.execute('SELECT COUNT(*) FROM event_mutations').fetchone()[0]==0



def test_events_ui_applied_reapply_uses_reconciliation_endpoint():
    from app.events_ui import EVENTS_HTML
    assert 'plan._reconcile' in EVENTS_HTML
    assert '? "reconcile-sort"' in EVENTS_HTML
    assert ': (plan._reapply ? "reapply-sort" : "apply-sort")' in EVENTS_HTML
