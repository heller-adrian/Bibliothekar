from app.metadata_correction_ui import METADATA_CORRECTION_HTML
from app.ui_shell import BIBLIOTHEKAR_0425_CSS


def test_0425_pwa_cards_are_only_promoted_during_wobble():
    css = BIBLIOTHEKAR_0425_CSS

    assert 'html[data-bk-display-mode="standalone"] [data-bk-pwa-select] {' in css
    assert "will-change: auto;" in css
    assert '[data-bk-pwa-select].bk-pwa-select-wobble' in css
    assert "will-change: transform;" in css


def test_0425_metadata_initial_long_press_keeps_touch_target_alive():
    html = METADATA_CORRECTION_HTML

    assert "function activateMetaSelectionModeInPlace(index,desired=true)" in html
    assert "activateMetaSelectionModeInPlace(index,desired);" in html
    assert "row.prepend(checkbox);" in html
    assert (
        'if(phase==="start"&&!state.selectionMode){\n'
        "          state.selectionMode=true;"
    ) not in html


def test_0425_multiple_initial_long_press_keeps_touch_target_alive():
    html = METADATA_CORRECTION_HTML

    assert "function activateMultipleSelectionModeInPlace(index,desired=true)" in html
    assert "activateMultipleSelectionModeInPlace(index,desired);" in html
    assert 'if(marker?.tagName==="SPAN")marker.replaceWith(checkbox);' in html
    assert (
        'if(phase==="start"&&!state.multipleSelectionMode){\n'
        "          state.multipleSelectionMode=true;"
    ) not in html


def test_0425_nonmodal_metadata_sheet_reserves_scroll_clearance():
    html = METADATA_CORRECTION_HTML
    css = BIBLIOTHEKAR_0425_CSS

    assert "function updateMobileSelectionSheetClearance()" in html
    assert 'document.body?.classList.add("bk-meta-selection-sheet-open")' in html
    assert '"--bk-meta-selection-sheet-height"' in html
    assert "dialog.getBoundingClientRect().height" in html
    assert 'new ResizeObserver(()=>updateMobileSelectionSheetClearance())' in html

    assert "body[data-bk-area=\"metadata\"].bk-meta-selection-sheet-open main" in css
    assert "var(--bk-meta-selection-sheet-height, 44dvh)" in css
