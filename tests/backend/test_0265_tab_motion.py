from app.ui_shell import BIBLIOTHEKAR_CSS, BIBLIOTHEKAR_JS


def test_0265_main_tabs_lift_instead_of_brighten():
    assert ".bk-tab:hover:not(.active)" in BIBLIOTHEKAR_CSS
    assert "transform: translateY(-3px);" in BIBLIOTHEKAR_CSS
    assert ".bk-tab.is-navigating:not(.active)" in BIBLIOTHEKAR_CSS
    assert "transform: translateY(-8px);" in BIBLIOTHEKAR_CSS
    assert "--bk-tab-motion-tail: 9px;" in BIBLIOTHEKAR_CSS
    assert ".bk-tab:not(.active)::before" in BIBLIOTHEKAR_CSS
    assert "bottom: calc(-1 * var(--bk-tab-motion-tail));" in BIBLIOTHEKAR_CSS
    assert "z-index: 55 !important" not in BIBLIOTHEKAR_CSS
    assert "z-index: 60 !important" not in BIBLIOTHEKAR_CSS
    assert "filter: brightness(1.025)" not in BIBLIOTHEKAR_CSS
    assert ".bk-tab:hover:not(.active)::before" in BIBLIOTHEKAR_CSS
    assert ".bk-tab.is-navigating:not(.active)::before" in BIBLIOTHEKAR_CSS
    assert "border-top-left-radius: 17px;" in BIBLIOTHEKAR_CSS
    assert "border-top-right-radius: 17px;" in BIBLIOTHEKAR_CSS
    assert "border-top-left-radius: 12px;" in BIBLIOTHEKAR_CSS
    assert "border-top-right-radius: 12px;" in BIBLIOTHEKAR_CSS
    assert "@keyframes bk-tab-arrive" in BIBLIOTHEKAR_CSS
    assert "prefers-reduced-motion: reduce" in BIBLIOTHEKAR_CSS
    assert "-webkit-tap-highlight-color: transparent;" in BIBLIOTHEKAR_CSS
    assert "-webkit-touch-callout: none;" in BIBLIOTHEKAR_CSS
    assert ".bk-tab:focus-visible" in BIBLIOTHEKAR_CSS


def test_0265_main_tab_click_animation_preserves_modified_clicks():
    assert 'document.querySelectorAll(".bk-tab").forEach(tab =>' in BIBLIOTHEKAR_JS
    assert 'tab.classList.add("is-navigating")' in BIBLIOTHEKAR_JS
    assert "event.metaKey" in BIBLIOTHEKAR_JS
    assert "event.ctrlKey" in BIBLIOTHEKAR_JS
    assert "event.shiftKey" in BIBLIOTHEKAR_JS
    assert "event.altKey" in BIBLIOTHEKAR_JS
    assert "window.location.assign(href)" in BIBLIOTHEKAR_JS
