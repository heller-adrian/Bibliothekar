"""0.45.3: Schnellansicht und Verlauf dürfen fachliche Sicherheit nicht verändern."""
from __future__ import annotations

from app import __version__, main, view_cache
from app.database import initialize_database, database_connection
from app.library_context import LibraryContext
from app.library_runtime import set_current_library, reset_current_library
from app.ui_shell import BIBLIOTHEKAR_0452_CSS, apply_shell
from app.workspace_ui import WORKSPACE_HTML
from app.events_ui import EVENTS_HTML


def test_0452_versions_and_reload_controls():
    assert __version__ == "0.55.2"
    assert main.DEPLOYMENT_VERSION == "0.55.2"
    assert 'id="day-reload"' in WORKSPACE_HTML
    assert 'id="event-reload"' in EVENTS_HTML
    assert "physicalRefresh:true" in WORKSPACE_HTML
    assert "physicalRefresh:true" in EVENTS_HTML
    assert "bkForceExternalChangeCheck" in WORKSPACE_HTML
    assert "bkForceExternalChangeCheck" in EVENTS_HTML
    assert "Tagesgruppen geladen." not in WORKSPACE_HTML


def test_0452_no_date_light_background_override():
    assert 'html[data-bk-theme="light"]' in BIBLIOTHEKAR_0452_CSS
    assert ".day-card.without-date.review-card" in BIBLIOTHEKAR_0452_CSS
    assert "#b56d22" in BIBLIOTHEKAR_0452_CSS
    assert "background: #f3e3cf !important" in BIBLIOTHEKAR_0452_CSS


def test_0452_library_name_is_in_first_html_response(tmp_path):
    ctx = LibraryContext(
        library_id="main", display_name="Main-Bibo",
        database_path=tmp_path / "db.sqlite3", workspace_root=tmp_path,
        work_root=tmp_path, archive_root=tmp_path,
        is_main=True, settings={},
    )
    token = set_current_library(ctx)
    try:
        html = apply_shell(
            '<!doctype html><html><head></head><body></body></html>',
            active_area="workspace", subarea="captures",
        )
    finally:
        reset_current_library(token)
    assert 'id="bk-current-library-name" class="bk-brand-library">Main-Bibo<' in html
    assert "Bibliothek …" not in html


def test_0452_cache_is_namespaced_and_db_writes_invalidate(tmp_path):
    a = tmp_path / "a.sqlite3"
    b = tmp_path / "b.sqlite3"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    view_cache.put_snapshot(a, "workspace", {"days": 42}, ("one",))
    assert view_cache.get_snapshot(a, "workspace", ("one",)) == {"days": 42}
    assert view_cache.get_snapshot(b, "workspace", ("one",)) is None
    a.write_bytes(b"new snapshot marker")
    assert view_cache.get_snapshot(a, "workspace", ("one",)) is None


def test_0452_import_visibility_is_persistent_and_only_for_completed(tmp_path, monkeypatch):
    db = tmp_path / "imports.sqlite3"
    initialize_database(db)
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    monkeypatch.setattr(main, "backup_deletion_status", lambda *args, **kwargs: {
        "allowed": False, "reason": "Geschützte Sicherung",
    })
    with database_connection(db) as conn:
        conn.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at,operation)"
            " VALUES ('done','sd_import','approved_sd','completed','completed','2026-10-08','2026-10-08','folder_import')"
        )
        conn.execute(
            "INSERT INTO jobs(id,kind,trigger_type,state,stage,created_at,updated_at,operation)"
            " VALUES ('busy','sd_import','approved_sd','copying','copying','2026-10-09','2026-10-09','folder_import')"
        )
    before = main.api_import_history(limit=20)
    assert before["total"] == 2
    assert {r["id"] for r in before["jobs"]} == {"done", "busy"}
    denied = None
    try:
        main.api_import_history_visibility("busy", {"hidden": True})
    except Exception as error:
        denied = error
    assert getattr(denied, "status_code", None) == 409
    assert main.api_import_history_visibility("done", {"hidden": True})["hidden"]
    visible = main.api_import_history(limit=20)
    assert [j["id"] for j in visible["jobs"]] == ["busy"]
    hidden = main.api_import_history(hidden=True, limit=20)
    assert [j["id"] for j in hidden["jobs"]] == ["done"]
    with database_connection(db) as conn:
        assert conn.execute("SELECT history_hidden FROM jobs WHERE id='done'").fetchone()[0] == 1
        assert conn.execute("SELECT state FROM jobs WHERE id='done'").fetchone()[0] == "completed"
    main.api_import_history_visibility("done", {"hidden": False})
    assert main.api_import_history(hidden=True)["total"] == 0


