"""UI-Abnahme 0.45.3: Importkarten, Theme, mobile Aktionen, Hovers, Suche."""
from pathlib import Path

from app import __version__, main
from app.events_ui import EVENTS_HTML
from app.ui_shell import BIBLIOTHEKAR_0453_CSS, apply_shell

ROOT = Path(__file__).resolve().parents[2]


def test_0453_release_version():
    assert __version__ == "0.47.4"
    assert main.DEPLOYMENT_VERSION == "0.47.4"
    assert "Version <span data-bk-version>0.47.4</span>" in apply_shell(
        "<html><head></head><body></body></html>", active_area="import"
    )


def test_0453_import_details_do_not_repeat_compact_title_and_controls_are_last():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    card = source.split("    function renderJob(job, isHidden=false) {", 1)[1].split(
        "    async function loadHealth()", 1
    )[0]
    detail = card.split("const detailMarkup = `", 1)[1].split("`;", 1)[0]
    assert 'class="job-name"' not in detail
    assert 'class="job-title"' not in detail
    assert 'class="bk-history-detail-date"' in detail
    assert 'data-history-toggle=' in card
    # Nach dem aufklappbaren Detailbereich folgen die Aktionen.
    assert card.rindex('class="bk-history-details"') < card.rindex(
        'class="bk-history-actions"'
    )
    assert 'data-delete-backup=' in card
    assert 'data-history-hide=' in card
    assert 'data-history-unhide=' in card


def test_0453_import_cards_use_light_theme_and_mobile_footer():
    css = BIBLIOTHEKAR_0453_CSS
    assert 'html[data-bk-theme="light"]' in css
    assert '.bk-history-row {' in css
    assert 'background:var(--surface-soft) !important;' in css
    assert '.bk-history-details {' in css
    assert 'background:var(--surface) !important;' in css
    assert '@media(max-width:700px)' in css
    assert '.bk-history-actions {' in css
    assert 'grid-row:3;' in css
    assert 'flex-direction:row !important;' in css
    assert '#hidden-history-toggle' in css


def test_0453_hidden_history_is_accessible_text_button():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    block = source.split('function renderJobHistory(openDetails',1)[1].split(
        'function bindHistoryButtons',1
    )[0]
    assert 'Ausgeblendet (' in block
    assert '◉' not in block
    assert '▾' not in block
    assert '▴' not in block
    assert 'aria-expanded=' in block
    assert "label.textContent = 'Ausgeblendet ('" in source


def test_0453_event_search_is_icon_only_and_accessibly_named():
    assert '<span>Ereignisse suchen</span>' not in EVENTS_HTML
    assert '<label class="bk-visually-hidden" for="event-search">' in EVENTS_HTML
    assert 'class="bk-event-search-icon"' in EVENTS_HTML
    assert 'Suche nach Name, Datum oder Sicherung …' in EVENTS_HTML
    assert 'grid-template-columns:minmax(0,max-content) minmax(200px,1fr) auto;' in EVENTS_HTML
    assert 'gap:12px 32px !important;' in EVENTS_HTML


def test_0453_hover_and_footer_do_not_change_storage_logic():
    css = BIBLIOTHEKAR_0453_CSS
    assert '@media(hover:hover) and (pointer:fine)' in css
    assert '.day-card:not(.review-card):not(.selected):hover' in css
    assert '.event-card:not(.is-open):hover' in css
    assert 'padding-bottom:max(180px, 23vh) !important;' in css
    assert '@media(prefers-reduced-motion:reduce)' in css
