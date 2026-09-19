from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0221_mobile_rail_navigation_is_present():
    html = main.index()
    assert 'id="bk-mobile-nav-toggle"' in html
    assert 'class="bk-tab-mobile-label">Import</span>' in html
    assert 'class="bk-tab-mobile-label">Arbeitsbereich</span>' in html
    assert 'class="bk-tab-mobile-label">Archiv</span>' in html
    assert 'data-bk-area="import"' in html


def test_0221_mobile_css_uses_side_rail_and_full_overlay_menu():
    assert '@media (max-width: 700px) and (orientation: portrait)' in BIBLIOTHEKAR_CSS
    assert 'position: fixed;' in BIBLIOTHEKAR_CSS
    assert 'writing-mode: vertical-rl;' in BIBLIOTHEKAR_CSS
    assert 'body.bk-mobile-nav-collapsed .bk-tabs' in BIBLIOTHEKAR_CSS
    assert 'z-index: 5700;' in BIBLIOTHEKAR_CSS


def test_0221_area_tints_and_green_create_button():
    assert 'body[data-bk-area="import"]' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="workspace"]' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="archive"]' in BIBLIOTHEKAR_CSS
    assert '#new-event-button' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-green) !important;' in BIBLIOTHEKAR_CSS


def test_0221_mobile_assistant_uses_dedicated_mode():
    html = main.index()
    assert 'id="bk-ai-launcher"' in html
    assert 'id="bk-ai-panel"' in html
    assert 'id="bk-ai-close"' in html
    assert 'aria-expanded="false"' in html
