"""0.40.x -> 0.50.0 schema migration proof on synthetic data only.

Never attach, open, or copy the user's actual SQLite database. We build
a historical schema using exactly the repository's migrations <= 040.
"""
from __future__ import annotations

from pathlib import Path
from app import database
from app.database import database_connection, initialize_database


def test_0500_upgrade_from_synthetic_040_preserves_job_and_event(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-v040.sqlite3"
    real_available = database.available_migrations
    old_migrations = [row for row in real_available() if row[0] <= 40]
    assert old_migrations and old_migrations[-1][0] == 40
    with monkeypatch.context() as historical:
        historical.setattr(database, "available_migrations", lambda: old_migrations)
        previous = initialize_database(path)
    assert previous["integrity"] == "ok"
    assert previous["applied_versions"][-1] == 40

    with database_connection(path) as conn:
        conn.execute(
            """INSERT INTO jobs
               (id,kind,trigger_type,state,stage,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?)""",
            ("SYNTHETIC_UPGRADE", "sd_import", "manual",
             "completed", "complete", "2026-01-01", "2026-01-01"),
        )
        conn.execute(
            """INSERT INTO events
               (id,job_id,parent_event_id,event_level,name,
                start_datetime,end_datetime,folder_name,status,
                created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            ("SYNTH_EVENT", "SYNTHETIC_UPGRADE", None, "parent",
             "Before migration", "2026-01-01T01:02:03",
             "2026-01-01T04:05:06", "01.01 - Before migration",
             "planned", "2026-01-01", "2026-01-01"),
        )
    migration = initialize_database(path)
    assert migration["integrity"] == "ok"
    assert migration["foreign_key_errors"] == 0
    assert migration["newly_applied_versions"] == list(range(41, 53))
    assert migration["applied_versions"] == list(range(1, 53))
    with database_connection(path) as conn:
        event = conn.execute(
            "SELECT name,start_datetime,end_datetime,status "
            "FROM events WHERE id='SYNTH_EVENT'"
        ).fetchone()
        assert tuple(event) == (
            "Before migration", "2026-01-01T01:02:03",
            "2026-01-01T04:05:06", "planned",
        )
        assert conn.execute(
            "SELECT state FROM jobs WHERE id='SYNTHETIC_UPGRADE'"
        ).fetchone()[0] == "completed"
        columns = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(event_document_sync_tasks)"
            ).fetchall()
        }
        assert {"event_id", "job_id", "revision", "status"} <= columns
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    repeated = initialize_database(path)
    assert repeated["newly_applied_versions"] == []
    assert repeated["integrity"] == "ok"


def test_0500_upgrade_historical_051_to_052_is_atomic(tmp_path, monkeypatch):
    path = tmp_path / "synthetic-v051.sqlite3"
    real_available = database.available_migrations
    old_migrations = [row for row in real_available() if row[0] <= 51]
    with monkeypatch.context() as historical:
        historical.setattr(database, "available_migrations", lambda: old_migrations)
        previous = initialize_database(path)
    assert previous["applied_versions"][-1] == 51
    result = initialize_database(path)
    assert result["newly_applied_versions"] == [52]
    assert "event_document_sync_tasks" in result["tables"]
    assert initialize_database(path)["newly_applied_versions"] == []
