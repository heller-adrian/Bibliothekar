from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0222_version():
    assert main.APP_VERSION == "0.22.2"


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
    assert 'data-area="import"' in html
    assert 'data-area="workspace"' in html
    assert 'data-area="archive"' in html
    assert 'data-area="assistant"' not in html
    assert 'href="/assistant"' in html
    assert 'bk-assistant-button' in html

    assert '.bk-tabs-active-workspace' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-archive' in BIBLIOTHEKAR_CSS
    assert '.bk-tab::before {' in BIBLIOTHEKAR_CSS
    assert 'transform: perspective(108px) rotateX(7deg);' in BIBLIOTHEKAR_CSS
    assert 'bk-tab-shoulder-left' in html
    assert 'bk-tab-shoulder-right' in html
    assert 'radial-gradient(' in BIBLIOTHEKAR_CSS
    assert 'circle at left top' in BIBLIOTHEKAR_CSS
    assert 'circle at right top' in BIBLIOTHEKAR_CSS


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


def test_0221_shell_has_shared_typography_wider_canvas_and_left_brand_space():
    assert 'font-family: Inter, ui-sans-serif, system-ui' in BIBLIOTHEKAR_CSS
    assert 'width: min(1440px, calc(100% - 48px)) !important;' in BIBLIOTHEKAR_CSS
    assert 'grid-template-columns: minmax(190px, 235px) minmax(0, 1fr) auto;' in BIBLIOTHEKAR_CSS
    assert '@media (min-width: 1500px)' in BIBLIOTHEKAR_CSS


def test_0221_menu_entries_and_legacy_toolbars_are_visually_normalized():
    assert '.bk-menu button,' in BIBLIOTHEKAR_CSS
    assert 'height: 44px;' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-surface-2) !important;' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="workspace"] .bk-workspace-job-picker label' in BIBLIOTHEKAR_CSS
    assert 'body[data-bk-area="import"] .bk-metadata-toolbar .notice' in BIBLIOTHEKAR_CSS


def test_0222_registers_use_same_inactive_color_and_shadow_only_under_overlapping_tabs():
    assert 'flex: 1 1 0;' in BIBLIOTHEKAR_CSS
    assert 'margin-bottom: 0;' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-bg: #5f686d;' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-bg: #d3d6d5;' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-side-shadow' not in BIBLIOTHEKAR_CSS
    assert '--bk-stack-shadow:' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-import .bk-tab[data-area="workspace"]::after' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-workspace .bk-tab[data-area="import"]::after' in BIBLIOTHEKAR_CSS
    assert 'background: linear-gradient(to right, var(--bk-stack-shadow), transparent 88%);' in BIBLIOTHEKAR_CSS
    assert 'background: linear-gradient(to left, var(--bk-stack-shadow), transparent 88%);' in BIBLIOTHEKAR_CSS
    assert 'box-shadow: none;' in BIBLIOTHEKAR_CSS
    assert 'border-top-left-radius: 0;' in BIBLIOTHEKAR_CSS
    assert 'border-top-right-radius: 0;' in BIBLIOTHEKAR_CSS


def test_0221_legacy_white_strips_are_removed_at_markup_source():
    import_html = main.index()
    workspace_html = main.workspace_interface().body.decode("utf-8")

    assert 'class="toolbar bk-metadata-toolbar"' not in import_html
    assert 'class="bk-metadata-toolbar"' in import_html
    assert '<section class="command-header">' not in workspace_html
    assert '<section class="bk-workspace-command">' in workspace_html
    assert 'class="bk-workspace-job-picker"' in workspace_html


def test_0221_about_menu_icon_has_valid_svg_wrapper():
    html = main.index()
    assert '<span class="bk-menu-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"' in html


