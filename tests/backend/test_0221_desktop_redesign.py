from app import main
from app.ui_shell import BIBLIOTHEKAR_CSS


def test_0222_version():
    assert main.APP_VERSION == "0.26.0"


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
    assert 'bk-tab-shoulder' not in html
    assert '--bk-page-bridge-height:' in BIBLIOTHEKAR_CSS
    assert '.bk-shell::after {' in BIBLIOTHEKAR_CSS
    assert 'bottom: calc(-1 * var(--bk-page-bridge-height));' in BIBLIOTHEKAR_CSS


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


def test_0222_registers_use_same_inactive_color_and_in_face_depth_gradient():
    assert 'flex: 1 1 0;' in BIBLIOTHEKAR_CSS
    assert 'margin-bottom: 0;' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-bg: #5f686d;' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-bg: #d3d6d5;' in BIBLIOTHEKAR_CSS
    assert '--bk-stack-shadow' not in BIBLIOTHEKAR_CSS
    assert '--bk-stack-blend:' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-edge-gradient:' in BIBLIOTHEKAR_CSS
    assert '.bk-tab::after {' in BIBLIOTHEKAR_CSS
    assert 'content: none;' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-import .bk-tab[data-area="archive"] {' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-archive .bk-tab[data-area="import"] {' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-import .bk-tab[data-area="workspace"],' not in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-archive .bk-tab[data-area="workspace"],' not in BIBLIOTHEKAR_CSS
    assert 'to right,' in BIBLIOTHEKAR_CSS
    assert 'to left,' in BIBLIOTHEKAR_CSS
    assert 'var(--bk-stack-blend) 0,' in BIBLIOTHEKAR_CSS
    assert 'transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width))' in BIBLIOTHEKAR_CSS
    assert 'var(--bk-stack-blend) var(--bk-tab-overlap)' not in BIBLIOTHEKAR_CSS
    assert 'transparent calc(var(--bk-tab-overlap) - var(--bk-tab-seam-bleed))' not in BIBLIOTHEKAR_CSS
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


def test_0222_active_register_and_page_are_one_joined_surface():
    html = main.index()
    assert 'bk-tab-shoulder' not in html
    assert 'bk-tab-shoulder' not in BIBLIOTHEKAR_CSS
    assert '--bk-page-bridge-height: clamp(9px, .8vw, 13px);' in BIBLIOTHEKAR_CSS
    assert '.bk-shell::after {' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-page-bg, var(--bk-paper));' in BIBLIOTHEKAR_CSS
    assert '.bk-tab.active::before {' in BIBLIOTHEKAR_CSS
    assert 'bottom: calc(-1 * var(--bk-page-bridge-height));' in BIBLIOTHEKAR_CSS


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


def test_0222_register_geometry_is_responsive_and_gradient_follows_tab_face():
    assert '--bk-tab-overlap: clamp(24px, 3vw, 64px);' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-seam-bleed: clamp(2px, .28vw, 4px);' in BIBLIOTHEKAR_CSS
    assert '--bk-edge-gradient-width: clamp(22px, 2vw, 38px);' in BIBLIOTHEKAR_CSS
    assert 'margin-left: calc(0px - var(--bk-tab-overlap));' in BIBLIOTHEKAR_CSS
    assert 'left: calc(0px - var(--bk-tab-seam-bleed));' in BIBLIOTHEKAR_CSS
    assert 'right: calc(0px - var(--bk-tab-seam-bleed));' in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-size' not in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-skew-left' not in BIBLIOTHEKAR_CSS
    assert '--bk-shoulder-skew-right' not in BIBLIOTHEKAR_CSS
    assert 'var(--bk-tab-edge-gradient),' in BIBLIOTHEKAR_CSS
    assert 'box-shadow: none;' in BIBLIOTHEKAR_CSS


def test_0222_no_fixed_desktop_overlap_or_shadow_offsets_remain():
    assert 'margin-left: -34px;' not in BIBLIOTHEKAR_CSS
    assert 'margin-left: -26px;' not in BIBLIOTHEKAR_CSS
    assert 'left: 27px;' not in BIBLIOTHEKAR_CSS
    assert 'right: 27px;' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-overlap: clamp(44px, 3vw, 72px);' in BIBLIOTHEKAR_CSS


