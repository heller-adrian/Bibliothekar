from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0221_mobile_navigation_keeps_three_main_registers_on_top():
    html = main.index()
    assert 'id="bk-mobile-nav-toggle"' not in html
    assert 'class="bk-tab-mobile-label">Import</span>' in html
    assert 'class="bk-tab-mobile-label">Arbeitsbereich</span>' in html
    assert 'class="bk-tab-mobile-label">Archiv</span>' in html
    assert 'class="bk-tab-mobile-label">KI</span>' not in html
    assert 'href="/assistant"' in html
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


def test_0221_assistant_is_small_header_action_not_large_register():
    html = main.index()
    assert 'bk-assistant-button' in html
    assert 'href="/assistant"' in html
    assert 'id="bk-ai-tab"' not in html
    assert 'id="bk-ai-panel"' not in html


def test_0222_mobile_tabs_keep_trapezoid_with_joined_page_surface():
    html = main.index()
    assert 'transform: perspective(88px) rotateX(5deg);' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-overlap: clamp(12px, 4vw, 18px);' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-seam-bleed: clamp(3px, 1vw, 5px);' in BIBLIOTHEKAR_CSS
    assert '--bk-edge-gradient-width: clamp(18px, 5vw, 28px);' in BIBLIOTHEKAR_CSS
    assert '--bk-page-bridge-height: 10px;' in BIBLIOTHEKAR_CSS
    assert 'bottom: calc(-1 * var(--bk-page-bridge-height));' in BIBLIOTHEKAR_CSS
    assert 'margin-left: calc(0px - var(--bk-tab-overlap));' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-size' not in BIBLIOTHEKAR_CSS
    assert 'bk-tab-shoulder' not in html


def test_0223_narrow_portrait_keeps_the_shared_overlap_geometry():
    assert '@media (max-width: 430px)' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-overlap: 4px;' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-overlap: clamp(12px, 4vw, 18px);' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-seam-bleed: clamp(3px, 1vw, 5px);' in BIBLIOTHEKAR_CSS
    assert '--bk-edge-gradient-width: clamp(18px, 6vw, 28px);' in BIBLIOTHEKAR_CSS


def test_0223_mobile_uses_same_angled_depth_cues_as_desktop():
    assert '--bk-edge-gradient-angle-right: 100deg;' in BIBLIOTHEKAR_CSS
    assert '--bk-edge-gradient-angle-left: 260deg;' in BIBLIOTHEKAR_CSS
