"""0.45.3: störungsfreier Wechsel zwischen Hauptbereichen und früher Dark-Mode-Paint."""
from app import __version__, main
from app.ui_shell import (
    BIBLIOTHEKAR_0451_HEAD_JS, BIBLIOTHEKAR_0451_CSS,
    BIBLIOTHEKAR_JS, apply_shell,
)


def test_0451_versions():
    assert __version__ == "0.55.1"
    assert main.DEPLOYMENT_VERSION == "0.55.1"


def test_0451_theme_script_is_in_head_before_all_styles():
    sample = '<!doctype html><html lang="de"><head><style>body{color:red}</style></head>' \
             '<body><main>x</main></body></html>'
    rendered = apply_shell(sample, active_area="workspace")
    head = rendered.split("</head>", 1)[0]
    assert head.index('localStorage.getItem("bibliothekar-language")') < head.index("<style>")
    assert head.index('localStorage.getItem("bibliothekar-theme")') < head.index("<style>", head.index('localStorage.getItem("bibliothekar-theme")'))
    assert head.index("bk-tab-navigation-0451") < head.index("<style>", head.index("bk-tab-navigation-0451"))
    assert head.index("<script>") < head.index("<style>")
    assert rendered.count('data-bk-area="workspace"') >= 1


def test_0451_theme_and_pwa_are_preseeded_synchronously():
    init = BIBLIOTHEKAR_0451_HEAD_JS
    assert 'root.dataset.bkTheme' in init
    assert 'choice === "system" && systemDark' in init
    assert 'root.dataset.bkDisplayMode' in init
    assert 'sessionStorage.removeItem(key)' in init
    assert 'Date.now() - Number(saved.at) < 30000' in init
    assert 'next.pathname === location.pathname' in init
    assert 'html[data-bk-theme="dark"]' in BIBLIOTHEKAR_0451_CSS
    assert 'html[data-bk-theme="light"]' in BIBLIOTHEKAR_0451_CSS


def test_0451_navigation_has_single_press_and_arrival_motion():
    script = BIBLIOTHEKAR_JS
    css = BIBLIOTHEKAR_0451_CSS
    assert 'addEventListener("pointerdown"' in script
    assert 'addEventListener("pointerup"' in script
    assert 'addEventListener("pointercancel"' in script
    assert 'bkTabNavigationStarted = true' in script
    assert 'window.setTimeout(() => window.location.assign(href), 190)' not in script
    assert 'requestAnimationFrame(() => requestAnimationFrame(() => window.location.assign(href)))' in script
    assert 'sessionStorage.setItem("bk-tab-navigation-0451"' in script
    assert 'requestAnimationFrame(() => requestAnimationFrame(' in script
    assert 'window.addEventListener("pageshow", event =>' in script
    assert '.bk-tab.bk-tab-pressing:not(.active)' in css
    assert '@media (hover: none), (pointer: coarse)' in css
    assert 'html[data-bk-nav-arriving="workspace"] .bk-tab.active' in css
    assert '.bk-tab.active { animation: none; }' in css
    assert '@media (prefers-reduced-motion: reduce)' in css


def test_0451_original_shell_css_keeps_0450_typography():
    html = apply_shell('<html><head></head><body></body></html>', active_area="import")
    assert 'Futura, "Helvetica Neue", Helvetica, Arial, sans-serif' in html
    assert BIBLIOTHEKAR_0451_CSS in html
    assert 'href="/assistant"' not in html