def test_0222_active_page_bridge_replaces_outer_shoulders_and_shadow_overlay():
    assert '.bk-shell::after {' in BIBLIOTHEKAR_CSS
    assert 'height: calc(var(--bk-page-bridge-height) + var(--bk-tab-page-mask));' in BIBLIOTHEKAR_CSS
    assert 'margin-bottom: var(--bk-page-bridge-height);' in BIBLIOTHEKAR_CSS
    assert '.bk-tab::after {' in BIBLIOTHEKAR_CSS
    assert 'content: none;' in BIBLIOTHEKAR_CSS
    assert '--bk-stack-shadow' not in BIBLIOTHEKAR_CSS
    assert 'bk-tab-shoulder' not in BIBLIOTHEKAR_CSS


def test_0222_tab_face_bleed_closes_hairline_gaps_responsively():
    assert '--bk-tab-seam-bleed: clamp(2px, .28vw, 4px);' in BIBLIOTHEKAR_CSS
    assert '--bk-tab-seam-bleed: clamp(3px, .24vw, 5px);' in BIBLIOTHEKAR_CSS
    assert 'left: calc(0px - var(--bk-tab-seam-bleed));' in BIBLIOTHEKAR_CSS
    assert 'right: calc(0px - var(--bk-tab-seam-bleed));' in BIBLIOTHEKAR_CSS


def test_0222_header_has_page_coloured_scroll_buffer():
    assert '--bk-page-bridge-height: clamp(9px, .8vw, 13px);' in BIBLIOTHEKAR_CSS
    assert 'bottom: calc(-1 * var(--bk-page-bridge-height));' in BIBLIOTHEKAR_CSS
    assert 'background: var(--bk-page-bg, var(--bk-paper));' in BIBLIOTHEKAR_CSS


def test_0223_shell_bridge_masks_only_inactive_tab_bottoms():
    html = main.index()
    assert 'bk-tab-junction' not in html
    assert 'bk-tab-shoulder' not in html
    assert '--bk-active-shoulder' not in BIBLIOTHEKAR_CSS
    assert '--bk-junction-radius' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-junction-width' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-junction-rise' not in BIBLIOTHEKAR_CSS
    assert '--bk-tab-page-mask: clamp(3px, .35vw, 5px);' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs::after {' not in BIBLIOTHEKAR_CSS
    assert '.bk-shell::after {' in BIBLIOTHEKAR_CSS
    assert 'z-index: 25;' in BIBLIOTHEKAR_CSS
    assert 'height: calc(var(--bk-page-bridge-height) + var(--bk-tab-page-mask));' in BIBLIOTHEKAR_CSS
    assert 'isolation: auto;' in BIBLIOTHEKAR_CSS
    assert '.bk-tab::after {\n  content: none;' in BIBLIOTHEKAR_CSS
    assert 'clip-path: polygon(' not in BIBLIOTHEKAR_CSS


def test_0223_depth_gradient_starts_hidden_under_the_foreground_tab():
    assert '--bk-edge-gradient-angle-right' not in BIBLIOTHEKAR_CSS
    assert '--bk-edge-gradient-angle-left' not in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-import .bk-tab[data-area="archive"] {' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-archive .bk-tab[data-area="import"] {' in BIBLIOTHEKAR_CSS
    assert 'linear-gradient(\n      to right,\n      var(--bk-stack-blend) 0,' in BIBLIOTHEKAR_CSS
    assert 'linear-gradient(\n      to left,\n      var(--bk-stack-blend) 0,' in BIBLIOTHEKAR_CSS
    assert 'transparent calc(var(--bk-tab-overlap) + var(--bk-edge-gradient-width))' in BIBLIOTHEKAR_CSS
    assert 'var(--bk-stack-blend) var(--bk-tab-overlap)' not in BIBLIOTHEKAR_CSS
    assert 'transform: perspective(108px) rotateX(7deg);' in BIBLIOTHEKAR_CSS


def test_0223_neutral_pages_keep_both_tab_depth_gradients():
    assert '.bk-tabs-active-assistant .bk-tab[data-area="workspace"],' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-metadata .bk-tab[data-area="workspace"] {' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-assistant .bk-tab[data-area="archive"],' in BIBLIOTHEKAR_CSS
    assert '.bk-tabs-active-metadata .bk-tab[data-area="archive"] {' in BIBLIOTHEKAR_CSS
