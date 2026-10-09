"""0.47.3: kompakter, seitenfarbiger PWA-Kopf und großer, lesbarer Dock."""
from pathlib import Path

from app import __version__, main
from app.ui_shell import BIBLIOTHEKAR_0470_CSS, BIBLIOTHEKAR_0470_HEAD_JS, apply_shell

ROOT = Path(__file__).resolve().parents[2]


def test_0470_version_and_pwa_css_injected_after_branding():
    assert __version__ == main.DEPLOYMENT_VERSION == "0.47.6"
    html = apply_shell("<html><head></head><body><main></main></body></html>", active_area="import")
    assert "<style>" + BIBLIOTHEKAR_0470_CSS + "</style>" in html
    assert "BIBLIOTHEKAR_0460_CSS" not in html
    assert 'src="/assets/bibliothekar-logo-v2.svg?v=0.47.3"' in html


def test_0470_about_modal_shows_white_vector_logo_on_dark_ground():
    html = apply_shell("<html><head></head><body></body></html>", active_area="archive")
    about = html.split('<dialog id="bk-about-dialog"', 1)[1].split("</dialog>", 1)[0]
    assert 'class="bk-about-logo-heading"' in about
    assert 'alt="Bibliothekar"' in about
    assert 'src="/assets/bibliothekar-logo-v2.svg?v=0.47.3"' in about
    assert "<h2>Bibliothekar</h2>" not in about
    assert "Sichern · Ordnen · Bewahren" in about
    assert "background:#15222c" in BIBLIOTHEKAR_0470_CSS


def test_0470_top_shell_hidden_only_inside_mobile_standalone():
    css = BIBLIOTHEKAR_0470_CSS
    assert '@media (max-width:820px)' in css
    assert 'html[data-bk-display-mode="standalone"] body.bibliothekar-redesign > .bk-shell' in css
    assert "display:none !important" in css
    assert 'html[data-bk-display-mode="browser"]' not in css
    assert 'body.bibliothekar-redesign:not([data-bk-area="workspace"]):not([data-bk-area="metadata"]) > .bk-page-heading' in css
    for area in ["import", "workspace", "archive", "metadata", "assistant", "trash"]:
        assert f':has(body[data-bk-area="{area}"])' in css


def test_0470_work_and_metadata_subnav_cover_safe_area_and_stick_to_top():
    css = BIBLIOTHEKAR_0470_CSS
    assert "env(safe-area-inset-top)" in css
    assert "padding-top:calc(max(44px, env(safe-area-inset-top)) + 6px)" in css
    assert 'body.bibliothekar-redesign[data-bk-area="workspace"] > .bk-workspace-subnav' in css
    assert 'body.bibliothekar-redesign[data-bk-area="metadata"] > .bk-metadata-subnav' in css
    assert "top:0 !important" in css
    assert "background:var(--bk-page-bg) !important" in css
    js = (ROOT / "app/ui_shell.py").read_text(encoding="utf-8")
    assert 'const shellHeight=compactPwa ? 0 :' in js


def test_0470_dock_large_labels_not_ellipsized_and_dialog_above():
    css = BIBLIOTHEKAR_0470_CSS
    assert 'min-height:87px !important' in css
    assert 'width:32px !important' in css
    assert 'text-overflow:clip !important' in css
    assert 'white-space:nowrap !important' in css
    assert '.bk-pwa-task-toggle .bk-pwa-label' in css
    assert 'display:grid !important' in css
    assert 'bottom:calc(120px + env(safe-area-inset-bottom)) !important' in css
    assert 'data-bk-area="metadata"].bk-meta-selection-sheet-open main' in css
    html = apply_shell("<html><head></head><body></body></html>", active_area="trash")
    for label in ["Import", "Arbeitsbereich", "Archiv", "Aufgaben"]:
        assert f'<span class="bk-pwa-label">{label}</span>' in html


def test_0470_status_bar_theme_follows_page_and_pwa_only():
    html = apply_shell("<html><head></head><body></body></html>", active_area="import")
    assert "<script>" + BIBLIOTHEKAR_0470_HEAD_JS + "</script>" in html
    script=BIBLIOTHEKAR_0470_HEAD_JS
    assert 'root.dataset.bkDisplayMode!=="standalone"' in script
    assert '"#f8efec","#120f11"' in script
    assert '"#eef4f8","#0c1217"' in script
    assert '"#f8f4e8","#14120c"' in script
    assert 'apple-mobile-web-app-status-bar-style' in script
    assert 'dark?"black-translucent":"default"' in script
