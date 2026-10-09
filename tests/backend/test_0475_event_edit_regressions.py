"""0.47.5: regression guards for removed/renamed children and archive cleanup."""
from contextlib import contextmanager
from pathlib import Path
import json

from app.database import create_job, database_connection, initialize_database
from app.sort_plan import (
    _observed_organization_path,
    _reapply_original_child_folder_names,
)
from app import archive_staging


def test_0475_removed_child_is_not_treated_as_user_organization():
    inventory = {"event_relative_path": "2025-12-04 - Teil 04/Alle/IMG.JPG"}
    assert _observed_organization_path(
        inventory, child_folder_names={"2025-12-04 - Teil 04"}
    ).as_posix() == "Alle"
    assert _observed_organization_path(
        {"event_relative_path": "2025-12-04 - Teil 04/2025-12-04/Alle/IMG.JPG"},
        child_folder_names={"2025-12-04 - Teil 04"},
    ).as_posix() == "Alle"


def test_0475_keeps_real_user_organization_when_child_was_removed():
    assert _observed_organization_path(
        {"event_relative_path": "Eigenes/Sortiert/IMG.JPG"},
        child_folder_names={"2025-12-04 - Teil 04"},
    ).as_posix() == "Eigenes/Sortiert"


def test_0475_original_children_survive_sqlite_soll_change(tmp_path: Path):
    db = tmp_path / "kamera.sqlite3"
    initialize_database(db)
    create_job(
        db, job_id="J", kind="sd_import", trigger_type="approved_sd",
        source_path="/source", working_path="/workspace",
        operation="folder_import",
    )
    old_state = {"events": [
        {"id": "E", "parent_event_id": None, "folder_name": "Erste Hälfte"},
        {"id": "C", "parent_event_id": "E", "folder_name": "Teil 04"},
    ]}
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO event_mutations(
                   id,job_id,anchor_event_id,mutation_kind,status,
                   affected_event_ids_json,original_state_json,target_state_json,
                   created_at,updated_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            ("M", "J", "E", "edit", "pending_apply", '["E"]',
             json.dumps(old_state), "{}", "2026-10-09", "2026-10-09"),
        )
    assert _reapply_original_child_folder_names(db, "J", "E") == {"Teil 04"}
    assert _reapply_original_child_folder_names(db, "J", "other") == set()


def test_0475_archived_empty_child_is_in_manual_removal_plan(monkeypatch, tmp_path):
    class FakeCursor:
        def fetchall(self):
            return [{"folder_name": "Teil 04"}, {"folder_name": "Erhalten"}]
    class FakeConnection:
        def execute(self, sql, args):
            assert "SELECT folder_name FROM events" in sql
            assert args == ("E",)
            return FakeCursor()
    @contextmanager
    def fake_connection(_):
        yield FakeConnection()
    monkeypatch.setattr(archive_staging, "database_connection", fake_connection)
    monkeypatch.setattr(
        archive_staging, "_current_event_root",
        lambda db, eid: archive_staging.PurePosixPath("2025", "Ereignis"),
    )
    preview = {
        "start_date": "2025-12-04", "parent_folder": "Ereignis",
        "subevents": [{"folder_name": "Erhalten"}],
    }
    result = archive_staging._obsolete_directories_from_plan(
        tmp_path / "db.sqlite3", "E", preview,
        {"families_with_plans": [], "assets_with_plans": []},
    )
    assert result == ["2025/Ereignis/Teil 04"]
