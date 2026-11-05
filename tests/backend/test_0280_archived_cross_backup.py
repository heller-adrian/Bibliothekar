"""0.28.0: later backups extend one archived canonical event via archive change."""
from __future__ import annotations

from tests.backend.legacy_storage_fixture import provision_legacy_storage

from pathlib import Path
import hashlib

from app import main
from app.database import database_connection, initialize_database
from app.event_access import register_source_jobs
from app.event_layout import ensure_event_layout_snapshot
from app.workspace_layout import ensure_workspace_layout
from tests.backend.test_0263_event_inventory import NOW
from tests.backend.test_0280_foundation import _family, _job


def test_0280_later_backup_extends_archived_event_via_change_request(
    tmp_path: Path,
    monkeypatch,
):
    db = tmp_path / "db.sqlite3"
    workspace = tmp_path / "workspace"
    archive = tmp_path / "archive"
    workspace.mkdir()
    provision_legacy_storage(workspace)
    archive.mkdir()
    ensure_workspace_layout(workspace)
    initialize_database(db)

    camera_a = b"archived-camera"
    digest_a = hashlib.sha256(camera_a).hexdigest()
    incoming_b = b"incoming-camera"
    digest_b = hashlib.sha256(incoming_b).hexdigest()

    with database_connection(db) as connection:
        _job(connection, "a")
        _job(connection, "b")
        connection.execute(
            """INSERT INTO events(
                   id,job_id,parent_event_id,event_level,name,start_datetime,end_datetime,
                   uses_time_range,folder_name,status,created_at,updated_at,event_kind,
                   preserve_day_folders,revision,applied_at,archived_at,
                   time_model_version,timeline_model
               ) VALUES (
                   'arch','a',NULL,'parent','Archiv',
                   '2026-07-19T00:00:00','2026-07-19T23:59:59',0,
                   '07-19 - Archiv','archived',?,?,'event',0,1,?,?,2,'continuous'
               )""",
            (NOW, NOW, NOW, NOW),
        )
        fa, file_a = _family(connection, "a", "A")
        fb, file_b = _family(connection, "b", "B")
        connection.execute(
            """UPDATE files
               SET current_relative_path='2026/07-19 - Archiv/Alle/A.JPG',
                   current_root_kind='camera_archive',
                   size_bytes=?,sha256_original=?,sha256_current=?
               WHERE id=?""",
            (len(camera_a), digest_a, digest_a, file_a),
        )
        connection.execute(
            """UPDATE files
               SET current_relative_path='2026/incoming/B.JPG',
                   current_root_kind='shared_workspace',
                   size_bytes=?,sha256_original=?,sha256_current=?
               WHERE id=?""",
            (len(incoming_b), digest_b, digest_b, file_b),
        )
        connection.execute(
            """INSERT INTO event_assignments(
                   event_id,family_id,file_id,assignment_source,created_at
               ) VALUES ('arch',?,NULL,'manual',?)""",
            (fa, NOW),
        )
        register_source_jobs(connection, "arch", ["a"], created_at=NOW)
        ensure_event_layout_snapshot(connection, "arch", now=NOW)

    archive_event = archive / "2026" / "07-19 - Archiv"
    for name in ("Alle", "Sortiert", "Export"):
        (archive_event / name).mkdir(parents=True, exist_ok=True)
    (archive_event / "Alle" / "A.JPG").write_bytes(camera_a)

    incoming_path = workspace / "Arbeitsbereich" / "2026" / "incoming" / "B.JPG"
    incoming_path.parent.mkdir(parents=True, exist_ok=True)
    incoming_path.write_bytes(incoming_b)

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
    monkeypatch.setattr(
        main,
        "blocked_family_ids",
        lambda *args, **kwargs: set(),
    )
    monkeypatch.setattr(main, "WORKSPACE_PATH", workspace)
    monkeypatch.setattr(main, "ARCHIVE_ROOT", archive)

    result = main.api_accept_event_suggestion(
        "b",
        {"family_ids": [fb], "target_event_id": "arch"},
    )

    assert result["status"] == "archive_change_request_created"
    assert result["target_event_id"] == "arch"
    assert result["target_job_id"] == "a"
    assert result["linkage_kind"] == "archive_change_request"

    with database_connection(db) as connection:
        roots = connection.execute(
            """SELECT id,job_id,linked_event_id,linkage_kind
               FROM events WHERE parent_event_id IS NULL"""
        ).fetchall()
        change = connection.execute(
            """SELECT event_id,job_id,status
               FROM event_change_requests WHERE id=?""",
            (result["change_request_id"],),
        ).fetchone()

    assert [tuple(row) for row in roots] == [("arch", "a", None, None)]
    assert tuple(change) == ("arch", "a", "aenderbar_vorschlagen")
