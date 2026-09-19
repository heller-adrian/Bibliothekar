from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0221_mobile_navigation_returns_to_top_header():
    html = main.index()
    assert 'id="bk-mobile-nav-toggle"' not in html
    assert 'class="bk-tab-mobile-label">Import</span>' in html
    assert 'class="bk-tab-mobile-label">Arbeitsbereich</span>' in html
    assert 'class="bk-tab-mobile-label">Archiv</span>' in html
    assert 'class="bk-tab-mobile-label">KI</span>' in html
    assert 'data-bk-area="import"' in html


def test_0221_mobile_css_uses_compact_horizontal_registers():
    assert '@media (max-width: 820px)' in BIBLIOTHEKAR_CSS
    assert 'grid-column: 1 / -1;' in BIBLIOTHEKAR_CSS
    assert 'writing-mode: vertical-rl;' not in BIBLIOTHEKAR_CSS
    assert 'bk-mobile-nav-collapsed' not in BIBLIOTHEKAR_CSS
    assert 'z-index: 9000;' in BIBLIOTHEKAR_CSS


def test_0221_mobile_sources_remain_three_cards():
    assert '.bk-source-picker {' in BIBLIOTHEKAR_CSS
    assert 'grid-template-columns: repeat(3, minmax(0, 1fr));' in BIBLIOTHEKAR_CSS
    assert '.bk-source-option small { display: none; }' in BIBLIOTHEKAR_CSS


def test_0221_assistant_is_a_header_register_not_floating_button():
    html = main.index()
    assert 'id="bk-ai-tab"' in html
    assert 'data-area="assistant"' in html
    assert 'id="bk-ai-panel"' in html
    assert 'id="bk-ai-close"' in html
    assert 'id="bk-ai-launcher"' not in html
