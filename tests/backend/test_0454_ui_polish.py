"""0.45.6: Importverlauf, Klickhilfen und dezente UI-Übergänge."""
from pathlib import Path

from app import __version__, main
from app.database import database_connection, initialize_database
from app.events_ui import EVENTS_HTML
from app.ui_shell import (
    BIBLIOTHEKAR_0353_CSS,
    BIBLIOTHEKAR_0454_CSS,
    BIBLIOTHEKAR_JS,
    apply_shell,
)

ROOT = Path(__file__).resolve().parents[2]


def test_0454_version_and_style_is_loaded():
    assert __version__ == "0.45.6"
    assert main.DEPLOYMENT_VERSION == "0.45.6"
    page = apply_shell("<html><head></head><body></body></html>", active_area="workspace", subarea="events")
    assert "0.45.6 · Kamerakern 0.32.11" in page
    assert f"<style>{BIBLIOTHEKAR_0454_CSS}</style>" in page


def test_0454_hidden_count_is_lightweight_and_persistent(tmp_path, monkeypatch):
    db = tmp_path / "history.sqlite3"
    initialize_database(db)
    monkeypatch.setattr(main, "DATABASE_FILE", db)

    def no_expensive_lookup(*args, **kwargs):
        raise AssertionError("Count-only must not fetch a backup or file metadata")

    monkeypatch.setattr(main, "get_job", no_expensive_lookup)
    monkeypatch.setattr(main, "backup_deletion_status", no_expensive_lookup)
    with database_connection(db) as conn:
        for ident, is_hidden in (("hidden", 1), ("visible", 0)):
            conn.execute(
                "INSERT INTO jobs(id,kind,trigger_type,state,stage,operation,created_at,updated_at,history_hidden) "
                "VALUES (?, 'sd_import','manual','completed','completed','folder_import',"
                "'2026-10-08T12:00:00','2026-10-08T12:00:00',?)",
                (ident, is_hidden),
            )
    hidden = main.api_import_history(hidden=True, count_only=True)
    visible = main.api_import_history(hidden=False, count_only=True)
    assert hidden == {"jobs": [], "total": 1, "has_more": False}
    assert visible == {"jobs": [], "total": 1, "has_more": False}
    main.api_import_history_visibility("visible", {"hidden": True})
    assert main.api_import_history(hidden=True, count_only=True)["total"] == 2
    main.api_import_history_visibility("hidden", {"hidden": False})
    assert main.api_import_history(hidden=True, count_only=True)["total"] == 1


def test_0454_hidden_history_opens_immediately_and_discards_stale_data():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    drawer = source.split("function renderJobHistory(openDetails", 1)[1].split(
        "function bindHistoryButtons(host)", 1
    )[0]
    assert 'list.hidden = !hiddenHistoryOpen;' in drawer
    assert 'toggle.setAttribute("aria-expanded", String(hiddenHistoryOpen))' in drawer
    assert "void loadHiddenHistory().catch(showError)" in drawer
    assert "await loadHiddenHistory();" not in drawer
    assert "requestId !== hiddenHistoryRequestId" in source
    assert "requestId !== importHistoryRequestId" in source
    assert "const [data, hiddenCount] = await Promise.all([" in source
    assert "/api/import-history?hidden=true&count_only=true" in source
    assert "sessionStorage.getItem(importHistoryCacheKey)" not in source


def test_0454_import_detail_contents_are_full_width():
    css = BIBLIOTHEKAR_0454_CSS
    assert ".bk-history-details .bk-history-expanded" in css
    assert "display:block !important;" in css
    assert "grid-template-columns:none !important;" in css


def test_0454_all_title_help_is_click_only_and_floats():
    assert ".bk-title-help:hover::after" not in BIBLIOTHEKAR_0353_CSS
    assert "bkTitleHelpMedia?.matches" not in BIBLIOTHEKAR_JS
    assert 'trigger.addEventListener("click", event => {' in BIBLIOTHEKAR_JS
    assert ".bk-title-help.is-open::after" in BIBLIOTHEKAR_0454_CSS
    assert "position:absolute;" in BIBLIOTHEKAR_0454_CSS
    assert "pointer-events:none;" in BIBLIOTHEKAR_0454_CSS


def test_0454_events_summary_has_no_unused_status_gap():
    assert ".status:empty { display:none; }" in EVENTS_HTML
    assert "main > #status:empty" in BIBLIOTHEKAR_0454_CSS


def test_0454_hover_is_consistent_but_not_a_selection():
    css = BIBLIOTHEKAR_0454_CSS
    assert ".day-card:not(.review-card):not(.selected):hover" in css
    assert ".day-card.review-card:hover" in css
    assert ".timeline-event-card:not(.selected-preview):hover" in css
    assert ".event-card:not(.selected-preview):not(.is-open):hover" in css
    assert ".24s ease-in-out" in css
    assert "@media (prefers-reduced-motion:reduce)" in css
