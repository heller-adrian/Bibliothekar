"""0.44.4: Desktop-Statusdock für die drei bestehenden Hintergrundprozesse."""
from __future__ import annotations

import sqlite3

from app import main
from app.background_activity import current_activity
from app.ui_shell import BIBLIOTHEKAR_0444_CSS, BIBLIOTHEKAR_0444_JS, apply_shell


def _fixture(tmp_path):
    global_db = tmp_path / "global.sqlite3"
    library_db = tmp_path / "library.sqlite3"
    with sqlite3.connect(global_db) as db:
        db.execute(
            "CREATE TABLE jobs(id TEXT,operation TEXT,state TEXT,stage TEXT,"
            "source_volume_label TEXT,created_at TEXT)"
        )
        db.executemany(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?)",
            [
                ("imp-active", "folder_import", "copying", "copying", "SD-Karte", "2026-10-08"),
                ("imp-finished", "folder_import", "completed", "completed", "Abgeschlossen", "2026-10-07"),
                ("not-import", "hardlink_sync", "copying", "copying", "Sort", "2026-10-08"),
            ],
        )
    with sqlite3.connect(library_db) as db:
        db.executescript("""
            CREATE TABLE events(id TEXT,name TEXT);
            CREATE TABLE operation_batches(
              id TEXT,status TEXT,item_count INTEGER,completed_item_count INTEGER,created_at TEXT
            );
            CREATE TABLE sort_runs(
              id TEXT,job_id TEXT,event_id TEXT,status TEXT,created_at TEXT
            );
            CREATE TABLE operation_batch_items(sort_run_id TEXT);
            CREATE TABLE background_mutation_cancellations(
              id TEXT,job_id TEXT,mutation_id TEXT,status TEXT,error_message TEXT,
              created_at TEXT,updated_at TEXT,started_at TEXT,completed_at TEXT
            );
        """)
        db.execute("INSERT INTO events VALUES ('evt','Testereignis')")
        db.executemany(
            "INSERT INTO sort_runs VALUES(?,?,?,?,?)",
            [
                ("sort-active", "job-1", "evt", "moving", "2026-10-08"),
                ("sort-in-batch", "job-1", "evt", "verifying", "2026-10-08"),
                ("sort-finished", "job-1", "evt", "applied", "2026-10-07"),
            ],
        )
        db.execute("INSERT INTO operation_batch_items VALUES('sort-in-batch')")
        db.execute("INSERT INTO operation_batches VALUES('batch-1','running',2,1,'2026-10-08')")
        db.execute(
            "INSERT INTO background_mutation_cancellations VALUES ("
            "'cancel-1','job-1','mut-1','running',NULL,"
            "datetime('now'),datetime('now'),datetime('now'),NULL)"
        )
    return global_db, library_db


def test_0444_read_only_status_uses_global_import_and_library_sort(tmp_path):
    global_db, library_db = _fixture(tmp_path)
    result = current_activity(library_db, global_db)
    ids = {(item["kind"], item["id"]) for item in result["operations"]}
    assert ids == {
        ("import", "imp-active"), ("apply", "sort-active"),
        ("apply", "batch-1"), ("cancel", "cancel-1"),
    }
    assert result["active_count"] == 4
    assert next(x for x in result["operations"] if x["id"] == "imp-active")["href"] == "/"
    assert next(x for x in result["operations"] if x["id"] == "sort-active")["href"].startswith("/events")
    assert next(x for x in result["operations"] if x["id"] == "cancel-1")["job_id"] == "job-1"


def test_0444_empty_background_returns_no_overlay_items(tmp_path):
    global_db, library_db = _fixture(tmp_path)
    with sqlite3.connect(global_db) as db:
        db.execute("DELETE FROM jobs")
    with sqlite3.connect(library_db) as db:
        db.execute("DELETE FROM sort_runs")
        db.execute("DELETE FROM operation_batches")
        db.execute("DELETE FROM background_mutation_cancellations")
    assert current_activity(library_db, global_db) == {"operations": [], "active_count": 0}


def test_0444_cancel_failure_keeps_retry_action(tmp_path):
    global_db, library_db = _fixture(tmp_path)
    with sqlite3.connect(library_db) as db:
        db.execute(
            "UPDATE background_mutation_cancellations "
            "SET status='failed',error_message='Dateikonflikt',completed_at=datetime('now')"
        )
    result = current_activity(library_db, global_db)
    failed = next(x for x in result["operations"] if x["kind"] == "cancel")
    assert failed["active"] is False
    assert failed["can_retry"] is True
    assert "Dateikonflikt" in failed["detail"]


def test_0444_desktop_dock_and_minimize_behaviour():
    page = apply_shell("<!doctype html><html><head></head><body>Inhalt</body></html>", active_area="workspace")
    assert 'id="bk-background-cancel-notice"' in page
    assert '/api/background-activity?library=' in page
    assert "BIBLIOTHEKAR_0444_CSS" not in page
    assert 'position:fixed' in BIBLIOTHEKAR_0444_CSS
    assert 'bottom:22px' in BIBLIOTHEKAR_0444_CSS
    assert 'top:auto' in BIBLIOTHEKAR_0444_CSS
    assert 'max-width:900px' in BIBLIOTHEKAR_0444_CSS
    assert '(hover:none)' in BIBLIOTHEKAR_0444_CSS
    assert 'bk-activity-collapsed' in BIBLIOTHEKAR_0444_JS
    assert 'setCollapsed(true)' in BIBLIOTHEKAR_0444_JS
    assert 'setCollapsed(false)' in BIBLIOTHEKAR_0444_JS
    assert 'Hintergrundvorgänge verkleinern' in BIBLIOTHEKAR_0444_JS
    assert 'window.setInterval(refresh, 2500)' in BIBLIOTHEKAR_0444_JS
    assert 'window.setInterval(refresh,1500)' not in page  # alter Header-Hinweis entfernt


def test_0444_links_to_import_and_events_preserve_library():
    assert 'if (item.kind === "import") return "/?library=" + lib;' in BIBLIOTHEKAR_0444_JS
    assert 'return "/events?library=" + lib + job;' in BIBLIOTHEKAR_0444_JS
    assert 'new Event("bk-cancellation-queued")' not in BIBLIOTHEKAR_0444_JS
    assert "window.addEventListener(\"bk-cancellation-queued\", refresh)" in BIBLIOTHEKAR_0444_JS
    assert main.DEPLOYMENT_VERSION == "0.50.9"