def test_0452_physical_check_once_then_fast_search(tmp_path, monkeypatch):
    path = tmp_path / "library.sqlite3"
    path.write_bytes(b"test")
    calls = []
    monkeypatch.setattr(main, "current_database_file", lambda: path)
    monkeypatch.setattr(main, "current_workspace_root", lambda: tmp_path)
    monkeypatch.setattr(main, "current_archive_root", lambda: tmp_path)
    monkeypatch.setattr(main, "refresh_live_event_inventories", lambda *args: calls.append("scan"))
    monkeypatch.setattr(main, "reconcile_global_central_stock_state", lambda **kwargs: calls.append("stock"))
    monkeypatch.setattr(main, "detect_all_event_structure_changes", lambda *args: calls.append("change"))
    monkeypatch.setattr(main, "search_events", lambda *args, **kwargs: {"events": [], "q": kwargs["query"]})
    assert main.api_search_events(q="Test", physical_refresh=False)["q"] == "Test"
    assert calls == ["scan", "stock", "change"]
    assert main.api_search_events(q="Test", physical_refresh=False)["q"] == "Test"
    assert calls == ["scan", "stock", "change"]
    main.api_search_events(q="Test", physical_refresh=True)
    assert calls == ["scan", "stock", "change", "scan", "stock", "change"]


def test_0452_history_ui_is_compact_and_paginated():
    from pathlib import Path
    source = Path(main.__file__).read_text(encoding="utf-8")
    for item in (
        'data-history-toggle=', 'data-history-hide=', 'data-history-unhide=',
        'bk-history-spinner', 'requestHistoryPages(hidden, count)',
        'history_hidden=?', 'backup_delete_allowed', 'restoreOpenJobDetails',
    ):
        assert item in source


def test_0452_hidden_history_remains_reachable_without_visible_jobs():
    from pathlib import Path
    source = Path(main.__file__).read_text(encoding="utf-8")
    assert "renderJobHistory(openDetails);" in source
    assert "Keine sichtbaren Importe vorhanden." in source
    assert 'if(!jobHistoryJobs.length && !hiddenHistoryTotal)' not in source
    assert 'activeStates.has(job.state)' in source


def test_0452_cache_ttl_for_external_mount_state(tmp_path, monkeypatch):
    import app.view_cache as cache
    db = tmp_path / "main.sqlite3"
    db.write_bytes(b"test")
    cache.put_snapshot(db, "import-sources", {"mounted": True})
    assert cache.get_snapshot(db, "import-sources", max_age_seconds=15) == {"mounted": True}
    baseline = cache.time.monotonic()
    monkeypatch.setattr(cache.time, "monotonic", lambda: baseline + 1800)
    assert cache.get_snapshot(db, "import-sources", max_age_seconds=15) is None


def test_0452_github_build_is_manual_for_patch_branches():
    from pathlib import Path
    project = Path(__file__).resolve().parents[2]
    qa = (project / ".github/workflows/qa-tests.yml").read_text(encoding="utf-8")
    publish = (project / ".github/workflows/publish-container.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in qa
    assert "workflow_dispatch:" in publish
    assert "'patch/**'" not in qa
    assert "'patch/**'" not in publish
    assert "type=raw,value=patch-" in publish


def test_0452_patch_publish_requires_explicit_release_request():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    main_workflow = (root / ".github/workflows/publish-container.yml").read_text()
    trigger_workflow = (root / ".github/workflows/publish-patch-request.yml").read_text()
    assert "workflow_call:" in main_workflow
    assert "'patch/**'" in trigger_workflow
    assert "'.github/release-requests/**'" in trigger_workflow
    assert "uses: ./.github/workflows/publish-container.yml" in trigger_workflow


def test_0452_import_history_excludes_internal_metadata_jobs(tmp_path, monkeypatch):
    db = tmp_path / "global.sqlite3"
    initialize_database(db)
    monkeypatch.setattr(main, "DATABASE_FILE", db)
    with database_connection(db) as conn:
        for ident, operation in (
            ("VISIBLE", "folder_import"),
            ("INTERNAL_GENERAL", "metadata_general_import"),
            ("INTERNAL_MULTIPLE", "metadata_multiple_import"),
        ):
            conn.execute(
                "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,created_at,updated_at)"
                " VALUES (?, 'sd_import', 'manual', 'completed', 'completed', ?, ?, ?)",
                (ident, operation, "2026-10-08T13:00:00", "2026-10-08T13:00:00"),
            )
    result = main.api_import_history(limit=10)
    assert result["total"] == 1
    assert [job["id"] for job in result["jobs"]] == ["VISIBLE"]
