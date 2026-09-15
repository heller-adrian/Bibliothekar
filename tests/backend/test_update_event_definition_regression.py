"""Regressionstest: update_event_definition darf keine ea.job_id Spalte verwenden.

Die event_assignments-Tabelle hat KEINE job_id-Spalte (Schema 001_initial.sql).
Job-Zuordnung erfolgt über events.job_id. Die Abfrage in update_event_definition
muss e.job_id statt ea.job_id verwenden (Fix b13abf5).
"""
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import (
    apply_migration,
    available_migrations,
    database_connection,
    initialize_database,
    update_event_definition,
)

DB_PATH = Path(tempfile.gettempdir()) / "test_regression_update_ea.sqlite3"


def _setup_db(path: Path) -> Path:
    """Erzeuge eine leere DB ausschließlich über apply_migration (001–013)."""
    p = Path(path)
    if p.exists():
        p.unlink()

    conn = sqlite3.connect(str(p))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    for version, migration_path in available_migrations():
        apply_migration(conn, version, migration_path)

    conn.close()
    return p


@pytest.fixture(scope="module")
def test_db_path() -> Path:
    return _setup_db(DB_PATH)


def test_update_event_definition_no_ea_job_id_column(test_db_path: Path) -> None:
    """Prüft, dass update_event_definition mit dem echten Schema funktioniert.

    Erzeugt eine Test-Datenbank ausschließlich über apply_migration (Migrationen
    001–013), erzeugt einen Job, ein Event und eine File_Family, ruft
    update_event_definition auf und bestätigt, dass die Abfrage keinen
    'no such column: ea.job_id'-Fehler auslöst.
    """
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "")

    job_id = "TEST_JOB_" + uuid.uuid4().hex[:24].upper()
    event_id = "TEST_EVENT_" + uuid.uuid4().hex[:24].upper()
    family_id = None

    # --- Job + Event + File_Family + Assignment erzeugen ---
    with database_connection(test_db_path) as conn:
        # Job
        conn.execute(
            """INSERT INTO jobs (id, kind, trigger_type, state, stage,
               source_path, working_path, archive_target_path,
               source_device_id, source_filesystem_uuid, source_volume_label,
               file_count, total_size_bytes, error_message,
               created_at, started_at, updated_at, finished_at)
               VALUES (?, 'sd_import', 'manual', 'organizing', 'analyzing_metadata',
                       '/test/src', '/test/work', '/test/archive',
                       'DEV001', 'UUID-TEST-001', 'USB-STICK',
                       10, 50000000, NULL,
                       ?, ?, ?, NULL)""",
            (job_id, now, now, now),
        )

        # Event (parent)
        conn.execute(
            """INSERT INTO events (id, job_id, parent_event_id, event_level, name,
               start_datetime, end_datetime, uses_time_range, folder_name,
               status, created_at, updated_at, revision, applied_at, archived_at,
               notes, edited_at, event_kind, preserve_day_folders)
               VALUES (?, ?, NULL, 'parent', 'Test-Event',
                       '2026-08-28T10:00:00', '2026-08-28T18:00:00',
                       0, '2026-08-28', 'draft',
                       ?, ?, 1, NULL, NULL, '', NULL, 'event', 0)""",
            (event_id, job_id, now, now),
        )

        # File family
        cur = conn.execute(
            """INSERT INTO file_families (id, job_id, family_key, original_stem,
               status, selected_capture_time, capture_time_confidence)
               VALUES ((SELECT COALESCE(MAX(id), 0) + 1 FROM file_families), ?, 'FAM-001', 'DSC_001.CR2', 'complete',
                       '2026-08-28T14:30:00', 'high')""",
            (job_id,),
        )
        family_id = cur.lastrowid

        # Event assignment (nur family_id, KEIN job_id!)
        conn.execute(
            """INSERT INTO event_assignments (event_id, family_id, file_id,
               assignment_source, created_at)
               VALUES (?, ?, NULL, 'date_range', ?)""",
            (event_id, family_id, now),
        )

        conn.commit()

    # --- update_event_definition aufrufen ---
    preview = {
        "selected_family_ids": [family_id],
        "start_date": "2026-08-28",
        "end_date": "2026-08-28",
        "start_time": "10",
        "end_time": "18",
        "uses_time_range": False,
        "parent_folder": "2026-08-28",
        "child_folder": "",
        "child_event_name": "",
        "event_kind": "event",
        "preserve_day_folders": False,
    }

    result = update_event_definition(
        database_path=test_db_path,
        job_id=job_id,
        event_id=event_id,
        preview=preview,
        event_name="Test-Event (bearbeitet)",
        notes="Regressionstest-Note",
        expected_revision=1,
    )

    # --- Assertions ---
    assert result["structural_changed"] is True
    assert result["assigned_family_ids"] == [family_id]
    assert result["resort_required"] is False  # draft → keine Sortierung

    # Event im DB wurde aktualisiert
    with database_connection(test_db_path) as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        assert row is not None
        assert row["name"] == "Test-Event (bearbeitet)"
        assert row["notes"] == "Regressionstest-Note"
        assert row["revision"] == 2
