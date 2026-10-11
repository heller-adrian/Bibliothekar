"""0.27.9: Mehrsicherungs-Antwort und Import-Refresh regressionsfest."""
from __future__ import annotations

from pathlib import Path

from app import main
from app.database import database_connection, initialize_database
from tests.backend.test_0278_patch import _family
from tests.backend.test_0263_event_inventory import NOW


def test_0279_release_version():
    assert main.RELEASE_VERSION == "0.50.4"
    assert main.api_health()["version"] == "0.50.4"


def test_0279_cross_backup_accept_api_returns_after_success(tmp_path: Path, monkeypatch):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        for job_id in ("anchor","incoming"):
            connection.execute(
                """INSERT INTO jobs(
                       id,kind,trigger_type,state,stage,operation,source_volume_label,
                       progress_current,progress_total,created_at,updated_at
                   ) VALUES (?,"sd_import","manual","completed","completed",
                             "folder_import",?,0,0,?,?)""",
                (job_id, job_id, NOW, NOW),
            )
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision
               ) VALUES ("anchor_event","anchor",NULL,"parent","Test",
                         "2026-07-19T00:00:00","2026-07-20T23:59:59",0,
                         "07-19 - Test","planned",?,?,"event",0,1)""",
            (NOW, NOW),
        )
        family_id = _family(connection, "incoming", "INCOMING", b"incoming")
        connection.execute(
            "UPDATE file_families SET selected_capture_time='2026-07-19T12:00:00' WHERE id=?",
            (family_id,),
        )
        connection.execute(
            "UPDATE files SET selected_capture_time='2026-07-19T12:00:00' WHERE family_id=?",
            (family_id,),
        )

    monkeypatch.setattr(main, "DATABASE_FILE", db)
    # 0.31.0 adds a separate global claim layer. This historical regression
    # remains scoped to the frozen cross-backup event behavior; dedicated
    # 0.31 tests exercise the registry/claim integration.
    monkeypatch.setattr(
        main,
        "_reserve_global_family_ids",
        lambda event_id, family_ids: {"newly_reserved": []},
    )
    monkeypatch.setattr(
        main,
        "_release_new_global_reservations",
        lambda reservation: None,
    )
    result = main.api_accept_event_suggestion(
        "incoming",
        {"family_ids": [family_id], "target_event_id": "anchor_event"},
    )
    assert result["job_id"] == "incoming"
    assert result["target_job_id"] == "anchor"
    assert result["target_event_id"] == "anchor_event"
    assert result["linkage_kind"] is None

    with database_connection(db) as connection:
        linked = connection.execute(
            """SELECT job_id,linked_event_id,linkage_kind,status
               FROM events WHERE id='anchor_event'"""
        ).fetchone()
        count = connection.execute(
            "SELECT COUNT(*) FROM events WHERE parent_event_id IS NULL"
        ).fetchone()[0]
    assert tuple(linked) == ("anchor", None, None, "planned")
    assert count == 1


def test_0279_import_job_id_declared_before_duplicate_notice():
    source = Path("app/main.py").read_text(encoding="utf-8")
    render = source[source.index("function renderJob(job, isHidden=false)"): ]
    job_id = render.index('const jobId = String(job.job_id || job.id || "");')
    duplicate_notice = render.index("const duplicateNotice = duplicateCount > 0")
    assert job_id < duplicate_notice


def test_0279_no_sqlite_row_get_for_target_job():
    source = Path("app/main.py").read_text(encoding="utf-8")
    assert 'target.get("job_id")' not in source
    assert 'target_job_id = str(target["job_id"]) if target is not None else None' in source
