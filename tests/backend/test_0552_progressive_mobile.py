"""0.55.2 – mobile stage-one navigation without fullscreen loading masks."""
from app import __version__
from app import main
from app.ui_shell import (
    apply_shell, BIBLIOTHEKAR_0552_PROGRESSIVE_CSS, BIBLIOTHEKAR_0505_LANGUAGE_CSS,
)
from app.ui_i18n import I18N_UI_JS


def test_0552_version_and_early_shell_before_main():
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == "0.55.3"
    for area, subarea, heading in (
        ("import", None, "Import &amp; Prüfung"),
        ("workspace", "captures", "Aufnahmen"),
        ("workspace", "events", "Ereignisse"),
        ("archive", None, "Archiv"),
    ):
        html = apply_shell("<html><head></head><body><main>Loading</main></body></html>",
                           active_area=area, subarea=subarea)
        # Translation runs after the server-rendered shell, and before <main>.
        assert html.index('<nav class="bk-pwa-dock"') < html.index(I18N_UI_JS[:80])
        assert html.index(I18N_UI_JS[:80]) < html.index("<main>Loading")
        assert html.count(I18N_UI_JS[:80]) == 1
        assert 'BIBLIOTHEKAR_0552_EARLY_LINKS_JS' not in html
        assert heading in html


def test_0552_subnav_and_dock_are_not_covered_by_busy_overlay():
    html=apply_shell("<html><head></head><body><main></main></body></html>",
                     active_area="workspace", subarea="captures")
    assert 'href="/events"' in html
    assert "bk-workspace-subnav" in html
    assert 'body > main' in BIBLIOTHEKAR_0505_LANGUAGE_CSS
    assert 'body { visibility: hidden !important; }' not in BIBLIOTHEKAR_0505_LANGUAGE_CSS
    assert '[data-bk-i18n-pending="true"]::before' in BIBLIOTHEKAR_0552_PROGRESSIVE_CSS
    assert 'content:none!important;' in BIBLIOTHEKAR_0552_PROGRESSIVE_CSS
    assert 'body > main' in BIBLIOTHEKAR_0552_PROGRESSIVE_CSS
    assert 'pointer-events:none;' in BIBLIOTHEKAR_0552_PROGRESSIVE_CSS


def test_0552_dock_accents_are_owned_by_destination_links():
    css=BIBLIOTHEKAR_0552_PROGRESSIVE_CSS
    for key, color in (("import","red"),("workspace","blue"),("archive","yellow")):
        assert f'.bk-pwa-nav-item[data-area="{key}"]' in css
        assert f'--bk-area-accent:var(--bk-{color});' in css


def test_0552_i18n_reveals_main_at_dom_ready_not_api_completion():
    assert 'if (document.readyState === "loading" && !document.querySelector?.(".bk-shell"))' in I18N_UI_JS
    assert 'document.addEventListener("DOMContentLoaded", () => {' in I18N_UI_JS
    assert 'walk(document.body);' in I18N_UI_JS
    assert 'delete document.documentElement.dataset.bkI18nPending;' in I18N_UI_JS
    assert 'fetch(' not in I18N_UI_JS.split('function init()',1)[1].split('})();',1)[0]
