from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0221_version():
    assert main.APP_VERSION == "0.22.1"


def test_0221_import_uses_three_source_cards_and_keeps_all_paths():
    html = main.index()

    assert 'id="bk-source-trigger"' not in html
    assert 'id="bk-source-menu"' not in html
    assert html.count('data-source-mode=') == 3
    assert 'data-source-mode="sd"' in html
    assert 'data-source-mode="drive"' in html
    assert 'data-source-mode="folder"' in html
    assert 'id="device-select"' in html
    assert 'id="folder-root-select"' in html
    assert 'id="source-select"' in html

    assert 'class="bk-action-tile bk-action-mount"' in html
    assert 'class="bk-action-tile bk-action-save"' in html
    assert 'class="bk-action-tile bk-action-eject"' in html


def test_0221_desktop_theme_overrides_legacy_dark_workspace():
    assert 'html[data-bk-theme="light"] {' in BIBLIOTHEKAR_CSS
    assert '--background: var(--bk-paper);' in BIBLIOTHEKAR_CSS
    assert 'html[data-bk-theme] body.bibliothekar-redesign main' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-page-bg, var(--bk-paper)) !important;' in BIBLIOTHEKAR_CSS


def test_0221_only_three_main_registers_and_assistant_is_header_action():
    html = main.index()

    assert 'bk-tabs-active-import' in html
    assert html.count('class="bk-tab') == 3
    assert 'data-area="import"' in html
    assert 'data-area="workspace"' in html
    assert 'data-area="archive"' in html
    assert 'data-area="assistant"' not in html
    assert 'href="/assistant"' in html
    assert 'bk-assistant-button' in html

    assert '.bk-tabs-active-workspace' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-archive' in BIBLIOTHEKAR_CSS
    assert '.bk-tab::before,' in BIBLIOTHEKAR_CSS
    assert 'transform: skewX(-11deg);' in BIBLIOTHEKAR_CSS
    assert 'border-radius: 14px 14px 0 0 !important;' in BIBLIOTHEKAR_CSS


def test_0221_page_accents_match_import_workspace_and_archive():
    assert 'body[data-bk-area="import"] .import-panel' in BIBLIOTHEKAR_CSS
    assert 'border-left: 4px solid var(--bk-red)' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="workspace"] #new-event-button' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-blue) !important;' in BIBLIOTHEKAR_CSS
    assert 'span.badge.success.metadata-ok' in BIBLIOTHEKAR_CSS
    assert '-webkit-text-fill-color: var(--bk-blue) !important;' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="archive"] .archive-check-card' in BIBLIOTHEKAR_CSS
    assert 'border-left: 4px solid var(--bk-yellow)' in BIBLIOTHEKAR_CSS


def test_0221_assistant_and_metadata_correction_are_real_pages():
    assistant = main.assistant_interface().body.decode("utf-8")
    metadata = main.metadata_correction_interface().body.decode("utf-8")

    assert 'data-bk-area="assistant"' in assistant
    assert 'Bibliothekar Assistent' in assistant
    assert 'Der KI-Assistent ist in diesem Designstand noch nicht verbunden.' in assistant

    assert 'data-bk-area="metadata"' in metadata
    assert 'Metadatenkorrektion' in metadata
    assert 'href="/metadata-correction"' in metadata