def test_0222_register_shoulders_are_quarter_circle_transitions_not_ears():
    html = main.index()
    assert 'bk-tab-shoulder bk-tab-shoulder-left' in html
    assert 'bk-tab-shoulder bk-tab-shoulder-right' in html
    assert '--bk-shoulder-size: clamp(8px, .65vw, 12px);' in BIBLIOTHEKAR_CSS
    assert 'circle at left top' in BIBLIOTHEKAR_CSS
    assert 'circle at right top' in BIBLIOTHEKAR_CSS
    assert 'transparent calc(var(--bk-shoulder-size) - 1px)' in BIBLIOTHEKAR_CSS
    assert '.bk-tab.active .bk-tab-shoulder {' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-color: var(--bk-page-bg, var(--bk-paper));' in BIBLIOTHEKAR_CSS


def test_0221_minimal_pages_have_no_browser_body_gutter_and_header_buttons_match():
    assert 'margin: 0 !important;' in BIBLIOTHEKAR_CSS
    assert 'padding: 0 !important;' in BIBLIOTHEKAR_CSS
    assert 'max-width: 44px;' in BIBLIOTHEKAR_CSS
    assert 'max-height: 44px;' in BIBLIOTHEKAR_CSS
    assert 'flex: 0 0 44px;' in BIBLIOTHEKAR_CSS


def test_0221_page_heading_and_main_share_same_horizontal_inset():
    assert 'padding-left: 18px !important;' in BIBLIOTHEKAR_CSS
    assert 'padding-right: 18px !important;' in BIBLIOTHEKAR_CSS
    assert '.bk-page-heading {' in BIBLIOTHEKAR_CSS
    assert 'padding-left: 18px;' in BIBLIOTHEKAR_CSS
    assert 'padding-right: 18px;' in BIBLIOTHEKAR_CSS


def test_0222_register_geometry_is_responsive_and_shadow_tracks_slope():
    assert '--bk-tab-overlap: clamp(24px, 3vw, 64px);' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-size: clamp(8px, .65vw, 12px);' in BIBLIOTHEKAR_CSS
    assert '--bk-shadow-width: clamp(8px, .7vw, 12px);' in BIBLIOTHEKAR_CSS
    assert 'margin-left: calc(0px - var(--bk-tab-overlap));' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-skew-left: -12deg;' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-skew-right: 12deg;' in BIBLIOTHEKAR_CSS
    assert 'transform: skewX(var(--bk-shoulder-skew-left));' in BIBLIOTHEKAR_CSS
    assert 'transform: skewX(var(--bk-shoulder-skew-right));' in BIBLIOTHEKAR_CSS
    assert 'left: calc(var(--bk-tab-overlap) - var(--bk-shadow-edge-inset));' in BIBLIOTHEKAR_CSS
    assert 'right: calc(var(--bk-tab-overlap) - var(--bk-shadow-edge-inset));' in BIBLIOTHEKAR_CSS
    assert 'bottom: calc(var(--bk-shoulder-size) - 1px);' in BIBLIOTHEKAR_CSS
    assert 'border-bottom-left-radius: var(--bk-shoulder-size);' in BIBLIOTHEKAR_CSS
    assert 'border-bottom-right-radius: var(--bk-shoulder-size);' in BIBLIOTHEKAR_CSS
    assert 'box-shadow: none;' in BIBLIOTHEKAR_CSS


def test_0222_no_fixed_desktop_overlap_or_shadow_offsets_remain():
    assert 'margin-left: -34px;' not in BIBLIOTHEKAR_CSS
    assert 'margin-left: -26px;' not in BIBLIOTHEKAR_CSS
    assert 'left: 27px;' not in BIBLIOTHEKAR_CSS
    assert 'right: 27px;' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-overlap: clamp(44px, 3vw, 72px);' in BIBLIOTHEKAR_CSS


def test_0222_active_outer_shoulders_close_seam_without_bottom_shadow():
    assert '.bk-tab:first-child.active .bk-tab-shoulder-left {' in BIBLIOTHEKAR_CSS
    assert '.bk-tab:last-child.active .bk-tab-shoulder-right {' in BIBLIOTHEKAR_CSS
    assert 'bottom: -1px;' in BIBLIOTHEKAR_CSS
    assert 'background: linear-gradient(to right, var(--bk-stack-shadow), transparent 88%);' in BIBLIOTHEKAR_CSS
    assert 'background: linear-gradient(to left, var(--bk-stack-shadow), transparent 88%);' in BIBLIOTHEKAR_CSS
