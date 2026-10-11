"""0.27.8: Sicherungsstatus, globale Duplikate und Arbeitsbereichsvertrag."""
from __future__ import annotations

from pathlib import Path
import hashlib

from app import main
from app.event_suggestions import accept_event_suggestion
from app.folder_import import partition_import_entries
from app.database import (
    create_job,
    database_connection,
    initialize_database,
    list_database_jobs,
    list_imported_media_origins,
)
from tests.backend.test_0263_event_inventory import NOW, seed_event, seed_file_for_family, seed_job


def _family(connection, job_id: str, stem: str, content: bytes) -> int:
    family_id = int(
        connection.execute(
            """INSERT INTO file_families(
                   job_id,family_key,original_stem,status,
                   selected_capture_time,capture_time_confidence
               ) VALUES (?,?,?,'complete','2026-07-23T12:00:00','high')""",
            (job_id, stem, stem),
        ).lastrowid
    )
    digest = hashlib.sha256(content).hexdigest()
    connection.execute(
        """INSERT INTO files(
               job_id,family_id,original_relative_path,current_relative_path,
               original_filename,extension,media_type,size_bytes,
               sha256_original,sha256_current,selected_capture_time,
               selected_capture_source,capture_time_confidence,review_status,
               metadata_write_status,created_at,updated_at,current_root_kind
           ) VALUES (?,?,?,?,?,'JPG','jpeg',?,?,?,?,?,'high','not_required',
                     'not_requested',?,?, 'shared_workspace')""",
        (
            job_id, family_id, f"DCIM/{stem}.JPG", f"2026/07-23/{stem}.JPG",
            f"{stem}.JPG", len(content), digest, digest,
            "2026-07-23T12:00:00", "EXIF:DateTimeOriginal", NOW, NOW,
        ),
    )
    return family_id


def test_0278_release_version():
    assert main.RELEASE_VERSION == "0.51.0"
    assert main.api_health()["version"] == main.RELEASE_VERSION


