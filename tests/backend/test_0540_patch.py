"""0.54.5: mobile editor and non-destructive background activity controls."""
from datetime import datetime, timezone
from pathlib import Path

from app import __version__, main
from app.background_activity import current_activity, clear_finished_activity
from app.database import database_connection, initialize_database
from app.events_ui import EVENTS_HTML
from app.ui_i18n import UI_TRANSLATIONS
from app.ui_shell import BIBLIOTHEKAR_0444_CSS, BIBLIOTHEKAR_0444_JS


def test_0540_version_and_mobile_editor_layout():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.54.5"
    assert "@media (max-width:820px)" in EVENTS_HTML
    assert "#event-edit-dialog .edit-boundaries" in EVENTS_HTML
    assert "#event-edit-dialog .child-segment-boundary" in EVENTS_HTML
    assert "#event-edit-dialog .edit-date-entry" in EVENTS_HTML
    assert "box-sizing:border-box !important;" in EVENTS_HTML


def test_0540_centered_compact_status_and_localized_clear():
    assert "bk-activity-center" in BIBLIOTHEKAR_0444_JS
    assert 'mini.dataset.status = busy' in BIBLIOTHEKAR_0444_JS
    assert "bk-activity-mini-count" in BIBLIOTHEKAR_0444_CSS
    assert "transform:translate(-50%,-50%)" in BIBLIOTHEKAR_0444_CSS
    assert "bk-activity-clear" in BIBLIOTHEKAR_0444_JS
    assert '/api/background-activity/clear?library=' in BIBLIOTHEKAR_0444_JS
    assert UI_TRANSLATIONS["Leeren"] == "Clear"
    assert any(
        route.path == "/api/background-activity/clear"
        and "POST" in route.methods
        for route in main.app.routes
    )


def _create_job(db: Path, job_id: str, state: str, updated: str):
    with database_connection(db) as connection:
        connection.execute(
            """INSERT INTO jobs
               (id,kind,trigger_type,state,stage,operation,created_at,updated_at,
                source_volume_label,progress_current,progress_total)
               VALUES (?,'sd_import','manual',?,'done','trash_import',?,?,?,0,1)""",
            (job_id, state, updated, updated, "From Trash"),
        )


def test_0540_completed_expires_failed_persists_and_clear_is_safe(tmp_path):
    db = tmp_path / "activity.sqlite3"
    initialize_database(db)
    now = datetime.now(timezone.utc).isoformat()
    _create_job(db, "completed-recent", "completed", now)
    _create_job(db, "failed-old", "failed", "2026-01-05T10:00:00+00:00")
    operations = current_activity(db, db)["operations"]
    assert {item["id"] for item in operations} >= {"completed-recent", "failed-old"}

    result = clear_finished_activity(db, db)
    assert result["cleared"] >= 2
    assert not any(item["kind"] == "trash_restore" for item in current_activity(db, db)["operations"])
    with database_connection(db) as connection:
        rows = connection.execute(
            "SELECT state FROM jobs WHERE id IN ('completed-recent','failed-old')"
        ).fetchall()
        assert len(rows) == 2  # Clearing did not delete the underlying jobs.
        connection.execute(
            "UPDATE jobs SET state='copying',updated_at=? WHERE id='failed-old'",
            (now,),
        )
    assert any(
        item["id"] == "failed-old" and item["active"]
        for item in current_activity(db, db)["operations"]
    )
    with database_connection(db) as connection:
        connection.execute(
            "UPDATE jobs SET state='failed',updated_at=? WHERE id='failed-old'",
            ("2026-10-13T16:00:00+00:00",),
        )
    assert any(
        item["id"] == "failed-old" and not item["active"]
        for item in current_activity(db, db)["operations"]
    )
