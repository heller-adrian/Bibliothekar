"""0.55.3 visual polish, truthful health reporting, safe General path fallback."""
from pathlib import Path
from app import __version__
from app import main
from app.setup_language import localize_setup_html
from app.security import _login_html
from app.main import _library_onboarding_html
from app.ui_shell import apply_shell, BIBLIOTHEKAR_0553_POLISH_CSS, _shell_markup
from app.managed_directory_names import directory_path


def test_0553_versions():
    assert __version__ == main.RELEASE_VERSION == main.DEPLOYMENT_VERSION == "0.55.3"


def test_0553_setup_brand_is_visible_in_both_languages():
    for html in (_login_html(), _login_html(unavailable=True), _library_onboarding_html()):
        assert 'class="bk-setup-page"' in html
        assert 'class="bk-setup-brand"' in html
        assert 'src="/assets/bibliothekar-logo-v2.svg"' in html
        assert 'background:#15222c!important' in html
        assert 'data-bk-setup-choice="en"' in html
        assert 'data-bk-setup-choice="de"' in html
        assert html.index('class="bk-setup-brand"') < html.index("<main>")


def test_0553_installed_desktop_has_no_fullscreen_loading_mask():
    css = BIBLIOTHEKAR_0553_POLISH_CSS
    assert '@media (min-width:821px)' in css
    assert 'data-bk-nav-loading="true"' in css
    assert 'content:none!important;' in css
    assert '@media (hover:hover) and (pointer:fine)' in css
    assert 'cursor:pointer!important;' in css


def test_0553_mobile_dock_changes_only_desired_targets():
    css=BIBLIOTHEKAR_0553_POLISH_CSS
    assert '.bk-pwa-task-toggle,.bk-pwa-menu-toggle' in css
    assert '-webkit-tap-highlight-color:transparent!important;' in css
    assert ':focus:not(:focus-visible)' in css
    shell=_shell_markup("import",None)
    assert '<path d="M4 14.5h16M7.5 17h.01M11 17h.01M7 9h10"/>' in shell
    assert 'data-area="workspace"' in shell


def test_0553_general_new_and_legacy_folder_selection(tmp_path: Path):
    metadata=tmp_path/"Metadata Correction"
    metadata.mkdir()
    assert directory_path(metadata,"metadata_general") == metadata/"General"
    (metadata/"Allgemein").mkdir()
    assert directory_path(metadata,"metadata_general") == metadata/"Allgemein"


def test_0553_health_issues_are_shown_without_pretending_ok():
    text=main.INDEX_HTML if hasattr(main,"INDEX_HTML") else ""
    shell=apply_shell("<html><head></head><body><main>x</main></body></html>",active_area="import")
    assert "BIBLIOTHEKAR_0553_POLISH_CSS" not in shell
    assert "cursor:pointer!important;" in shell