def test_0278_workflow_status_is_derived_from_family_state(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        for job_id in ("planned_job","applied_job","archived_job"):
            connection.execute(
                """INSERT INTO jobs(
                       id,kind,trigger_type,state,stage,operation,source_volume_label,
                       progress_current,progress_total,created_at,updated_at
                   ) VALUES (?,'sd_import','manual','completed','completed',
                             'folder_import',?,0,0,?,?)""",
                (job_id, job_id, NOW, NOW),
            )
            family = _family(connection, job_id, f"{job_id}_IMG", job_id.encode())
            event_id = f"{job_id}_event"
            status = {
                "planned_job":"planned",
                "applied_job":"applied",
                "archived_job":"archived",
            }[job_id]
            connection.execute(
                """INSERT INTO events(
                       id,job_id,parent_event_id,event_level,name,start_datetime,
                       end_datetime,uses_time_range,folder_name,status,created_at,
                       updated_at,event_kind,preserve_day_folders,revision
                   ) VALUES (?,?,NULL,'parent','Test','2026-07-23T00:00:00',
                             '2026-07-23T23:59:59',0,'07-23 - Test',?,?,?,
                             'event',0,1)""",
                (event_id, job_id, status, NOW, NOW),
            )
            connection.execute(
                """INSERT INTO event_assignments(
                       event_id,family_id,file_id,assignment_source,created_at
                   ) VALUES (?,?,NULL,'date_range',?)""",
                (event_id, family, NOW),
            )
            if status == "archived":
                connection.execute(
                    "UPDATE files SET current_root_kind='camera_archive' WHERE family_id=?",
                    (family,),
                )

    states={row["id"]:row["workflow_status"] for row in list_database_jobs(db)}
    assert states["planned_job"] == "planned"
    assert states["applied_job"] == "applied"
    assert states["archived_job"] == "archived"


def test_0278_global_hash_origin_is_source_independent(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs(
                   id,kind,trigger_type,state,stage,operation,source_volume_label,
                   progress_current,progress_total,created_at,updated_at
               ) VALUES ('old','sd_import','manual','completed','completed',
                         'folder_import','Erste Sicherung',0,0,?,?)""",
            (NOW, NOW),
        )
        _family(connection, "old", "IMG_0001", b"same-photo")

    origins=list_imported_media_origins(db)
    assert len(origins) == 1
    assert origins[0]["source_volume_label"] == "Erste Sicherung"
    assert origins[0]["sha256"] == hashlib.sha256(b"same-photo").hexdigest()


def test_0278_workspace_ui_contracts():
    source=Path("app/workspace_ui.py").read_text(encoding="utf-8")
    assert "Sicherungsfilter" in source
    assert "Alle aktiven Sicherungen" in source
    assert "Archivierte Sicherungen einblenden" in source
    assert "selectedJobIds" in source
    assert "planned_extension" not in source
    assert "verknüpfter Nachtrag" not in source
    assert "Nachtrag geplant" not in source
    assert "Neue Aufnahmen passen zu bestehenden Ereignissen" in source
    assert "selected_family_ids: familyIds" in source
    assert "decodeApiResponse" in source
    assert "Serverfehler" in source


def test_0278_import_ui_reports_skipped_duplicates():
    source=Path("app/main.py").read_text(encoding="utf-8")
    assert "Duplikate" in source
    assert "identischer Größe und identischem SHA-256" in source
    assert "data-job-detail-key" in source
    assert "openJobDetailKeys" in source
    assert "restoreOpenJobDetails" in source



def test_0278_cross_backup_extension_mirrors_subevents(tmp_path: Path):
    db = tmp_path / "db.sqlite3"
    initialize_database(db)
    with database_connection(db) as connection:
        for job_id in ("anchor","incoming"):
            connection.execute(
                """INSERT INTO jobs(
                       id,kind,trigger_type,state,stage,operation,source_volume_label,
                       progress_current,progress_total,created_at,updated_at
                   ) VALUES (?,'sd_import','manual','completed','completed',
                             'folder_import',?,0,0,?,?)""",
                (job_id, job_id, NOW, NOW),
            )

        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision
               ) VALUES ('anchor_event','anchor',NULL,'parent','Reise',
                         '2026-07-23T00:00:00','2026-07-23T23:59:59',0,
                         '07-23 - Reise','planned',?,?,'event',0,1)""",
            (NOW, NOW),
        )
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision
               ) VALUES ('anchor_morning','anchor','anchor_event','child','Morgen',
                         '2026-07-23T00:00:00','2026-07-23T11:59:59',1,
                         '00-00–11-59 - Morgen','planned',?,?,'event',0,1)""",
            (NOW, NOW),
        )
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision
               ) VALUES ('anchor_afternoon','anchor','anchor_event','child','Nachmittag',
                         '2026-07-23T12:00:00','2026-07-23T23:59:59',1,
                         '12-00–23-59 - Nachmittag','planned',?,?,'event',0,1)""",
            (NOW, NOW),
        )

        first=_family(connection,"incoming","IN_1",b"one")
        second=_family(connection,"incoming","IN_2",b"two")
        connection.execute(
            "UPDATE file_families SET selected_capture_time='2026-07-23T10:00:00' WHERE id=?",
            (first,),
        )
        connection.execute(
            "UPDATE files SET selected_capture_time='2026-07-23T10:00:00' WHERE family_id=?",
            (first,),
        )
        connection.execute(
            "UPDATE file_families SET selected_capture_time='2026-07-23T18:00:00' WHERE id=?",
            (second,),
        )
        connection.execute(
            "UPDATE files SET selected_capture_time='2026-07-23T18:00:00' WHERE family_id=?",
            (second,),
        )

    result=accept_event_suggestion(
        db,
        "incoming",
        [first,second],
        "anchor_event",
    )
    assert result["event_id"] == "anchor_event"
    assert result["linkage_kind"] is None

    with database_connection(db) as connection:
        linked=connection.execute(
            "SELECT * FROM events WHERE id='anchor_event'"
        ).fetchone()
        assert linked["linked_event_id"] is None
        assert linked["linkage_kind"] is None

        children=connection.execute(
            """SELECT id,name,start_datetime,end_datetime
               FROM events WHERE parent_event_id='anchor_event' ORDER BY start_datetime"""
        ).fetchall()
        assert [row["name"] for row in children] == ["Morgen","Nachmittag"]

        assigned=connection.execute(
            """SELECT ff.original_stem,e.name AS event_name
               FROM event_assignments ea
               JOIN file_families ff ON ff.id=ea.family_id
               JOIN events e ON e.id=ea.event_id
               WHERE ff.job_id='incoming'
               ORDER BY ff.original_stem"""
        ).fetchall()
        assert [(row["original_stem"],row["event_name"]) for row in assigned] == [
            ("IN_1","Morgen"),
            ("IN_2","Nachmittag"),
        ]



def test_0278_mixed_import_keeps_new_file_and_skips_only_exact_duplicate():
    old_digest=hashlib.sha256(b"old-photo").hexdigest()
    new_digest=hashlib.sha256(b"new-photo").hexdigest()
    entries=[
        {"relative_path":"DCIM/OLD.JPG","size_bytes":9,"sha256":old_digest},
        {"relative_path":"DCIM/NEW.JPG","size_bytes":9,"sha256":new_digest},
    ]
    key=(9,old_digest)
    new,duplicates,details=partition_import_entries(
        entries,
        {key},
        {key:{
            "job_id":"previous",
            "source_volume_label":"Frühere Sicherung",
            "current_relative_path":"2026/07-23/OLD.JPG",
            "original_filename":"OLD.JPG",
        }},
    )
    assert [row["relative_path"] for row in new] == ["DCIM/NEW.JPG"]
    assert [row["relative_path"] for row in duplicates] == ["DCIM/OLD.JPG"]
    assert details == [{
        "relative_path":"DCIM/OLD.JPG",
        "size_bytes":9,
        "sha256":old_digest,
        "existing_job_id":"previous",
        "existing_source_label":"Frühere Sicherung",
        "existing_relative_path":"2026/07-23/OLD.JPG",
        "existing_filename":"OLD.JPG",
    }]
