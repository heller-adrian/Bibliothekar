from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0221_version():
    assert main.APP_VERSION == "0.22.1"


def test_0221_import_uses_single_source_trigger_and_icon_options():
    html = main.index()

    assert 'id="bk-source-trigger"' in html
    assert 'id="bk-source-menu"' in html
    assert 'data-source-mode="sd"' in html
    assert 'data-source-mode="drive"' in html
    assert 'data-source-mode="folder"' in html

    assert 'class="bk-action-tile bk-action-mount"' in html
    assert 'class="bk-action-tile bk-action-save"' in html
    assert 'class="bk-action-tile bk-action-eject"' in html


def test_0221_desktop_theme_overrides_legacy_dark_workspace():
    assert 'html[data-bk-theme="light"] {' in BIBLIOTHEKAR_CSS
    assert '--background: var(--bk-paper);' in BIBLIOTHEKAR_CSS
    assert 'html[data-bk-theme] body.bibliothekar-redesign main' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-paper) !important;' in BIBLIOTHEKAR_CSS


def test_0221_tabs_and_menu_use_refined_components():
    assert 'border-top: 5px solid transparent;' in BIBLIOTHEKAR_CSS
    assert 'border-top-color: var(--bk-tab-accent);' in BIBLIOTHEKAR_CSS
    assert '.bk-menu {' in BIBLIOTHEKAR_CSS
    assert 'display: grid;' in BIBLIOTHEKAR_CSS
    assert '.bk-action-save' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-green) !important;' in BIBLIOTHEKAR_CSS
